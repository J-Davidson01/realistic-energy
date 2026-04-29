package main

import (
	"bytes"
	"encoding/json"
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
	defaultChunkItems                 = 1024
	pipelineBufferGrowthFactor        = 2
	fileCopyWriteAmplification        = 8
)

type rawItemsRoot struct {
	Items []json.RawMessage `json:"items"`
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

func buildJSONChunks(inputJSON []byte, chunkItems int) ([]goworkloads.PipelineChunk, int, error) {
	if chunkItems <= 0 {
		chunkItems = 1
	}

	var root rawItemsRoot
	if err := json.Unmarshal(inputJSON, &root); err != nil {
		return nil, 0, err
	}

	chunkCount := 0
	if len(root.Items) > 0 {
		chunkCount = (len(root.Items) + chunkItems - 1) / chunkItems
	}

	chunks := make([]goworkloads.PipelineChunk, 0, chunkCount)
	maxChunkInputLen := 0

	for start := 0; start < len(root.Items); start += chunkItems {
		end := start + chunkItems
		if end > len(root.Items) {
			end = len(root.Items)
		}

		chunkBytes, err := json.Marshal(rawItemsRoot{Items: root.Items[start:end]})
		if err != nil {
			return nil, 0, err
		}

		if len(chunkBytes) > maxChunkInputLen {
			maxChunkInputLen = len(chunkBytes)
		}

		chunks = append(chunks, goworkloads.PipelineChunk{
			JSON:    chunkBytes,
			JSONLen: len(chunkBytes),
		})
	}

	return chunks, maxChunkInputLen, nil
}

func fileEqualsStreamedChunks(path string, chunks []goworkloads.PipelineChunk) bool {
	fileBytes, err := os.ReadFile(path)
	if err != nil {
		return false
	}

	offset := 0

	for _, chunk := range chunks {
		var verifyJSON []byte
		var verifyLen int

		goworkloads.JSONParse(chunk.JSON, &verifyJSON, &verifyLen)

		repeatedLen := verifyLen * fileCopyWriteAmplification
		if offset+repeatedLen > len(fileBytes) {
			return false
		}

		for rep := 0; rep < fileCopyWriteAmplification; rep++ {
			if !bytes.Equal(fileBytes[offset:offset+verifyLen], verifyJSON) {
				return false
			}
			offset += verifyLen
		}
	}

	return offset == len(fileBytes)
}

func boolToInt(v bool) int {
	if v {
		return 1
	}
	return 0
}

func main() {
	dataset := flag.String("dataset", "", "pipeline dataset selector directory")
	jsonDataset := flag.String("json-dataset", defaultJSONDatasetDir, "json_parse dataset directory")
	sha256Dataset := flag.String("sha256-dataset", defaultSHA256DatasetDir, "sha256 dataset directory")
	outputDirFlag := flag.String("output-dir", defaultOutputDir, "output directory")
	iterations := flag.Uint64("iterations", defaultIterations, "number of iterations")
	chunkItems := flag.Int("chunk-items", defaultChunkItems, "number of JSON items per chunk")
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

	chunks, maxChunkInputLen, err := buildJSONChunks(inputJSON, *chunkItems)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to build JSON chunks")
		os.Exit(1)
	}

	pipelineBufferLen := maxChunkInputLen*pipelineBufferGrowthFactor + 64
	ciphertext := make([]byte, pipelineBufferLen)
	decrypted := make([]byte, pipelineBufferLen)
	outHmac := make([]byte, 32)

	if *verify {
		dstFile, err := os.Create(outputPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "Failed to open destination file")
			os.Exit(1)
		}

		goworkloads.WorkloadPipelineE2EStream(
			chunks,
			keyHMAC,
			keyXOR,
			ciphertext,
			decrypted,
			outHmac,
			dstFile,
		)
		_ = dstFile.Close()

		verification := fileEqualsStreamedChunks(outputPath, chunks)

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

		goworkloads.WorkloadPipelineE2EStream(
			chunks,
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
