package goworkloads

import "os"

var file_copy_sink byte

const (
	FileCopyWriteAmplification uint64 = 8
	fileCopySyncInterval       uint64 = 64 * 1024 * 1024
)

func writeAll(dstFile *os.File, buffer []byte) {
	written := 0
	for written < len(buffer) {
		n, _ := dstFile.Write(buffer[written:])
		written += n
	}
}

func FileCopy(dstFile *os.File, buffer []byte) uint64 {
	var bytesSinceSync uint64
	bufferLen := uint64(len(buffer))

	for i := uint64(0); i < FileCopyWriteAmplification; i++ {
		writeAll(dstFile, buffer)
		bytesSinceSync += bufferLen

		if bytesSinceSync >= fileCopySyncInterval {
			_ = dstFile.Sync()
			bytesSinceSync = 0
		}
	}

	_ = dstFile.Sync()

	file_copy_sink ^= byte(bufferLen & 0xFF)
	file_copy_sink ^= buffer[0]

	return 1
}
