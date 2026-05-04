#!/usr/bin/env python3
import argparse
import sys
from typing import List, Tuple
from pathlib import Path

import json

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.workloads.python.file_copy_workload import FILE_COPY_WRITE_AMPLIFICATION
from benchmarks.workloads.python.json_parse_workload import workload_json_parse
from benchmarks.workloads.python.pipeline_e2e_stream_workload import workload_pipeline_e2e_stream

DEFAULT_JSON_DATASET_DIR = "../../../datasets/json_parse/1048576"
DEFAULT_SHA256_DATASET_DIR = "../../../datasets/sha256/1048576"
DEFAULT_OUTPUT_DIR = "../../../datasets/file_copy/1048576"
DEFAULT_ITERATIONS = 1000000
DEFAULT_CHUNK_ITEMS = 1024
PIPELINE_BUFFER_GROWTH_FACTOR = 2


def derive_dataset_dirs_from_selector(dataset_selector: str) -> Tuple[str, str, str]:
    selector = Path(dataset_selector)
    size_name = selector.name
    datasets_root = selector.parent.parent

    json_dataset_dir = datasets_root / "json_parse" / size_name
    sha256_dataset_dir = datasets_root / "sha256" / size_name
    output_dir = datasets_root / "file_copy" / size_name

    return str(json_dataset_dir), str(sha256_dataset_dir), str(output_dir)


def build_json_chunks(input_json: str, chunk_items: int) -> Tuple[List[str], int]:
    root = json.loads(input_json)
    items = root["items"]

    if chunk_items <= 0:
        chunk_items = 1

    chunks: List[str] = []
    max_chunk_input_len = 0

    for start in range(0, len(items), chunk_items):
        end = min(start + chunk_items, len(items))
        chunk_root = {"items": items[start:end]}
        serialized = json.dumps(chunk_root, separators=(",", ":"))

        chunks.append(serialized)
        serialized_len = len(serialized.encode("utf-8"))
        if serialized_len > max_chunk_input_len:
            max_chunk_input_len = serialized_len

    return chunks, max_chunk_input_len


def file_equals_streamed_chunks(path: Path, chunks: List[str]) -> bool:
    file_bytes = path.read_bytes()
    offset = 0

    for chunk in chunks:
        verify_json = [""]
        verify_len = [0]

        workload_json_parse(chunk, verify_json, verify_len)

        verify_bytes = verify_json[0].encode("utf-8")
        repeated_len = verify_len[0] * FILE_COPY_WRITE_AMPLIFICATION

        if offset + repeated_len > len(file_bytes):
            return False

        for _ in range(FILE_COPY_WRITE_AMPLIFICATION):
            if file_bytes[offset:offset + verify_len[0]] != verify_bytes:
                return False
            offset += verify_len[0]

    return offset == len(file_bytes)


def bool_to_int(v: bool) -> int:
    return 1 if v else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--json-dataset", default=DEFAULT_JSON_DATASET_DIR)
    parser.add_argument("--sha256-dataset", default=DEFAULT_SHA256_DATASET_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--chunk-items", type=int, default=DEFAULT_CHUNK_ITEMS)
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

    chunks, max_chunk_input_len = build_json_chunks(input_json, args.chunk_items)

    pipeline_buffer_len = max_chunk_input_len * PIPELINE_BUFFER_GROWTH_FACTOR + 64
    ciphertext = bytearray(pipeline_buffer_len)
    decrypted = bytearray(pipeline_buffer_len)
    out_hmac = bytearray(32)

    if args.verify:
        try:
            with output_path.open("wb") as dst:
                workload_pipeline_e2e_stream(
                    chunks,
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

        verification = file_equals_streamed_chunks(output_path, chunks)
        print(f"verify= {bool_to_int(verification)}")

        if not verification:
            raise SystemExit(1)
        return

    for _ in range(args.iterations):
        try:
            with output_path.open("wb") as dst:
                workload_pipeline_e2e_stream(
                    chunks,
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
