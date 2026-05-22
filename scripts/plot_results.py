#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


ISOLATED_WORKLOADS = ["json_parse", "sha256", "file_copy"]
PIPELINE_WORKLOADS = ["pipeline_e2e", "pipeline_e2e_stream"]
ALL_WORKLOADS = ISOLATED_WORKLOADS + PIPELINE_WORKLOADS

DEFAULT_LANG_ORDER = ["c", "go", "julia", "python"]

BASELINE_VARIANTS = {
    "json_parse": {
        "c": "cjson",
        "go": "encoding_json",
        "julia": "json",
        "python": "json",
    }
}

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    numeric_columns = [
        "size",
        "n",
        "median_elapsed_s",
        "median_energy_pkg_j",
        "median_energy_core_j",
        "median_energy_dram_j",
        "median_rss_peak_bytes",
        "norm_runtime",
        "norm_energy_pkg",
        "norm_energy_core",
        "norm_energy_dram",
        "norm_peak_memory",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["size_mib"] = df["size"] / (1024 * 1024)

    return df


def label_for_row(language: str, variant: str) -> str:
    if variant == "default":
        return language
    return f"{language}/{variant}"


def filter_baseline_variants(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in df.iterrows():
        benchmark = row["benchmark"]
        language = row["language"]
        variant = row["variant"]

        if benchmark == "json_parse":
            baseline = {
                "c": "cjson",
                "go": "encoding_json",
                "julia": "json",
                "python": "json",
            }
            if baseline.get(language) == variant:
                rows.append(row)
        else:
            if variant == "default":
                rows.append(row)

    return pd.DataFrame(rows)


def plot_metric_by_workload(
    df: pd.DataFrame,
    workload: str,
    metric: str,
    ylabel: str,
    output_path: Path,
    include_variants: bool = False,
    title: str | None = None,
) -> None:
    plot_df = df[df["benchmark"] == workload].copy()

    if not include_variants:
        plot_df = filter_baseline_variants(plot_df)

    if plot_df.empty:
        print(f"Skipping {workload} / {metric}: no rows")
        return

    plt.figure(figsize=(8, 5))

    for (language, variant), group in plot_df.groupby(["language", "variant"], sort=False):
        group = group.sort_values("size")
        label = label_for_row(language, variant)

        plt.plot(
            group["size_mib"],
            group[metric],
            marker="o",
            linewidth=1.8,
            label=label,
        )

    plt.xscale("log", base=2)
    plt.xlabel("Input size S (MiB)")
    plt.ylabel(ylabel)
    plt.title(title or f"{workload}: {ylabel}")
    plt.legend()
    plt.grid(True, which="both", linewidth=0.5)
    plt.tight_layout()

    ensure_dir(output_path.parent)
    plt.savefig(output_path.with_suffix(".png"), dpi=300)
    plt.savefig(output_path.with_suffix(".pdf"))
    plt.close()


def plot_default_workload_metric_sets(df: pd.DataFrame, out_dir: Path) -> None:
    metrics = [
        ("median_energy_pkg_j", "Median CPU package energy (J)", "energy/package"),
        ("median_energy_dram_j", "Median DRAM energy (J)", "energy/dram"),
        ("median_elapsed_s", "Median wall-clock time (s)", "runtime"),
        ("median_rss_peak_bytes", "Median peak RSS (bytes)", "memory"),
    ]

    for workload in ALL_WORKLOADS:
        for metric, ylabel, subdir in metrics:
            plot_metric_by_workload(
                df=df,
                workload=workload,
                metric=metric,
                ylabel=ylabel,
                output_path=out_dir / subdir / f"{workload}_{metric}",
                include_variants=False,
                title=f"{workload}: {ylabel}",
            )


def plot_json_variants(df: pd.DataFrame, out_dir: Path) -> None:
    metrics = [
        ("median_elapsed_s", "Median wall-clock time (s)", "json_parse_runtime_variants"),
        ("median_energy_pkg_j", "Median CPU package energy (J)", "json_parse_package_energy_variants"),
        ("median_energy_dram_j", "Median DRAM energy (J)", "json_parse_dram_energy_variants"),
        ("median_rss_peak_bytes", "Median peak RSS (bytes)", "json_parse_peak_rss_variants"),
    ]

    for metric, ylabel, filename in metrics:
        plot_metric_by_workload(
            df=df,
            workload="json_parse",
            metric=metric,
            ylabel=ylabel,
            output_path=out_dir / "json_variants" / filename,
            include_variants=True,
            title=f"JSON parser variants: {ylabel}",
        )


def plot_normalized_heatmap(
    df: pd.DataFrame,
    metric: str,
    title: str,
    output_path: Path,
    largest_size_only: bool = True,
) -> None:
    plot_df = filter_baseline_variants(df)

    if largest_size_only:
        max_sizes = plot_df.groupby("benchmark")["size"].transform("max")
        plot_df = plot_df[plot_df["size"] == max_sizes].copy()

    pivot = plot_df.pivot_table(
        index="language",
        columns="benchmark",
        values=metric,
        aggfunc="median",
    )

    # Keep a stable row/column order where possible.
    row_order = [lang for lang in DEFAULT_LANG_ORDER if lang in pivot.index]
    pivot = pivot.reindex(row_order)
    col_order = [w for w in ALL_WORKLOADS if w in pivot.columns]
    pivot = pivot.reindex(columns=col_order)

    plt.figure(figsize=(9, 4.8))
    image = plt.imshow(pivot.values, aspect="auto")

    plt.colorbar(image, label="Normalized value, lower is better")
    plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=30, ha="right")
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.title(title)

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.values[i, j]
            if pd.notna(value):
                plt.text(j, i, f"{value:.2f}", ha="center", va="center")

    plt.tight_layout()

    ensure_dir(output_path.parent)
    plt.savefig(output_path.with_suffix(".png"), dpi=300)
    plt.savefig(output_path.with_suffix(".pdf"))
    plt.close()


def plot_isolated_vs_composed(
    df: pd.DataFrame,
    metric: str,
    ylabel: str,
    output_path: Path,
) -> None:
    plot_df = filter_baseline_variants(df)

    # Use the largest shared size per workload for a compact comparison.
    max_sizes = plot_df.groupby("benchmark")["size"].transform("max")
    plot_df = plot_df[plot_df["size"] == max_sizes].copy()
    plot_df = plot_df[plot_df["benchmark"].isin(ALL_WORKLOADS)]

    plot_df["label"] = plot_df.apply(
        lambda r: f"{r['language']}",
        axis=1,
    )

    workloads = [w for w in ALL_WORKLOADS if w in plot_df["benchmark"].unique()]
    languages = [l for l in DEFAULT_LANG_ORDER if l in plot_df["language"].unique()]

    x = range(len(workloads))
    width = 0.18

    plt.figure(figsize=(10, 5))

    for idx, language in enumerate(languages):
        values = []
        for workload in workloads:
            rows = plot_df[
                (plot_df["benchmark"] == workload) &
                (plot_df["language"] == language)
            ]
            if rows.empty:
                values.append(float("nan"))
            else:
                values.append(rows[metric].iloc[0])

        positions = [pos + (idx - (len(languages) - 1) / 2) * width for pos in x]
        plt.bar(positions, values, width=width, label=language)

    plt.xticks(list(x), workloads, rotation=25, ha="right")
    plt.ylabel(ylabel)
    plt.title("Isolated workloads versus composed pipelines")
    plt.legend()
    plt.tight_layout()

    ensure_dir(output_path.parent)
    plt.savefig(output_path.with_suffix(".png"), dpi=300)
    plt.savefig(output_path.with_suffix(".pdf"))
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create thesis plots from summary_normalized.csv")
    parser.add_argument("--input", required=True, type=Path, help="Path to summary_normalized.csv")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for generated plots")
    args = parser.parse_args()

    df = load_summary(args.input)
    out_dir = args.output_dir

    plot_default_workload_metric_sets(df, out_dir)
    plot_json_variants(df, out_dir)

    plot_normalized_heatmap(
        df=df,
        metric="norm_energy_pkg",
        title="Normalized CPU package energy at largest input size",
        output_path=out_dir / "normalized" / "heatmap_norm_package_energy_largest_size",
    )

    plot_normalized_heatmap(
        df=df,
        metric="norm_runtime",
        title="Normalized runtime at largest input size",
        output_path=out_dir / "normalized" / "heatmap_norm_runtime_largest_size",
    )

    plot_normalized_heatmap(
        df=df,
        metric="norm_peak_memory",
        title="Normalized peak RSS at largest input size",
        output_path=out_dir / "normalized" / "heatmap_norm_peak_memory_largest_size",
    )

    plot_isolated_vs_composed(
        df=df,
        metric="norm_energy_pkg",
        ylabel="Normalized CPU package energy, lower is better",
        output_path=out_dir / "isolated_vs_composed" / "isolated_vs_composed_norm_package_energy",
    )

    plot_isolated_vs_composed(
        df=df,
        metric="norm_runtime",
        ylabel="Normalized runtime, lower is better",
        output_path=out_dir / "isolated_vs_composed" / "isolated_vs_composed_norm_runtime",
    )

    print(f"Plots written to {out_dir}")


if __name__ == "__main__":
    main()