#include "sha256.h"
#include <openssl/evp.h>
#include <openssl/hmac.h>

volatile unsigned char sha256_sink = 0; // Volatile variable to prevent compiler optimizations

void workload_sha256(
    const unsigned char *buffer, size_t buffer_len,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor,  size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32]
) {
    //XOR Encrypt
    for (size_t i = 0; i < buffer_len; i++) {
        ciphertext[i] = buffer[i] ^ key_xor[i % key_xor_len];
    }

    //Compute HMAC-SHA256
    unsigned int hmac_len = 0;
    HMAC(EVP_sha256(), key_hmac, key_hmac_len, ciphertext, buffer_len, out_hmac, &hmac_len);

    //XOR Decrypt (same key)
    for (size_t i = 0; i < buffer_len; i++) {
        decrypted[i] = ciphertext[i] ^ key_xor[i % key_xor_len];
    }

    // Discard output (use the results in a way that prevents optimization and introduces barely any overhead)
    sha256_sink ^= out_hmac[0]; //We use ^= to prevent the compiler from optimizing away the HMAC computation, when using = some aggresive optimization cases might simplify or partially eliminate work because intermediate values are irrelevant.
    sha256_sink ^= decrypted[0]; //Again we use ^= to prevent the compiler from optimizing away the decryption step
    
}

// volatile sha256_sink 

// function WORKLOAD_SHA256(buffer, key_hmac, key_xor):

//     # -----------------------------
//     # 1. XOR Encrypt
//     # -----------------------------
//     ciphertext = new byte array of length buffer.length
//     for i from 0 to buffer.length - 1:
//         ciphertext[i] = buffer[i] XOR key_xor[i mod key_xor.length]

//     # -----------------------------
//     # 2. Compute HMAC-SHA256
//     # -----------------------------
//     hmac_value = HMAC_SHA256(key_hmac, ciphertext)

//     # -----------------------------
//     # 3. XOR Decrypt (same key)
//     # -----------------------------
//     decrypted = new byte array of length ciphertext.length
//     for i from 0 to ciphertext.length - 1:
//         decrypted[i] = ciphertext[i] XOR key_xor[i mod key_xor.length]

//     # -----------------------------
//     # 4. Discard output
//     # -----------------------------
//     return hmac_value   # plaintext discarded
//     sha256_sink ^= out_hmac[0]
//     sha256_sink ^= decrypted[0]