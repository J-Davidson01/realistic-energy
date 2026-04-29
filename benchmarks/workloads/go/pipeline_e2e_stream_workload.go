package goworkloads

import "os"

type PipelineChunk struct {
	JSON    []byte
	JSONLen int
}

var pipelineE2EStreamSink byte

const (
	pipelineStreamWriteAmplification uint64 = 8
	pipelineStreamSyncInterval       uint64 = 64 * 1024 * 1024
)

func WorkloadPipelineE2EStream(
	chunks []PipelineChunk,
	keyHMAC []byte,
	keyXOR []byte,
	ciphertext []byte,
	decrypted []byte,
	outHmac []byte,
	dstFile *os.File,
) uint64 {
	var bytesSinceSync uint64

	for _, chunk := range chunks {
		var transformedJSON []byte
		var transformedLen int

		JSONParse(chunk.JSON, &transformedJSON, &transformedLen)

		SHA256Workload(
			transformedJSON,
			keyHMAC,
			keyXOR,
			ciphertext[:transformedLen],
			decrypted[:transformedLen],
			outHmac,
		)

		for rep := uint64(0); rep < pipelineStreamWriteAmplification; rep++ {
			writeAll(dstFile, decrypted[:transformedLen])
			bytesSinceSync += uint64(transformedLen)

			if bytesSinceSync >= pipelineStreamSyncInterval {
				_ = dstFile.Sync()
				bytesSinceSync = 0
			}
		}

		pipelineE2EStreamSink ^= byte(transformedLen & 0xFF)
		pipelineE2EStreamSink ^= decrypted[0]
		pipelineE2EStreamSink ^= outHmac[0]
	}

	_ = dstFile.Sync()

	return 1
}
