#!/usr/bin/env python3
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple, Optional


RAW_METRICS = {
    "pkg": "energy_pkg_j",
    "core": "energy_core_j",
    "dram": "energy_dram_j",
    "time": "elapsed_s",
    "memory": "rss_peak_bytes",
}

NORMALIZED_METRICS = {
    "pkg": "norm_energy_pkg",
    "core": "norm_energy_core",
    "dram": "norm_energy_dram",
    "time": "norm_runtime",
    "memory": "norm_peak_memory",
}


def parse_weights(raw: str) -> Dict[str, float]:
    weights: Dict[str, float] = {}

    if not raw:
        return weights

    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        if "=" not in part:
            raise ValueError(f"Invalid weight entry '{part}'. Expected name=value.")

        name, value = part.split("=", 1)
        name = name.strip()
        value = float(value.strip())

        if value < 0:
            raise ValueError(f"Weight for '{name}' must be non-negative.")

        weights[name] = value

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one weight must be positive.")

    return {k: v / total for k, v in weights.items()}


def parse_optional_float(value: str) -> Optional[float]:
    if value is None:
        return None

    value = str(value).strip()
    if value == "" or value.lower() == "none":
        return None

    try:
        parsed = float(value)
    except ValueError:
        return None

    if math.isnan(parsed):
        return None

    return parsed


def read_rows(path: Path) -> List[dict]:
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def aggregate_repetitions(rows: List[dict]) -> List[dict]:
    groups = defaultdict(list)

    for row in rows:
        if str(row.get("returncode", "")).strip() != "0":
            continue

        key = (
            row["benchmark"],
            row["language"],
            row["variant"],
            row.get("dataset_name", row["benchmark"]),
            int(row["size"]),
        )
        groups[key].append(row)

    summary_rows = []

    for key, group in groups.items():
        benchmark, language, variant, dataset_name, size = key

        out = {
            "benchmark": benchmark,
            "language": language,
            "variant": variant,
            "dataset_name": dataset_name,
            "size": size,
            "n": len(group),
        }

        for metric_name, column in RAW_METRICS.items():
            values = [
                parse_optional_float(row.get(column, ""))
                for row in group
            ]
            values = [v for v in values if v is not None]

            if values:
                out[f"median_{column}"] = median(values)
            else:
                out[f"median_{column}"] = ""

        summary_rows.append(out)

    summary_rows.sort(
        key=lambda r: (
            r["benchmark"],
            r["dataset_name"],
            int(r["size"]),
            r["language"],
            r["variant"],
        )
    )

    return summary_rows


def add_normalized_metrics(summary_rows: List[dict]) -> List[dict]:
    groups = defaultdict(list)

    for row in summary_rows:
        key = (
            row["benchmark"],
            row["dataset_name"],
            int(row["size"]),
        )
        groups[key].append(row)

    normalized_rows = []

    for _, group in groups.items():
        best_values = {}

        for metric_name, raw_column in RAW_METRICS.items():
            summary_column = f"median_{raw_column}"
            values = [
                parse_optional_float(row.get(summary_column, ""))
                for row in group
            ]
            values = [v for v in values if v is not None and v > 0]

            best_values[metric_name] = min(values) if values else None

        for row in group:
            out = dict(row)

            for metric_name, raw_column in RAW_METRICS.items():
                summary_column = f"median_{raw_column}"
                norm_column = NORMALIZED_METRICS[metric_name]

                value = parse_optional_float(row.get(summary_column, ""))
                best = best_values[metric_name]

                if value is None or best is None or best <= 0:
                    out[norm_column] = ""
                else:
                    out[norm_column] = value / best

            normalized_rows.append(out)

    normalized_rows.sort(
        key=lambda r: (
            r["benchmark"],
            r["dataset_name"],
            int(r["size"]),
            r["language"],
            r["variant"],
        )
    )

    return normalized_rows


