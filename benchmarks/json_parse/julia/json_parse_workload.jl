using JSON

const sink = Ref{UInt8}(0x00)

function workload_json_parse(
    input_json_text::String,
    output_json::Base.RefValue{String},
    output_len::Base.RefValue{Int}
)
    # 1. Parse JSON
    parsed_root = JSON.parse(input_json_text)

    # 2. Transform
    items = parsed_root["items"]
    for item in items
        item["id"] = item["id"] + 1
        item["active"] = !item["active"]

        upper = uppercase(item["name"])
        item["name"] = upper
        item["name_length"] = length(upper)
    end

    # 3. Serialize
    serialized = JSON.json(parsed_root)

    output_json[] = serialized
    output_len[] = ncodeunits(serialized)

    # 4. Prevent optimization
    sink[] = xor(sink[], UInt8(output_len[] % 256))
    sink[] = xor(sink[], codeunits(serialized)[1])

    return nothing
end
