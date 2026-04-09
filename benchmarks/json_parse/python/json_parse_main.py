#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from json_parse_workload import workload_json_parse

def read_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")

def verify_json_parse_output(output_json: str) -> bool:
    if not output_json:
        return False

    try:
        root = json.loads(output_json)
    except json.JSONDecodeError:
        return False

    items = root.get("items")
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            return False

        if "id" not in item or "active" not in item or "name" not in item or "name_length" not in item:
            return False

        id_value = item["id"]
        active_value = item["active"]
        name_value = item["name"]
        name_length_value = item["name_length"]

        if type(id_value) is not int:
            return False
        if type(active_value) is not bool:
            return False
        if not isinstance(name_value, str):
            return False
        if not isinstance(name_length_value, (int, float)):
            return False

        actual_len = len(name_value)
        if int(name_length_value) != actual_len:
            return False

        for ch in name_value:
            if ch.isalpha() and ch != ch.upper():
                return False

    return True

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../../../datasets/json_parse/1048576")
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    input_json = read_file(dataset_dir / "input.json")

    if args.verify:
        output_json, _ = workload_json_parse(input_json)
        verified = verify_json_parse_output(output_json)

        if verified:
            print("verify= 1")
        else:
            print("verify= 0")
            raise SystemExit(1)

        return

    for i in range(args.iterations):
        try:
            workload_json_parse(input_json)
        except Exception:
            print(f"workload_json_parse failed at iteration {i}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()