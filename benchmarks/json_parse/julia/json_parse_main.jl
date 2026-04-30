import Pkg
Pkg.activate(@__DIR__)
using JSON

include("../../workloads/julia/json_parse_workload.jl")

function parse_args(args)
    dataset = "../../../datasets/json_parse/1048576"
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

function verify_json_parse_output(output_json_text::String)
    root = JSON.parse(output_json_text)
    items = root["items"]

    for item in items
        name = item["name"]
        name_length = item["name_length"]

        if length(name) != name_length
            return 0
        end

        if name != uppercase(name)
            return 0
        end
    end

    return 1
end

function main()
    dataset, iterations, verify = parse_args(ARGS)

    input_json_text = read(joinpath(dataset, "input.json"), String)

    if verify
        output_json = Ref("")
        output_len = Ref(0)

        JsonParseWorkload.workload_json_parse(input_json_text, output_json, output_len)
        verified = (verify_json_parse_output(output_json[]) == 1)

        println("verify= ", verified ? 1 : 0)
        return
    end

    for _ in 1:iterations
        output_json = Ref("")
        output_len = Ref(0)

        JsonParseWorkload.workload_json_parse(input_json_text, output_json, output_len)
    end
end

main()