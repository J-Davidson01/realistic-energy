package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	goworkloads "realistic-energy/benchmarks/workloads/go"
	"strings"
)

func verifyJSONParseOutput(outputJSON []byte) bool {
	var root map[string]any
	json.Unmarshal(outputJSON, &root)

	items := root["items"].([]any)
	for _, itemRaw := range items {
		item := itemRaw.(map[string]any)

		name := item["name"].(string)
		nameLength := int(item["name_length"].(float64))

		if nameLength != len(name) {
			return false
		}
		if name != strings.ToUpper(name) {
			return false
		}
	}

	return true
}

func main() {
	dataset := flag.String("dataset", "../../../datasets/json_parse/1048576", "dataset directory")
	iterations := flag.Uint64("iterations", 1000000, "number of iterations")
	verify := flag.Bool("verify", false, "run one iteration and verify output")
	flag.Parse()

	inputPath := *dataset + "/input.json"
	inputJSON, _ := os.ReadFile(inputPath)

	if *verify {
		var outputJSON []byte
		var outputLen int

		goworkloads.JSONParse(inputJSON, &outputJSON, &outputLen)
		verified := verifyJSONParseOutput(outputJSON)

		fmt.Printf("verify= %d\n", boolToInt(verified))
		if verified {
			os.Exit(0)
		}
		os.Exit(1)
	}

	for i := uint64(0); i < *iterations; i++ {
		var outputJSON []byte
		var outputLen int
		goworkloads.JSONParse(inputJSON, &outputJSON, &outputLen)
	}
}

func boolToInt(v bool) int {
	if v {
		return 1
	}
	return 0
}
