package goworkloads

import (
	"strings"

	goccyjson "github.com/goccy/go-json"
)

func JSONParseGoccy(inputJSON []byte, outputJSON *[]byte, outputLen *int) int {
	var root map[string]any

	goccyjson.Unmarshal(inputJSON, &root)

	items := root["items"].([]any)

	for _, itemRaw := range items {
		item := itemRaw.(map[string]any)

		item["id"] = item["id"].(float64) + 1
		item["active"] = !item["active"].(bool)

		name := item["name"].(string)
		upper := strings.ToUpper(name)
		item["name"] = upper
		item["name_length"] = len([]byte(upper))
	}

	serialized, _ := goccyjson.Marshal(root)

	*outputJSON = serialized
	*outputLen = len(serialized)

	json_parse_sink ^= byte(*outputLen & 0xFF)
	json_parse_sink ^= serialized[0]

	return 1
}
