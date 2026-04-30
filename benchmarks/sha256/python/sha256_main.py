#!/usr/bin/env python3
import argparse
from pathlib import Path
import hmac
import hashlib
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.workloads.python.sha256_workload import workload_sha256

def read_file(file_path: Path) -> bytes:
    return file_path.read_bytes()

def verify(buffer: bytes, key_hmac: bytes, key_xor:bytes, ciphertext: bytearray, decrypted: bytearray, out_hmac: bytearray) -> bool:
    expected_ciphertext = bytearray(len(buffer))
    key_xor_len = len(key_xor)

    for i in range(len(buffer)):
        expected_ciphertext[i] = buffer[i] ^ key_xor[i % key_xor_len]

    expected_hmac = hmac.new(key_hmac, expected_ciphertext, hashlib.sha256).digest()

    if out_hmac != expected_hmac:
        print("HMAC verification failed!")
        return False

    expected_plain = bytearray(len(buffer))
    for i in range(len(buffer)):
        expected_plain[i] = ciphertext[i] ^ key_xor[i % key_xor_len]

    if decrypted != expected_plain:
        print("Decryption verification failed!")
        return False
    
    print("Verification successful!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../../../datasets/sha256/1048576")
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    
    buffer = read_file(dataset_dir / "buffer.bin")
    key_hmac = read_file(dataset_dir / "key_hmac.bin")
    key_xor = read_file(dataset_dir / "key_xor.bin")

    ciphertext = bytearray(len(buffer))
    decrypted = bytearray(len(buffer))
    out_hmac = bytearray(32)  # SHA-256 produces a 32-byte hash

    if args.verify:
        workload_sha256(buffer, key_hmac, key_xor, ciphertext, decrypted, out_hmac)

        if verify(buffer, key_hmac, key_xor, ciphertext, decrypted, out_hmac):
            print("HMAC: ", out_hmac.hex())
            print("\nVerification 1")
        else:
            print("Verification 0")
            exit(1)


    for _ in range(args.iterations):
        workload_sha256(buffer, key_hmac, key_xor, ciphertext, decrypted, out_hmac)

if __name__ == "__main__":
    main()