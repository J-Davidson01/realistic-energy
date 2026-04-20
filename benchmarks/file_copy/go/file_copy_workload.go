package main

import "os"

var sink byte

const (
	fileCopyWriteAmplification uint64 = 8
	fileCopySyncInterval       uint64 = 64 * 1024 * 1024
)

func writeAll(f *os.File, buf []byte) {
	written := 0
	for written < len(buf) {
		n, _ := f.Write(buf[written:])
		written += n
	}
}

func workloadFileCopy(srcPath string, dstPath string, buffer []byte) uint64 {
	src, _ := os.Open(srcPath)
	dst, _ := os.Create(dstPath)

	var totalBytesRead uint64
	var totalBytesWritten uint64
	var bytesSinceSync uint64

	for {
		bytesRead, _ := src.Read(buffer)
		if bytesRead == 0 {
			break
		}

		chunk := buffer[:bytesRead]
		n := uint64(bytesRead)
		totalBytesRead += n

		for i := uint64(0); i < fileCopyWriteAmplification; i++ {
			writeAll(dst, chunk)
			totalBytesWritten += n
			bytesSinceSync += n

			if bytesSinceSync >= fileCopySyncInterval {
				_ = dst.Sync()
				bytesSinceSync = 0
			}
		}
	}

	_ = dst.Sync()

	sink ^= byte(totalBytesRead & 0xFF)
	sink ^= byte(totalBytesWritten & 0xFF)
	if len(buffer) > 0 {
		sink ^= buffer[0]
	}

	_ = src.Close()
	_ = dst.Close()

	return totalBytesWritten
}
