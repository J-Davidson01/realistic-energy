#!/usr/bin/env python3
import hashlib
import hmac


sink = 0

def workload_sha256(buffer: bytes, key_hmac: bytes, 
                    key_xor: bytes, ciphertext: bytearray, 
                    decrypted: bytearray, out_hmac: bytearray) -> None:
    global sink

    key_xor_len = len(key_xor)

    for i in range(len(buffer)):  #we can use len(buffer) as python objects store their length
        ciphertext[i] = buffer[i] ^ key_xor[i % key_xor_len]

    hmac_value = hmac.new(key_hmac, ciphertext, hashlib.sha256).digest()

    out_hmac[:] = hmac_value

    for i in range(len(ciphertext)):
        decrypted[i] = ciphertext[i] ^ key_xor[i % key_xor_len]

    sink ^= out_hmac[0]  # Although Python does not optimize code away, we still implement the sink to make all languages idiomatic.
    sink ^= decrypted[0]


# // function WORKLOAD_SHA256(buffer, key_hmac, key_xor):

# //     # -----------------------------
# //     # 1. XOR Encrypt
# //     # -----------------------------
# //     ciphertext = new byte array of length buffer.length
# //     for i from 0 to buffer.length - 1:
# //         ciphertext[i] = buffer[i] XOR key_xor[i mod key_xor.length]

# //     # -----------------------------
# //     # 2. Compute HMAC-SHA256
# //     # -----------------------------
# //     hmac_value = HMAC_SHA256(key_hmac, ciphertext)

# //     # -----------------------------
# //     # 3. XOR Decrypt (same key)
# //     # -----------------------------
# //     decrypted = new byte array of length ciphertext.length
# //     for i from 0 to ciphertext.length - 1:
# //         decrypted[i] = ciphertext[i] XOR key_xor[i mod key_xor.length]

# //     # -----------------------------
# //     # 4. Discard output
# //     # -----------------------------
# //     return hmac_value   # plaintext discarded