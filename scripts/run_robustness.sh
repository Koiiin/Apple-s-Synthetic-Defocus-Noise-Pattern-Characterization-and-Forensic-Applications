#!/usr/bin/env bash
# Tạo biến thể ảnh và chạy detector trên từng điều kiện robustness
set -euo pipefail

BP="data/bp"
LABELS="data/labels.csv"

CONDITIONS=(
  # "exif_stripped:--strip-exif"
  # "jpeg_q95:--jpeg-quality 95"
  # "jpeg_q80:--jpeg-quality 80"
  # "jpeg_q60:--jpeg-quality 60"
  # "resize_05:--resize 0.5"
  "resize_025:--resize 0.25"
)

for entry in "${CONDITIONS[@]}"; do
  name="${entry%%:*}"
  args="${entry##*:}"
  echo "=== Condition: $name ==="
  # shellcheck disable=SC2086
  python src/transform_images.py --input data/raw --output "data/processed/$name" $args
  det_flags=(--images "data/processed/$name" --bp "$BP" --labels "$LABELS" --output "results/$name/sdnp_results.csv" --beta 0.0072)

  if [[ "$name" == "resize_05" || "$name" == "resize_025" ]]; then
    det_flags+=(--scale-aware)
  fi
  python src/sdnp_detector.py "${det_flags[@]}"

  # exif_stripped: chạy exif_baseline trên ảnh đã stripped để baseline phản ánh đúng (TPR=0)
  if [[ "$name" == "exif_stripped" ]]; then
    python src/exif_baseline.py --input "data/processed/$name" --output "results/$name/exif_baseline_stripped.csv"
    baseline_file="results/$name/exif_baseline_stripped.csv"
  else
    baseline_file="results/exif_baseline.csv"
  fi
  python src/evaluate.py --pred "results/$name/sdnp_results.csv" --baseline "$baseline_file" --labels "$LABELS" --output "results/$name/"
done