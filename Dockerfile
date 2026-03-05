FROM ubuntu:24.04

# 1. Install system dependencies
RUN apt update && apt install -y \
    build-essential \
    cmake \
    libssl-dev \
    python3 python3-pip python3-venv \
    golang \
    julia \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy benchmarks into container
WORKDIR /benchmarks
COPY . .

# 3. Build all C workloads
RUN find benchmarks -type f -name CMakeLists.txt -exec \
    sh -c 'cd "$(dirname "{}")" && mkdir -p build && cd build && cmake .. && make' \;

# -----------------------------
RUN find benchmarks -type f -name go.mod -exec \
    sh -c 'cd "$(dirname "{}")" && go build' \;

# 5. Install Python dependencies
RUN find benchmarks -type f -name requirements.txt -exec \
    sh -c 'cd "$(dirname "{}")" && pip install -r requirements.txt' \;

# 6. Install Julia environments
RUN find benchmarks -type f -name Project.toml -exec \
    sh -c 'cd "$(dirname "{}")" && julia --project=. -e "using Pkg; Pkg.instantiate()"'; \

# 7. Default entry point
CMD ["python3", "scripts/run_benchmarks.py"]