# Realistic Energy Benchmark Suite

A reproducible benchmark suite for comparing runtime, energy consumption, and peak memory usage across programming languages on controlled data-processing workloads.

This repository was developed for a thesis project on programming language energy efficiency. The benchmark suite evaluates C, Go, Julia, and Python implementations of isolated workloads and composed ETL-inspired data-processing pipelines.

## Overview

Many existing programming-language energy studies rely on isolated algorithmic benchmarks or small synthetic workloads. This project instead uses controlled workloads that resemble recurring stages in data-processing systems:

- **JSON parse-transform-serialize**: semi-structured data parsing and transformation.
- **SHA-256/XOR processing**: CPU-oriented byte-buffer processing.
- **Sequential file copy**: file-output and I/O-oriented behavior.
- **Composed pipeline**: JSON transformation, byte processing, and file output combined.
- **Streaming composed pipeline**: chunked pipeline variant to evaluate streaming behavior and memory usage.

## Repository structure

```text
.
├── benchmarks/
│   ├── file_copy/
│   │   ├── c/
│   │   ├── go/
│   │   ├── julia/
│   │   └── python/
│   ├── json_parse/
│   ├── pipeline_e2e/
│   ├── pipeline_e2e_stream/
│   ├── sha256/
│   └── workloads/
│       ├── c/
│       ├── go/
│       ├── julia/
│       └── python/
├── datasets/
├── results/
├── scripts/
│   ├── analyze_results.py
│   ├── das5_run.sh
│   ├── das5_setup_tool.sh
│   ├── generate_inputs.py
│   ├── plot_results.py
│   └── run_benchmarks.py
├── go.mod
├── go.sum
└── README.md
```

Note that benchmarks/file_copy/c/... contains the orchestrator and benchmarks/workloads/c/... contains the actual workload.
Perhaps a better way of visualizing this with the repository structure would have been by having the following structure, though this might require some effort to change as this would require updating numerous paths:

```text
benchmarks/
├── orchestrators/
│   ├── file_copy/
│   │   ├── c/
│   │   ├── go/
│   │   ├── julia/
│   │   └── python/
│   ├── json_parse/
│   └── sha256/
└── workloads/
    ├── c/
    ├── go/
    ├── julia/
    └── python/
```

## Benchmarks

| Benchmark | Workload class | Input | Main pressure |
|---|---|---|---|
| `json_parse` | Parsing and serialization | JSON records | CPU and memory |
| `sha256` | Hashing and byte processing | Binary buffer + keys | CPU |
| `file_copy` | Sequential file output | Binary file | I/O |
| `pipeline_e2e` | Composed pipeline | JSON + keys | Mixed |
| `pipeline_e2e_stream` | Streaming composed pipeline | JSON chunks + keys | Mixed |

## Languages and variants

The benchmark suite includes baseline implementations for:

- C
- Go
- Julia
- Python

The JSON workload also includes parser variants to evaluate the effect of library choice:

| Language | Variant |
|---|---|
| C | `cjson`, `yyjson` |
| Go | `encoding_json`, `goccy_go_json` |
| Julia | `json`, `json3` |
| Python | `json`, `json_no_c_acc`, `orjson` |

The `json_no_c_acc` Python variant disables CPython's standard-library JSON C acceleration paths for experimental comparison.

## Requirements

The benchmark was designed and executed on DAS-5 Linux compute nodes with Intel RAPL available through the Linux powercap interface.

Main tool versions used in the thesis run:

| Tool | Version |
|---|---|
| GCC/G++ | 12.4.0 |
| CMake | 3.24.2 |
| Python | 3.11.9 |
| Go | 1.25.0 |
| Julia | 1.12.5 |
| Git | 2.43.5 |

The repository includes `scripts/das5_setup_tool.sh`, which installs the language toolchains used by the benchmark under:

```text
~/.local/realistic-energy/tools
```

RAPL energy measurement requires access to files such as:

```text
/sys/class/powercap/intel-rapl:0/energy_uj
```

If RAPL is unavailable, the benchmark can still measure runtime and memory, but CPU package and DRAM energy results will not be available.

## Setup

On DAS-5 or a comparable Linux environment, clone the repository and run the setup script:

```bash
git clone <repository-url>
cd realistic-energy

bash scripts/das5_setup_tool.sh
```

After setup, make sure the installed tools are available in your environment. On DAS-5 this should be handled by the run script.

## Generating input datasets

Input datasets are generated before running the benchmark suite.

