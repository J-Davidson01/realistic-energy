package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
)

const (
	defaultDatasetDir = "../../../datasets/file_copy/1048576"
	defaultIterations = 1000000
	chunkSize         = 65536
)

func filesEqual(srcPath string, dstPath string, amplification int) bool {
	src, _ := os.ReadFile(srcPath)
	dst, _ := os.ReadFile(dstPath)

	if len(dst) != len(src)*amplification {
		return false
	}

	for i := 0; i < amplification; i++ {
		start := i * len(src)
		end := start + len(src)
		if !bytes.Equal(src, dst[start:end]) {
			return false
		}
	}

	return true
}

func boolToInt(v bool) int {
	if v {
		return 1
	}
	return 0
}

func main() {
	dataset := flag.String("dataset", defaultDatasetDir, "dataset directory")
	iterations := flag.Uint64("iterations", defaultIterations, "number of iterations")
	verify := flag.Bool("verify", false, "run one iteration and verify output")
	flag.Parse()

	srcPath := *dataset + "/input.bin"
	dstPath := *dataset + "/output.bin"

	buffer := make([]byte, chunkSize)

	if *verify {
		copiedBytes := workloadFileCopy(srcPath, dstPath, buffer)
		verification := filesEqual(srcPath, dstPath, 8)

		fmt.Printf("copied_bytes= %d\n", copiedBytes)
		fmt.Printf("verify= %d\n", boolToInt(verification))

		if verification {
			os.Exit(0)
		}
		os.Exit(1)
	}

	for i := uint64(0); i < *iterations; i++ {
		_ = workloadFileCopy(srcPath, dstPath, buffer)
	}
}
