package goworkloads

import (
	"encoding/json"
	"strings"
)

var json_parse_sink byte

func JSONParse(input_json []byte, output_json *[]byte, output_len *int) int {
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
		item["name_length"] = len([]byte(upper))
	}

	serialized, _ := json.Marshal(root)

	*output_json = serialized
	*output_len = len(serialized)

	json_parse_sink ^= byte(*output_len & 0xFF)
	json_parse_sink ^= serialized[0]

	return 1
}
