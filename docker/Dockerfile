FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /realistic-energy

# Core deps
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
    wget \
    xz-utils \
    libcjson-dev \
    && rm -rf /var/lib/apt/lists/*

# Julia (pinned version for reproducibility)
ARG JULIA_VERSION=1.11.3
RUN wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-${JULIA_VERSION}-linux-x86_64.tar.gz \
    && mkdir -p /opt/julia \
    && tar -xzf julia-${JULIA_VERSION}-linux-x86_64.tar.gz -C /opt/julia --strip-components=1 \
    && rm julia-${JULIA_VERSION}-linux-x86_64.tar.gz

ENV PATH="/opt/julia/bin:${PATH}"

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []