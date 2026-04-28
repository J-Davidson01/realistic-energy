module JsonParseWorkload

using JSON

const sink = Ref{UInt8}(0x00)

function workload_json_parse(input_json::String, output_json::Base.RefValue{String}, output_len::Base.RefValue{Int})
    root = JSON.parse(input_json)

    items = root["items"]
    for item in items
        item["id"] = item["id"] + 1
        item["active"] = !item["active"]

        upper = uppercase(item["name"])
        item["name"] = upper
        item["name_length"] = ncodeunits(upper)
    end

    serialized = JSON.json(root)

    output_json[] = serialized
    output_len[] = ncodeunits(serialized)

    sink[] = xor(sink[], UInt8(output_len[] % 0x100))
    sink[] = xor(sink[], codeunit(serialized, 1))
    
    return 1
end