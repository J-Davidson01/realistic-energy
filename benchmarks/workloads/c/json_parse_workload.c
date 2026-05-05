#include "json_parse.h"

#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "cJSON.h"

volatile unsigned char json_parse_sink = 0; // Volatile variable to prevent compiler optimizations

static void uppercase_inplace(char *str) {
    if(!str) return;
    while (*str) {
        *str = (char)toupper((unsigned char)*str);
        str++;
    }
}

int workload_json_parse(const char *input_json, char **output_json, size_t *output_len) {
    cJSON *root = cJSON_Parse(input_json);
    
    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "items");
    cJSON *item = NULL;

    cJSON_ArrayForEach(item, items) {
        cJSON *id = cJSON_GetObjectItemCaseSensitive(item, "id");
        id->valueint += 1; 

        cJSON *active = cJSON_GetObjectItemCaseSensitive(item, "active");
        active->valueint = !active->valueint; 

        cJSON *name = cJSON_GetObjectItemCaseSensitive(item, "name");
        char *upper = strdup(name->valuestring);
        uppercase_inplace(upper);
        cJSON_ReplaceItemInObjectCaseSensitive(item, "name", cJSON_CreateString(upper));

        cJSON_AddNumberToObject(item, "name_length", (double)strlen(upper));

        free(upper);
    }

    char *serialized = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);

    *output_json = serialized;
    *output_len = strlen(serialized);

    json_parse_sink ^= (unsigned char)(*output_len & 0xFF);
    json_parse_sink ^= (unsigned char)(serialized[0] & 0xFF);

    return 1;
}


// function WORKLOAD_JSON_PARSE(input_json_text):

//     # -----------------------------
//     # 1. Parse JSON text
//     #    (allocates parsed object tree)
//     # -----------------------------
//     parsed_root = JSON_PARSE(input_json_text)

//     # -----------------------------
//     # 2. Transform parsed objects
//     #    (may allocate new/updated strings or fields)
//     # -----------------------------
//     for each object in parsed_root["items"]:
//         object["id"] = object["id"] + 1
//         object["active"] = NOT object["active"]
//         object["name"] = TO_UPPERCASE(object["name"])
//         object["name_length"] = LENGTH(object["name"])

//     # -----------------------------
//     # 3. Serialize transformed JSON
//     #    (allocates output JSON buffer)
//     # -----------------------------
//     output_json_text = JSON_SERIALIZE(parsed_root)

//     # -----------------------------
//     # 4. Prevent optimization
//     # -----------------------------
//     json_parse_sink = json_parse_sink XOR LENGTH(output_json_text)
//     if LENGTH(output_json_text) > 0:
//         json_parse_sink = json_parse_sink XOR BYTE_AT(output_json_text, 0)

//     # -----------------------------
//     # 5. Free temporary parsed/serialized data
//     # -----------------------------
//     FREE(parsed_root)
//     return output_json_text