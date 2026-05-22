include("../../workloads/julia/pipeline_e2e_stream_workload.jl")

using JSON

const DEFAULT_JSON_DATASET_DIR = "../../../datasets/json_parse/1048576"
const DEFAULT_SHA256_DATASET_DIR = "../../../datasets/sha256/1048576"
const DEFAULT_OUTPUT_DIR = "../../../datasets/file_copy/1048576"
const DEFAULT_ITERATIONS = 1000000
const DEFAULT_CHUNK_ITEMS = 1024
const PIPELINE_BUFFER_GROWTH_FACTOR = 2

function parse_args(args)
    dataset_selector = nothing
    json_dataset_override = nothing
    sha256_dataset_override = nothing
    output_dir_override = nothing
    iterations = DEFAULT_ITERATIONS
    chunk_items = DEFAULT_CHUNK_ITEMS
    verify = false

    i = 1
    while i <= length(args)
        if args[i] == "--dataset"
            dataset_selector = args[i + 1]
            i += 2
        elseif args[i] == "--json-dataset"
            json_dataset_override = args[i + 1]
            i += 2
        elseif args[i] == "--sha256-dataset"
            sha256_dataset_override = args[i + 1]
            i += 2
        elseif args[i] == "--output-dir"
            output_dir_override = args[i + 1]
            i += 2
        elseif args[i] == "--iterations"
            iterations = parse(Int, args[i + 1])
            i += 2
        elseif args[i] == "--chunk-items"
            chunk_items = parse(Int, args[i + 1])
            i += 2
        elseif args[i] == "--verify"
            verify = true
            i += 1
        else
            error("Unknown argument: $(args[i])")
        end
    end

    return dataset_selector,
           json_dataset_override,
           sha256_dataset_override,
           output_dir_override,
           iterations,
           chunk_items,
           verify
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

function build_json_chunks(input_json::String, chunk_items::Int)
    root = JSON.parse(input_json)
    items = root["items"]

    chunk_items <= 0 && (chunk_items = 1)

    chunks = String[]
    max_chunk_input_len = 0

    start_idx = 1
    while start_idx <= length(items)
        end_idx = min(start_idx + chunk_items - 1, length(items))
        chunk_root = Dict("items" => items[start_idx:end_idx])
        serialized = JSON.json(chunk_root)

        push!(chunks, serialized)
        max_chunk_input_len = max(max_chunk_input_len, ncodeunits(serialized))

        start_idx = end_idx + 1
    end

    return chunks, max_chunk_input_len
end

function file_equals_streamed_chunks(path::String, chunks::Vector{String})
    file_bytes = read(path)
    offset = 1

    for chunk in chunks
        verify_json = Ref("")
        verify_len = Ref(0)

        PipelineE2EStreamWorkload.JsonParseWorkload.workload_json_parse(
            chunk,
            verify_json,
            verify_len,
        )

        verify_bytes = Vector{UInt8}(codeunits(verify_json[]))
        repeated_len = verify_len[] * PipelineE2EStreamWorkload.FileCopyWorkload.FILE_COPY_WRITE_AMPLIFICATION

        if offset + repeated_len - 1 > length(file_bytes)
            return false
        end

        for _ in 1:PipelineE2EStreamWorkload.FileCopyWorkload.FILE_COPY_WRITE_AMPLIFICATION
            if verify_len[] > 0
                if @view(file_bytes[offset:(offset + verify_len[] - 1)]) != verify_bytes
                    return false
                end
                offset += verify_len[]
            end
        end
    end

    return offset == length(file_bytes) + 1
end

function main()
    dataset_selector,
    json_dataset_override,
    sha256_dataset_override,
    output_dir_override,
    iterations,
    chunk_items,
    verify = parse_args(ARGS)

    if dataset_selector !== nothing
        json_dataset_dir, sha256_dataset_dir, output_dir =
            derive_dataset_dirs_from_selector(dataset_selector)
    else
        json_dataset_dir = DEFAULT_JSON_DATASET_DIR
        sha256_dataset_dir = DEFAULT_SHA256_DATASET_DIR
        output_dir = DEFAULT_OUTPUT_DIR
    end

    if json_dataset_override !== nothing
        json_dataset_dir = json_dataset_override
    end

    if sha256_dataset_override !== nothing
        sha256_dataset_dir = sha256_dataset_override
    end

    if output_dir_override !== nothing
        output_dir = output_dir_override
    end

    input_path = joinpath(json_dataset_dir, "input.json")
    key_hmac_path = joinpath(sha256_dataset_dir, "key_hmac.bin")
    key_xor_path = joinpath(sha256_dataset_dir, "key_xor.bin")
    output_path = joinpath(output_dir, "output.bin")

    input_json = read(input_path, String)
    key_hmac = read(key_hmac_path)
    key_xor = read(key_xor_path)

    chunks, max_chunk_input_len = build_json_chunks(input_json, chunk_items)

    pipeline_buffer_len = max_chunk_input_len * PIPELINE_BUFFER_GROWTH_FACTOR + 64

    ciphertext = Vector{UInt8}(undef, pipeline_buffer_len)
    decrypted = Vector{UInt8}(undef, pipeline_buffer_len)
    out_hmac = Vector{UInt8}(undef, 32)

    if verify
        open(output_path, "w") do dst
            PipelineE2EStreamWorkload.workload_pipeline_e2e_stream!(
                chunks,
                key_hmac,
                key_xor,
                ciphertext,
                decrypted,
                out_hmac,
                dst,
            )
        end

        verification = file_equals_streamed_chunks(output_path, chunks)
        println("verify= ", verification ? 1 : 0)

        if !verification
            exit(1)
        end
        return
    end

    for _ in 1:iterations
        open(output_path, "w") do dst
            PipelineE2EStreamWorkload.workload_pipeline_e2e_stream!(
                chunks,
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
