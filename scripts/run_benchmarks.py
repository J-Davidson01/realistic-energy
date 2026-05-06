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
from typing import Dict, List, Optional
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
    "variant",
    "dataset_name",
    "size",
    "iterations",
    "chunk_items",
    "repetition",
    "elapsed_s",
    "energy_pkg_j",
    "energy_core_j",
    "energy_dram_j",
    "energy_other_j",
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
    key: str
    domain: str
    path: Path
    energy_uj_path: Path
    max_energy_range_uj_path: Path

@dataclass
class MemoryStats:
    rss_start: int = 0
    rss_peak: int = 0
    rss_end: int = 0
    samples: int = 0

# =======
# Energy (RAPL) monitoring functions

def discover_rapl_zones(powercap_root=Path("/sys/class/powercap")) -> List[RaplZone]:
    zones: List[RaplZone] = []

    if not powercap_root.exists():
        print(f"Powercap root {powercap_root} does not exist. No RAPL zones will be monitored.")
        return zones

    for child in powercap_root.iterdir():
        if not child.is_dir():
            continue

        if not re.fullmatch(r"intel-rapl:\d+(?::\d+)?", child.name):
            continue

        name_file = child / "name"
        energy_file = child / "energy_uj"
        max_energy_file = child / "max_energy_range_uj"

        if not (name_file.exists() and energy_file.exists() and max_energy_file.exists()):
            print(f"Skipping {child} because it does not contain the required files.")
            continue

        domain = name_file.read_text().strip()

        zones.append(RaplZone(
            key=child.name,
            domain=domain,
            path=child,
            energy_uj_path=energy_file,
            max_energy_range_uj_path=max_energy_file,
        ))

    zones.sort(key=lambda z: z.key)
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
        snapshot[zone.key] = read_zone_energy_uj(zone)
    return snapshot

def compute_energy_by_domain(
    start_snapshot: Dict[str, int],
    end_snapshot: Dict[str, int],
    zones: List[RaplZone],
) -> Dict[str, float]:
    totals_uj = {
        "package": 0,
        "core": 0,
        "dram": 0,
        "other": 0,
    }

    for zone in zones:
        start_uj = start_snapshot[zone.key]
        end_uj = end_snapshot[zone.key]
        max_range_uj = read_zone_max_energy_range_uj(zone)
        delta_uj = compute_energy_delta(start_uj, end_uj, max_range_uj)

        domain = zone.domain.lower()

        if domain.startswith("package"):
            totals_uj["package"] += delta_uj
        elif domain == "core":
            totals_uj["core"] += delta_uj
        elif domain == "dram":
            totals_uj["dram"] += delta_uj
        else:
            totals_uj["other"] += delta_uj

    return {
        "package": totals_uj["package"] / 1_000_000,
        "core": totals_uj["core"] / 1_000_000,
        "dram": totals_uj["dram"] / 1_000_000,
        "other": totals_uj["other"] / 1_000_000,
    }


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

def discover_datasets(dataset_name: str, datasets_root: Path) -> List[Path]:
    base = datasets_root / dataset_name
    if not base.exists():
        print(f"Dataset directory {base} does not exist. No datasets will be run for dataset {dataset_name}.")
        return []

    dirst = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit()]
    dirst.sort(key=lambda d: int(d.name))
    return dirst

def format_command(template: List[str], dataset_dir: Path, iterations: int, verify: bool = False) -> List[str]:
    command = [
        part.format(dataset=str(dataset_dir), iterations=str(iterations))
        for part in template
    ]
    if verify:
        command.append("--verify")
    return command

