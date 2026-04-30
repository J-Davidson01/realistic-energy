#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.workloads.python.file_copy_workload import workload_file_copy, FILE_COPY_WRITE_AMPLIFICATION


def files_equal_amplified(src_path: Path, dst_path: Path, amplification: int) -> bool:
    src = src_path.read_bytes()
    dst = dst_path.read_bytes()

    if len(dst) != len(src) * amplification:
        return False

    n = len(src)
    for i in range(amplification):
        start = i * n
        end = start + n
        if dst[start:end] != src:
            return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../../../datasets/file_copy/1048576")
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    src_path = dataset_dir / "input.bin"
    dst_path = dataset_dir / "output.bin"

    input_buffer = src_path.read_bytes()

    if args.verify:
        with dst_path.open("wb") as dst:
            workload_file_copy(dst, input_buffer)

        verification = files_equal_amplified(
            src_path,
            dst_path,
            FILE_COPY_WRITE_AMPLIFICATION,
        )

        print(f"verify= {1 if verification else 0}")

        if verification:
            return
        raise SystemExit(1)

    for _ in range(args.iterations):
        with dst_path.open("wb") as dst:
            workload_file_copy(dst, input_buffer)


if __name__ == "__main__":
    main()