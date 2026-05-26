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

RAW_TO_NORM = {
    "median_elapsed_s": "norm_runtime",
    "median_energy_pkg_j": "norm_energy_pkg",
    "median_energy_core_j": "norm_energy_core",
    "median_energy_dram_j": "norm_energy_dram",
    "median_rss_peak_bytes": "norm_peak_memory",
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

def recompute_normalized_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute normalized metrics within the provided dataframe.

    This is needed because summary_normalized.csv may have been normalized across
    all JSON variants. For baseline cross-language plots, we first filter to one
    baseline variant per language and then normalize within that filtered set.
    """
    out = df.copy()

    group_cols = ["benchmark", "dataset_name", "size"]

    for raw_col, norm_col in RAW_TO_NORM.items():
        if raw_col not in out.columns:
            continue

        best = out.groupby(group_cols)[raw_col].transform(
            lambda s: s.where(s > 0).min()
        )

        out[norm_col] = out[raw_col] / best

    return out


def baseline_normalized_df(df: pd.DataFrame) -> pd.DataFrame:
    baseline_df = filter_baseline_variants(df)
    return recompute_normalized_metrics(baseline_df)


def all_variant_normalized_df(df: pd.DataFrame) -> pd.DataFrame:
    return recompute_normalized_metrics(df)

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
    mode: str = "baseline",
) -> None:
    if mode == "baseline":
        plot_df = baseline_normalized_df(df)
    elif mode == "all":
        plot_df = all_variant_normalized_df(df)
    else:
        raise ValueError(f"Unknown heatmap mode: {mode}")

    if largest_size_only:
        max_sizes = plot_df.groupby("benchmark")["size"].transform("max")
        plot_df = plot_df[plot_df["size"] == max_sizes].copy()

    plot_df["label"] = plot_df.apply(
        lambda r: label_for_row(r["language"], r["variant"]),
        axis=1,
    )

    index_col = "language" if mode == "baseline" else "label"

    pivot = plot_df.pivot_table(
        index=index_col,
        columns="benchmark",
        values=metric,
        aggfunc="median",
    )

    if mode == "baseline":
        row_order = [lang for lang in DEFAULT_LANG_ORDER if lang in pivot.index]
        pivot = pivot.reindex(row_order)
    else:
        pivot = pivot.sort_index()

    col_order = [w for w in ALL_WORKLOADS if w in pivot.columns]
    pivot = pivot.reindex(columns=col_order)

    fig, ax = plt.subplots(figsize=(9, 4.8))

    # Lighter, thesis-friendly color map.
    image = ax.imshow(
        pivot.values,
        aspect="auto",
        cmap="YlGnBu",
    )

    fig.colorbar(image, ax=ax, label="Normalized value, lower is better")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(title)

    # Use black text on light cells and white text on dark cells.
    finite_values = pivot.values[pd.notna(pivot.values)]
    threshold = finite_values.max() * 0.55 if len(finite_values) > 0 else 0

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.values[i, j]
            if pd.notna(value):
                text_color = "white" if value > threshold else "black"
                ax.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    color=text_color,
                    fontsize=9,
                )

    fig.tight_layout()

    ensure_dir(output_path.parent)
    fig.savefig(output_path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_isolated_vs_composed(
    df: pd.DataFrame,
    metric: str,
    ylabel: str,
    output_path: Path,
) -> None:
    plot_df = baseline_normalized_df(df)

    max_sizes = plot_df.groupby("benchmark")["size"].transform("max")
    plot_df = plot_df[plot_df["size"] == max_sizes].copy()
    plot_df = plot_df[plot_df["benchmark"].isin(ALL_WORKLOADS)]

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
        title="Baseline-normalized CPU package energy at largest input size",
        output_path=out_dir / "normalized" / "heatmap_baseline_norm_package_energy_largest_size",
        mode="baseline",
    )

    plot_normalized_heatmap(
        df=df,
        metric="norm_runtime",
        title="Baseline-normalized runtime at largest input size",
        output_path=out_dir / "normalized" / "heatmap_baseline_norm_runtime_largest_size",
        mode="baseline",
    )

    plot_normalized_heatmap(
        df=df,
        metric="norm_peak_memory",
        title="Baseline-normalized peak RSS at largest input size",
        output_path=out_dir / "normalized" / "heatmap_baseline_norm_peak_memory_largest_size",
        mode="baseline",
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

    json_df = df[df["benchmark"] == "json_parse"].copy()

    plot_normalized_heatmap(
        df=json_df,
        metric="norm_energy_pkg",
        title="JSON parser variants: normalized CPU package energy at largest input size",
        output_path=out_dir / "json_variants" / "heatmap_json_variants_norm_package_energy_largest_size",
        mode="all",
    )

    plot_normalized_heatmap(
        df=json_df,
        metric="norm_runtime",
        title="JSON parser variants: normalized runtime at largest input size",
        output_path=out_dir / "json_variants" / "heatmap_json_variants_norm_runtime_largest_size",
        mode="all",
    )

    print(f"Plots written to {out_dir}")


if __name__ == "__main__":
    main()