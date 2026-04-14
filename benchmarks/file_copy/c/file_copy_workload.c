#include "file_copy.h"

#include <fcntl.h>
#include <unistd.h>

volatile unsigned char sink = 0;

size_t workload_file_copy(
    const char *src_path,
    const char *dst_path,
    unsigned char *buffer,
    size_t chunk_size
) {
    int src = open(src_path, O_RDONLY);
    int dst = open(dst_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);

    size_t total_bytes = 0;

    while (1) {
        ssize_t bytes_read = read(src, buffer, chunk_size);
        if (bytes_read == 0) {
            break;
        }

        ssize_t bytes_written = 0;
        while (bytes_written < bytes_read) {
            ssize_t n = write(dst, buffer + bytes_written, (size_t)(bytes_read - bytes_written));
            bytes_written += n;
        }

        total_bytes += (size_t)bytes_read;
    }

    fsync(dst);

    sink ^= (unsigned char)(total_bytes & 0xFF);

    close(src);
    close(dst);

    return total_bytes;
}