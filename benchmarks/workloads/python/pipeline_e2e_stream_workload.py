#!/usr/bin/env python3
from .file_copy_workload import (
    FILE_COPY_SYNC_INTERVAL,
    FILE_COPY_WRITE_AMPLIFICATION,
    write_all,
)
from .sha256_workload import workload_sha256
from .json_parse_workload import workload_json_parse
from typing import List

import os

pipeline_e2e_stream_sink = 0


def workload_pipeline_e2e_stream(
    chunks: List[str],
    key_hmac: bytes,
    key_xor: bytes,
    ciphertext: bytearray,
    decrypted: bytearray,
    out_hmac: bytearray,
    dst,
) -> int:
    global pipeline_e2e_stream_sink

    bytes_since_sync = 0

    for chunk in chunks:
        output_json = [""]
        output_len = [0]

        workload_json_parse(chunk, output_json, output_len)

        transformed_json = output_json[0]
        transformed_len = output_len[0]
        transformed_bytes = transformed_json.encode("utf-8")

        ciphertext_view = memoryview(ciphertext)[:transformed_len]
        decrypted_view = memoryview(decrypted)[:transformed_len]

        workload_sha256(
            transformed_bytes,
            key_hmac,
            key_xor,
            ciphertext_view,
            decrypted_view,
            out_hmac,
        )

        for _ in range(FILE_COPY_WRITE_AMPLIFICATION):
            write_all(dst, decrypted_view)
            bytes_since_sync += transformed_len

            if bytes_since_sync >= FILE_COPY_SYNC_INTERVAL:
                dst.flush()
                os.fsync(dst.fileno())
                bytes_since_sync = 0

        pipeline_e2e_stream_sink ^= transformed_len & 0xFF
        pipeline_e2e_stream_sink ^= decrypted[0]
        pipeline_e2e_stream_sink ^= out_hmac[0]

    dst.flush()
    os.fsync(dst.fileno())

    return 1
