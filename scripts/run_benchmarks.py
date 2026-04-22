#!/usr/bin/env python3
import argparse
import csv
import json
import re
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import socket
import platform
from datetime import datetime

import psutil

# ======
# Constants

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASETS_ROOT = PROJECT_ROOT / "datasets"
BENCHMARKS_ROOT = PROJECT_ROOT / "benchmarks"
RESULTS_DIR = PROJECT_ROOT / "results"

CSV_FIELDS = [
    "benchmark",
    "language",
    "size",
    "iterations",
    "repetition",
    "elapsed_s",
    "energy_pkg_j",
    "rss_start_bytes",
    "rss_peak_bytes",
    "rss_end_bytes",
    "rss_samples",
    "returncode",
    "stdout",
    "stderr",
    "command",
    "dataset_dir"
]

# ======
# Structs

@dataclass
class RaplZone:
    name: str
    path: Path
    energy_uj_path : Path
    max_energy_range_uj_path: Path

@dataclass
class MemoryStats:
    rss_start: int = 0
    rss_peak: int = 0
    rss_end: int = 0
    samples: int = 0

# =======
# Energy (RAPL) monitoring functions

def discover_package_rapl_zones(powercap_root = Path("/sys/class/powercap")) -> List[RaplZone]:
    zones: List[RaplZone] = []

    if not powercap_root.exists():
        print(f"Powercap root {powercap_root} does not exist. No RAPL zones will be monitored.")
        return zones
    
    for child in powercap_root.iterdir():
        if not child.is_dir():
            continue
        if not re.fullmatch(r"intel-rapl:\d+", child.name):
            continue
    
        name_file = child / "name"
        energy_file = child / "energy_uj"
        max_energy_file = child / "max_energy_range_uj"

        if not (name_file.exists() and energy_file.exists() and max_energy_file.exists()):
            print(f"Skipping {child} because it does not contain the required files.")

        zone_name = name_file.read_text().strip()
        zones.append(RaplZone(
            name=zone_name,
            path=child,
            energy_uj_path=energy_file,
            max_energy_range_uj_path=max_energy_file
        ))

    return zones

def read_zone_energy_uj(zone: RaplZone) -> int:
    return int(zone.energy_uj_path.read_text().strip())

def read_zone_max_energy_range_uj(zone: RaplZone) -> int:
    return int(zone.max_energy_range_uj_path.read_text().strip())

def compute_energy_delta(start_uj: int, end_uj: int, max_range_uj: int) -> int:
    if end_uj >= start_uj:
        return end_uj - start_uj
    else:
        return (max_range_uj - start_uj) + end_uj

def snapshot_rapl(zones: List[RaplZone]) -> Dict[str, int]:
    snapshot = {}
    for zone in zones:
        snapshot[zone.name] = read_zone_energy_uj(zone)
    return snapshot

def compute_total_package_energy(start_snapshot: Dict[str, int], end_snapshot: Dict[str, int], zones: List[RaplZone]) -> int:
    total_energy_uj = 0
    for zone in zones:
        start_uj = start_snapshot[zone.name]
        end_uj = end_snapshot[zone.name]
        max_range_uj = read_zone_max_energy_range_uj(zone)
        total_energy_uj += compute_energy_delta(start_uj, end_uj, max_range_uj)
    return total_energy_uj / 1_000_000  # convert to joules


# ======
# Memory monitoring functions

def process_tree_rss(proc: psutil.Process) -> int:
    rss = 0
    try:
        rss += proc.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return rss
    
    try:
        for child in proc.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    return rss

