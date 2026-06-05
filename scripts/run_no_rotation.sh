#!/usr/bin/env bash
# No-rotation baseline experiment:
# Chạy detector chỉ với BP ở 0°, bỏ qua 90°/180°/270°.
# Mục đích: đánh giá vai trò của bước xử lý orientation.
# Kỳ vọng: TPR thấp hơn full-rotation detector → chứng minh rotation test là cần thiết.
set -euo pipefail

IMAGES="data/raw/apple_sdnp_official"
BP="data/bp"
LABELS="data/labels.csv"
OUT="results/no_rotation_control"

echo "=== No-Rotation Baseline Experiment ==="
python src/sdnp_detector.py \
    --images "$IMAGES" \
    --bp "$BP" \
    --labels "$LABELS" \
    --beta 0.0072 \
    --no-rotation \
    --output "$OUT/sdnp_results.csv"

python src/evaluate.py \
    --pred "$OUT/sdnp_results.csv" \
    --output "$OUT/"

echo ""
echo "So sánh với results/original/metrics.json để thấy ảnh hưởng của rotation testing."
