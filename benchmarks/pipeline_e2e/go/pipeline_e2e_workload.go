package main

import (
	"os"
	"realistic-energy/benchmarks/goworkloads"
)

var pipelineE2ESink byte

func workload_pipeline_e2e(
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

	goworkloads.JSONParse(inputJSON, &transformedJSON, &transformedLen)

	goworkloads.SHA256Workload(
		transformedJSON,
		keyHMAC,
		keyXOR,
		ciphertext[:transformedLen],
		decrypted[:transformedLen],
		outHmac,
	)

	goworkloads.FileCopy(dstFile, decrypted[:transformedLen])

	pipelineE2ESink ^= byte(transformedLen & 0xFF)
	pipelineE2ESink ^= decrypted[0]
	pipelineE2ESink ^= outHmac[0]

	return 1
}
