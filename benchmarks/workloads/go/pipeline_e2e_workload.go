package goworkloads

import (
	"os"
)

var pipelineE2ESink byte

func WorkloadPipelineE2E(
	inputJSON []byte,
	keyHMAC []byte,
	keyXOR []byte,
	ciphertext []byte,
	decrypted []byte,
	outHmac []byte,
	dstFile *os.File,
) uint64 {
	var transformedJSON []byte
	var transformedLen int

	JSONParse(inputJSON, &transformedJSON, &transformedLen)

	SHA256Workload(
		transformedJSON,
		keyHMAC,
		keyXOR,
		ciphertext[:transformedLen],
		decrypted[:transformedLen],
		outHmac,
	)

	FileCopy(dstFile, decrypted[:transformedLen])

	pipelineE2ESink ^= byte(transformedLen & 0xFF)
	pipelineE2ESink ^= decrypted[0]
	pipelineE2ESink ^= outHmac[0]

	return 1
}
