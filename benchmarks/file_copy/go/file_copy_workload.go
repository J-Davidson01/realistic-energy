package main

import "os"

var sink byte

const (
	fileCopyWriteAmplification uint64 = 8
	fileCopySyncInterval       uint64 = 64 * 1024 * 1024
)

func writeAll(dstFile *os.File, buffer []byte) {
	written := 0
	for written < len(buffer) {
		n, _ := dstFile.Write(buffer[written:])
		written += n
	}
}

func workload_file_copy(dstFile *os.File, buffer []byte) uint64 {
	var bytesSinceSync uint64
	bufferLen := uint64(len(buffer))

	for i := uint64(0); i < fileCopyWriteAmplification; i++ {
		writeAll(dstFile, buffer)
		bytesSinceSync += bufferLen

		if bytesSinceSync >= fileCopySyncInterval {
			_ = dstFile.Sync()
			bytesSinceSync = 0
		}
	}

	_ = dstFile.Sync()

	sink ^= byte(bufferLen & 0xFF)
	sink ^= buffer[0]

	return 1
}
