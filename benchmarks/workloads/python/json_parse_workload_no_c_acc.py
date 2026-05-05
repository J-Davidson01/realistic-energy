import json
import json.decoder
import json.encoder
import json.scanner

sink = 0


def _disable_json_c_accelerators() -> None:
    """
    Force CPython's stdlib json module onto its pure-Python scanner/encoder paths.

    Must run before workload calls json.loads/json.dumps. We also recreate the
    module-level default decoder/encoder so json.loads without custom arguments
    does not keep using a decoder created before patching.
    """

    # Decoder/scanner side
    json.decoder.scanstring = json.decoder.py_scanstring
    json.scanner.c_make_scanner = None
    json.scanner.make_scanner = json.scanner.py_make_scanner

    # Encoder side
    json.encoder.c_make_encoder = None

    # Rebuild defaults used by json.loads/json.dumps fast paths.
    json._default_decoder = json.JSONDecoder()
    json._default_encoder = json.JSONEncoder(
        skipkeys=False,
        ensure_ascii=True,
        check_circular=True,
        allow_nan=True,
        indent=None,
        separators=None,
        default=None,
    )


_disable_json_c_accelerators()


def workload_json_parse(input_json: str, output_json, output_len) -> int:
    global sink

    root = json.loads(input_json)

    items = root["items"]
    for item in items:
        item["id"] = item["id"] + 1
        item["active"] = not item["active"]

        upper = item["name"].upper()
        item["name"] = upper
        item["name_length"] = len(upper.encode("utf-8"))

    serialized = json.dumps(root, separators=(",", ":"))
    serialized_bytes = serialized.encode("utf-8")

    output_json[0] = serialized
    output_len[0] = len(serialized_bytes)

    sink ^= output_len[0] & 0xFF
    sink ^= serialized_bytes[0]

    return 1
