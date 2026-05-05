#include "json_parse.h"

#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "yyjson.h"

static char *uppercase_copy(const char *str) {
    size_t len = strlen(str);
    char *upper = (char *)malloc(len + 1);

    for (size_t i = 0; i < len; i++) {
        upper[i] = (char)toupper((unsigned char)str[i]);
    }

    upper[len] = '\0';
    return upper;
}

int workload_json_parse_yyjson(const char *input_json, char **output_json, size_t *output_len) {
    yyjson_doc *doc = yyjson_read(input_json, strlen(input_json), 0);

    yyjson_val *root = yyjson_doc_get_root(doc);
    yyjson_val *items = yyjson_obj_get(root, "items");

    yyjson_mut_doc *mut_doc = yyjson_doc_mut_copy(doc, NULL);
    yyjson_doc_free(doc);

    yyjson_mut_val *mut_root = yyjson_mut_doc_get_root(mut_doc);
    yyjson_mut_val *mut_items = yyjson_mut_obj_get(mut_root, "items");

    yyjson_mut_val *item = NULL;
    size_t idx = 0;
    size_t max = 0;

    yyjson_mut_arr_foreach(mut_items, idx, max, item) {
        yyjson_mut_val *id = yyjson_mut_obj_get(item, "id");
        yyjson_mut_val *active = yyjson_mut_obj_get(item, "active");
        yyjson_mut_val *name = yyjson_mut_obj_get(item, "name");

        int id_value = yyjson_mut_get_int(id);
        yyjson_mut_set_int(id, id_value + 1);

        bool active_value = yyjson_mut_get_bool(active);
        yyjson_mut_set_bool(active, !active_value);

        const char *name_value = yyjson_mut_get_str(name);
        char *upper = uppercase_copy(name_value);
        size_t upper_len = strlen(upper);

        yyjson_mut_val *upper_val = yyjson_mut_strcpy(mut_doc, upper);
        yyjson_mut_obj_replace(item, yyjson_mut_str(mut_doc, "name"), upper_val);

        yyjson_mut_val *name_len_val = yyjson_mut_uint(mut_doc, upper_len);
        yyjson_mut_obj_add(item, yyjson_mut_str(mut_doc, "name_length"), name_len_val);

        free(upper);
    }

    size_t serialized_len = 0;
    char *serialized = yyjson_mut_write(mut_doc, 0, &serialized_len);
    yyjson_mut_doc_free(mut_doc);

    *output_json = serialized;
    *output_len = serialized_len;

    json_parse_sink ^= (unsigned char)(*output_len & 0xFF);
    json_parse_sink ^= (unsigned char)(serialized[0] & 0xFF);

    return 1;
}