```bash
python3 scripts/generate_inputs.py
```

The generator creates deterministic inputs for each workload:

- JSON datasets derived from the selected JSON source data.
- Binary buffers and keys for SHA-256/XOR.
- Binary input files for file copy.
- Reused inputs for the composed pipeline workloads.

Input sizes are generated as powers of two in bytes and are usually shown in plots as MiB.

## Running benchmarks

The benchmark runner executes language-specific subprocesses and records runtime, RAPL energy, and peak RSS.

For a direct local run, use `scripts/run_benchmarks.py`:

```bash
python3 scripts/run_benchmarks.py \
  --results-dir results/das5/benchmark_results.csv
```

On DAS-5, use the wrapper script:

```bash
bash scripts/das5_run.sh
```

The DAS-5 wrapper handles setup, dataset generation, rebuilding binaries, and passing benchmark options to `scripts/run_benchmarks.py`.

### DAS-5 wrapper options

`das5_run.sh` supports the following options:

| Option                     | Description                                                              |
| -------------------------- | ------------------------------------------------------------------------ |
| `--setup-tools`            | Install missing user-local tools, such as Go, Python, Julia, and OpenSSL |
| `--regen`                  | Regenerate datasets                                                      |
| `--rebuild`                | Rebuild C and Go binaries                                                |
| `--benchmarks LIST`        | Benchmarks to generate, build, or run                                    |
| `--min-dataset-size BYTES` | Minimum dataset size in bytes                                            |
| `--max-dataset-size BYTES` | Maximum dataset size in bytes                                            |
| `--no-run`                 | Only setup, build, or generate; do not run benchmarks                    |
| `--go-version VERSION`     | Go version to install locally if Go is missing                           |
| `--julia-module MODULE`    | Julia module to load                                                     |
| `--cmake-module MODULE`    | CMake module to load                                                     |
| `--datasets-out-root DIR`  | Directory where generated datasets are stored                            |
| `--results-out-root DIR`   | Directory where benchmark results are stored                             |
| `-h`, `--help`             | Show help                                                                |

All arguments after `--` are passed directly to `scripts/run_benchmarks.py`.

### Benchmark runner options

`run_benchmarks.py` supports the following commonly used options:

| Option                        |                                                        Default | Description                                                      |
| ----------------------------- | -------------------------------------------------------------: | ---------------------------------------------------------------- |
| `--benchmark`                 | `sha256,json_parse,file_copy,pipeline_e2e,pipeline_e2e_stream` | Comma-separated benchmark names                                  |
| `--languages`                 |                                            `c,go,python,julia` | Comma-separated languages to run                                 |
| `--iterations`                |                                                           `25` | Number of workload iterations inside each benchmark subprocess   |
| `--repetitions`               |                                                            `5` | Number of repeated subprocess runs per configuration             |
| `--memory-interval-ms`        |                                                         `10.0` | Interval between memory usage samples                            |
| `--results-dir`               |                                `results/benchmark_results.csv` | Path for the benchmark results CSV                               |
| `--verify`                    |                                                       disabled | Run verification before benchmarking                             |
| `--datasets-root`             |                                        repository dataset root | Root directory where datasets are stored                         |
| `--sleep-between-runs`        |                                                          `0.1` | Sleep time between repeated runs                                 |
| `--warmup`                    |                                                       disabled | Run a warmup execution before measured repetitions               |
| `--min-dataset-size`          |                                                          unset | Minimum dataset size in bytes to include                         |
| `--max-dataset-size`          |                                                          unset | Maximum dataset size in bytes to include                         |
| `--chunk-items`               |                                                         `1024` | Number of JSON items per chunk for streaming benchmarks          |
| `--python-json-impls`         |                                                         `json` | Python JSON variants, e.g. `json,json_no_c_acc,orjson`           |
| `--c-json-impls`              |                                                        `cjson` | C JSON variants, e.g. `cjson,yyjson`                             |
| `--julia-json-impls`          |                                                         `json` | Julia JSON variants, e.g. `json,json3`                           |
| `--go-json-impls`             |                                                `encoding_json` | Go JSON variants, e.g. `encoding_json,goccy_go_json`             |
| `--dataset-overrides`         |                                                          empty | Benchmark-to-dataset mappings, e.g. `json_parse=json_parse_yelp` |
| `--pipeline-json-dataset`     |                                                          empty | JSON dataset used by `pipeline_e2e` and `pipeline_e2e_stream`    |
| `--analyze`                   |                                                       disabled | Run `scripts/analyze_results.py` after benchmarking              |
| `--analysis-output-dir`       |                                                 auto-generated | Directory for analysis CSV outputs                               |
| `--analysis-workload-weights` |                                     all workloads weighted `1` | Workload weights passed to `analyze_results.py`                  |
| `--analysis-metric-weights`   |                             `pkg=0.5,dram=0.5,time=0,memory=0` | Metric weights passed to `analyze_results.py`                    |

