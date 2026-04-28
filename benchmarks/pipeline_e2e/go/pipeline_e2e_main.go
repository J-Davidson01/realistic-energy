package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	goworkloads "realistic-energy/benchmarks/workloads/go"
)

const (
	defaultJSONDatasetDir             = "../../../datasets/json_parse/1048576"
	defaultSHA256DatasetDir           = "../../../datasets/sha256/1048576"
	defaultOutputDir                  = "../../../datasets/file_copy/1048576"
	defaultIterations          uint64 = 1000000
	pipelineBufferGrowthFactor        = 2
	fileCopyWriteAmplification        = 8
)

func fileEqualsAmplifiedBuffer(path string, buffer []byte, amplification int) bool {
	fileBytes, err := os.ReadFile(path)
	if err != nil {
		return false
	}

	expectedLen := len(buffer) * amplification
	if len(fileBytes) != expectedLen {
		return false
	}

	for i := 0; i < amplification; i++ {
		start := i * len(buffer)
		end := start + len(buffer)
		if !bytes.Equal(fileBytes[start:end], buffer) {
			return false
		}
	}

	return true
}

func deriveDatasetDirsFromSelector(datasetSelector string) (string, string, string) {
	sizeName := filepath.Base(datasetSelector)
	pipelineRoot := filepath.Dir(datasetSelector)
	datasetsRoot := filepath.Dir(pipelineRoot)

	jsonDatasetDir := filepath.Join(datasetsRoot, "json_parse", sizeName)
	sha256DatasetDir := filepath.Join(datasetsRoot, "sha256", sizeName)
	outputDir := filepath.Join(datasetsRoot, "file_copy", sizeName)

	return jsonDatasetDir, sha256DatasetDir, outputDir
}

func main() {
	dataset := flag.String("dataset", "", "pipeline dataset selector directory")
	jsonDataset := flag.String("json-dataset", defaultJSONDatasetDir, "json_parse dataset directory")
	sha256Dataset := flag.String("sha256-dataset", defaultSHA256DatasetDir, "sha256 dataset directory")
	outputDirFlag := flag.String("output-dir", defaultOutputDir, "output directory")
	iterations := flag.Uint64("iterations", defaultIterations, "number of iterations")
	verify := flag.Bool("verify", false, "run one iteration and verify output")
	flag.Parse()

	var jsonDatasetDir string
	var sha256DatasetDir string
	var outputDir string

	if *dataset != "" {
		jsonDatasetDir, sha256DatasetDir, outputDir = deriveDatasetDirsFromSelector(*dataset)
	} else {
		jsonDatasetDir = *jsonDataset
		sha256DatasetDir = *sha256Dataset
		outputDir = *outputDirFlag
	}

	inputPath := filepath.Join(jsonDatasetDir, "input.json")
	keyHMACPath := filepath.Join(sha256DatasetDir, "key_hmac.bin")
	keyXORPath := filepath.Join(sha256DatasetDir, "key_xor.bin")
	outputPath := filepath.Join(outputDir, "output.bin")

	inputJSON, err := os.ReadFile(inputPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to open input JSON")
		os.Exit(1)
	}

	keyHMAC, err := os.ReadFile(keyHMACPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to open HMAC key")
		os.Exit(1)
	}

	keyXOR, err := os.ReadFile(keyXORPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to open XOR key")
		os.Exit(1)
	}

	pipelineBufferLen := len(inputJSON)*pipelineBufferGrowthFactor + 64
	ciphertext := make([]byte, pipelineBufferLen)
	decrypted := make([]byte, pipelineBufferLen)
	outHmac := make([]byte, 32)

	if *verify {
		dstFile, err := os.Create(outputPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "Failed to open destination file")
			os.Exit(1)
		}

		goworkloads.WorkloadPipelineE2E(
			inputJSON,
			keyHMAC,
			keyXOR,
			ciphertext,
			decrypted,
			outHmac,
			dstFile,
		)
		_ = dstFile.Close()

		var verifyJSON []byte
		var verifyLen int
		goworkloads.JSONParse(inputJSON, &verifyJSON, &verifyLen)

		cryptoOK := verifyLen == 0 || bytes.Equal(verifyJSON, decrypted[:verifyLen])
		fileOK := fileEqualsAmplifiedBuffer(
			outputPath,
			decrypted[:verifyLen],
			fileCopyWriteAmplification,
		)

		verification := cryptoOK && fileOK
		fmt.Printf("verify= %d\n", boolToInt(verification))
		if !verification {
			os.Exit(1)
		}
		return
	}

	for i := uint64(0); i < *iterations; i++ {
		dstFile, err := os.Create(outputPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "Failed to open destination file")
			os.Exit(1)
		}

		goworkloads.WorkloadPipelineE2E(
			inputJSON,
			keyHMAC,
			keyXOR,
			ciphertext,
			decrypted,
			outHmac,
			dstFile,
		)

		_ = dstFile.Close()
	}
}

func boolToInt(v bool) int {
	if v {
		return 1
	}
	return 0
}
