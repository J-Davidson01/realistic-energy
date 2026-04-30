#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BENCHMARKS="sha256,json_parse,file_copy,pipeline_e2e,pipeline_e2e_stream"
MIN_SIZE="1048576"
MAX_SIZE="8589934592"
REGEN="0"
REBUILD="0"
INSTALL_DEPS="0"
RUN_BENCHMARKS="1"
JULIA_VERSION="1.12.5"
PYTHON_VENV=".venv"

usage() {
  cat <<EOF
Usage: $0 [setup options] [-- benchmark options]

Setup options:
  --install-deps          Install Debian packages and Julia
  --regen                 Regenerate datasets
  --rebuild               Rebuild C/Go binaries
  --benchmarks LIST       Benchmarks to generate/build/run
  --min-size BYTES        Minimum dataset size
  --max-size BYTES        Maximum dataset size
  --no-run                Only setup/build/generate, do not run benchmarks
  --julia-version VER     Julia version to install if missing
  -h, --help              Show this help

Everything after -- is passed to scripts/run_benchmarks.py.

Examples:
  $0 --install-deps --regen --rebuild -- --verify --iterations 25 --repetitions 5
  $0 --rebuild --benchmarks sha256,json_parse -- --languages c,go --iterations 50
  $0 --no-run --install-deps --rebuild
EOF
}

RUN_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-deps)
      INSTALL_DEPS="1"
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
    --min-size)
      MIN_SIZE="$2"
      shift 2
      ;;
    --max-size)
      MAX_SIZE="$2"
      shift 2
      ;;
    --no-run)
      RUN_BENCHMARKS="0"
      shift
      ;;
    --julia-version)
      JULIA_VERSION="$2"
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

# -----------------------------
# 1) Install host dependencies
# -----------------------------
if [[ "$INSTALL_DEPS" == "1" ]]; then
  echo "[native] Installing Debian dependencies..."

  sudo apt update
  sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    libcjson-dev \
    ca-certificates \
    git \
    curl \
    wget \
    xz-utils \
    python3 \
    python3-venv \
    python3-pip \
    golang-go \
    htop \
    linux-cpupower

  if ! command -v julia >/dev/null 2>&1; then
    echo "[native] Installing Julia $JULIA_VERSION to /opt/julia..."

    tmpdir="$(mktemp -d)"
    wget -q "https://julialang-s3.julialang.org/bin/linux/x64/1.12/julia-${JULIA_VERSION}-linux-x86_64.tar.gz" \
      -O "$tmpdir/julia.tar.gz"

    sudo rm -rf /opt/julia
    sudo mkdir -p /opt/julia
    sudo tar -xzf "$tmpdir/julia.tar.gz" -C /opt/julia --strip-components=1
    sudo ln -sf /opt/julia/bin/julia /usr/local/bin/julia

    rm -rf "$tmpdir"
  else
    echo "[native] Julia already available: $(julia --version)"
  fi
fi

# -----------------------------
# 2) Python virtual environment
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
# 3) Generate datasets
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
# 4) Instantiate Julia projects
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
# 5) Build C workloads
# -----------------------------
echo "[native] Building C workloads..."

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

# -----------------------------
# 6) Prepare Go module
# -----------------------------
if command -v go >/dev/null 2>&1; then
  echo "[native] Preparing Go module..."

  if [[ ! -f go.mod ]]; then
    echo "  go.mod not found; creating root module realistic-energy"
    go mod init realistic-energy
  fi

  go mod tidy
else
  echo "[native] Go not found; skipping Go module setup."
fi

# -----------------------------
# 7) Build Go workloads
# -----------------------------
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

# -----------------------------
# 8) RAPL visibility check
# -----------------------------
echo "[native] Checking RAPL zones..."

if [[ -d /sys/class/powercap ]]; then
  find /sys/class/powercap -maxdepth 2 -name energy_uj -print | while read -r energy_file; do
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
# 9) Run benchmarks
# -----------------------------
if [[ "$RUN_BENCHMARKS" == "1" ]]; then
  echo "[native] Running benchmarks..."
  exec python -u scripts/run_benchmarks.py "${RUN_ARGS[@]}"
fi