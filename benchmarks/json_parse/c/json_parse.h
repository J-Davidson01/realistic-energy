#ifndef JSON_PARSE_H
#define JSON_PARSE_H

#include <stddef.h>

extern volatile unsigned char sink;

int workload_json_parse(
    const char *input_json,
    char **output_json,
    size_t *output_len
);

int verify_json_parse_output(const char *output_json);

#endif