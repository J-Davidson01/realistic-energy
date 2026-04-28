import Pkg
Pkg.activate(@__DIR__)

include("../../workloads/julia/file_copy_workload.jl")

function parse_args(args)
    dataset = "../../../datasets/file_copy/1048576"
    iterations = 1000000
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

function files_equal(src_path::String, dst_path::String, amplification::Int)
    src = read(src_path)
    dst = read(dst_path)

    if length(dst) != amplification * length(src)
        return false
    end

    n = length(src)
    for i in 0:(amplification - 1)
        start_idx = i * n + 1
        end_idx = (i + 1) * n
        if @view(dst[start_idx:end_idx]) != src
            return false
        end
    end

    return true
end

function main()
    dataset, iterations, verify = parse_args(ARGS)

    src_path = joinpath(dataset, "input.bin")
    dst_path = joinpath(dataset, "output.bin")

    input_buffer = read(src_path)

    if verify
        dst = open(dst_path, "w")
        FileCopyWorkload.workload_file_copy!(dst, input_buffer)
        close(dst)

        verification = files_equal(
            src_path,
            dst_path,
            FileCopyWorkload.FILE_COPY_WRITE_AMPLIFICATION,
        )

        println("verify= ", verification ? 1 : 0)
        return
    end

    for _ in 1:iterations
        dst = open(dst_path, "w")
        FileCopyWorkload.workload_file_copy!(dst, input_buffer)
        close(dst)
    end
end

main()