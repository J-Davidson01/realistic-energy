




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