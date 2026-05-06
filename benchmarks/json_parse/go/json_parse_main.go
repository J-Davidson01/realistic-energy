package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	goworkloads "realistic-energy/benchmarks/workloads/go"
	"strings"
)

type jsonParseWorkloadFunc func(inputJSON []byte, outputJSON *[]byte, outputLen *int) int

func selectJSONParseImplementation(impl string) (jsonParseWorkloadFunc, bool) {
	switch impl {
	case "encoding_json":
		return goworkloads.JSONParse, true
	case "goccy_go_json":
		return goworkloads.JSONParseGoccy, true
	default:
		return nil, false
	}
}

func verifyJSONParseOutput(outputJSON []byte) bool {
	var root map[string]any
	if err := json.Unmarshal(outputJSON, &root); err != nil {
		return false
	}

	itemsRaw, ok := root["items"].([]any)
	if !ok {
		return false
	}

	for _, itemRaw := range itemsRaw {
		item, ok := itemRaw.(map[string]any)
		if !ok {
			return false
		}

		name, ok := item["name"].(string)
		if !ok {
			return false
		}

		nameLengthFloat, ok := item["name_length"].(float64)
		if !ok {
			return false
		}

		nameLength := int(nameLengthFloat)

		if nameLength != len([]byte(name)) {
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
	jsonImpl := flag.String("json-impl", "encoding_json", "JSON implementation: encoding_json or goccy_go_json")
	flag.Parse()

	workload, ok := selectJSONParseImplementation(*jsonImpl)
	if !ok {
		fmt.Fprintf(os.Stderr, "Unknown --json-impl: %s\n", *jsonImpl)
		fmt.Fprintln(os.Stderr, "Supported values: encoding_json, goccy_go_json")
		os.Exit(1)
	}

	inputPath := *dataset + "/input.json"
	inputJSON, err := os.ReadFile(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read input JSON: %v\n", err)
		os.Exit(1)
	}

	if *verify {
		var outputJSON []byte
		var outputLen int

		ok := workload(inputJSON, &outputJSON, &outputLen)
		verified := ok == 1 && verifyJSONParseOutput(outputJSON)

		fmt.Printf("json_impl= %s\n", *jsonImpl)
		fmt.Printf("verify= %d\n", boolToInt(verified))

		if verified {
			os.Exit(0)
		}
		os.Exit(1)
	}

	for i := uint64(0); i < *iterations; i++ {
		var outputJSON []byte
		var outputLen int

		ok := workload(inputJSON, &outputJSON, &outputLen)
		if ok != 1 {
			fmt.Fprintf(os.Stderr, "JSONParse failed at iteration %d\n", i)
			os.Exit(1)
		}
	}
}

func boolToInt(v bool) int {
	if v {
		return 1
	}
	return 0
}
