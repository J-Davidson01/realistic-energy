module SHA256Workload

using SHA

const sink = Ref{UInt8}(0)

function workload_sha256!(buffer::Vector{UInt8}, key_hmac::Vector{UInt8}, 
    key_xor::Vector{UInt8}, ciphertext::Vector{UInt8},
    decrypted::Vector{UInt8}, out_hmac::Vector{UInt8})
    
    # 1. XOR Encrypt
    n = length(buffer)
    kx = length(key_xor)

    @inbounds for i in 1:n    #we use inbounds to avoid bounds checking for performance, to match C's implementation
        ciphertext[i] = buffer[i] ⊻ key_xor[((i - 1) % kx) + 1]
    end

    # 2. Compute HMAC-SHA256
    h = hmac_sha256(key_hmac, ciphertext)

    @inbounds for i in 1:32
        out_hmac[i] = h[i]
    end

    # 3. XOR Decrypt
    @inbounds for i in 1:n
        decrypted[i] = ciphertext[i] ⊻ key_xor[((i - 1) % kx) + 1]
    end

    # Prevent compiler optimization
    sink[] ⊻= out_hmac[1]
    sink[] ⊻= decrypted[1]    
    
    return nothing
end

end # module




# // volatile sink 

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
# //     sink ^= out_hmac[0]
# //     sink ^= decrypted[0]