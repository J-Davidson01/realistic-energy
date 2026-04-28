#ifndef PIPELINE_E2E_H
#define PIPELINE_E2E_H

#include <stddef.h>

size_t workload_pipeline_e2e(
    const char *input_json,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor, size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32],
    int dst_fd
);

#endif