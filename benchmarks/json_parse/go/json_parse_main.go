package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
)

func verifyJSONParseOutput(outputJSON []byte) bool {
	var root Root
	if err := json.Unmarshal(outputJSON, &root); err != nil {
		return false
	}

	for _, item := range root.Items {
		if item.NameLength != len(item.Name) {
			return false
		}
		if item.Name != strings.ToUpper(item.Name) {
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

	inputJSON, err := os.ReadFile(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load input JSON: %v\n", err)
		os.Exit(1)
	}

	if *verify {
		outputJSON, err := workloadJSONParse(inputJSON)
		verified := err == nil && verifyJSONParseOutput(outputJSON)

		fmt.Printf("verify= %d\n", boolToInt(verified))
		if verified {
			os.Exit(0)
		}
		os.Exit(1)
	}

	for i := uint64(0); i < *iterations; i++ {
		_, err := workloadJSONParse(inputJSON)
		if err != nil {
			fmt.Fprintf(os.Stderr, "workloadJSONParse failed at iteration %d: %v\n", i, err)
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
