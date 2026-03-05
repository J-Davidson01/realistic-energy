#pragma once
#include <stddef.h>

void workload_sha256(
    const unsigned char *buffer, size_t buffer_len,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor,  size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32]
);

