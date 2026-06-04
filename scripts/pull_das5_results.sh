#!/usr/bin/env bash
set -euo pipefail

VUNETID="${VUNETID:-}"
DAS5ID="${DAS5ID:-}"
REMOTE_HOST="fs0.das5.cs.vu.nl"
REMOTE_DIR=""
LOCAL_DIR="../results/das5/"

usage() {
  echo "Usage: $0 --vunetid <id> --das5id <id> [--remote-dir <path>] [--local-dir <path>]"
  echo
  echo "Environment variable alternatives:"
  echo "  VUNETID=<id> DAS5ID=<id> $0"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vunetid)
      VUNETID="$2"
      shift 2
      ;;
    --das5id)
      DAS5ID="$2"
      shift 2
      ;;
    --remote-dir)
      REMOTE_DIR="$2"
      shift 2
      ;;
    --local-dir)
      LOCAL_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      ;;
  esac
done

if [[ -z "$VUNETID" ]]; then
  echo "Error: --vunetid or VUNETID is required"
  usage
fi

if [[ -z "$DAS5ID" ]]; then
  echo "Error: --das5id or DAS5ID is required"
  usage
fi

if [[ -z "$REMOTE_DIR" ]]; then
  REMOTE_DIR="/var/scratch/${DAS5ID}/realistic-energy/results/"
fi

mkdir -p "$LOCAL_DIR"

rsync -avz \
  -e "ssh -J ${VUNETID}@ssh.data.vu.nl" \
  "${DAS5ID}@${REMOTE_HOST}:${REMOTE_DIR}" \
  "$LOCAL_DIR"

echo "DAS-5 results copied to $LOCAL_DIR"
