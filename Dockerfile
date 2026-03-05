FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /realistic-energy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    ca-certificates \
    git \
    python3 \
    python3-pip \
    golang-go \
    julia \
    && rm -rf /var/lib/apt/lists/*

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "scripts/run_benchmarks.py"]