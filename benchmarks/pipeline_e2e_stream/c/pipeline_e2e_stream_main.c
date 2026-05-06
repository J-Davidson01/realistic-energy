#include "../../workloads/c/pipeline_e2e_stream.h"

#include "../../workloads/c/file_copy.h"
#include "../../workloads/c/json_parse.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <libgen.h>
#include "cJSON.h"
#include <time.h>

#ifndef DEFAULT_JSON_DATASET_DIR
#define DEFAULT_JSON_DATASET_DIR "../../../datasets/json_parse/1048576"
#endif

#ifndef DEFAULT_SHA256_DATASET_DIR
#define DEFAULT_SHA256_DATASET_DIR "../../../datasets/sha256/1048576"
#endif

#ifndef DEFAULT_OUTPUT_DIR
#define DEFAULT_OUTPUT_DIR "../../../datasets/file_copy/1048576"
#endif

#ifndef DEFAULT_ITERATIONS
#define DEFAULT_ITERATIONS 1000000UL
#endif

#ifndef DEFAULT_CHUNK_ITEMS
#define DEFAULT_CHUNK_ITEMS 1024UL
#endif

#ifndef PIPELINE_BUFFER_GROWTH_FACTOR
#define PIPELINE_BUFFER_GROWTH_FACTOR 2UL
#endif

#ifndef FILE_COPY_WRITE_AMPLIFICATION
#define FILE_COPY_WRITE_AMPLIFICATION 8
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

    unsigned char *buffer = (unsigned char *)malloc((size_t)file_size + 1);
    if (!buffer) {
        perror("Failed to allocate buffer");
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
    buffer[read_size] = '\0';
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

static void derive_dataset_dirs_from_selector(
    const char *dataset_selector,
    char *json_dataset_dir,
    size_t json_dataset_dir_size,
    char *sha256_dataset_dir,
    size_t sha256_dataset_dir_size,
    char *output_dir,
    size_t output_dir_size
) {
    char selector_copy1[512];
    char selector_copy2[512];
    char pipeline_root_copy[512];

    snprintf(selector_copy1, sizeof(selector_copy1), "%s", dataset_selector);
    snprintf(selector_copy2, sizeof(selector_copy2), "%s", dataset_selector);

    char *size_name = basename(selector_copy1);
    char *pipeline_size_dir = dirname(selector_copy2);

    snprintf(pipeline_root_copy, sizeof(pipeline_root_copy), "%s", pipeline_size_dir);
    char *datasets_root = dirname(pipeline_root_copy);

    snprintf(json_dataset_dir, json_dataset_dir_size, "%s/json_parse/%s", datasets_root, size_name);
    snprintf(sha256_dataset_dir, sha256_dataset_dir_size, "%s/sha256/%s", datasets_root, size_name);
    snprintf(output_dir, output_dir_size, "%s/file_copy/%s", datasets_root, size_name);
}

static pipeline_chunk_t *build_json_chunks(
    const char *input_json,
    size_t chunk_items,
    size_t *out_chunk_count,
    size_t *out_max_chunk_input_len
) {
    cJSON *root = cJSON_Parse(input_json);
    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "items");

    int total_items = cJSON_GetArraySize(items);
    size_t chunk_count = (size_t)((total_items + (int)chunk_items - 1) / (int)chunk_items);

    pipeline_chunk_t *chunks = (pipeline_chunk_t *)calloc(chunk_count, sizeof(pipeline_chunk_t));
    size_t max_chunk_input_len = 0;
    size_t chunk_index = 0;

    cJSON *item = items->child;

    while (item != NULL) {
        cJSON *chunk_root = cJSON_CreateObject();
        cJSON *chunk_items_array = cJSON_CreateArray();

        size_t items_in_chunk = 0;
        while (item != NULL && items_in_chunk < chunk_items) {
            cJSON_AddItemToArray(chunk_items_array, cJSON_Duplicate(item, 1));
            item = item->next;
            items_in_chunk++;
        }

        cJSON_AddItemToObject(chunk_root, "items", chunk_items_array);

        char *serialized = cJSON_PrintUnformatted(chunk_root);
        size_t serialized_len = strlen(serialized);

        chunks[chunk_index].json = serialized;
        chunks[chunk_index].json_len = serialized_len;

        if (serialized_len > max_chunk_input_len) {
            max_chunk_input_len = serialized_len;
        }

        chunk_index++;
        cJSON_Delete(chunk_root);
    }

    cJSON_Delete(root);

    *out_chunk_count = chunk_count;
    *out_max_chunk_input_len = max_chunk_input_len;
    return chunks;
}

static void free_json_chunks(pipeline_chunk_t *chunks, size_t chunk_count) {
    for (size_t i = 0; i < chunk_count; i++) {
        free((void *)chunks[i].json);
    }
    free(chunks);
}

static bool file_equals_streamed_chunks(
    const char *path,
    const pipeline_chunk_t *chunks,
    size_t chunk_count
) {
    size_t file_len = 0;
    unsigned char *file_bytes = read_file(path, &file_len);
    if (!file_bytes) {
        return false;
    }

    size_t offset = 0;

    for (size_t i = 0; i < chunk_count; i++) {
        char *verify_json = NULL;
        size_t verify_len = 0;

        workload_json_parse(chunks[i].json, &verify_json, &verify_len);

        size_t repeated_len = verify_len * (size_t)FILE_COPY_WRITE_AMPLIFICATION;
        if (offset + repeated_len > file_len) {
            free(verify_json);
            free(file_bytes);
            return false;
        }

        for (int rep = 0; rep < FILE_COPY_WRITE_AMPLIFICATION; rep++) {
            if (memcmp(file_bytes + offset, verify_json, verify_len) != 0) {
                free(verify_json);
                free(file_bytes);
                return false;
            }
            offset += verify_len;
        }

        free(verify_json);
    }

    bool ok = (offset == file_len);
    free(file_bytes);
    return ok;
}

