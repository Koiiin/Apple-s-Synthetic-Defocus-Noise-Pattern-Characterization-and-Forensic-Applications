#!/usr/bin/env bash
# Run SDNP detector on non-Apple negative controls to estimate false positive rate.
set -euo pipefail

IMAGES="data/raw/fpr_controls/PrnuModernDevices"
BP="data/bp"
LABELS="data/labels_fpr_controls.csv"
OUT="results/fpr_controls"

python3 scripts/prepare_fpr_controls.py \
  --write-labels \
  --write-manifest \
  --write-summary

python3 src/forensic_manifest.py --input "$IMAGES" --labels "$LABELS" --output "$OUT/manifest.csv"
python3 src/sdnp_detector.py --images "$IMAGES" --bp "$BP" --labels "$LABELS" --beta 0.0072 --output "$OUT/sdnp_results.csv"
python3 src/evaluate.py --pred "$OUT/sdnp_results.csv" --labels "$LABELS" --output "$OUT/"