def run_command_capture(command: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

def run_verify(
    language: str,
    benchmark: str,
    dataset_dir: Path,
    chunk_items: int,
    variant: str = "default",
    pipeline_json_dataset_name: Optional[str] = None,
) -> bool:
    command = get_language_command(
        language,
        benchmark,
        dataset_dir,
        1,
        chunk_items,
        variant,
        verify=True,
        pipeline_json_dataset_name=pipeline_json_dataset_name,
    )
    completed = run_command_capture(command)

    cleanup_benchmark_outputs(benchmark, dataset_dir)

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
    chunk_items: int,
    variant: str,
    memory_interval_s: float,
    rapl_zones: List[RaplZone],
    pipeline_json_dataset_name: Optional[str] = None,
) -> Dict[str, object]:
    command = get_language_command(language, benchmark, dataset_dir, iterations, chunk_items, variant, verify=False, pipeline_json_dataset_name=pipeline_json_dataset_name,)

    start_snapshot = snapshot_rapl(rapl_zones) if rapl_zones else {}
    t0 = time.perf_counter()

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
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

    energy_by_domain = (
        compute_energy_by_domain(start_snapshot, end_snapshot, rapl_zones)
        if rapl_zones else {
            "package": None,
            "core": None,
            "dram": None,
            "other": None,
        }
    )

    cleanup_benchmark_outputs(benchmark, dataset_dir)

    size = int(dataset_dir.name)

    return {
        "benchmark": benchmark,
        "language": language,
        "variant": variant,
        "size": size,
        "iterations": iterations,
        "chunk_items": chunk_items if benchmark == "pipeline_e2e_stream" else "",
        "elapsed_s": elapsed_time_s,
        "energy_pkg_j": energy_by_domain["package"],
        "energy_core_j": energy_by_domain["core"],
        "energy_dram_j": energy_by_domain["dram"],
        "energy_other_j": energy_by_domain["other"],
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

def detect_languages(benchmark: str) -> List[str]:
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

def get_language_command(
    language: str,
    benchmark: str,
    dataset_dir: Path,
    iterations: int,
    chunk_items: int,
    variant: str = "default",
    verify: bool = False,
    pipeline_json_dataset_name: Optional[str] = None,
) -> List[str]:
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

    if benchmark == "pipeline_e2e_stream":
        command.extend(["--chunk-items", str(chunk_items)])

    if benchmark == "json_parse" and language in ("python", "c", "julia", "go") and variant != "default":
        command.extend(["--json-impl", variant])

    if benchmark in ("pipeline_e2e", "pipeline_e2e_stream") and pipeline_json_dataset_name:
        size_name = dataset_dir.name
        selected_datasets_root = dataset_dir.parent.parent

        command.extend([
            "--json-dataset",
            str(selected_datasets_root / pipeline_json_dataset_name / size_name),
        ])

    if verify:
        command.append("--verify")

    return command

def cleanup_benchmark_outputs(benchmark: str, dataset_dir: Path) -> None:
    output_paths = []

    if benchmark == "file_copy":
        output_paths.append(dataset_dir / "output.bin")

    elif benchmark in ("pipeline_e2e", "pipeline_e2e_stream"):
        size_name = dataset_dir.name
        datasets_root = dataset_dir.parent.parent
        output_paths.append(datasets_root / "file_copy" / size_name / "output.bin")

    for output_path in output_paths:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass

def filter_datasets_by_size(dataset_dirs: List[Path], min_size: Optional[int], max_size: Optional[int]) -> List[Path]:
    filtered = []
    for d in dataset_dirs:
        size = int(d.name)
        if min_size is not None and size < min_size:
            continue
        if max_size is not None and size > max_size:
            continue
        filtered.append(d)
    return filtered

def get_git_commit() -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except OSError:
        pass

    return None

def get_variants_for_run(
    language: str,
    benchmark: str,
    python_json_impls: List[str],
    c_json_impls: List[str],
    julia_json_impls: List[str],
    go_json_impls: List[str],
) -> List[str]:
    if benchmark == "json_parse" and language == "python":
        return python_json_impls

    if benchmark == "json_parse" and language == "c":
        return c_json_impls

    if benchmark == "json_parse" and language == "julia":
        return julia_json_impls
    
    if benchmark == "json_parse" and language == "go":
        return go_json_impls

    return ["default"]

def parse_dataset_overrides(raw: str) -> Dict[str, str]:
    overrides = {}

    if not raw:
        return overrides

    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        if "=" not in part:
            raise ValueError(
                f"Invalid dataset override '{part}'. "
                "Expected format: benchmark=dataset_name"
            )

        benchmark, dataset_name = part.split("=", 1)
        benchmark = benchmark.strip()
        dataset_name = dataset_name.strip()

        if not benchmark or not dataset_name:
            raise ValueError(
                f"Invalid dataset override '{part}'. "
                "Expected format: benchmark=dataset_name"
            )

        overrides[benchmark] = dataset_name

    return overrides

def run_analysis_script(
    benchmark_csv_path: Path,
    output_dir: Optional[Path],
    workload_weights: str,
    metric_weights: str,
) -> None:
    analysis_script = PROJECT_ROOT / "scripts" / "analyze_results.py"

    if not analysis_script.exists():
        print(f"Analysis script not found: {analysis_script}")
        return

    if output_dir is None:
        output_dir = RESULTS_DIR / f"analysis_{benchmark_csv_path.stem}"

    command = [
        sys.executable,
        str(analysis_script),
        "--input",
        str(benchmark_csv_path),
        "--output-dir",
        str(output_dir),
        "--workload-weights",
        workload_weights,
        "--metric-weights",
        metric_weights,
    ]

    print("Running analysis:")
    print(" ".join(shlex.quote(part) for part in command))

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )

    if completed.stdout.strip():
        print(completed.stdout.strip())

    if completed.stderr.strip():
        print(completed.stderr.strip())

    if completed.returncode != 0:
        print(f"Analysis failed with return code {completed.returncode}")
    else:
        print(f"Analysis completed. Results written to {output_dir}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmarks and collect energy and memory usage data")
    parser.add_argument("--benchmark", type=str, default="sha256,json_parse,file_copy,pipeline_e2e,pipeline_e2e_stream", help="Comma-separated benchmark names, e.g. sha256,json_parse,file_copy,pipeline")
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
    parser.add_argument("--chunk-items", type=int, default=1024, help="Amount of items to process in each chunk for streaming benchmarks")
    parser.add_argument("--python-json-impls", type=str, default="json", help="Comma-separated Python JSON implementations for json_parse, e.g. json,json_no_c_acc,orjson")
    parser.add_argument("--c-json-impls", type=str, default="cjson", help="Comma-separated C JSON implementations for json_parse, e.g. cjson,yyjson")
    parser.add_argument("--julia-json-impls", type=str, default="json", help="Comma-separated Julia JSON implementations for json_parse, e.g. json,json3")
    parser.add_argument("--go-json-impls", type=str, default="encoding_json", help="Comma-separated Go JSON implementations for json_parse, e.g. encoding_json,goccy_go_json")
    parser.add_argument( "--dataset-overrides", type=str, default="", help="Comma-separated benchmark-to-dataset mappings. Example: json_parse=json_parse_yelp,pipeline_e2e=pipeline_e2e_yelp" )
    parser.add_argument( "--pipeline-json-dataset", type=str, default="", help="Benchmark-to-dataset mappings. Example: json_parse_yelp to make pipeline_e2e and pipeline_e2e_stream use Yelp dataset" )
    parser.add_argument( "--analyze", action="store_true", help="Run scripts/analyze_results.py after benchmark execution finishes", ) 
    parser.add_argument( "--analysis-output-dir", type=Path, default=None, help="Directory for analysis CSV outputs. Defaults to results/analysis_<benchmark_csv_stem>", ) 
    parser.add_argument( "--analysis-workload-weights", type=str, default="sha256=1,json_parse=1,file_copy=1,pipeline_e2e=1,pipeline_e2e_stream=1", help="Workload weights passed to analyze_results.py", ) 
    parser.add_argument( "--analysis-metric-weights", type=str, default="pkg=0.5,dram=0.5,time=0,memory=0", help="Metric weights passed to analyze_results.py", )
    args = parser.parse_args()

    benchmarks = [b.strip() for b in args.benchmark.split(",") if b.strip()]
    requested_languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    datasets_root = Path(args.datasets_root)
    dataset_overrides = parse_dataset_overrides(args.dataset_overrides)
    csv_path = make_timestamped_results_path(Path(args.results_dir))
    memory_interval_s = args.memory_interval_ms / 1000.0

    go_json_impls = [
        impl.strip()
        for impl in args.go_json_impls.split(",")
        if impl.strip()
    ]

    python_json_impls = [
        impl.strip()
        for impl in args.python_json_impls.split(",")
        if impl.strip()
    ]

    c_json_impls = [
        impl.strip()
        for impl in args.c_json_impls.split(",")
        if impl.strip()
    ]

    julia_json_impls = [
        impl.strip()
        for impl in args.julia_json_impls.split(",")
        if impl.strip()
    ]

    if not benchmarks:
        print("No benchmarks specified. Exiting.")
        return

    rapl_zones = discover_rapl_zones()
    if rapl_zones:
        zone_names = ", ".join(f"{zone.key}:{zone.domain}" for zone in rapl_zones)
        print(f"Discovered RAPL zones: {zone_names}. Energy measurements will be collected for these zones.")
    else:
        print("No RAPL zones discovered. Energy measurements will be skipped.")

    run_metadata = {
        "timestamp": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": sys.version,
        "rapl_available": bool(rapl_zones),
        "rapl_zones": [
            {
                "key": zone.key,
                "domain": zone.domain,
                "path": str(zone.path),
            }
            for zone in rapl_zones
        ],
    }

    run_metadata["git_commit"] = get_git_commit()

    for benchmark in benchmarks:
        available_languages = detect_languages(benchmark)
        languages = [lang for lang in requested_languages if lang in available_languages]

        invalid = [lang for lang in requested_languages if lang not in available_languages]
        if invalid:
            print(f"Warning: requested languages not available for {benchmark}: {', '.join(invalid)}")

        if not languages:
            print(f"No runnable languages found for benchmark {benchmark}. Skipping.")
            continue

        dataset_name = dataset_overrides.get(benchmark, benchmark)
        dataset_dirs = discover_datasets(dataset_name, datasets_root)
        dataset_dirs = filter_datasets_by_size(
            dataset_dirs,
            args.min_dataset_size,
            args.max_dataset_size,
        )

        print(f"Running benchmark: {benchmark}")
        print(f"Using dataset: {dataset_name}")
        print(f"Running languages: {', '.join(languages)}")

        if not dataset_dirs:
            print(f"No datasets found for benchmark {benchmark} in {datasets_root}. Skipping.")
            continue

        for language in languages:
            variants = get_variants_for_run(
                language,
                benchmark,
                python_json_impls,
                c_json_impls,
                julia_json_impls,
                go_json_impls,
            )

            for variant in variants:
                if args.verify:
                    verify_dataset = dataset_dirs[0]
                    print(
                        f"Running verification for {language} on {benchmark} "
                        f"variant {variant} dataset {verify_dataset.name}..."
                    )

                    if not run_verify(
                        language,
                        benchmark,
                        verify_dataset,
                        args.chunk_items,
                        variant,
                        pipeline_json_dataset_name=args.pipeline_json_dataset,
                    ):
                        print(
                            f"Verification failed for {language} variant {variant}. "
                            "Skipping benchmark runs for this variant."
                        )
                        continue

                    print(
                        f"Verification succeeded for {language} variant {variant}. "
                        "Proceeding with benchmark runs."
                    )

                for dataset_dir in dataset_dirs:
                    if args.warmup:
                        warmup_command = get_language_command(
                            language,
                            benchmark,
                            dataset_dir,
                            1,
                            args.chunk_items,
                            variant,
                            verify=False,
                            pipeline_json_dataset_name=args.pipeline_json_dataset,
                        )

                        subprocess.run(
                            warmup_command,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )

                        cleanup_benchmark_outputs(benchmark, dataset_dir)

                    for repetition in range(args.repetitions):
                        print(
                            f"[run] Running {benchmark} in {language} variant {variant} "
                            f"with dataset {dataset_dir.name} for {args.iterations} iterations "
                            f"(rep {repetition + 1}/{args.repetitions})..."
                        )

                        row = run_benchmark(
                            language=language,
                            benchmark=benchmark,
                            dataset_dir=dataset_dir,
                            iterations=args.iterations,
                            chunk_items=args.chunk_items,
                            variant=variant,
                            memory_interval_s=memory_interval_s,
                            rapl_zones=rapl_zones,
                            pipeline_json_dataset_name=args.pipeline_json_dataset,
                        )

                        row["repetition"] = repetition
                        row["dataset_name"] = dataset_name
                        append_csv_row(csv_path, row)

                        status = (
                            "success"
                            if row["returncode"] == 0
                            else f"failed (return code {row['returncode']})"
                        )

                        energy_parts = []

                        if row["energy_pkg_j"] not in (None, ""):
                            energy_parts.append(f"pkg={row['energy_pkg_j']:.6f}J")

                        if row["energy_core_j"] not in (None, "") and row["energy_core_j"] != 0:
                            energy_parts.append(f"core={row['energy_core_j']:.6f}J")

                        if row["energy_dram_j"] not in (None, "") and row["energy_dram_j"] != 0:
                            energy_parts.append(f"dram={row['energy_dram_j']:.6f}J")

                        if row["energy_other_j"] not in (None, "") and row["energy_other_j"] != 0:
                            energy_parts.append(f"other={row['energy_other_j']:.6f}J")

                        energy_str = " ".join(energy_parts)
                        if energy_str:
                            energy_str += " "

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

    if args.analyze:
        run_analysis_script(
            benchmark_csv_path=csv_path,
            output_dir=args.analysis_output_dir,
            workload_weights=args.analysis_workload_weights,
            metric_weights=args.analysis_metric_weights,
        )
    
if __name__ == "__main__":
    main()