def sample_memory_until_exit(proc: psutil.Process, interval_s: float, stats: MemoryStats, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            current_rss = process_tree_rss(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break

        stats.samples += 1
        if current_rss > stats.rss_peak:
            stats.rss_peak = current_rss

        time.sleep(interval_s)

    try:
        stats.rss_end = process_tree_rss(proc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        stats.rss_end = 0

# ======
# Benchmark execution functions

def discover_datasets(benchmark: str, datasets_root: Path) -> List[Path]:
    base = datasets_root / benchmark
    if not base.exists():
        print(f"Dataset directory {base} does not exist. No datasets will be run for benchmark {benchmark}.")
        return []

    dirst = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit()]
    dirst.sort(key=lambda d: int(d.name))
    return dirst

def format_command(template: list[str], dataset_dir: Path, iterations: int, verify: bool = False) -> list[str]:
    command = [
        part.format(dataset=str(dataset_dir), iterations=str(iterations))
        for part in template
    ]
    if verify:
        command.append("--verify")
    return command

def run_command_capture(command: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True)

def run_verify(language: str, benchmark: str, dataset_dir: Path) -> bool:
    command = get_language_command(language, benchmark, dataset_dir, 1, verify=True)
    completed = run_command_capture(command)

    cleanup_file_copy_outputs(benchmark, dataset_dir)

    if completed.returncode != 0:
        print(f"[verify:{language}] stdout:\n{completed.stdout}")
        print(f"[verify:{language}] stderr:\n{completed.stderr}")
        return False

    return True

def run_benchmark(
    language: str,
    benchmark: str,
    dataset_dir: Path,
    iterations: int,
    memory_interval_s: float,
    rapl_zones: List[RaplZone]
) -> Dict[str, object]:
    command = get_language_command(language, benchmark, dataset_dir, iterations, verify=False)

    start_snapshot = snapshot_rapl(rapl_zones) if rapl_zones else {}
    t0 = time.perf_counter()

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    proc_ps = psutil.Process(proc.pid)

    mem_stats = MemoryStats()
    try:
        mem_stats.rss_start = process_tree_rss(proc_ps)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        mem_stats.rss_start = 0

    mem_stats.rss_peak = mem_stats.rss_start

    stop_event = threading.Event()
    sampler = threading.Thread(
        target=sample_memory_until_exit,
        args=(proc_ps, memory_interval_s, mem_stats, stop_event),
        daemon=True,
    )
    sampler.start()

    stdout, stderr = proc.communicate()

    stop_event.set()
    sampler.join()

    elapsed_time_s = time.perf_counter() - t0
    end_snapshot = snapshot_rapl(rapl_zones) if rapl_zones else {}

    energy_j = (
        compute_total_package_energy(start_snapshot, end_snapshot, rapl_zones)
        if rapl_zones else None
    )

    cleanup_file_copy_outputs(benchmark, dataset_dir)

    size = int(dataset_dir.name)

    return {
        "benchmark": benchmark,
        "language": language,
        "size": size,
        "iterations": iterations,
        "elapsed_s": elapsed_time_s,
        "energy_pkg_j": energy_j,
        "rss_start_bytes": mem_stats.rss_start,
        "rss_peak_bytes": mem_stats.rss_peak,
        "rss_end_bytes": mem_stats.rss_end,
        "rss_samples": mem_stats.samples,
        "returncode": proc.returncode,
        "stdout": (stdout or "").strip(),
        "stderr": (stderr or "").strip(),
        "command": " ".join(shlex.quote(x) for x in command),
        "dataset_dir": str(dataset_dir),
    }

#======
# CSV output

def append_csv_row(csv_path: Path, row: Dict[str, object]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()

    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

#======
# Helpers

def make_timestamped_results_path(path: Path) -> Path:
    """Return a new path with the current date/time appended to the filename.

    This helps avoid overwriting previous runs when the script is executed multiple times.
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if path.suffix:
        return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
    return Path(f"{path}_{timestamp}")

def detect_languages(benchmark: str) -> list[str]:
    benchmark_root = BENCHMARKS_ROOT / benchmark
    languages = []

    if (benchmark_root / "c" / "build" / f"{benchmark}_c").exists():
        languages.append("c")

    if (benchmark_root / "go" / f"{benchmark}_go").exists():
        languages.append("go")

    if (benchmark_root / "python" / f"{benchmark}_main.py").exists():
        languages.append("python")

    if (benchmark_root / "julia" / f"{benchmark}_main.jl").exists():
        languages.append("julia")

    return languages

def get_language_command(language: str, benchmark: str, dataset_dir: Path, iterations: int, verify: bool = False) -> list[str]:
    benchmark_root = BENCHMARKS_ROOT / benchmark

    if language == "c":
        command = [
            str(benchmark_root / "c" / "build" / f"{benchmark}_c"),
            "--dataset", str(dataset_dir),
            "--iterations", str(iterations),
        ]
    elif language == "go":
        command = [
            str(benchmark_root / "go" / f"{benchmark}_go"),
            "--dataset", str(dataset_dir),
            "--iterations", str(iterations),
        ]
    elif language == "python":
        command = [
            sys.executable,
            str(benchmark_root / "python" / f"{benchmark}_main.py"),
            "--dataset", str(dataset_dir),
            "--iterations", str(iterations),
        ]
    elif language == "julia":
        julia_dir = benchmark_root / "julia"
        command = [
            "julia",
            f"--project={julia_dir}",
            str(julia_dir / f"{benchmark}_main.jl"),
            "--dataset", str(dataset_dir),
            "--iterations", str(iterations),
        ]
    else:
        raise ValueError(f"Unsupported language: {language}")

    if verify:
        command.append("--verify")

    return command

def cleanup_file_copy_outputs(benchmark: str, dataset_dir: Path) -> None:
    if benchmark != "file_copy":
        return

    output_path = dataset_dir / "output.bin"
    try:
        output_path.unlink()
    except FileNotFoundError:
        pass

def filter_datasets_by_size(dataset_dirs: List[Path], min_size: int | None, max_size: int | None) -> List[Path]:
    filtered = []
    for d in dataset_dirs:
        size = int(d.name)
        if min_size is not None and size < min_size:
            continue
        if max_size is not None and size > max_size:
            continue
        filtered.append(d)
    return filtered

def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmarks and collect energy and memory usage data")
    parser.add_argument("--benchmark", type=str, default="sha256,json_parse,file_copy", help="Comma-separated benchmark names, e.g. sha256,json_parse,file_copy,pipeline")
    parser.add_argument("--languages", type=str, default="c,go,python,julia", help="Comma-separated list of languages to run, e.g. c,go,python,julia")
    parser.add_argument("--iterations", type=int, default=25, help="Number of iterations to run each benchmark")
    parser.add_argument("--memory-interval-ms", type=float, default=10.0, help="Interval in milliseconds between memory usage samples")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR / "benchmark_results.csv", help="Directory to store results CSV files")
    parser.add_argument("--verify", action="store_true", help="Whether to run verification before the benchmark")
    parser.add_argument("--datasets-root", default=str(DATASETS_ROOT), help="Root directory where datasets are stored")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--sleep-between-runs", type=float, default=0.1)
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument("--min-dataset-size", type=int, default=None, help="Minimum dataset size in bytes to include")
    parser.add_argument("--max-dataset-size", type=int, default=None, help="Maximum dataset size in bytes to include")
    args = parser.parse_args()

    benchmarks = [b.strip() for b in args.benchmark.split(",") if b.strip()]
    requested_languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    datasets_root = Path(args.datasets_root)
    csv_path = make_timestamped_results_path(Path(args.results_dir))
    memory_interval_s = args.memory_interval_ms / 1000.0

    if not benchmarks:
        print("No benchmarks specified. Exiting.")
        return

    rapl_zones = discover_package_rapl_zones()
    if rapl_zones:
        zone_names = ", ".join(zone.name for zone in rapl_zones)
        print(f"Discovered RAPL zones: {zone_names}. Energy measurements will be collected for these zones.")
    else:
        print("No RAPL zones discovered. Energy measurements will be skipped.")

    run_metadata = {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "rapl_available": bool(rapl_zones),
    }

    for benchmark in benchmarks:
        available_languages = detect_languages(benchmark)
        languages = [lang for lang in requested_languages if lang in available_languages]

        invalid = [lang for lang in requested_languages if lang not in available_languages]
        if invalid:
            print(f"Warning: requested languages not available for {benchmark}: {', '.join(invalid)}")

        if not languages:
            print(f"No runnable languages found for benchmark {benchmark}. Skipping.")
            continue

        print(f"Running benchmark: {benchmark}")
        print(f"Running languages: {', '.join(languages)}")

        dataset_dirs = discover_datasets(benchmark, datasets_root)
        dataset_dirs = filter_datasets_by_size(
            dataset_dirs,
            args.min_dataset_size,
            args.max_dataset_size,
        )
        
        if not dataset_dirs:
            print(f"No datasets found for benchmark {benchmark} in {datasets_root}. Skipping.")
            continue

        for language in languages:
            if args.verify:
                verify_dataset = dataset_dirs[0]
                print(f"Running verification for {language} on {benchmark} dataset {verify_dataset.name}...")
                if not run_verify(language, benchmark, verify_dataset):
                    print(f"Verification failed for {language}. Skipping benchmark runs for this language.")
                    continue
                print(f"Verification succeeded for {language}. Proceeding with benchmark runs.")

            for dataset_dir in dataset_dirs:
                if args.warmup:
                    warmup_command = get_language_command(language, benchmark, dataset_dir, 1, verify=False)
                    subprocess.run(
                        warmup_command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    cleanup_file_copy_outputs(benchmark, dataset_dir)

                for repetition in range(args.repetitions):
                    print(
                        f"[run] Running {benchmark} in {language} with dataset {dataset_dir.name} "
                        f"for {args.iterations} iterations (rep {repetition + 1}/{args.repetitions})..."
                    )

                    row = run_benchmark(
                        language=language,
                        benchmark=benchmark,
                        dataset_dir=dataset_dir,
                        iterations=args.iterations,
                        memory_interval_s=memory_interval_s,
                        rapl_zones=rapl_zones,
                    )
                    row["repetition"] = repetition
                    append_csv_row(csv_path, row)

                    status = "success" if row["returncode"] == 0 else f"failed (return code {row['returncode']})"
                    energy_str = (
                        f"energy={row['energy_pkg_j']:.6f}J "
                        if row["energy_pkg_j"] not in (None, "")
                        else ""
                    )

                    print(
                        f" -> {status} "
                        f"time={row['elapsed_s']:.6f}s "
                        f"{energy_str}"
                        f"rss_peak={row['rss_peak_bytes']} bytes"
                    )

                    time.sleep(args.sleep_between_runs)

    print(f"All benchmarks completed. Results have been saved to {csv_path}")
    metadata_path = csv_path.with_name(csv_path.stem + "_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2)
    
if __name__ == "__main__":
    main()


    


