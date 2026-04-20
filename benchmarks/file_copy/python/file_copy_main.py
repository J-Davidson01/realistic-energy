#!/usr/bin/env python3
import argparse
from pathlib import Path

from file_copy_workload import workload_file_copy, FILE_COPY_WRITE_AMPLIFICATION

def files_equal_amplified(src_path: Path, dst_path: Path, chunk_size: int, amplification: int) -> bool:
    with src_path.open("rb") as src, dst_path.open("rb") as dst:
        while True:
            src_chunk = src.read(chunk_size)
            if not src_chunk:
                break

            for _ in range(amplification):
                dst_chunk = dst.read(len(src_chunk))
                if dst_chunk != src_chunk:
                    return False

        return dst.read(1) == b""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../../../datasets/file_copy/1048576")
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    src_path = dataset_dir / "input.bin"
    dst_path = dataset_dir / "output.bin"

    chunk_size = 65536
    buffer = bytearray(chunk_size)

    if args.verify:
        copied_bytes = workload_file_copy(str(src_path), str(dst_path), buffer)
        verification = files_equal_amplified(
            src_path,
            dst_path,
            chunk_size,
            FILE_COPY_WRITE_AMPLIFICATION,
        )

        print(f"copied_bytes= {copied_bytes}")
        print(f"verify= {1 if verification else 0}")

        if verification:
            return
        raise SystemExit(1)

    for _ in range(args.iterations):
        workload_file_copy(str(src_path), str(dst_path), buffer)

if __name__ == "__main__":
    main()