int main(int argc, char **argv) {
    const char *dataset_selector = parse_str(argc, argv, "--dataset", NULL);

    char json_dataset_dir_buf[512];
    char sha256_dataset_dir_buf[512];
    char output_dir_buf[512];

    const char *json_dataset_dir = NULL;
    const char *sha256_dataset_dir = NULL;
    const char *output_dir = NULL;

    if (dataset_selector) {
        derive_dataset_dirs_from_selector(
            dataset_selector,
            json_dataset_dir_buf, sizeof(json_dataset_dir_buf),
            sha256_dataset_dir_buf, sizeof(sha256_dataset_dir_buf),
            output_dir_buf, sizeof(output_dir_buf)
        );
    } else {
        snprintf(json_dataset_dir_buf, sizeof(json_dataset_dir_buf), "%s", DEFAULT_JSON_DATASET_DIR);
        snprintf(sha256_dataset_dir_buf, sizeof(sha256_dataset_dir_buf), "%s", DEFAULT_SHA256_DATASET_DIR);
        snprintf(output_dir_buf, sizeof(output_dir_buf), "%s", DEFAULT_OUTPUT_DIR);
    }

    json_dataset_dir = parse_str(argc, argv, "--json-dataset", json_dataset_dir_buf);
    sha256_dataset_dir = parse_str(argc, argv, "--sha256-dataset", sha256_dataset_dir_buf);
    output_dir = parse_str(argc, argv, "--output-dir", output_dir_buf);

    size_t iterations = parse_u64(argc, argv, "--iterations", DEFAULT_ITERATIONS);
    size_t chunk_items = parse_u64(argc, argv, "--chunk-items", DEFAULT_CHUNK_ITEMS);
    bool verify = has_flag(argc, argv, "--verify");

    char input_path[512];
    char key_hmac_path[512];
    char key_xor_path[512];
    char output_path[512];

    snprintf(input_path, sizeof(input_path), "%s/input.json", json_dataset_dir);
    snprintf(key_hmac_path, sizeof(key_hmac_path), "%s/key_hmac.bin", sha256_dataset_dir);
    snprintf(key_xor_path, sizeof(key_xor_path), "%s/key_xor.bin", sha256_dataset_dir);
    snprintf(output_path, sizeof(output_path), "%s/output.bin", output_dir);

    size_t input_len = 0;
    unsigned char *input_json = read_file(input_path, &input_len);

    size_t key_hmac_len = 0;
    unsigned char *key_hmac = read_file(key_hmac_path, &key_hmac_len);

    size_t key_xor_len = 0;
    unsigned char *key_xor = read_file(key_xor_path, &key_xor_len);

    if (chunk_items == 0) {
        chunk_items = 1;
    }

    size_t chunk_count = 0;
    size_t max_chunk_input_len = 0;
    
    pipeline_chunk_t *chunks = build_json_chunks(
        (const char *)input_json,
        chunk_items,
        &chunk_count,
        &max_chunk_input_len
    );

    size_t pipeline_buffer_len = max_chunk_input_len * PIPELINE_BUFFER_GROWTH_FACTOR + 64;

    unsigned char *ciphertext = (unsigned char *)malloc(pipeline_buffer_len);
    unsigned char *decrypted = (unsigned char *)malloc(pipeline_buffer_len);
    unsigned char out_hmac[32];

    if (!input_json || !key_hmac || !key_xor || !chunks || !ciphertext || !decrypted) {
        fprintf(stderr, "Failed to allocate or load pipeline inputs\n");
        free(input_json);
        free(key_hmac);
        free(key_xor);
        free(chunks);
        free(ciphertext);
        free(decrypted);
        return 1;
    }

    if (verify) {
        int dst_fd = open(output_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (dst_fd < 0) {
            perror("Failed to open destination file");
            free_json_chunks(chunks, chunk_count);
            free(input_json);
            free(key_hmac);
            free(key_xor);
            free(ciphertext);
            free(decrypted);
            return 1;
        }

        workload_pipeline_e2e_stream(
            chunks,
            chunk_count,
            key_hmac,
            key_hmac_len,
            key_xor,
            key_xor_len,
            ciphertext,
            decrypted,
            out_hmac,
            dst_fd
        );

        close(dst_fd);

        int verification = file_equals_streamed_chunks(output_path, chunks, chunk_count);

        printf("verify= %d\n", verification ? 1 : 0);

        free_json_chunks(chunks, chunk_count);
        free(input_json);
        free(key_hmac);
        free(key_xor);
        free(ciphertext);
        free(decrypted);

        return verification ? 0 : 1;
    }

    for (size_t i = 0; i < iterations; i++) {
        int dst_fd = open(output_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (dst_fd < 0) {
            perror("Failed to open destination file");
            free_json_chunks(chunks, chunk_count);
            free(input_json);
            free(key_hmac);
            free(key_xor);
            free(ciphertext);
            free(decrypted);
            return 1;
        }

        workload_pipeline_e2e_stream(
            chunks,
            chunk_count,
            key_hmac,
            key_hmac_len,
            key_xor,
            key_xor_len,
            ciphertext,
            decrypted,
            out_hmac,
            dst_fd
        );

        close(dst_fd);
    }

    free_json_chunks(chunks, chunk_count);
    free(input_json);
    free(key_hmac);
    free(key_xor);
    free(ciphertext);
    free(decrypted);
    return 0;
}