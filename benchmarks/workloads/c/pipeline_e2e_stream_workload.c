#include "pipeline_e2e_stream.h"

#include "json_parse.h"
#include "sha256.h"
#include "file_copy.h"

#include <stdlib.h>
#include <unistd.h>

#ifndef FILE_COPY_WRITE_AMPLIFICATION
#define FILE_COPY_WRITE_AMPLIFICATION 8
#endif

#ifndef FILE_COPY_SYNC_INTERVAL
#define FILE_COPY_SYNC_INTERVAL (64ULL * 1024ULL * 1024ULL)
#endif

volatile unsigned char pipeline_e2e_stream_sink = 0;

size_t workload_pipeline_e2e_stream(
    const pipeline_chunk_t *chunks,
    size_t chunk_count,
    const unsigned char *key_hmac, size_t key_hmac_len,
    const unsigned char *key_xor, size_t key_xor_len,
    unsigned char *ciphertext,
    unsigned char *decrypted,
    unsigned char out_hmac[32],
    int dst_fd
) {
    size_t bytes_since_sync = 0;

    for (size_t i = 0; i < chunk_count; i++) {
        char *transformed_json = NULL;
        size_t transformed_len = 0;

        workload_json_parse(chunks[i].json, &transformed_json, &transformed_len);

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

        for (int rep = 0; rep < FILE_COPY_WRITE_AMPLIFICATION; rep++) {
            write_all(dst_fd, decrypted, transformed_len);
            bytes_since_sync += transformed_len;

            if (bytes_since_sync >= FILE_COPY_SYNC_INTERVAL) {
                fdatasync(dst_fd);
                bytes_since_sync = 0;
            }
        }

        pipeline_e2e_stream_sink ^= (unsigned char)(transformed_len & 0xFF);
        pipeline_e2e_stream_sink ^= decrypted[0];
        pipeline_e2e_stream_sink ^= out_hmac[0];

        free(transformed_json);
    }

    fdatasync(dst_fd);

    return 1;
}
