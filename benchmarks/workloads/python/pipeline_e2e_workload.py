#!/usr/bin/env python3
import sys
from pathlib import Path

BENCHMARKS_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(BENCHMARKS_DIR / "file_copy" / "python"))
sys.path.append(str(BENCHMARKS_DIR / "sha256" / "python"))
sys.path.append(str(BENCHMARKS_DIR / "json_parse" / "python"))

from file_copy_workload import workload_file_copy
from sha256_workload import workload_sha256
from json_parse_workload import workload_json_parse

pipeline_e2e_sink = 0


def workload_pipeline_e2e(
    input_json: str,
    key_hmac: bytes,
    key_xor: bytes,
    ciphertext: bytearray,
    decrypted: bytearray,
    out_hmac: bytearray,
    dst,
) -> int:
    global pipeline_e2e_sink

    output_json = [""]
    output_len = [0]

    workload_json_parse(input_json, output_json, output_len)

    transformed_json = output_json[0]
    transformed_len = output_len[0]
    transformed_bytes = transformed_json.encode("utf-8")

    workload_sha256(
        transformed_bytes,
        key_hmac,
        key_xor,
        ciphertext[:transformed_len],
        decrypted[:transformed_len],
        out_hmac,
    )

    workload_file_copy(dst, decrypted[:transformed_len])

    pipeline_e2e_sink ^= transformed_len & 0xFF
    pipeline_e2e_sink ^= decrypted[0]
    pipeline_e2e_sink ^= out_hmac[0]

    return 1