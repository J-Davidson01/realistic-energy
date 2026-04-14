#ifndef FILE_COPY_H
#define FILE_COPY_H

#include <stddef.h>

extern volatile unsigned char sink;

size_t workload_file_copy(
    const char *src_path,
    const char *dst_path,
    unsigned char *buffer,
    size_t chunk_size
);

#endif