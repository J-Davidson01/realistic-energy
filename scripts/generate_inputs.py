#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def pow2(min_size: int, max_size: int):
    sizes = []
    size = 1
    while size < min_size:
        size *= 2
    while size <= max_size:
        sizes.append(size)
        size *= 2
    return sizes


def xorshift(length: int, seed: int):
    x = seed & 0xFFFFFFFF
    out = bytearray(length)
    i = 0

    while i + 4 <= length:
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        out[i:i + 4] = x.to_bytes(4, "little")
        i += 4

    if i < length:
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        tail = x.to_bytes(4, "little")
        out[i:length] = tail[:length - i]

    return bytes(out)


def write_repeated_block_file(path: Path, size: int, seed: int, block_size: int = 4 * 1024 * 1024):
    block_size = min(block_size, size) if size > 0 else 0

    with path.open("wb") as f:
        if size == 0:
            return

        block = xorshift(block_size, seed)
        remaining = size

        while remaining > 0:
            n = min(block_size, remaining)
            f.write(block[:n])
            remaining -= n


def write_small_xorshift_file(path: Path, size: int, seed: int):
    path.write_bytes(xorshift(size, seed))


def write_sha256(base_dir: Path, size: int, seed: int, block_size: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)

    write_small_xorshift_file(outdir / "key_hmac.bin", 32, seed)
    write_small_xorshift_file(outdir / "key_xor.bin", 16, seed + 1)
    write_repeated_block_file(outdir / "buffer.bin", size, seed + 2, block_size)


def stable_bench_seed(seed: int, bench: str) -> int:
    x = seed & 0xFFFFFFFF
    for ch in bench.encode("utf-8"):
        x = (x * 16777619) ^ ch
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

def build_json_item_block(seed: int, block_items: int = 4096) -> list[bytes]:
    items = []
    for index in range(block_items):
        item = make_json_item(seed, index)
        item_bytes = json.dumps(item, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        items.append(item_bytes)
    return items

def write_json_parse(base_dir: Path, size: int, seed: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)

    path = outdir / "input.json"
    prefix = b'{"items":['
    suffix = b']}'

    block = build_json_item_block(seed, 4096)

    with path.open("wb") as f:
        f.write(prefix)
        total_len = len(prefix) + len(suffix)
        first = True
        block_index = 0

        while total_len < size:
            item_bytes = block[block_index]

            if first:
                extra = len(item_bytes)
            else:
                extra = 1 + len(item_bytes)

            if not first:
                f.write(b",")
            f.write(item_bytes)

            total_len += extra
            first = False

            block_index += 1
            if block_index == len(block):
                block_index = 0

        f.write(suffix)


def write_file_copy(base_dir: Path, size: int, seed: int, block_size: int):
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)
    write_repeated_block_file(outdir / "input.bin", size, seed, block_size)


def main():
    parser = argparse.ArgumentParser(description="Generate input files for the benchmarks")
    parser.add_argument("--base-dir", type=Path, default=Path("inputs"), help="Base directory for generated inputs")
    parser.add_argument("--min-size", type=int, default=64, help="Minimum size of the buffer (in bytes)")
    parser.add_argument("--max-size", type=int, default=1024 * 1024 * 512, help="Maximum size of the buffer (in bytes)")
    parser.add_argument("--seed", type=int, default=12345, help="Seed for random number generation")
    parser.add_argument("--benchmarks", type=str, default="sha256,json_parse", help="Comma separated benchmarks")
    parser.add_argument("--out-root", type=str, default="datasets", help="Root directory for generated inputs")
    parser.add_argument("--block-size", type=int, default=4 * 1024 * 1024, help="Block size for repeated binary data generation")

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
                write_sha256(base_dir, size, bench_seed + size, args.block_size)
                print(f"Generated SHA256 dataset of size {size} bytes")
            elif bench == "json_parse":
                write_json_parse(base_dir, size, bench_seed + size)
                print(f"Generated JSON Parse dataset of size {size} bytes")
            elif bench == "file_copy":
                write_file_copy(base_dir, size, bench_seed + size, args.block_size)
                print(f"Generated File Copy dataset of size {size} bytes")
            else:
                print(f"Skipping unsupported benchmark: {bench}")
                continue
            total += 1

    print(f"Generated {total} dataset directories for benchmarks: {', '.join(benchmarks)}")


if __name__ == "__main__":
    main()