package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
)

var sink byte // Volatile variable to prevent compiler optimizations

func workload_sha256(buffer []byte, keyHMAC []byte, keyXOR []byte, ciphertext []byte, decrypted []byte, outHmac []byte) {

	// XOR Encrypt
	//We can use len(buffer) instead of providing a buffer length, since in go the length of the slice is known and provided in []byte, therefore essentially free.
	//[]byte looks like struct {pointer, length, capacity} and the length is used to determine how many bytes to read from the pointer, so we can just use len(buffer) to get the length of the buffer.
	for i := 0; i < len(buffer); i++ {
		ciphertext[i] = buffer[i] ^ keyXOR[i%len(keyXOR)]
	}

	// HMAC-SHA256(ciphertext) into outHmac without allocation
	mac := hmac.New(sha256.New, keyHMAC)
	mac.Write(ciphertext)
	mac.Sum(outHmac[:0]) // writes 32 bytes into outHmac backing array

	// XOR Decrypt (same key)
	for i := 0; i < len(ciphertext); i++ {
		decrypted[i] = ciphertext[i] ^ keyXOR[i%len(keyXOR)]
	}

	sink ^= outHmac[0]   //We use ^= to prevent the compiler from optimizing away the HMAC computation, when using = some aggresive optimization cases might simplify or partially eliminate work because intermediate values are irrelevant.
	sink ^= decrypted[0] //Again we use ^= to prevent the compiler from optimizing away the decryption step
}

func read(path string) []byte {
	b, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	return b
}

func main() {
	dataset := flag.String("dataset", "../../../datasets/sha256/4096", "Path to the dataset directory")
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
		workload_sha256(buffer, keyHMAC, keyXOR, ciphertext, decrypted, outHmac)

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
		workload_sha256(buffer, keyHMAC, keyXOR, ciphertext, decrypted, outHmac)
	}
}

// function WORKLOAD_SHA256(buffer, key_hmac, key_xor):

//     # -----------------------------
//     # 1. XOR Encrypt
//     # -----------------------------
//     ciphertext = new byte array of length buffer.length
//     for i from 0 to buffer.length - 1:
//         ciphertext[i] = buffer[i] XOR key_xor[i mod key_xor.length]

//     # -----------------------------
//     # 2. Compute HMAC-SHA256
//     # -----------------------------
//     hmac_value = HMAC_SHA256(key_hmac, ciphertext)

//     # -----------------------------
//     # 3. XOR Decrypt (same key)
//     # -----------------------------
//     decrypted = new byte array of length ciphertext.length
//     for i from 0 to ciphertext.length - 1:
//         decrypted[i] = ciphertext[i] XOR key_xor[i mod key_xor.length]

//     # -----------------------------
//     # 4. Return output
//     # -----------------------------
//     return hmac_value
