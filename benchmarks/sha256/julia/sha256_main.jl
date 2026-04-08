import Pkg
Pkg.activate(@__DIR__)
using SHA

include("sha256_workload.jl")

function parse_args(args)
    dataset = "../../../datasets/sha256/1048576"
    iterations = 100000
    verify = false

    i = 1
    while i <= length(args)
        if args[i] == "--dataset"
            dataset = args[i + 1]
            i += 2
        elseif args[i] == "--iterations"
            iterations = parse(Int, args[i + 1])
            i += 2
        elseif args[i] == "--verify"
            verify = true
            i += 1
        else
            error("Unknown argument: $(args[i])")
        end
    end

    return dataset, iterations, verify
end

function print_hex(bytes::Vector{UInt8})
    println("hmac=", bytes2hex(bytes))
end

function main()
    dataset, iterations, verify = parse_args(ARGS)

    # Load dataset
    buffer = read(joinpath(dataset, "buffer.bin"))
    key_hmac = read(joinpath(dataset, "key_hmac.bin"))
    key_xor = read(joinpath(dataset, "key_xor.bin"))

    ciphertext = Vector{UInt8}(undef, length(buffer))
    decrypted = Vector{UInt8}(undef, length(buffer))
    out_hmac = Vector{UInt8}(undef, 32)

    if verify
        SHA256Workload.workload_sha256!(buffer, key_hmac, key_xor, ciphertext, decrypted, out_hmac)
        print_hex(out_hmac)
        println("verify=", decrypted == buffer ? 1 : 0)
        return
    end

    for _ in 1:iterations
        SHA256Workload.workload_sha256!(buffer, key_hmac, key_xor, ciphertext, decrypted, out_hmac)
    end

end

main()
