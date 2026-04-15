#!/usr/bin/env python3
import os

sink = 0

FILE_COPY_WRITE_AMPLIFICATION = 8
FILE_COPY_SYNC_INTERVAL = 64 * 1024 * 1024

def write_all(dst, buffer: bytearray, length: int) -> None:
    written = 0
    view = memoryview(buffer)
    while written < length:
        written += dst.write(view[written:length])

def workload_file_copy(src_path: str, dst_path: str, buffer: bytearray) -> int:
    global sink

    src = open(src_path, "rb")
    dst = open(dst_path, "wb")

    total_bytes_read = 0
    total_bytes_written = 0
    bytes_since_sync = 0

    while True:
        bytes_read = src.readinto(buffer)
        if bytes_read == 0:
            break

        total_bytes_read += bytes_read

        for _ in range(FILE_COPY_WRITE_AMPLIFICATION):
            write_all(dst, buffer, bytes_read)
            total_bytes_written += bytes_read
            bytes_since_sync += bytes_read

            if bytes_since_sync >= FILE_COPY_SYNC_INTERVAL:
                dst.flush()
                os.fsync(dst.fileno())
                bytes_since_sync = 0

    dst.flush()
    os.fsync(dst.fileno())

    sink ^= (total_bytes_read & 0xFF)
    sink ^= (total_bytes_written & 0xFF)
    sink ^= buffer[0]

    src.close()
    dst.close()

    return total_bytes_written