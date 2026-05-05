#ifndef JSON_PARSE_H
#define JSON_PARSE_H

#include <stddef.h>

extern volatile unsigned char json_parse_sink;

int workload_json_parse(
    const char *input_json,
    char **output_json,
    size_t *output_len
);

int workload_json_parse_yyjson(
    const char *input_json,
    char **output_json,
    size_t *output_len
);

#endif