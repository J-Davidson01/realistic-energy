#include "pipeline_e2e.h"

#include "json_parse.h"
#include "sha256.h"
#include "file_copy.h"

#include <stdlib.h>

volatile unsigned char pipeline_e2e_sink = 0;

size_t workload_pipeline_e2e(
    const char *input_json,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor, size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32],
    int dst_fd
) {
    char *transformed_json = NULL;
    size_t transformed_len = 0;

    workload_json_parse(input_json, &transformed_json, &transformed_len);

    workload_sha256(
        (const unsigned char *)transformed_json,
        transformed_len,
        key_hmac,
        key_hmac_len,
        key_xor,
        key_xor_len,
        ciphertext,
        decrypted,
        out_hmac
    );

    workload_file_copy(dst_fd, decrypted, transformed_len);

    pipeline_e2e_sink ^= (unsigned char)(transformed_len & 0xFF);
    pipeline_e2e_sink ^= decrypted[0];
    pipeline_e2e_sink ^= out_hmac[0];

    free(transformed_json);

    return 1;
}
