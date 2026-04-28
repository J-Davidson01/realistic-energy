#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.workloads.python.file_copy_workload import FILE_COPY_WRITE_AMPLIFICATION
from benchmarks.workloads.python.json_parse_workload import workload_json_parse
from benchmarks.workloads.python.pipeline_e2e_workload import workload_pipeline_e2e

DEFAULT_JSON_DATASET_DIR = "../../../datasets/json_parse/1048576"
DEFAULT_SHA256_DATASET_DIR = "../../../datasets/sha256/1048576"
DEFAULT_OUTPUT_DIR = "../../../datasets/file_copy/1048576"
DEFAULT_ITERATIONS = 1000000
PIPELINE_BUFFER_GROWTH_FACTOR = 2


def derive_dataset_dirs_from_selector(dataset_selector: str) -> tuple[str, str, str]:
    selector = Path(dataset_selector)
    size_name = selector.name
    datasets_root = selector.parent.parent

    json_dataset_dir = datasets_root / "json_parse" / size_name
    sha256_dataset_dir = datasets_root / "sha256" / size_name
    output_dir = datasets_root / "file_copy" / size_name

    return str(json_dataset_dir), str(sha256_dataset_dir), str(output_dir)


def file_equals_amplified_buffer(path: Path, buffer: bytes, amplification: int) -> bool:
    file_bytes = path.read_bytes()

    if len(file_bytes) != len(buffer) * amplification:
        return False

    for i in range(amplification):
        start = i * len(buffer)
        end = start + len(buffer)
        if file_bytes[start:end] != buffer:
            return False

    return True


def bool_to_int(v: bool) -> int:
    return 1 if v else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--json-dataset", default=DEFAULT_JSON_DATASET_DIR)
    parser.add_argument("--sha256-dataset", default=DEFAULT_SHA256_DATASET_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.dataset is not None:
        json_dataset_dir, sha256_dataset_dir, output_dir = derive_dataset_dirs_from_selector(args.dataset)
    else:
        json_dataset_dir = args.json_dataset
        sha256_dataset_dir = args.sha256_dataset
        output_dir = args.output_dir

    input_path = Path(json_dataset_dir) / "input.json"
    key_hmac_path = Path(sha256_dataset_dir) / "key_hmac.bin"
    key_xor_path = Path(sha256_dataset_dir) / "key_xor.bin"
    output_path = Path(output_dir) / "output.bin"

    try:
        input_json = input_path.read_text(encoding="utf-8")
        key_hmac = key_hmac_path.read_bytes()
        key_xor = key_xor_path.read_bytes()
    except OSError:
        print("Failed to allocate or load pipeline inputs")
        raise SystemExit(1)

    input_len = len(input_json.encode("utf-8"))
    pipeline_buffer_len = input_len * PIPELINE_BUFFER_GROWTH_FACTOR + 64

    ciphertext = bytearray(pipeline_buffer_len)
    decrypted = bytearray(pipeline_buffer_len)
    out_hmac = bytearray(32)

    if args.verify:
        try:
            with output_path.open("wb") as dst:
                workload_pipeline_e2e(
                    input_json,
                    key_hmac,
                    key_xor,
                    ciphertext,
                    decrypted,
                    out_hmac,
                    dst,
                )
        except OSError:
            print("Failed to open destination file")
            raise SystemExit(1)

        verify_json = [""]
        verify_len = [0]
        workload_json_parse(input_json, verify_json, verify_len)

        verify_bytes = verify_json[0].encode("utf-8")
        crypto_ok = verify_len[0] == 0 or decrypted[:verify_len[0]] == verify_bytes
        file_ok = file_equals_amplified_buffer(
            output_path,
            verify_bytes,
            FILE_COPY_WRITE_AMPLIFICATION,
        )

        verification = crypto_ok and file_ok
        print(f"verify= {bool_to_int(verification)}")
        if not verification:
            raise SystemExit(1)
        return

    for _ in range(args.iterations):
        try:
            with output_path.open("wb") as dst:
                workload_pipeline_e2e(
                    input_json,
                    key_hmac,
                    key_xor,
                    ciphertext,
                    decrypted,
                    out_hmac,
                    dst,
                )
        except OSError:
            print("Failed to open destination file")
            raise SystemExit(1)


if __name__ == "__main__":
    main()