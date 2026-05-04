#!/usr/bin/env bash
set -euo pipefail

TOOLS_ROOT="${HOME}/.local/realistic-energy/tools"
SRC_ROOT="${TOOLS_ROOT}/src"

GO_VERSION="1.25.0"
GO_ROOT="${TOOLS_ROOT}/go"
GO_TARBALL="go${GO_VERSION}.linux-amd64.tar.gz"
GO_URL="https://go.dev/dl/${GO_TARBALL}"

OPENSSL_VERSION="1.1.1w"
OPENSSL_ROOT="${TOOLS_ROOT}/openssl"
OPENSSL_TARBALL="openssl-${OPENSSL_VERSION}.tar.gz"
OPENSSL_URL="https://www.openssl.org/source/${OPENSSL_TARBALL}"

mkdir -p "${TOOLS_ROOT}"
mkdir -p "${SRC_ROOT}"

echo "[setup] Host: $(hostname)"
echo "[setup] User: ${USER}"
echo "[setup] Tools root: ${TOOLS_ROOT}"
echo

# -----------------------------
# Go
# -----------------------------
echo "[setup] Installing Go ${GO_VERSION}"

if [[ -x "${GO_ROOT}/bin/go" ]]; then
  echo "[setup] Go already installed: $("${GO_ROOT}/bin/go" version)"
else
  cd "${SRC_ROOT}"

  echo "[setup] Downloading ${GO_URL}"
  wget -O "${GO_TARBALL}" "${GO_URL}"

  echo "[setup] Removing old Go root: ${GO_ROOT}"
  rm -rf "${GO_ROOT}"

  echo "[setup] Extracting Go into ${TOOLS_ROOT}"
  tar -xzf "${GO_TARBALL}" -C "${TOOLS_ROOT}"

  if [[ ! -x "${GO_ROOT}/bin/go" ]]; then
    echo "[setup] ERROR: Go install failed. Expected binary not found:"
    echo "        ${GO_ROOT}/bin/go"
    echo
    echo "[setup] Contents of ${TOOLS_ROOT}:"
    find "${TOOLS_ROOT}" -maxdepth 4 -print | sort | head -200
    exit 1
  fi

  echo "[setup] Go installed: $("${GO_ROOT}/bin/go" version)"
fi

echo

# -----------------------------
# OpenSSL
# -----------------------------
echo "[setup] Installing OpenSSL ${OPENSSL_VERSION}"

if [[ -f "${OPENSSL_ROOT}/include/openssl/evp.h" && -f "${OPENSSL_ROOT}/lib/libcrypto.a" ]]; then
  echo "[setup] OpenSSL already installed:"
  "${OPENSSL_ROOT}/bin/openssl" version || true
else
  cd "${SRC_ROOT}"

  echo "[setup] Downloading ${OPENSSL_URL}"
  wget -O "${OPENSSL_TARBALL}" "${OPENSSL_URL}"

  echo "[setup] Removing old OpenSSL root: ${OPENSSL_ROOT}"
  rm -rf "${OPENSSL_ROOT}"

  echo "[setup] Extracting OpenSSL"
  rm -rf "openssl-${OPENSSL_VERSION}"
  tar -xzf "${OPENSSL_TARBALL}"
  cd "openssl-${OPENSSL_VERSION}"

  echo "[setup] Configuring OpenSSL"
  ./Configure linux-x86_64 \
    --prefix="${OPENSSL_ROOT}" \
    --openssldir="${OPENSSL_ROOT}/ssl" \
    no-shared

  echo "[setup] Building OpenSSL"
  make -j"$(nproc)"

  echo "[setup] Installing OpenSSL"
  make install_sw

  if [[ ! -f "${OPENSSL_ROOT}/include/openssl/evp.h" ]]; then
    echo "[setup] ERROR: OpenSSL header missing after install."
    exit 1
  fi

  if [[ ! -f "${OPENSSL_ROOT}/lib/libcrypto.a" ]]; then
    echo "[setup] ERROR: OpenSSL libcrypto.a missing after install."
    exit 1
  fi

  echo "[setup] OpenSSL installed:"
  "${OPENSSL_ROOT}/bin/openssl" version
fi

echo

# -----------------------------
# Final summary
# -----------------------------
echo "[setup] Final tool summary"
echo "  Go root:      ${GO_ROOT}"
echo "  Go binary:    ${GO_ROOT}/bin/go"
"${GO_ROOT}/bin/go" version

echo "  OpenSSL root: ${OPENSSL_ROOT}"
echo "  OpenSSL bin:  ${OPENSSL_ROOT}/bin/openssl"
"${OPENSSL_ROOT}/bin/openssl" version

echo
echo "[setup] Add this to PATH when needed:"
echo "  export PATH=\"${GO_ROOT}/bin:\$PATH\""
echo
echo "[setup] Done."