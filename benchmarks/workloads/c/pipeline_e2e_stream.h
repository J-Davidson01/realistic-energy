#ifndef PIPELINE_E2E_STREAM_H
#define PIPELINE_E2E_STREAM_H

#include <stddef.h>

typedef struct {
    const char *json;
    size_t json_len;
} pipeline_chunk_t;

size_t workload_pipeline_e2e_stream(
    const pipeline_chunk_t *chunks,
    size_t chunk_count,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor, size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32],
    int dst_fd
);

#endif
