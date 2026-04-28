package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	goworkloads "realistic-energy/benchmarks/workloads/go"
)

const (
	defaultDatasetDir = "../../../datasets/file_copy/1048576"
	defaultIterations = 1000000
)

func filesEqual(srcPath string, dstPath string, amplification int) bool {
	src, err := os.ReadFile(srcPath)
	if err != nil {
		return false
	}

	dst, err := os.ReadFile(dstPath)
	if err != nil {
		return false
	}

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

	inputBuffer, err := os.ReadFile(srcPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to load input buffer")
		os.Exit(1)
	}

	if *verify {
		dst, err := os.Create(dstPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "Failed to open destination file")
			os.Exit(1)
		}

		goworkloads.FileCopy(dst, inputBuffer)
		_ = dst.Close()

		verification := filesEqual(srcPath, dstPath, int(goworkloads.FileCopyWriteAmplification))

		fmt.Printf("verify= %d\n", boolToInt(verification))

		if verification {
			os.Exit(0)
		}
		os.Exit(1)
	}

	for i := uint64(0); i < *iterations; i++ {
		dst, err := os.Create(dstPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "Failed to open destination file")
			os.Exit(1)
		}

		goworkloads.FileCopy(dst, inputBuffer)
		_ = dst.Close()
	}
}
