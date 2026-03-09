#include "sha256.h"
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
                return (size_t)strtoull(argv[i+1], NULL, 10);
            }
        }
        return def;
    }

    static const char* parse_str(int argc, char **argv, const char *name, const char *def) {
        for (int i = 1; i + 1 < argc; i++) {
            if (strcmp(argv[i], name) == 0) return argv[i+1];
        }
        return def;
    }

    static bool has_flag(int argc, char **argv, const char *name) {
        for (int i = 1; i < argc; i++) {
            if (strcmp(argv[i], name) == 0) return true;
        }
        return false;
    }

    static void print_hex(const unsigned char *buf, size_t len) {
        for (size_t i = 0; i < len; i++) {
            printf("%02x", buf[i]);
        }
    }

    int main(int argc, char **argv) {
        const char *dataset_dir = parse_str(argc, argv, "--dataset", "../../../datasets/sha256/1048576"); //default dataset
        size_t iterations = parse_u64(argc, argv, "--iterations", 1000000); //default iterations

        char input_path[512];

        snprintf(input_path, sizeof(input_path), "%s/buffer.bin", dataset_dir);
        size_t buffer_len = 0;
        unsigned char *buffer = read_file(input_path, &buffer_len);

        snprintf(input_path, sizeof(input_path), "%s/key_hmac.bin", dataset_dir);
        size_t key_hmac_len = 0;
        unsigned char *key_hmac = read_file(input_path, &key_hmac_len);

        snprintf(input_path, sizeof(input_path), "%s/key_xor.bin", dataset_dir);
        size_t key_xor_len = 0;
        unsigned char *key_xor = read_file(input_path, &key_xor_len);

        unsigned char *ciphertext = (unsigned char*)malloc(buffer_len);
        unsigned char *decrypted = (unsigned char*)malloc(buffer_len);
        unsigned char out_hmac[32];

        if (!buffer || !key_hmac || !key_xor || !ciphertext || !decrypted) {
            fprintf(stderr, "Failed to allocate memory for inputs or outputs\n");
            free(buffer);
            free(key_hmac);
            free(key_xor);
            free(ciphertext);
            free(decrypted);
            return 1;
        }

        if(has_flag(argc, argv, "--verify")) {
            workload_sha256(buffer, buffer_len, key_hmac, key_hmac_len, key_xor, key_xor_len, ciphertext, decrypted, out_hmac);
            int verification = (buffer_len == 0) || (memcmp(buffer, decrypted, buffer_len) == 0);
            printf("HMAC: ");
            print_hex(out_hmac, 32);
            printf("\verify= %s\n", verification ? "1" : "0");
            
            goto cleanup;
        }

        for (size_t i = 0; i < iterations; i++) {
            workload_sha256(buffer, buffer_len, key_hmac, key_hmac_len, key_xor, key_xor_len, ciphertext, decrypted, out_hmac);
        }

        cleanup:
            free(buffer);
            free(key_hmac);
            free(key_xor);
            free(ciphertext);
            free(decrypted);
            return 0;
    }

