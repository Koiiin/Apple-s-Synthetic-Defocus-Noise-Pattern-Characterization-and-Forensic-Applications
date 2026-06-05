#!/usr/bin/env bash
# Download and validate PrnuModernDevices C01-C18 negative controls for FPR.
set -euo pipefail

PARALLEL_MAX="${PARALLEL_MAX:-2}"
RETRY="${RETRY:-10}"
RETRY_DELAY="${RETRY_DELAY:-10}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/4] Preparing official C01-C18 download config..."
python3 scripts/prepare_fpr_controls.py --make-curl-config --make-url-list

echo "[2/4] Downloading from official PrnuModernDevices URLs..."
echo "      parallel=${PARALLEL_MAX}, retry=${RETRY}, retry_delay=${RETRY_DELAY}s"
set +e
curl --parallel \
  --parallel-max "$PARALLEL_MAX" \
  --fail \
  --location \
  --continue-at - \
  --create-dirs \
  --retry "$RETRY" \
  --retry-delay "$RETRY_DELAY" \
  --config data/raw/fpr_controls/prnu_modern_c01_c18.curl
CURL_STATUS=$?
set -e

echo "[3/4] Writing labels, SHA-256 manifest, and completeness summary..."
python3 scripts/prepare_fpr_controls.py --write-labels --write-manifest --write-summary

echo "[4/4] Checking completeness..."
python3 - <<'PY'
import json
import sys
from pathlib import Path

summary_path = Path("data/raw/fpr_controls/PrnuModernDevices_C01_C18_summary.json")
summary = json.loads(summary_path.read_text(encoding="utf-8"))

present = summary["present_negative_files"]
expected = summary["expected_negative_files"]
missing = summary["missing_negative_files"]
invalid = summary["invalid_or_partial_image_files"]

print(f"valid_negative_files: {present}/{expected}")
print(f"missing_negative_files: {missing}")
print(f"invalid_or_partial_image_files: {invalid}")
print(f"summary: {summary_path}")

if present == expected and missing == 0 and invalid == 0:
    print("FPR controls are complete and ready.")
    sys.exit(0)

print("FPR controls are not complete yet. Re-run this script to resume.")
sys.exit(2)
PY
CHECK_STATUS=$?

if [[ "$CHECK_STATUS" -eq 0 ]]; then
  exit 0
fi

if [[ "$CURL_STATUS" -ne 0 ]]; then
  echo "curl exited with status $CURL_STATUS; downloads may still have partially progressed."
fi

exit "$CHECK_STATUS"
