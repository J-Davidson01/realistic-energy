#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.workloads.python.json_parse_workload import workload_json_parse

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

        actual_len = len(name_value.encode("utf-8"))
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
        output_json = [""]
        output_len = [0]
        workload_json_parse(input_json, output_json, output_len)
        verified = verify_json_parse_output(output_json[0])

        print(f"verify= {1 if verified else 0}")
        if not verified:
            raise SystemExit(1)
        return

    for i in range(args.iterations):
        try:
            output_json = [""]
            output_len = [0]
            workload_json_parse(input_json, output_json, output_len)
        except Exception:
            print(f"workload_json_parse failed at iteration {i}")
            raise SystemExit(1)

if __name__ == "__main__":
    main()