#include "file_copy.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef DEFAULT_DATASET_DIR
#define DEFAULT_DATASET_DIR "../../../datasets/file_copy/1048576"
#endif

#ifndef DEFAULT_ITERATIONS
#define DEFAULT_ITERATIONS 1000000UL
#endif

#ifndef CHUNK_SIZE
#define CHUNK_SIZE 65536UL
#endif

static size_t parse_u64(int argc, char **argv, const char *name, size_t def) {
    for (int i = 1; i + 1 < argc; i++) {
        if (strcmp(argv[i], name) == 0) {
            return (size_t)strtoull(argv[i + 1], NULL, 10);
        }
    }
    return def;
}

static const char *parse_str(int argc, char **argv, const char *name, const char *def) {
    for (int i = 1; i + 1 < argc; i++) {
        if (strcmp(argv[i], name) == 0) {
            return argv[i + 1];
        }
    }
    return def;
}

static bool has_flag(int argc, char **argv, const char *name) {
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], name) == 0) {
            return true;
        }
    }
    return false;
}

static bool files_equal(const char *a_path, const char *b_path) {
    FILE *a = fopen(a_path, "rb");
    FILE *b = fopen(b_path, "rb");

    if (!a || !b) {
        if (a) fclose(a);
        if (b) fclose(b);
        return false;
    }

    int ok = 1;

    while (1) {
        int ca = fgetc(a);
        int cb = fgetc(b);

        if (ca != cb) {
            ok = 0;
            break;
        }

        if (ca == EOF) {
            break;
        }
    }

    fclose(a);
    fclose(b);
    return ok != 0;
}

int main(int argc, char **argv) {
    const char *dataset_dir = parse_str(argc, argv, "--dataset", DEFAULT_DATASET_DIR);
    size_t iterations = parse_u64(argc, argv, "--iterations", DEFAULT_ITERATIONS);
    bool verify = has_flag(argc, argv, "--verify");

    char src_path[512];
    char dst_path[512];

    snprintf(src_path, sizeof(src_path), "%s/input.bin", dataset_dir);
    snprintf(dst_path, sizeof(dst_path), "%s/output.bin", dataset_dir);

    unsigned char *buffer = (unsigned char *)malloc(CHUNK_SIZE);
    if (!buffer) {
        fprintf(stderr, "Failed to allocate copy buffer\n");
        return 1;
    }

    if (verify) {
        size_t copied_bytes = workload_file_copy(src_path, dst_path, buffer, CHUNK_SIZE);
        int verification = files_equal(src_path, dst_path);

        printf("copied_bytes= %zu\n", copied_bytes);
        printf("verify= %d\n", verification ? 1 : 0);

        free(buffer);
        return verification ? 0 : 1;
    }

    for (size_t i = 0; i < iterations; i++) {
        workload_file_copy(src_path, dst_path, buffer, CHUNK_SIZE);
    }

    free(buffer);
    return 0;
}