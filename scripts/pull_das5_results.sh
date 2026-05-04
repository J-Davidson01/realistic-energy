#!/usr/bin/env bash
set -euo pipefail

VUNETID="jdn439"
DAS5ID="jdn439"

REMOTE_HOST="fs0.das5.cs.vu.nl"
REMOTE_DIR="~/realistic-energy/results/"
LOCAL_DIR="../results/das5/"

mkdir -p "$LOCAL_DIR"

rsync -avz \
  -e "ssh -J ${VUNETID}@ssh.data.vu.nl" \
  "${DAS5ID}@${REMOTE_HOST}:${REMOTE_DIR}" \
  "$LOCAL_DIR"

echo "DAS-5 results copied to $LOCAL_DIR"