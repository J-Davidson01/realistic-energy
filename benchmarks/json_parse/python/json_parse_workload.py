#!/usr/bin/env python3
import json

sink = 0

def workload_json_parse(input_json_text: str) -> tuple[str, int]:
    global sink

    parsed_root = json.loads(input_json_text)

    items = parsed_root["items"]
    for item in items:
        item["id"] += 1
        item["active"] = not item["active"]

        upper_name = item["name"].upper()
        item["name"] = upper_name
        item["name_length"] = len(upper_name)

    output_json_text = json.dumps(parsed_root, separators=(",", ":"))
    output_len = len(output_json_text)

    sink ^= output_len & 0xFF
    sink ^= ord(output_json_text[0]) & 0xFF

    return output_json_text, output_len


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