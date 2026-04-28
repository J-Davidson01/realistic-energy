import Pkg
Pkg.activate(@__DIR__)

include("../../workloads/julia/pipeline_e2e_workload.jl")

using JSON

const DEFAULT_JSON_DATASET_DIR = "../../../datasets/json_parse/1048576"
const DEFAULT_SHA256_DATASET_DIR = "../../../datasets/sha256/1048576"
const DEFAULT_OUTPUT_DIR = "../../../datasets/file_copy/1048576"
const DEFAULT_ITERATIONS = 1000000
const PIPELINE_BUFFER_GROWTH_FACTOR = 2

function parse_args(args)
    dataset_selector = nothing
    json_dataset_dir = DEFAULT_JSON_DATASET_DIR
    sha256_dataset_dir = DEFAULT_SHA256_DATASET_DIR
    output_dir = DEFAULT_OUTPUT_DIR
    iterations = DEFAULT_ITERATIONS
    verify = false

    i = 1
    while i <= length(args)
        if args[i] == "--dataset"
            dataset_selector = args[i + 1]
            i += 2
        elseif args[i] == "--json-dataset"
            json_dataset_dir = args[i + 1]
            i += 2
        elseif args[i] == "--sha256-dataset"
            sha256_dataset_dir = args[i + 1]
            i += 2
        elseif args[i] == "--output-dir"
            output_dir = args[i + 1]
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

    return dataset_selector, json_dataset_dir, sha256_dataset_dir, output_dir, iterations, verify
end

function derive_dataset_dirs_from_selector(dataset_selector::String)
    size_name = basename(dataset_selector)
    pipeline_size_dir = dirname(dataset_selector)
    datasets_root = dirname(pipeline_size_dir)

    json_dataset_dir = joinpath(datasets_root, "json_parse", size_name)
    sha256_dataset_dir = joinpath(datasets_root, "sha256", size_name)
    output_dir = joinpath(datasets_root, "file_copy", size_name)

    return json_dataset_dir, sha256_dataset_dir, output_dir
end

function file_equals_amplified_buffer(path::String, buffer::Vector{UInt8}, amplification::Int)
    file_bytes = read(path)

    expected_len = length(buffer) * amplification
    if length(file_bytes) != expected_len
        return false
    end

    for i in 0:(amplification - 1)
        start_idx = i * length(buffer) + 1
        end_idx = (i + 1) * length(buffer)
        if @view(file_bytes[start_idx:end_idx]) != buffer
            return false
        end
    end

    return true
end

function main()
    dataset_selector, json_dataset_dir, sha256_dataset_dir, output_dir, iterations, verify =
        parse_args(ARGS)

    if dataset_selector !== nothing
        json_dataset_dir, sha256_dataset_dir, output_dir =
            derive_dataset_dirs_from_selector(dataset_selector)
    end

    input_path = joinpath(json_dataset_dir, "input.json")
    key_hmac_path = joinpath(sha256_dataset_dir, "key_hmac.bin")
    key_xor_path = joinpath(sha256_dataset_dir, "key_xor.bin")
    output_path = joinpath(output_dir, "output.bin")

    input_json = read(input_path, String)
    key_hmac = read(key_hmac_path)
    key_xor = read(key_xor_path)

    input_len = ncodeunits(input_json)
    pipeline_buffer_len = input_len * PIPELINE_BUFFER_GROWTH_FACTOR + 64

    ciphertext = Vector{UInt8}(undef, pipeline_buffer_len)
    decrypted = Vector{UInt8}(undef, pipeline_buffer_len)
    out_hmac = Vector{UInt8}(undef, 32)

    if verify
        open(output_path, "w") do dst
            PipelineE2EWorkload.workload_pipeline_e2e!(
                input_json,
                key_hmac,
                key_xor,
                ciphertext,
                decrypted,
                out_hmac,
                dst,
            )
        end

        verify_json = Ref("")
        verify_len = Ref(0)
        PipelineE2EWorkload.JsonParseWorkload.workload_json_parse(input_json, verify_json, verify_len)

        verify_bytes = Vector{UInt8}(codeunits(verify_json[]))
        crypto_ok = isempty(verify_bytes) || (@view(decrypted[1:verify_len[]]) == verify_bytes)
        file_ok = file_equals_amplified_buffer(
            output_path,
            verify_bytes,
            PipelineE2EWorkload.FileCopyWorkload.FILE_COPY_WRITE_AMPLIFICATION,
        )

        verification = crypto_ok && file_ok
        println("verify= ", verification ? 1 : 0)

        if !verification
            exit(1)
        end
        return
    end

    for _ in 1:iterations
        open(output_path, "w") do dst
            PipelineE2EWorkload.workload_pipeline_e2e!(
                input_json,
                key_hmac,
                key_xor,
                ciphertext,
                decrypted,
                out_hmac,
                dst,
            )
        end
    end
end

main()