### Thesis run example

The thesis results were generated using the following command on DAS-5:

```bash
prun -v -1 -np 1 -t 43200 ./scripts/das5_run.sh \
  --rebuild \
  --regen \
  -- \
  --min-dataset-size 1048576 \
  --max-dataset-size 1073741824 \
  --iterations 1 \
  --repetitions 8 \
  --python-json-impls json,json_no_c_acc,orjson \
  --c-json-impls cjson,yyjson \
  --julia-json-impls json,json3 \
  --go-json-impls encoding_json,goccy_go_json \
  --dataset-overrides json_parse=json_parse_yelp \
  --pipeline-json-dataset json_parse_yelp \
  --analyze \
  --analysis-workload-weights sha256=1,json_parse=1,file_copy=1,pipeline_e2e=1,pipeline_e2e_stream=1 \
  --analysis-metric-weights pkg=0.5,dram=0.5,time=0,memory=0
```

In this command, `das5_run.sh` rebuilds binaries and regenerates datasets before running the benchmark suite. Arguments after `--` are passed to `run_benchmarks.py`.

## Docker usage

The repository also contains an experimental Docker setup under `docker/`. The Docker image installs the main build and runtime dependencies, including C/C++ build tools, CMake, OpenSSL, Python, Go, and Julia. This can be useful for local development.

Build the image from the repository root:

```bash
docker build -f docker/Dockerfile -t realistic-energy .
```

Run the container with the repository mounted into `/realistic-energy`:

```bash
docker run --rm -it \
  -v "$PWD":/realistic-energy \
  realistic-energy
```

By default, the Docker entrypoint generates missing datasets, installs benchmark dependencies, builds C and Go workloads, instantiates Julia environments, and then runs `scripts/run_benchmarks.py`.

The entrypoint can be configured through environment variables:

| Variable     |                                    Default | Description                              |
| ------------ | -----------------------------------------: | ---------------------------------------- |
| `BENCHMARKS` | `sha256,json_parse,file_copy,pipeline_e2e` | Benchmarks to generate and run           |
| `MIN_SIZE`   |                                  `1048576` | Minimum dataset size in bytes            |
| `MAX_SIZE`   |                               `8589934592` | Maximum dataset size in bytes            |
| `REGEN`      |                                        `0` | Set to `1` to force dataset regeneration |
| `REBUILD`    |                                        `0` | Set to `1` to force rebuilding workloads |

Example:

```bash
docker run --rm -it \
  -v "$PWD":/realistic-energy \
  -e REGEN=1 \
  -e REBUILD=1 \
  -e BENCHMARKS=sha256,json_parse,file_copy \
  -e MIN_SIZE=1048576 \
  -e MAX_SIZE=1073741824 \
  realistic-energy \
  --benchmark sha256,json_parse,file_copy \
  --languages c,go,python,julia \
  --iterations 1 \
  --repetitions 8
```

Any arguments passed after the image name are forwarded to `scripts/run_benchmarks.py`.

Note that the Docker setup is intended mainly for local testing and reproducibility of the software environment. Energy measurements based on Intel RAPL require access to the host Linux powercap interface. Therefore, Docker runs may not provide CPU package or DRAM energy measurements unless the relevant host paths, such as `/sys/class/powercap`, are mounted and readable inside the container. Docker was added at the start of the project, it might not actually be fully up to date anymore, so please note that it might be outdated compared to the das5 scripts.


## Analyzing results

After a benchmark run, pull the results by running the following:
./scripts/copy_das5_results.sh --vunetid <your-vunetid> --das5id <your-das5-id>

and aggregate and normalize the raw results:

```bash
python3 scripts/analyze_results.py \
  --input results/das5/benchmark_results.csv \
  --output-dir results/analysis \
  --metric-weights pkg=1,dram=0,time=0,memory=0
```

The analysis script produces summary CSV files such as:

```text
summary_raw.csv
summary_normalized.csv
```

Normalization is performed per workload, input size, and metric. A normalized value of `1.0` means the best observed baseline implementation for that configuration.

