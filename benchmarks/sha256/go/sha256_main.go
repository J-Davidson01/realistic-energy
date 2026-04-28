package main

import (
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"realistic-energy/benchmarks/goworkloads"
)

func read(path string) []byte {
	b, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	return b
}

func main() {
	dataset := flag.String("dataset", "../../../datasets/sha256/1048576", "Path to the dataset directory")
	iterations := flag.Int("iterations", 1000000, "Number of iterations to run the workload")
	verify := flag.Bool("verify", false, "Whether to verify the output of the workload")
	flag.Parse()

	buffer := read(*dataset + "/buffer.bin")
	keyHMAC := read(*dataset + "/key_hmac.bin")
	keyXOR := read(*dataset + "/key_xor.bin")

	ciphertext := make([]byte, len(buffer))
	decrypted := make([]byte, len(buffer))
	outHmac := make([]byte, 32) // SHA256 produces a 32-byte hash

	if *verify {
		goworkloads.SHA256Workload(buffer, keyHMAC, keyXOR, ciphertext, decrypted, outHmac)

		ok := true
		for i := 0; i < len(buffer); i++ {
			if decrypted[i] != buffer[i] {
				ok = false
				break
			}
		}

		fmt.Printf("HMAC: %x\n", hex.EncodeToString(outHmac))
		if ok {
			fmt.Println("verify= 1")
		} else {
			fmt.Println("verify= 0")
		}
		return
	}

	for i := 0; i < *iterations; i++ {
		goworkloads.SHA256Workload(buffer, keyHMAC, keyXOR, ciphertext, decrypted, outHmac)
	}
}
