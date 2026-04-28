package goworkloads

import (
	"crypto/hmac"
	"crypto/sha256"
)

var sha256_sink byte // Volatile variable to prevent compiler optimizations

func SHA256Workload(buffer []byte, keyHMAC []byte, keyXOR []byte, ciphertext []byte, decrypted []byte, outHmac []byte) {

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

	sha256_sink ^= outHmac[0]   //We use ^= to prevent the compiler from optimizing away the HMAC computation, when using = some aggresive optimization cases might simplify or partially eliminate work because intermediate values are irrelevant.
	sha256_sink ^= decrypted[0] //Again we use ^= to prevent the compiler from optimizing away the decryption step
}
