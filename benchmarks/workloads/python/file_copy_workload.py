#!/usr/bin/env python3
import os

sink = 0

FILE_COPY_WRITE_AMPLIFICATION = 8
FILE_COPY_SYNC_INTERVAL = 64 * 1024 * 1024


def write_all(dst, buffer: bytes) -> None:
    written = 0
    view = memoryview(buffer)
    length = len(buffer)

    while written < length:
        written += dst.write(view[written:])


def workload_file_copy(dst, buffer: bytes) -> int:
    global sink

    bytes_since_sync = 0
    buffer_len = len(buffer)

    for _ in range(FILE_COPY_WRITE_AMPLIFICATION):
        write_all(dst, buffer)
        bytes_since_sync += buffer_len

        if bytes_since_sync >= FILE_COPY_SYNC_INTERVAL:
            dst.flush()
            os.fsync(dst.fileno())
            bytes_since_sync = 0

    dst.flush()
    os.fsync(dst.fileno())

    sink ^= (buffer_len & 0xFF)
    sink ^= buffer[0]

    return 1