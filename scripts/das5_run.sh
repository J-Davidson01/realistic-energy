#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if PROJECT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
  :
elif PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

cd "$PROJECT_ROOT"

BENCHMARKS="sha256,json_parse,file_copy,pipeline_e2e,pipeline_e2e_stream"
MIN_SIZE="1048576"
MAX_SIZE="1073741824"
REGEN="0"
REBUILD="0"
SETUP_TOOLS="0"
RUN_BENCHMARKS="1"
PYTHON_VENV=".venv"

DATASETS_OUT_ROOT="/var/scratch/$USER/realistic-energy/datasets"
RESULTS_OUT_ROOT="/var/scratch/$USER/realistic-energy/results"

OPENSSL_ROOT="/var/scratch/$USER/realistic-energy/tools/openssl"
OPENSSL_INCLUDE_DIR="$OPENSSL_ROOT/include"
OPENSSL_CRYPTO_LIBRARY="$OPENSSL_ROOT/lib/libcrypto.a"

GO_ROOT="/var/scratch/$USER/realistic-energy/tools/go"
GO_VERSION="1.25.0"
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
  --datasets-out-root DIR  Directory where generated datasets are stored
  --results-out-root DIR   Directory where benchmark results are stored

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
    --datasets-out-root)
      DATASETS_OUT_ROOT="$2"
      shift 2
      ;;
    --results-out-root)
      RESULTS_OUT_ROOT="$2"
      shift 2
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
mkdir -p "$DATASETS_OUT_ROOT"
mkdir -p "$RESULTS_OUT_ROOT"
mkdir -p "$(dirname "$GO_ROOT")"

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
# 3b) Save environment / toolchain metadata
# -----------------------------
ENV_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ENV_TXT="results/native_environment_${ENV_TIMESTAMP}.txt"

echo "[native] Saving environment metadata to $ENV_TXT"

{
  echo "timestamp: $(date --iso-8601=seconds 2>/dev/null || date)"
  echo "hostname: $(hostname)"
  echo "user: $(whoami)"
  echo "working_directory: $(pwd)"
  echo

  echo "=== Kernel / OS ==="
  uname -a || true
  if [[ -f /etc/os-release ]]; then
    cat /etc/os-release
  fi
  echo

  echo "=== CPU ==="
  lscpu || true
  echo

  echo "=== Memory ==="
  free -h || true
  echo
  swapon --show || true
  echo

  echo "=== Loaded modules ==="
  if command -v module >/dev/null 2>&1; then
    module list 2>&1 || true
  else
    echo "module command not available"
  fi
  echo

  echo "=== Module availability snapshot ==="
  if command -v module >/dev/null 2>&1; then
    module --terse list 2>&1 || true
  else
    echo "module command not available"
  fi
  echo

  echo "=== Toolchain versions ==="
  command -v gcc >/dev/null 2>&1 && gcc --version | head -n 1 || echo "gcc: not found"
  command -v g++ >/dev/null 2>&1 && g++ --version | head -n 1 || echo "g++: not found"
  command -v cmake >/dev/null 2>&1 && cmake --version | head -n 1 || echo "cmake: not found"
  command -v pkg-config >/dev/null 2>&1 && pkg-config --version | sed 's/^/pkg-config: /' || echo "pkg-config: not found"
  command -v python >/dev/null 2>&1 && python --version || echo "python: not found"
  command -v python3 >/dev/null 2>&1 && python3 --version || echo "python3: not found"
  command -v pip >/dev/null 2>&1 && pip --version || echo "pip: not found"
  command -v go >/dev/null 2>&1 && go version || echo "go: not found"
  command -v julia >/dev/null 2>&1 && julia --version || echo "julia: not found"
  command -v git >/dev/null 2>&1 && git --version || echo "git: not found"
  echo

  echo "=== Python packages ==="
  if command -v python >/dev/null 2>&1; then
    python -m pip freeze || true
  fi
  echo

  echo "=== Julia environment status ==="
  if command -v julia >/dev/null 2>&1; then
    find benchmarks -type f -name Project.toml 2>/dev/null | while read -r proj; do
      dir="$(dirname "$proj")"
      echo "--- Julia project: $dir ---"
      julia --project="$dir" -e 'using Pkg; Pkg.status()' || true
      echo
    done
  else
    echo "julia: not found"
  fi
  echo

  echo "=== Go module info ==="
  if command -v go >/dev/null 2>&1; then
    go env GOVERSION GOOS GOARCH GOMOD GOPATH GOROOT || true
    if [[ -f go.mod ]]; then
      echo
      echo "--- go.mod ---"
      cat go.mod
    fi
    if [[ -f go.sum ]]; then
      echo
      echo "--- go.sum sha256 ---"
      sha256sum go.sum || true
    fi
  else
    echo "go: not found"
  fi
  echo

  echo "=== C library versions ==="
  if command -v pkg-config >/dev/null 2>&1; then
    pkg-config --modversion libcjson 2>/dev/null | sed 's/^/libcjson: /' || echo "libcjson: not found via pkg-config"
    pkg-config --modversion openssl 2>/dev/null | sed 's/^/openssl-pkgconfig: /' || echo "openssl: not found via pkg-config"
  fi
  command -v openssl >/dev/null 2>&1 && openssl version || echo "openssl binary: not found"
  echo

  echo "=== RAPL zones ==="
  if [[ -d /sys/class/powercap ]]; then
    for z in /sys/class/powercap/intel-rapl*; do
      if [[ -f "$z/name" ]]; then
        echo "$z"
        echo "  name: $(cat "$z/name")"
        [[ -f "$z/energy_uj" ]] && echo "  energy_uj: $(cat "$z/energy_uj")"
        [[ -f "$z/max_energy_range_uj" ]] && echo "  max_energy_range_uj: $(cat "$z/max_energy_range_uj")"
      fi
    done
  else
    echo "/sys/class/powercap not found"
  fi
  echo

  echo "=== Git revision ==="
  git rev-parse HEAD 2>/dev/null | sed 's/^/commit: /' || true
  git status --short 2>/dev/null || true
} > "$ENV_TXT"

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
  bench_dir="$DATASETS_OUT_ROOT/$b"

  if [[ ! -d "$bench_dir" ]]; then
    need_gen=1
  elif ! find "$bench_dir" -mindepth 1 -maxdepth 1 -type d | grep -q .; then
    need_gen=1
  fi
done

if [[ "$REGEN" == "1" || "$need_gen" == "1" ]]; then
  echo "[native] Generating datasets in $DATASETS_OUT_ROOT..."
  python scripts/generate_inputs.py \
    --benchmarks "$BENCHMARKS" \
    --min-size "$MIN_SIZE" \
    --max-size "$MAX_SIZE" \
    --out-root "$DATASETS_OUT_ROOT"
else
  echo "[native] Datasets already present in $DATASETS_OUT_ROOT; skipping generation."
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
      cmake -S "$dir" -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=Release \
        -DOPENSSL_INCLUDE_DIR=/usr/include \
        -DOPENSSL_CRYPTO_LIBRARY=/usr/lib64/libcrypto.so
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
  exec python -u scripts/run_benchmarks.py \
    --datasets-root "$DATASETS_OUT_ROOT" \
    --results-dir "$RESULTS_OUT_ROOT/benchmark_results.csv" \
    "${RUN_ARGS[@]}"
fi