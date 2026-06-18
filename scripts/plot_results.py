#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

import numpy as np
from scipy.stats import linregress


ISOLATED_WORKLOADS = ["json_parse", "sha256", "file_copy"]
PIPELINE_WORKLOADS = ["pipeline_e2e", "pipeline_e2e_stream"]
ALL_WORKLOADS = ISOLATED_WORKLOADS + PIPELINE_WORKLOADS
LOG_SCALE_Y = False

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

plt.rcParams.update({
    "font.size": 17,
    "axes.titlesize": 20,
    "axes.labelsize": 17,
    "xtick.labelsize": 15,
    "ytick.labelsize": 15,
    "legend.fontsize": 15,
})

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

    plt.figure(figsize=(10, 6))

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
    if LOG_SCALE_Y:
        plt.yscale("log")
    plt.title(title or f"{workload}: {ylabel}")
    plt.legend()
    plt.grid(True, which="both", linewidth=0.5)
    plt.tight_layout()

    ensure_dir(output_path.parent)
    plt.savefig(output_path.with_suffix(".png"), dpi=300)
    plt.savefig(output_path.with_suffix(".pdf"))
    plt.close()


def plot_dram_package_correlation_all(
    df: pd.DataFrame,
    output_path: Path,
) -> None:
    plot_df = filter_baseline_variants(df)

    fig, ax = plt.subplots(figsize=(10, 6))

    for benchmark in [b for b in ALL_WORKLOADS if b in plot_df["benchmark"].unique()]:
        bench_df = plot_df[plot_df["benchmark"] == benchmark]

        ax.scatter(
            bench_df["median_energy_pkg_j"],
            bench_df["median_energy_dram_j"],
            label=benchmark,
            alpha=0.8,
            zorder=3,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("CPU package energy (J)")
    ax.set_ylabel("DRAM energy (J)")
    ax.set_title("DRAM energy versus CPU package energy")
    ax.legend()
    ax.grid(True, which="both", linewidth=0.5)

    fig.tight_layout()

    ensure_dir(output_path.parent)
    fig.savefig(output_path.with_suffix(".png"), dpi=300)
    fig.savefig(output_path.with_suffix(".pdf"))
    plt.close(fig)


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

    fig, ax = plt.subplots(figsize=(12, 6))

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
                )

    fig.tight_layout()

    ensure_dir(output_path.parent)
    fig.savefig(output_path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_energy_runtime_correlation_all(
    df: pd.DataFrame,
    output_path: Path,
) -> None:
    plot_df = filter_baseline_variants(df)

    fig, ax = plt.subplots(figsize=(10, 6))

    for benchmark in [b for b in ALL_WORKLOADS if b in plot_df["benchmark"].unique()]:
        bench_df = plot_df[plot_df["benchmark"] == benchmark]

        ax.scatter(
            bench_df["median_elapsed_s"],
            bench_df["median_energy_pkg_j"],
            label=benchmark,
            alpha=0.8,
            zorder=3,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Runtime (s)")
    ax.set_ylabel("CPU package energy (J)")
    ax.set_title("Runtime versus CPU package energy")
    ax.legend()
    ax.grid(True, which="both", linewidth=0.5)

    fig.tight_layout()

    ensure_dir(output_path.parent)
    fig.savefig(output_path.with_suffix(".png"), dpi=300)
    fig.savefig(output_path.with_suffix(".pdf"))
    plt.close(fig)


def plot_isolated_vs_composed(
    df: pd.DataFrame,
    metric: str,
    ylabel: str,
    output_path: Path,
    highlight: str = "none",  # "none" | "star" | "hatch"
) -> None:
    plot_df = baseline_normalized_df(df)
 
    max_sizes = plot_df.groupby("benchmark")["size"].transform("max")
    plot_df = plot_df[plot_df["size"] == max_sizes].copy()
    plot_df = plot_df[plot_df["benchmark"].isin(ALL_WORKLOADS)]
 
    workloads = [w for w in ALL_WORKLOADS if w in plot_df["benchmark"].unique()]
    languages = [l for l in DEFAULT_LANG_ORDER if l in plot_df["language"].unique()]
 
    x = range(len(workloads))
    width = 0.18
 
    fig, ax = plt.subplots(figsize=(10, 6))
 
    bar_records = [] 
 
    for li, language in enumerate(languages):
        values = []
        for workload in workloads:
            rows = plot_df[
                (plot_df["benchmark"] == workload) &
                (plot_df["language"] == language)
            ]
            values.append(rows[metric].iloc[0] if not rows.empty else float("nan"))
 
        positions = [pos + (li - (len(languages) - 1) / 2) * width for pos in x]
        bars = ax.bar(positions, values, width=width, label=language)
 
        for wi, (bar, val) in enumerate(zip(bars, values)):
            bar_records.append((wi, li, val, bar))
 
    for wi in range(len(workloads)):
        group = [(li, val, bar) for (w, li, val, bar) in bar_records if w == wi and not np.isnan(val)]
        if not group:
            continue
        best_li, best_val, best_bar = min(group, key=lambda t: t[1])
 
        if highlight == "star":
            ax.text(
                best_bar.get_x() + best_bar.get_width() / 2,
                best_val,
                "★",
                ha="center",
                va="bottom",
                fontsize=14,
                color="black",
            )
 
        elif highlight == "hatch":
            best_bar.set_hatch("////")
            best_bar.set_edgecolor("black")
            best_bar.set_linewidth(0.8)
 
    ax.set_xticks(list(x))
    ax.set_xticklabels(workloads, rotation=25, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title("Isolated workloads versus composed pipelines")
    ax.legend()
    fig.tight_layout()
 
    ensure_dir(output_path.parent)
    fig.savefig(output_path.with_suffix(".png"), dpi=300)
    fig.savefig(output_path.with_suffix(".pdf"))
    plt.close(fig)

def plot_energy_runtime_correlation(
    df: pd.DataFrame,
    output_path: Path,
) -> None:
    plot_df = filter_baseline_variants(df)
    benchmarks = [b for b in ALL_WORKLOADS if b in plot_df["benchmark"].unique()]

    for benchmark in benchmarks:
        bench_df = plot_df[plot_df["benchmark"] == benchmark]

        fig, ax = plt.subplots(figsize=(10, 6))

        for language in [l for l in DEFAULT_LANG_ORDER if l in bench_df["language"].unique()]:
            lang_df = bench_df[bench_df["language"] == language].sort_values("median_elapsed_s")

            scatter = ax.scatter(
                lang_df["median_elapsed_s"],
                lang_df["median_energy_pkg_j"],
                label=language,
                alpha=0.8,
                zorder=3,
            )

            if len(lang_df) >= 2:
                color = scatter.get_facecolor()[0]  # grab color from the scatter itself

                log_x = np.log10(lang_df["median_elapsed_s"])
                log_y = np.log10(lang_df["median_energy_pkg_j"])
                fit = linregress(log_x, log_y)

                x_range = np.linspace(log_x.min(), log_x.max(), 100)
                y_range = fit.slope * x_range + fit.intercept

                ax.plot(
                    10 ** x_range,
                    10 ** y_range,
                    linewidth=1.5,
                    linestyle="--",
                    alpha=0.6,
                    color=color,
                )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Runtime (s)")
        ax.set_ylabel("CPU package energy (J)")
        ax.set_title(f"{benchmark}: runtime vs CPU package energy")
        ax.legend()
        ax.grid(True, which="both", linewidth=0.5)

        fig.tight_layout()

        ensure_dir(output_path.parent)
        fig.savefig(output_path.parent / f"{output_path.stem}_{benchmark}.png", dpi=300)
        fig.savefig(output_path.parent / f"{output_path.stem}_{benchmark}.pdf")
        plt.close(fig)


def plot_dram_package_correlation(
    df: pd.DataFrame,
    output_path: Path,
) -> None:
    plot_df = filter_baseline_variants(df)
    benchmarks = [b for b in ALL_WORKLOADS if b in plot_df["benchmark"].unique()]

    for benchmark in benchmarks:
        bench_df = plot_df[plot_df["benchmark"] == benchmark]

        fig, ax = plt.subplots(figsize=(10, 6))

        for language in [l for l in DEFAULT_LANG_ORDER if l in bench_df["language"].unique()]:
            lang_df = bench_df[bench_df["language"] == language].sort_values("median_energy_pkg_j")

            scatter = ax.scatter(
                lang_df["median_energy_pkg_j"],
                lang_df["median_energy_dram_j"],
                label=language,
                alpha=0.8,
                zorder=3,
            )

            if len(lang_df) >= 2:
                color = scatter.get_facecolor()[0]

                log_x = np.log10(lang_df["median_energy_pkg_j"])
                log_y = np.log10(lang_df["median_energy_dram_j"])
                fit = linregress(log_x, log_y)

                x_range = np.linspace(log_x.min(), log_x.max(), 100)
                y_range = fit.slope * x_range + fit.intercept

                ax.plot(
                    10 ** x_range,
                    10 ** y_range,
                    linewidth=1.5,
                    linestyle="--",
                    alpha=0.6,
                    color=color,
                )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("CPU package energy (J)")
        ax.set_ylabel("DRAM energy (J)")
        ax.set_title(f"{benchmark}: DRAM energy vs CPU package energy")
        ax.legend()
        ax.grid(True, which="both", linewidth=0.5)

        fig.tight_layout()

        ensure_dir(output_path.parent)
        fig.savefig(output_path.parent / f"{output_path.stem}_{benchmark}.png", dpi=300)
        fig.savefig(output_path.parent / f"{output_path.stem}_{benchmark}.pdf")
        plt.close(fig)

def create_runtime_scaling_table(
    df: pd.DataFrame,
    output_path: Path,
):
    rows = []

    plot_df = filter_baseline_variants(df)

    for (benchmark, language), group in (
        plot_df.groupby(["benchmark", "language"])
    ):
        group = group.sort_values("size")
        group = group[group["size"] >= group["size"].median()]

        x = np.log2(group["size"])
        y = np.log2(group["median_elapsed_s"])

        fit = linregress(x, y)

        rows.append({
            "benchmark": benchmark,
            "language": language,
            "runtime_exponent": fit.slope,
        })

    result = pd.DataFrame(rows)

    ensure_dir(output_path.parent)
    result.to_csv(output_path, index=False)

    print(result)

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
        ylabel="Normalized CPU package energy (J)",
        output_path=out_dir / "isolated_vs_composed" / "isolated_vs_composed_norm_package_energy",
        highlight="star",
    )
 
    plot_isolated_vs_composed(
        df=df,
        metric="norm_runtime",
        ylabel="Normalized runtime (s)",
        output_path=out_dir / "isolated_vs_composed" / "isolated_vs_composed_norm_runtime",
        highlight="star",
    )
 
    plot_isolated_vs_composed(
        df=df,
        metric="norm_peak_memory",
        ylabel="Normalized peak RSS (bytes)",
        output_path=out_dir / "isolated_vs_composed" / "isolated_vs_composed_norm_peak_memory",
        highlight="star",
    )
    json_df = df[df["benchmark"] == "json_parse"].copy()

    plot_energy_runtime_correlation(
        df=df,
        output_path=out_dir / "correlations" / "energy_runtime_correlation",
    )

    plot_dram_package_correlation(
        df=df,
        output_path=out_dir / "correlations" / "dram_package_correlation",
    )

    create_runtime_scaling_table(
        df=df,
        output_path=out_dir / "tables" / "runtime_scaling_exponents.csv",
    )

    plot_dram_package_correlation_all(
    df=df,
    output_path=out_dir / "correlations" / "dram_package_correlation",
    )

    plot_energy_runtime_correlation_all(
    df=df,
    output_path=out_dir / "correlations" / "energy_runtime_correlation",
    )

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