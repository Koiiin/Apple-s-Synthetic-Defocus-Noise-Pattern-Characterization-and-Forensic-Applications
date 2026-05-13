#!/usr/bin/env bash
# Reproduce toàn bộ kết quả từ đầu
set -euo pipefail

echo "=== Step 1: Original images ==="
bash scripts/run_original.sh

echo "=== Step 2: Robustness experiments ==="
bash scripts/run_robustness.sh

echo "=== Done. Kết quả trong results/ ==="
