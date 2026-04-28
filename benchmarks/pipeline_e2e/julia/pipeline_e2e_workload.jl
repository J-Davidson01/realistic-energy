module PipelineE2EWorkload

include("../../file_copy/julia/file_copy_workload.jl")
include("../../sha256/julia/sha256_workload.jl")
include("../../json_parse/julia/json_parse_workload.jl")

const pipeline_e2e_sink = Ref{UInt8}(0)

function workload_pipeline_e2e!(
    input_json::String,
    key_hmac::Vector{UInt8},
    key_xor::Vector{UInt8},
    ciphertext::Vector{UInt8},
    decrypted::Vector{UInt8},
    out_hmac::Vector{UInt8},
    dst::IO
)
    output_json = Ref("")
    output_len = Ref(0)

    JsonParseWorkload.workload_json_parse(input_json, output_json, output_len)

    transformed_json = output_json[]
    transformed_len = output_len[]
    transformed_bytes = Vector{UInt8}(codeunits(transformed_json))

    SHA256Workload.workload_sha256!(
        transformed_bytes,
        key_hmac,
        key_xor,
        ciphertext,
        decrypted,
        out_hmac,
    )

    FileCopyWorkload.workload_file_copy!(dst, @view decrypted[1:transformed_len])

    pipeline_e2e_sink[] ⊻= UInt8(transformed_len & 0xff)
    pipeline_e2e_sink[] ⊻= decrypted[1]
    pipeline_e2e_sink[] ⊻= out_hmac[1]

    return 1
end

end # module