## Plotting results

Use the plotting script to generate thesis figures:

```bash
python3 scripts/plot_results.py \
  --input results/analysis/summary_normalized.csv \
  --output-dir results/plots
```

The plotting script creates figures for:

- CPU package energy per workload,
- runtime per workload,
- peak RSS per workload,
- baseline-normalized heatmaps,
- JSON parser variants,
- isolated versus composed pipeline comparisons.

## Metrics

The benchmark records the following main metrics:

| Metric | Description |
|---|---|
| `elapsed_s` | Wall-clock runtime in seconds |
| `energy_pkg_j` | CPU package energy in joules |
| `energy_dram_j` | DRAM energy in joules |
| `rss_peak_bytes` | Peak resident set size in bytes |

RAPL counters are read in microjoules through Linux powercap files such as `energy_uj` and converted to joules in the result files.

Peak RSS is sampled during benchmark execution and represents the highest observed resident memory usage of the benchmark subprocess.

## Reproducibility notes

Each run stores metadata and environment information alongside the results. This includes:

- timestamp,
- hostname,
- operating system and kernel,
- CPU information,
- memory information,
- loaded modules,
- toolchain versions,
- RAPL domains,
- Git commit.

The thesis run was executed on DAS-5 node `node065`, using dual-socket Intel Xeon E5-2630 v3 hardware with RAPL package and DRAM domains available for both sockets.

## Implementation notes

The benchmark suite aims to keep the high-level algorithmic structure comparable across languages. However, the implementations are not identical at the machine-code level. Differences can arise from:

- standard library behavior,
- external parser libraries,
- runtime systems,
- garbage collection,
- bounds checks,
- compiler optimization,
- vectorization,
- interpreter overhead.

For example, compiler diagnostics for the SHA-256/XOR workload showed that the C XOR loops were not vectorized, Go retained some bounds checks, while Julia generated vector instructions for the XOR loops. These implementation-level effects are part of the benchmark interpretation.

## Limitations

The benchmark suite is controlled and reproducible, but it is not a full production ETL system. It is ETL-inspired: the workloads are based on recurring data-processing stages rather than on a distributed production infrastructure.

Important limitations include:

- only four programming languages are evaluated,
- only a limited number of workload classes are included,
- results depend on selected libraries and implementation style,
- CPU frequency and core placement may affect measurements,
- RAPL measures CPU package and DRAM energy, not total wall-socket energy,
- peak RSS sampling may miss very short-lived allocation spikes.

## Citation

If you use this repository, please cite it using the metadata provided in [`CITATION.cff`](CITATION.cff).

GitHub can automatically detect this file and show a **Cite this repository** button on the repository page.

Recommended citation information:

```text
Jonathan Davidson. Realistic Energy. Version 1.0. Vrije Universiteit, 2026.
https://github.com/J-Davidson01/realistic-energy
```

## Contributing and future work

Contributions are welcome, especially when they improve reproducibility, measurement quality, or extend the benchmark suite in a comparable way.

Potential extensions include:

* **CPU pinning**
  Pin the benchmark subprocess to a specific CPU core and run measurement tasks, such as RSS sampling, on a separate core. Energy measurements could also be restricted to the core or package on which the benchmark is executed. This would reduce background noise from unrelated cores and improve the comparability of CPU package energy measurements.

* **Recording time-series measurements**
  Extend the runner to record RSS samples, CPU package energy counters, and DRAM energy counters during benchmark execution. These measurements could then be visualized per language and workload to show memory growth, energy peaks, and runtime or garbage-collection effects, instead of only reporting aggregate values such as total energy and peak RSS.

* **Adding more programming languages**
  Add languages with different runtime and memory-management strategies. For example, adding Java would make it possible to compare JVM garbage collection with CPython reference counting, Go's tracing garbage collector, Julia's runtime system, and C's manual memory management.

* **Adding implementation variants**
  Add additional implementations within the same language to study how much implementation style affects the result. For example, a NumPy-based Python variant would provide a useful comparison with the current explicit Python byte-loop implementations.

* **Adding more workload types**
  Extend the benchmark suite with additional application-level workload types, such as compression, networking, concurrency, or database interaction.

When contributing benchmark changes, please document:

* which workload, language, or script was changed;
* whether the high-level algorithmic work changed;
* whether new libraries, compiler flags, or runtime options were introduced;
* whether the new results remain comparable to previous results;
* the command used to reproduce the benchmark run.

## License

license: Apache-2.0