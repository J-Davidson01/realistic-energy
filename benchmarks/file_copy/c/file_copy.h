#ifndef FILE_COPY_H
#define FILE_COPY_H

#include <stddef.h>

size_t workload_file_copy(
    int dst_fd,
    const unsigned char *buffer,
    size_t buffer_len
);

#endif