def compute_language_scores(
    normalized_rows: List[dict],
    workload_weights: Dict[str, float],
    metric_weights: Dict[str, float],
) -> List[dict]:
    language_metric_values = defaultdict(lambda: defaultdict(list))

    for row in normalized_rows:
        benchmark = row["benchmark"]

        if benchmark not in workload_weights:
            continue

        language_key = (row["language"], row["variant"])

        for metric_name, norm_column in NORMALIZED_METRICS.items():
            value = parse_optional_float(row.get(norm_column, ""))
            if value is None:
                continue

            weighted_value = workload_weights[benchmark] * value
            language_metric_values[language_key][metric_name].append(weighted_value)

    score_rows = []

    for (language, variant), metric_values in language_metric_values.items():
        out = {
            "language": language,
            "variant": variant,
        }

        combined_score = 0.0
        combined_weight_used = 0.0

        for metric_name in NORMALIZED_METRICS:
            values = metric_values.get(metric_name, [])

            if values:
                score = sum(values)
                out[f"weighted_{metric_name}_score"] = score
            else:
                score = None
                out[f"weighted_{metric_name}_score"] = ""

            metric_weight = metric_weights.get(metric_name, 0.0)

            if score is not None and metric_weight > 0:
                combined_score += metric_weight * score
                combined_weight_used += metric_weight

        if combined_weight_used > 0:
            out["combined_score"] = combined_score / combined_weight_used
        else:
            out["combined_score"] = ""

        score_rows.append(out)

    score_rows.sort(
        key=lambda r: (
            parse_optional_float(r.get("combined_score", "")) is None,
            parse_optional_float(r.get("combined_score", "")) or float("inf"),
            r["language"],
            r["variant"],
        )
    )

    return score_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze benchmark CSV results using normalized weighted metrics."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--workload-weights",
        default="sha256=1,json_parse=1,file_copy=1,pipeline_e2e=1,pipeline_e2e_stream=1",
        help="Comma-separated workload weights, e.g. sha256=1,json_parse=2,file_copy=1",
    )
    parser.add_argument(
        "--metric-weights",
        default="pkg=1,dram=0,time=0,memory=0",
        help="Comma-separated metric weights. Supported: pkg,core,dram,time,memory",
    )
    args = parser.parse_args()

    workload_weights = parse_weights(args.workload_weights)
    metric_weights = parse_weights(args.metric_weights)

    unknown_metrics = set(metric_weights) - set(RAW_METRICS)
    if unknown_metrics:
        raise ValueError(f"Unknown metric weights: {', '.join(sorted(unknown_metrics))}")

    rows = read_rows(args.input)

    summary_rows = aggregate_repetitions(rows)
    normalized_rows = add_normalized_metrics(summary_rows)
    score_rows = compute_language_scores(
        normalized_rows,
        workload_weights,
        metric_weights,
    )

    summary_fields = [
        "benchmark",
        "dataset_name",
        "size",
        "language",
        "variant",
        "n",
        "median_elapsed_s",
        "median_energy_pkg_j",
        "median_energy_core_j",
        "median_energy_dram_j",
        "median_rss_peak_bytes",
    ]

    normalized_fields = summary_fields + [
        "norm_runtime",
        "norm_energy_pkg",
        "norm_energy_core",
        "norm_energy_dram",
        "norm_peak_memory",
    ]

    score_fields = [
        "language",
        "variant",
        "weighted_pkg_score",
        "weighted_core_score",
        "weighted_dram_score",
        "weighted_time_score",
        "weighted_memory_score",
        "combined_score",
    ]

    write_rows(args.output_dir / "summary_raw.csv", summary_rows, summary_fields)
    write_rows(args.output_dir / "summary_normalized.csv", normalized_rows, normalized_fields)
    write_rows(args.output_dir / "language_scores.csv", score_rows, score_fields)

    print(f"Wrote {args.output_dir / 'summary_raw.csv'}")
    print(f"Wrote {args.output_dir / 'summary_normalized.csv'}")
    print(f"Wrote {args.output_dir / 'language_scores.csv'}")


if __name__ == "__main__":
    main()