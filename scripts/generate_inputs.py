#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

def pow2(min_size: int, max_size: int):
    """Generate powers of 2 between min_size and max_size."""
    sizes = []
    size = 1
    while size < min_size:
        size *= 2
    while size <= max_size:
        sizes.append(size)
        size *= 2
    return sizes

def xorshift(length: int, seed: int):
    """Generate a sequence of pseudo-random numbers using the XORShift algorithm."""
    x = seed
    result = bytearray(length)
    for i in range(length):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        result[i] = x & 0xFF
    return bytes(result)

def write_sha256(base_dir: Path, size: int, seed: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)

    key_hmac = xorshift(32, seed)
    key_xor = xorshift(16, seed + 1)
    buffer = xorshift(size, seed + 2)

    (outdir / "buffer.bin").write_bytes(buffer)
    (outdir / "key_hmac.bin").write_bytes(key_hmac)
    (outdir / "key_xor.bin").write_bytes(key_xor)

def stable_bench_seed(seed: int, bench: str) -> int:
    x = seed & 0xFFFFFFFF
    for lang in bench.encode("utf-8"):
        x = (x * 16777619) ^ lang
        x &= 0xFFFFFFFF
    return x

def deterministic_string(seed: int, index: int, length: int) -> str:
    raw = xorshift(length, seed + index)
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(alphabet[b % len(alphabet)] for b in raw)

def make_json_item(seed: int, index: int) -> dict:
    return {
        "id": index,
        "name": deterministic_string(seed + 1000, index, 12),
        "active": (index % 2 == 0),
        "score": ((seed ^ index) % 100000),
        "category": deterministic_string(seed + 2000, index, 4),
    }

def compact_json_bytes(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

def write_json_parse(base_dir: Path, size: int, seed: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)

    prefix = b'{"items":['
    suffix = b']}'

    parts = []
    total_len = len(prefix) + len(suffix)
    index = 0

    while total_len < size:
        item = make_json_item(seed, index)
        item_bytes = json.dumps(item, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

        extra = len(item_bytes)
        if parts:
            extra += 1  # comma

        parts.append(item_bytes)
        total_len += extra
        index += 1

    data = prefix + b",".join(parts) + suffix
    (outdir / "input.json").write_bytes(data)

def write_file_copy(base_dir: Path, size: int, seed: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)

    data = xorshift(size, seed)
    (outdir / "input.bin").write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description="Generate input files for the benchmarks")
    parser.add_argument("--base-dir", type=Path, default=Path("inputs"), help="Base directory for generated inputs")
    parser.add_argument("--min-size", type=int, default=64, help="Minimum size of the buffer (in bytes)")
    parser.add_argument("--max-size", type=int, default=1024*1024*512, help="Maximum size of the buffer (in bytes)")
    parser.add_argument("--seed", type=int, default=12345, help="Seed for random number generation")
    parser.add_argument("--benchmarks", type=str, default="sha256,json_parse", help="Name of the benchmark(s) (used as subdirectory), comma seperated, e.g. sha256,json_parse,file_copy,pipeline")
    parser.add_argument("--out-root", type=str, default="datasets", help="Root directory for generated inputs")
    
    args = parser.parse_args()
    
    benchmarks = [b.strip() for b in args.benchmarks.split(",") if b.strip()]
    if not benchmarks:
        print("No benchmarks specified. Exiting.")
        return
    
    sizes = pow2(args.min_size, args.max_size)

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for bench in benchmarks:
        print(f"Generating inputs for benchmark: {bench}")
        base_dir = out_root / bench
        base_dir.mkdir(parents=True, exist_ok=True)

        bench_seed = stable_bench_seed(args.seed, bench)

        for size in sizes:
            if bench == "sha256":
                write_sha256(base_dir, size, bench_seed + size)
            elif bench == "json_parse":
                write_json_parse(base_dir, size, bench_seed + size)
            elif bench == "file_copy":
                write_file_copy(base_dir, size, bench_seed + size)
            else:
                print(f"Skipping unsupported benchmark: {bench}")
                continue
            total += 1

    print(f"Generated {total} dataset directories for benchmarks: {', '.join(benchmarks)}")

if __name__ == "__main__":
    main()