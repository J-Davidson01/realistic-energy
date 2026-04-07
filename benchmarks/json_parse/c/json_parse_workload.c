#include "json_parse.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include <cjson/cJSON.h>

volatile unsigned char sink = 0; // Volatile variable to prevent compiler optimizations

static void uppercase_inplace(char *str) {
    if(!str) return;
    while (*str) {
        *str = (char)toupper((unsigned char)*str);
        str++;
    }
}

int workload_json_parse(const char *input_json, char **output_json, size_t *output_len) {
    *output_json = NULL;
    *output_len = 0;

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

    sink ^= (unsigned char)(*output_len & 0xFF);
    sink ^= (unsigned char)(serialized[0] & 0xFF);

    return 1;
}


// Verification function to check if the output JSON is correct, 
// called from _main when --verify flag is set
int verify_json_parse_output(const char *output_json) {
    if (!output_json) {
        return 0;
    }

    cJSON *root = cJSON_Parse(output_json);
    if (!root) {
        return 0;
    }

    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "items");
    if (!cJSON_IsArray(items)) {
        cJSON_Delete(root);
        return 0;
    }

    cJSON *item = NULL;
    cJSON_ArrayForEach(item, items) {
        if (!cJSON_IsObject(item)) {
            cJSON_Delete(root);
            return 0;
        }

        cJSON *id = cJSON_GetObjectItemCaseSensitive(item, "id");
        cJSON *active = cJSON_GetObjectItemCaseSensitive(item, "active");
        cJSON *name = cJSON_GetObjectItemCaseSensitive(item, "name");
        cJSON *name_length = cJSON_GetObjectItemCaseSensitive(item, "name_length");

        if (!cJSON_IsNumber(id) ||
            !cJSON_IsBool(active) ||
            !cJSON_IsString(name) || !name->valuestring ||
            !cJSON_IsNumber(name_length)) {
            cJSON_Delete(root);
            return 0;
        }

        size_t actual_len = strlen(name->valuestring);
        if ((size_t)name_length->valuedouble != actual_len) {
            cJSON_Delete(root);
            return 0;
        }

        for (size_t i = 0; i < actual_len; i++) {
            unsigned char ch = (unsigned char)name->valuestring[i];
            if (isalpha(ch) && name->valuestring[i] != (char)toupper(ch)) {
                cJSON_Delete(root);
                return 0;
            }
        }
    }

    cJSON_Delete(root);
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
//     sink = sink XOR LENGTH(output_json_text)
//     if LENGTH(output_json_text) > 0:
//         sink = sink XOR BYTE_AT(output_json_text, 0)

//     # -----------------------------
//     # 5. Free temporary parsed/serialized data
//     # -----------------------------
//     FREE(parsed_root)
//     return output_json_text