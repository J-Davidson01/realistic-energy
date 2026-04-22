#include "file_copy.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>

#ifndef DEFAULT_DATASET_DIR
#define DEFAULT_DATASET_DIR "../../../datasets/file_copy/1048576"
#endif

#ifndef DEFAULT_ITERATIONS
#define DEFAULT_ITERATIONS 1000000UL
#endif

static unsigned char *read_file(const char *path, size_t *out_len) {
    FILE *file = fopen(path, "rb");
    if (!file) {
        perror("Failed to open file");
        return NULL;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        perror("Failed to seek file");
        fclose(file);
        return NULL;
    }

    long file_size = ftell(file);
    if (file_size < 0) {
        perror("Failed to tell file size");
        fclose(file);
        return NULL;
    }

    rewind(file);

    unsigned char *buffer = (unsigned char *)malloc((size_t)file_size);
    if (!buffer) {
        perror("Failed to allocate input buffer");
        fclose(file);
        return NULL;
    }

    size_t read_size = fread(buffer, 1, (size_t)file_size, file);
    if (read_size != (size_t)file_size) {
        perror("Failed to read file");
        free(buffer);
        fclose(file);
        return NULL;
    }

    fclose(file);
    *out_len = read_size;
    return buffer;
}

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

    size_t input_len = 0;
    unsigned char *input_buffer = read_file(src_path, &input_len);
    if (!input_buffer) {
        fprintf(stderr, "Failed to load input buffer\n");
        return 1;
    }

    if (verify) {
        int dst_fd = open(dst_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (dst_fd < 0) {
            perror("Failed to open destination file");
            free(input_buffer);
            return 1;
        }

        size_t copied_bytes = workload_file_copy(dst_fd, input_buffer, input_len);
        close(dst_fd);

        int verification = files_equal(src_path, dst_path);

        printf("copied_bytes= %zu\n", copied_bytes);
        printf("verify= %d\n", verification ? 1 : 0);

        free(input_buffer);
        return verification ? 0 : 1;
    }

    for (size_t i = 0; i < iterations; i++) {
        int dst_fd = open(dst_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (dst_fd < 0) {
            perror("Failed to open destination file");
            free(input_buffer);
            return 1;
        }

        workload_file_copy(dst_fd, input_buffer, input_len);
        close(dst_fd);
    }

    free(input_buffer);
    return 0;
}