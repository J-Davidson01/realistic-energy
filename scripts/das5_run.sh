#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BENCHMARKS="sha256,json_parse,file_copy,pipeline_e2e,pipeline_e2e_stream"
MIN_SIZE="1048576"
MAX_SIZE="1073741824"
REGEN="0"
REBUILD="0"
SETUP_TOOLS="0"
RUN_BENCHMARKS="1"
PYTHON_VENV=".venv"

GO_VERSION="1.25.0"
GO_ROOT="$HOME/.local/go"
GO_TARBALL="go${GO_VERSION}.linux-amd64.tar.gz"
GO_URL="https://go.dev/dl/${GO_TARBALL}"

JULIA_MODULE="julia/1.11.4"
CMAKE_MODULE="cmake/3.24.2"

usage() {
  cat <<EOF
Usage: $0 [setup options] [-- benchmark options]

Setup options:
  --setup-tools           Install missing user-local tools, currently Go only
  --regen                 Regenerate datasets
  --rebuild               Rebuild C/Go binaries
  --benchmarks LIST       Benchmarks to generate/build/run
  --min-dataset-size BYTES
  --max-dataset-size BYTES
  --no-run                Only setup/build/generate, do not run benchmarks
  --go-version VERSION    Go version to install locally if Go is missing
  --julia-module MODULE   Julia module to load
  --cmake-module MODULE   CMake module to load
  -h, --help              Show this help

Everything after -- is passed to scripts/run_benchmarks.py.

Examples:
  $0 --setup-tools --regen --rebuild --no-run
  $0 --rebuild -- --verify --iterations 25 --repetitions 5 --max-dataset-size 1073741824
  $0 -- --benchmark sha256 --languages c,go --iterations 10 --repetitions 3
  prun -v -1 -np 1 $0 -- --benchmark sha256 --languages c --iterations 1 --repetitions 1
EOF
}

RUN_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup-tools)
      SETUP_TOOLS="1"
      shift
      ;;
    --install-deps)
      echo "[native] Note: --install-deps is not supported on DAS-5 without sudo."
      echo "[native] Treating it as --setup-tools for user-local tool setup."
      SETUP_TOOLS="1"
      shift
      ;;
    --regen)
      REGEN="1"
      shift
      ;;
    --rebuild)
      REBUILD="1"
      shift
      ;;
    --benchmarks)
      BENCHMARKS="$2"
      shift 2
      ;;
    --min-dataset-size)
      MIN_SIZE="$2"
      shift 2
      ;;
    --max-dataset-size)
      MAX_SIZE="$2"
      shift 2
      ;;
    --no-run)
      RUN_BENCHMARKS="0"
      shift
      ;;
    --go-version)
      GO_VERSION="$2"
      GO_TARBALL="go${GO_VERSION}.linux-amd64.tar.gz"
      GO_URL="https://go.dev/dl/${GO_TARBALL}"
      shift 2
      ;;
    --julia-module)
      JULIA_MODULE="$2"
      shift 2
      ;;
    --cmake-module)
      CMAKE_MODULE="$2"
      shift 2
      ;;
    --)
      shift
      RUN_ARGS=("$@")
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown setup option: $1"
      echo "Use -- before benchmark arguments."
      usage
      exit 1
      ;;
  esac
done

mkdir -p results

echo "[native] Project root: $PROJECT_ROOT"
echo "[native] Benchmarks: $BENCHMARKS"
echo "[native] Dataset size range: $MIN_SIZE .. $MAX_SIZE"

# -----------------------------
# 1) Load DAS-5 modules
# -----------------------------
if command -v module >/dev/null 2>&1; then
  echo "[native] Environment modules available."

  if [[ -n "$CMAKE_MODULE" ]]; then
    echo "[native] Loading CMake module: $CMAKE_MODULE"
    module load "$CMAKE_MODULE" || echo "[native] Warning: failed to load $CMAKE_MODULE"
  fi

  if [[ -n "$JULIA_MODULE" ]]; then
    echo "[native] Loading Julia module: $JULIA_MODULE"
    module load "$JULIA_MODULE" || echo "[native] Warning: failed to load $JULIA_MODULE"
  fi
else
  echo "[native] Environment modules command not found. Continuing with existing PATH."
fi

# -----------------------------
# 2) Optional user-local tool setup
# -----------------------------
mkdir -p "$HOME/.local/bin"

if [[ "$SETUP_TOOLS" == "1" ]]; then
  if ! command -v go >/dev/null 2>&1; then
    echo "[native] Go not found. Installing Go $GO_VERSION locally to $GO_ROOT"

    tmpdir="$(mktemp -d)"
    wget -q "$GO_URL" -O "$tmpdir/$GO_TARBALL"

    rm -rf "$GO_ROOT"
    mkdir -p "$HOME/.local"
    tar -xzf "$tmpdir/$GO_TARBALL" -C "$HOME/.local"

    rm -rf "$tmpdir"

    echo "[native] Go installed locally."
  else
    echo "[native] Go already available: $(go version)"
  fi
fi

if [[ -d "$GO_ROOT/bin" ]]; then
  export PATH="$GO_ROOT/bin:$PATH"
fi

# -----------------------------
# 3) Print tool versions
# -----------------------------
echo "[native] Toolchain check:"

if command -v gcc >/dev/null 2>&1; then
  echo "  gcc:    $(gcc --version | head -n 1)"
else
  echo "  gcc:    not found"
fi

if command -v cmake >/dev/null 2>&1; then
  echo "  cmake:  $(cmake --version | head -n 1)"
else
  echo "  cmake:  not found"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "  python: $(python3 --version)"
