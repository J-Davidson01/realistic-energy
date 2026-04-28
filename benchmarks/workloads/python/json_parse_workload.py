#!/usr/bin/env python3
import orjson

sink = 0

def workload_json_parse(input_json: str, output_json: list[str], output_len: list[int]) -> int:
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


# // volatile sink
#
# // function WORKLOAD_JSON_PARSE(input_json_text):
# //
# //     # -----------------------------
# //     # 1. Parse JSON text
# //     #    (allocates parsed object tree)
# //     # -----------------------------
# //     parsed_root = JSON_PARSE(input_json_text)
# //
# //     # -----------------------------
# //     # 2. Transform parsed objects
# //     #    (may allocate new/updated strings or fields)
# //     # -----------------------------
# //     for each object in parsed_root["items"]:
# //         object["id"] = object["id"] + 1
# //         object["active"] = NOT object["active"]
# //         object["name"] = TO_UPPERCASE(object["name"])
# //         object["name_length"] = LENGTH(object["name"])
# //
# //     # -----------------------------
# //     # 3. Serialize transformed JSON
# //     #    (allocates output JSON buffer)
# //     # -----------------------------
# //     output_json_text = JSON_SERIALIZE(parsed_root)
# //
# //     # -----------------------------
# //     # 4. Prevent optimization
# //     # -----------------------------
# //     sink = sink XOR LENGTH(output_json_text)
# //     if LENGTH(output_json_text) > 0:
# //         sink = sink XOR BYTE_AT(output_json_text, 0)
# //
# //     # -----------------------------
# //     # 5. Free temporary parsed/serialized data
# //     # -----------------------------
# //     FREE(parsed_root)
# //     return output_json_text