package main

import (
	"encoding/json"
	"strings"
)

var sink byte

func workload_json_parse(input_json []byte, output_json *[]byte, output_len *int) int {
	var root map[string]any

	json.Unmarshal(input_json, &root)

	items := root["items"].([]any)

	for _, item_raw := range items {
		item := item_raw.(map[string]any)

		item["id"] = item["id"].(float64) + 1
		item["active"] = !item["active"].(bool)

		name := item["name"].(string)
		upper := strings.ToUpper(name)
		item["name"] = upper
		item["name_length"] = len(upper)
	}

	serialized, _ := json.Marshal(root)

	*output_json = serialized
	*output_len = len(serialized)

	sink ^= byte(*output_len & 0xFF)
	sink ^= serialized[0]

	return 1
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
