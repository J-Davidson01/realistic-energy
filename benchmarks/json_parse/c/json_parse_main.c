#include "json_parse.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

static unsigned char* read_file(const char* path, size_t *out_len) {
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
        unsigned char *buffer = malloc(file_size);
        
        if (!buffer) {
            perror("Failed to allocate buffer");
            fclose(file);
            return NULL;
        }

        size_t read_size = fread(buffer, 1, file_size, file);
        
        if (read_size != file_size) {
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

int main(int argc, char **argv) {
    const char *dataset_dir = parse_str(argc, argv, "--dataset", "../../../datasets/json_parse/1048576");
    size_t iterations = parse_u64(argc, argv, "--iterations", 1000000);

    char input_path[512];
    snprintf(input_path, sizeof(input_path), "%s/input.json", dataset_dir);

    size_t input_len = 0;
    unsigned char *input_json = read_file(input_path, &input_len);
    if (!input_json) {
        fprintf(stderr, "Failed to load input JSON\n");
        return 1;
    }

    if (has_flag(argc, argv, "--verify")) {
        char *output_json = NULL;
        size_t output_len = 0;

        int ok = workload_json_parse((const char *)input_json, &output_json, &output_len);
        int verified = ok && verify_json_parse_output(output_json);

        if (verified) {
            printf("verify= 1\n");
        } else {
            printf("verify= 0\n");
        }

        free(output_json);
        free(input_json);
        return verified ? 0 : 1;
    }

    for (size_t i = 0; i < iterations; i++) {
        char *output_json = NULL;
        size_t output_len = 0;

        int ok = workload_json_parse((const char *)input_json, &output_json, &output_len);
        if (!ok) {
            fprintf(stderr, "workload_json_parse failed at iteration %zu\n", i);
            free(input_json);
            return 1;
        }

        free(output_json);
    }

    free(input_json);
    return 0;
}
