#!/usr/bin/env bash
# Run full pipeline trên ảnh gốc (không transform)
set -euo pipefail

IMAGES="data/raw"
BP="data/bp"
LABELS="data/labels.csv"
OUT="results/original"

python src/forensic_manifest.py --input "$IMAGES" --labels "$LABELS" --output "$OUT/manifest.csv"
python src/exif_baseline.py --input "$IMAGES" --output "results/exif_baseline.csv"
python src/sdnp_detector.py --images "$IMAGES" --bp "$BP" --labels "$LABELS" --beta 0.0072 --output "$OUT/sdnp_results.csv"
python src/evaluate.py --pred "$OUT/sdnp_results.csv" --baseline "results/exif_baseline.csv" --labels "$LABELS" --output "$OUT/"
python src/report_case.py --manifest "$OUT/manifest.csv" --pred "$OUT/sdnp_results.csv" --baseline "results/exif_baseline.csv" --output "$OUT/"

echo ""
echo "=== No-Rotation Baseline ==="
bash scripts/run_no_rotation.sh
