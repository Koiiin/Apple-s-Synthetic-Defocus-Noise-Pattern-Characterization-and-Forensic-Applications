#!/usr/bin/env bash
# Wrong-BP control experiment:
# Chạy detector với BP bị shuffle (phá huỷ spatial structure).
# Kỳ vọng: rho thấp, pred_label = 0 với tất cả ảnh → chứng minh detector
# không kích hoạt ngẫu nhiên, spatial structure của BP là cần thiết.
set -euo pipefail

IMAGES="data/raw"
BP="data/bp"
LABELS="data/labels.csv"
OUT="results/wrong_bp_control"

echo "=== Wrong-BP Control Experiment ==="
python src/sdnp_detector.py \
    --images "$IMAGES" \
    --bp "$BP" \
    --labels "$LABELS" \
    --beta 0.0072 \
    --shuffle-bp \
    --output "$OUT/sdnp_results.csv"

python src/evaluate.py \
    --pred "$OUT/sdnp_results.csv" \
    --output "$OUT/"

echo ""
echo "Kỳ vọng: TPR ~ 0, FPR ~ 0, tất cả rho << β = 0.0072"
echo "Nếu kết quả như vậy → detector không fire ngẫu nhiên."
