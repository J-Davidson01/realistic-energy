#include "../../workloads/c/json_parse.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <ctype.h>
#include "cJSON.h"

typedef int (*json_parse_workload_fn)(
    const char *input_json,
    char **output_json,
    size_t *output_len
);

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
        unsigned char *buffer = malloc((size_t)file_size + 1);
        buffer[file_size] = '\0'; 

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

// Verification function to check if the output JSON is correct, 
// called from _main when --verify flag is set
int verify_json_parse_output(const char *output_json) {
    if (!output_json) {
        return 0;
    }

    cJSON *root = cJSON_Parse(output_json);
    if (!root) {
        return 0;
    }

    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "items");
    if (!cJSON_IsArray(items)) {
        cJSON_Delete(root);
        return 0;
    }

    cJSON *item = NULL;
    cJSON_ArrayForEach(item, items) {
        if (!cJSON_IsObject(item)) {
            cJSON_Delete(root);
            return 0;
        }

        cJSON *id = cJSON_GetObjectItemCaseSensitive(item, "id");
        cJSON *active = cJSON_GetObjectItemCaseSensitive(item, "active");
        cJSON *name = cJSON_GetObjectItemCaseSensitive(item, "name");
        cJSON *name_length = cJSON_GetObjectItemCaseSensitive(item, "name_length");

        if (!cJSON_IsNumber(id) ||
            !cJSON_IsBool(active) ||
            !cJSON_IsString(name) || !name->valuestring ||
            !cJSON_IsNumber(name_length)) {
            cJSON_Delete(root);
            return 0;
        }

        size_t actual_len = strlen(name->valuestring);
        if ((size_t)name_length->valuedouble != actual_len) {
            cJSON_Delete(root);
            return 0;
        }

        for (size_t i = 0; i < actual_len; i++) {
            unsigned char ch = (unsigned char)name->valuestring[i];
            if (isalpha(ch) && name->valuestring[i] != (char)toupper(ch)) {
                cJSON_Delete(root);
                return 0;
            }
        }
    }

    cJSON_Delete(root);
    return 1;
}

static json_parse_workload_fn select_json_parse_impl(const char *impl_name) {
    if (strcmp(impl_name, "cjson") == 0) {
        return workload_json_parse;
    }

    if (strcmp(impl_name, "yyjson") == 0) {
        return workload_json_parse_yyjson;
    }

    fprintf(stderr, "Unknown --json-impl: %s\n", impl_name);
    fprintf(stderr, "Supported values: cjson, yyjson\n");
    return NULL;
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

    const char *json_impl = parse_str(argc, argv, "--json-impl", "cjson");
    json_parse_workload_fn workload = select_json_parse_impl(json_impl);
    if (!workload) {
        free(input_json);
        return 1;
    }

    if (has_flag(argc, argv, "--verify")) {
        char *output_json = NULL;
        size_t output_len = 0;

        int ok = workload((const char *)input_json, &output_json, &output_len);
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

        int ok = workload((const char *)input_json, &output_json, &output_len);
        if (!ok) {
            fprintf(stderr, "workload failed at iteration %zu\n", i);
            free(input_json);
            return 1;
        }

        free(output_json);
    }

    free(input_json);
    return 0;
}
