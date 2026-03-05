#!/usr/bin/env python3
import argparse
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

def write(base_dir: Path, size: int, key_hmac_len: int, key_xor_len: int, buffer_len: int, seed: int):
    """Write the generated input to a file."""
    outdir = base_dir / str(size)
    outdir.mkdir(parents=True, exist_ok=True)
    
    key_hmac = xorshift(key_hmac_len, seed)
    key_xor = xorshift(key_xor_len, seed + 1)
    buffer = xorshift(buffer_len, seed + 2)

    (outdir / "buffer.bin").write_bytes(buffer)
    (outdir / "key_hmac.bin").write_bytes(key_hmac)
    (outdir / "key_xor.bin").write_bytes(key_xor)

def main():
    parser = argparse.ArgumentParser(description="Generate input files for the benchmarks")
    parser.add_argument("--base-dir", type=Path, default=Path("inputs"), help="Base directory for generated inputs")
    parser.add_argument("--min-size", type=int, default=64, help="Minimum size of the buffer (in bytes)")
    parser.add_argument("--max-size", type=int, default=1024*1024*512, help="Maximum size of the buffer (in bytes)")
    parser.add_argument("--seed", type=int, default=12345, help="Seed for random number generation")
    parser.add_argument("--benchmarks", type=str, default="sha256", help="Name of the benchmark(s) (used as subdirectory), comma seperated, e.g. sha256,json_parse,file_copy,pipeline")
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
        bench_seed = args.seed + hash(bench) % (2**32)  # Derive a unique seed for each benchmark, while remaining deterministic
        
        for size in sizes:
            write(base_dir, size, 32, 16, size, bench_seed)
            total += 1

    print(f"Generated {total} input files for benchmarks: {', '.join(benchmarks)}")

if __name__ == "__main__":
    main()