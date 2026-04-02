#!/usr/bin/env bash
set -euo pipefail

cd /realistic-energy
mkdir -p results

BENCHMARKS="${BENCHMARKS:-sha256}"
MIN_SIZE="${MIN_SIZE:-1048576}" # 1 MiB
MAX_SIZE="${MAX_SIZE:-536870912}" # 512 MiB
REGEN="${REGEN:-0}"     # set to 1 to force regen datasets
REBUILD="${REBUILD:-0}" # set to 1 to force rebuild workloads

# -----------------------------
# 1) Generate datasets
# -----------------------------
need_gen=0
for b in ${BENCHMARKS//,/ }; do
  if [[ ! -d "datasets/$b" ]]; then
    need_gen=1
  else
    # if folder exists but empty, also generate
    if ! find "datasets/$b" -mindepth 1 -maxdepth 1 -type d | grep -q .; then
      need_gen=1
    fi
  fi
done

if [[ "$REGEN" == "1" || "$need_gen" == "1" ]]; then
  echo "[entrypoint] Generating datasets for: $BENCHMARKS"
  python3 scripts/generate_inputs.py \
    --benchmarks "$BENCHMARKS" \
    --min-size "$MIN_SIZE" \
    --max-size "$MAX_SIZE"
else
  echo "[entrypoint] Datasets already present; skipping generation."
fi

# -----------------------------
# 2) Install Python deps
# -----------------------------
echo "[entrypoint] Installing Python dependencies..."
find benchmarks -type f -name requirements.txt 2>/dev/null | while read -r req; do
  echo "  pip3 install -r $req"
  pip3 install --break-system-packages -r "$req"
done
[[ -f scripts/requirements.txt ]] && pip3 install --break-system-packages -r scripts/requirements.txt

# -----------------------------
# 3) Instantiate Julia envs
# -----------------------------
echo "[entrypoint] Instantiating Julia environments..."
find benchmarks -type f -name Project.toml 2>/dev/null | while read -r proj; do
  dir="$(dirname "$proj")"
  echo "  julia --project=$dir -e 'Pkg.resolve(); Pkg.instantiate()'"
  julia --project="$dir" -e 'using Pkg; Pkg.resolve(); Pkg.instantiate()'
done

# -----------------------------
# 4) Build C workloads (CMake)
# -----------------------------
echo "[entrypoint] Building C workloads..."
find benchmarks -type f -name CMakeLists.txt 2>/dev/null | while read -r cmakefile; do
  dir="$(dirname "$cmakefile")"
  build_dir="$dir/build"

  if [[ "$REBUILD" == "1" || ! -d "$build_dir" ]]; then
    mkdir -p "$build_dir"
    cmake -S "$dir" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release
    cmake --build "$build_dir" -j"$(nproc)"
  else
    echo "  (skip) $dir already built"
  fi
done

# -----------------------------
# 5) Build Go workloads
# -----------------------------
echo "[entrypoint] Building Go workloads..."
find benchmarks -type f -name '*_main.go' 2>/dev/null | while read -r mainfile; do
  dir="$(dirname "$mainfile")"
  base="$(basename "$mainfile" _main.go)"
  out="$dir/${base}_go"

  if [[ "$REBUILD" == "1" || ! -f "$out" ]]; then
    echo "  building $dir -> $out"
    (cd "$dir" && go build -o "$(basename "$out")" .)
  else
    echo "  (skip) $dir already built"
  fi
done

echo "[entrypoint] Setup complete."

# -----------------------------
# 6) Run command (default: run_benchmarks.py) including any args passed to the container
# -----------------------------
#exec python3 scripts/run_benchmarks.py "$@" #buffered outputs
exec python3 -u scripts/run_benchmarks.py "$@"