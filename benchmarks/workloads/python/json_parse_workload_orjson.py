import orjson

sink = 0


def workload_json_parse(input_json: str, output_json, output_len) -> int:
    global sink

    root = orjson.loads(input_json)

    items = root["items"]
    for item in items:
        item["id"] = item["id"] + 1
        item["active"] = not item["active"]

        upper = item["name"].upper()
        item["name"] = upper
        item["name_length"] = len(upper.encode("utf-8"))

    serialized_bytes = orjson.dumps(root)

    output_json[0] = serialized_bytes.decode("utf-8")
    output_len[0] = len(serialized_bytes)

    sink ^= output_len[0] & 0xFF
    sink ^= serialized_bytes[0]

    return 1