else
  echo "  python: not found"
fi

if command -v go >/dev/null 2>&1; then
  echo "  go:     $(go version)"
else
  echo "  go:     not found"
fi

if command -v julia >/dev/null 2>&1; then
  echo "  julia:  $(julia --version)"
else
  echo "  julia:  not found"
fi

if command -v pkg-config >/dev/null 2>&1; then
  echo "  pkg-config: found"
else
  echo "  pkg-config: not found"
fi

# -----------------------------
# 4) Python virtual environment
# -----------------------------
echo "[native] Preparing Python virtual environment..."

if [[ ! -d "$PYTHON_VENV" ]]; then
  python3 -m venv "$PYTHON_VENV"
fi

# shellcheck disable=SC1091
source "$PYTHON_VENV/bin/activate"

python -m pip install --upgrade pip wheel setuptools

if [[ -f scripts/requirements.txt ]]; then
  echo "[native] Installing script Python requirements..."
  python -m pip install -r scripts/requirements.txt
fi

find benchmarks -type f -name requirements.txt 2>/dev/null | while read -r req; do
  if [[ -s "$req" ]]; then
    echo "[native] Installing Python requirements: $req"
    python -m pip install -r "$req"
  fi
done

# -----------------------------
# 5) Generate datasets
# -----------------------------
need_gen=0

for b in ${BENCHMARKS//,/ }; do
  if [[ ! -d "datasets/$b" ]]; then
    need_gen=1
  elif ! find "datasets/$b" -mindepth 1 -maxdepth 1 -type d | grep -q .; then
    need_gen=1
  fi
done

if [[ "$REGEN" == "1" || "$need_gen" == "1" ]]; then
  echo "[native] Generating datasets..."
  python scripts/generate_inputs.py \
    --benchmarks "$BENCHMARKS" \
    --min-size "$MIN_SIZE" \
    --max-size "$MAX_SIZE" \
    --out-root datasets
else
  echo "[native] Datasets already present; skipping generation."
fi

# -----------------------------
# 6) Instantiate Julia projects
# -----------------------------
if command -v julia >/dev/null 2>&1; then
  echo "[native] Instantiating Julia environments..."

  find benchmarks -type f -name Project.toml 2>/dev/null | while read -r proj; do
    dir="$(dirname "$proj")"
    echo "  julia --project=$dir -e 'using Pkg; Pkg.instantiate()'"
    julia --project="$dir" -e 'using Pkg; Pkg.instantiate()'
  done
else
  echo "[native] Julia not found; skipping Julia environment setup."
fi

# -----------------------------
# 7) Build C workloads
# -----------------------------
echo "[native] Building C workloads..."

if ! command -v cmake >/dev/null 2>&1; then
  echo "[native] CMake not found; skipping C builds."
else
  if command -v pkg-config >/dev/null 2>&1; then
    if pkg-config --exists libcjson; then
      echo "[native] libcjson detected through pkg-config."
    else
      echo "[native] Warning: libcjson not detected through pkg-config."
      echo "[native] C targets depending on cJSON may fail to configure/build."
    fi
  fi

  find benchmarks -type f -name CMakeLists.txt 2>/dev/null | while read -r cmakefile; do
    dir="$(dirname "$cmakefile")"
    build_dir="$dir/build"

    if [[ "$REBUILD" == "1" || ! -d "$build_dir" ]]; then
      echo "  building C workload in $dir"
      mkdir -p "$build_dir"
      cmake -S "$dir" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release
      cmake --build "$build_dir" -j"$(nproc)"
    else
      echo "  (skip) $dir already built"
    fi
  done
fi

# -----------------------------
# 8) Prepare Go module
# -----------------------------
if command -v go >/dev/null 2>&1; then
  echo "[native] Preparing Go module..."

  if [[ ! -f go.mod ]]; then
    echo "  go.mod not found; creating root module realistic-energy"
    go mod init realistic-energy
  fi

  go mod tidy
else
  echo "[native] Go not found; skipping Go module setup and Go builds."
fi

# -----------------------------
# 9) Build Go workloads
# -----------------------------
if command -v go >/dev/null 2>&1; then
  echo "[native] Building Go workloads..."

  find benchmarks -type f -name '*_main.go' 2>/dev/null | while read -r mainfile; do
    dir="$(dirname "$mainfile")"
    base="$(basename "$mainfile" _main.go)"
    out="$dir/${base}_go"

    if [[ "$REBUILD" == "1" || ! -f "$out" ]]; then
      echo "  building Go workload in $dir -> $out"
      (cd "$dir" && go build -o "$(basename "$out")" .)
    else
      echo "  (skip) $dir already built"
    fi
  done
else
  echo "[native] Go not available; skipping Go builds."
fi

# -----------------------------
# 10) RAPL visibility check
# -----------------------------
echo "[native] Checking RAPL zones..."

if [[ -d /sys/class/powercap ]]; then
  find /sys/class/powercap -maxdepth 2 -name energy_uj -print | sort | while read -r energy_file; do
    zone_dir="$(dirname "$energy_file")"
    if [[ -f "$zone_dir/name" ]]; then
      echo "  $zone_dir: $(cat "$zone_dir/name")"
    else
      echo "  $zone_dir"
    fi
  done
else
  echo "  /sys/class/powercap not found."
fi

echo "[native] Setup complete."

# -----------------------------
# 11) Run benchmarks
# -----------------------------
if [[ "$RUN_BENCHMARKS" == "1" ]]; then
  echo "[native] Running benchmarks..."
  exec python -u scripts/run_benchmarks.py "${RUN_ARGS[@]}"
fi