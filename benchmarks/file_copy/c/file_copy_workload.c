#include "file_copy.h"

#include <unistd.h>

volatile unsigned char sink = 0;

#ifndef FILE_COPY_WRITE_AMPLIFICATION
#define FILE_COPY_WRITE_AMPLIFICATION 8
#endif

#ifndef FILE_COPY_SYNC_INTERVAL
#define FILE_COPY_SYNC_INTERVAL (64ULL * 1024ULL * 1024ULL) /* 64 MiB */
#endif

size_t workload_file_copy(
    int dst_fd,
    const unsigned char *buffer,
    size_t buffer_len
) {
    size_t bytes_since_sync = 0;

    for (int i = 0; i < FILE_COPY_WRITE_AMPLIFICATION; i++) {
        write_all(dst_fd, buffer, buffer_len);
        bytes_since_sync += buffer_len;

        if (bytes_since_sync >= FILE_COPY_SYNC_INTERVAL) {
            fdatasync(dst_fd);
            bytes_since_sync = 0;
        }
    }

    fdatasync(dst_fd);

    sink ^= (unsigned char)(buffer_len & 0xFF);
    sink ^= (unsigned char)(total_bytes_written & 0xFF);
    sink ^= buffer[0];

    return 1;
}