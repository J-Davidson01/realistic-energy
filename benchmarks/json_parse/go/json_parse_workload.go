package main

import (
	"encoding/json"
	"strings"
)

var sink uint64

type Item struct {
	ID         int    `json:"id"`
	Active     bool   `json:"active"`
	Name       string `json:"name"`
	NameLength int    `json:"name_length"`
}

type Root struct {
	Items []Item `json:"items"`
}

func workloadJSONParse(input []byte) ([]byte, error) {
	var root Root
	if err := json.Unmarshal(input, &root); err != nil {
		return nil, err
	}

	for I := range root.Items {
		root.Items[I].ID += 1
		root.Items[I].Active = !root.Items[I].Active
		root.Items[I].Name = strings.ToUpper(root.Items[I].Name)
		root.Items[I].NameLength = len(root.Items[I].Name)
	}

	outputJSON, err := json.Marshal(root)
	if err != nil {
		return nil, err
	}

	sink ^= uint64(len(outputJSON))
	if len(outputJSON) > 0 {
		sink ^= uint64(outputJSON[0])
	}

	return outputJSON, nil
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
