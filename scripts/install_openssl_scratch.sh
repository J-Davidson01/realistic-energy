#!/usr/bin/env bash
set -euo pipefail

OPENSSL_VERSION="1.1.1w"
TOOLS_ROOT="/var/scratch/${USER}/realistic-energy/tools"
SRC_ROOT="${TOOLS_ROOT}/src"
OPENSSL_PREFIX="${TOOLS_ROOT}/openssl"

mkdir -p "${SRC_ROOT}"
cd "${SRC_ROOT}"

echo "[openssl] Installing OpenSSL ${OPENSSL_VERSION}"
echo "[openssl] Prefix: ${OPENSSL_PREFIX}"
echo "[openssl] Host: $(hostname)"

if [[ ! -f "openssl-${OPENSSL_VERSION}.tar.gz" ]]; then
  wget "https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz"
fi

rm -rf "openssl-${OPENSSL_VERSION}"
tar -xzf "openssl-${OPENSSL_VERSION}.tar.gz"
cd "openssl-${OPENSSL_VERSION}"

./Configure linux-x86_64 \
  --prefix="${OPENSSL_PREFIX}" \
  --openssldir="${OPENSSL_PREFIX}/ssl" \
  no-shared

make -j"$(nproc)"
make install_sw

echo "[openssl] Installed:"
"${OPENSSL_PREFIX}/bin/openssl" version
ls -l "${OPENSSL_PREFIX}/include/openssl/evp.h"
ls -l "${OPENSSL_PREFIX}/lib/libcrypto.a"
