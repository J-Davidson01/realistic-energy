#include "file_copy.h"

#include <fcntl.h>
#include <unistd.h>

volatile unsigned char sink = 0;

#ifndef FILE_COPY_WRITE_AMPLIFICATION
#define FILE_COPY_WRITE_AMPLIFICATION 8
#endif

#ifndef FILE_COPY_SYNC_INTERVAL
#define FILE_COPY_SYNC_INTERVAL (64ULL * 1024ULL * 1024ULL) /* 64 MiB */
#endif

size_t workload_file_copy(
    const char *src_path,
    const char *dst_path,
    unsigned char *buffer,
    size_t chunk_size
) {
    int src = open(src_path, O_RDONLY);
    int dst = open(dst_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);

    size_t total_bytes_read = 0;
    size_t total_bytes_written = 0;
    size_t bytes_since_sync = 0;

    while (1) {
        ssize_t bytes_read = read(src, buffer, chunk_size);
        if (bytes_read == 0) {
            break;
        }

        size_t len = (size_t)bytes_read;
        total_bytes_read += len;

        for (int i = 0; i < FILE_COPY_WRITE_AMPLIFICATION; i++) {
            write_all(dst, buffer, len);
            total_bytes_written += len;
            bytes_since_sync += len;

            if (bytes_since_sync >= FILE_COPY_SYNC_INTERVAL) {
                fdatasync(dst);
                bytes_since_sync = 0;
            }
        }
    }

    fdatasync(dst);

    sink ^= (unsigned char)(total_bytes_read & 0xFF);
    sink ^= (unsigned char)(total_bytes_written & 0xFF);
    sink ^= buffer[0];

    close(src);
    close(dst);

    return total_bytes_written;
}