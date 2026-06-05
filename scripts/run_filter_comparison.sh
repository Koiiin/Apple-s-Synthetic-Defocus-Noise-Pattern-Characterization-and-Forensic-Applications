#!/usr/bin/env bash
# =============================================================================
# run_filter_comparison.sh
# Enhancement: compare 3 residual filters (box 5×5, Gaussian σ=1.0, σ=2.0)
# across original + all processed conditions.
#
# Box filter results already exist in results/ from previous pipeline runs
# (run_original.sh + run_robustness.sh), so we COPY them instead of re-running.
# Only gauss1 and gauss2 are executed fresh.
#
# Output: results_residual/<condition>/<filter>/
# =============================================================================
set -euo pipefail

BP="data/bp"
LABELS="data/labels.csv"
OUT_ROOT="results_residual"
NEW_FILTERS=(gauss1 gauss2)

echo "============================================="
echo " Filter Comparison Experiment"
echo " Box results: copied from results/"
echo " New filters: ${NEW_FILTERS[*]}"
echo " Output:      ${OUT_ROOT}/"
echo "============================================="

# =============================================================================
# Helper: copy existing box results from results/<cond>/ → results_residual/<cond>/box/
# =============================================================================
copy_box_results() {
  local src="$1"    # e.g. results/original
  local dst="$2"    # e.g. results_residual/original/box

  if [ ! -d "$src" ]; then
    echo "  SKIP box copy: $src not found"
    return
  fi

  mkdir -p "$dst"
  for f in sdnp_results.csv metrics.json confusion_matrix.png roc_curve.png; do
    if [ -f "$src/$f" ]; then
      cp "$src/$f" "$dst/$f"
    fi
  done
  echo "  Copied box results: $src → $dst"
}

# =============================================================================
# 1. Original images (data/raw/apple_sdnp_official)
# =============================================================================
echo ""
echo "=== [original] Copying box results ==="
copy_box_results "results/original" "$OUT_ROOT/original/box"

for flt in "${NEW_FILTERS[@]}"; do
  echo ""
  echo "=== [original] filter=$flt ==="
  python src/sdnp_detector.py \
    --images data/raw/apple_sdnp_official --bp "$BP" --labels "$LABELS" --beta 0.0072 \
    --filter "$flt" \
    --output "$OUT_ROOT/original/$flt/sdnp_results.csv"
  python src/evaluate.py \
    --pred "$OUT_ROOT/original/$flt/sdnp_results.csv" \
    --labels "$LABELS" \
    --output "$OUT_ROOT/original/$flt/"
done

# =============================================================================
# 2. Non-resize processed conditions
# =============================================================================
NON_RESIZE_CONDITIONS=(exif_stripped jpeg_q95 jpeg_q80 jpeg_q60)

for cond in "${NON_RESIZE_CONDITIONS[@]}"; do
  img_dir="data/processed/$cond"
  if [ ! -d "$img_dir" ]; then
    echo "SKIP $cond: $img_dir not found"
    continue
  fi

  echo ""
  echo "=== [$cond] Copying box results ==="
  copy_box_results "results/$cond" "$OUT_ROOT/$cond/box"

  for flt in "${NEW_FILTERS[@]}"; do
    echo ""
    echo "=== [$cond] filter=$flt ==="
    python src/sdnp_detector.py \
      --images "$img_dir" --bp "$BP" --labels "$LABELS" --beta 0.0072 \
      --filter "$flt" \
      --output "$OUT_ROOT/$cond/$flt/sdnp_results.csv"
    python src/evaluate.py \
      --pred "$OUT_ROOT/$cond/$flt/sdnp_results.csv" \
      --labels "$LABELS" \
      --output "$OUT_ROOT/$cond/$flt/"
  done
done

# =============================================================================
# 3. Resize conditions (need --scale-aware)
# =============================================================================
RESIZE_CONDITIONS=(resize_05 resize_025)

for cond in "${RESIZE_CONDITIONS[@]}"; do
  img_dir="data/processed/$cond"
  if [ ! -d "$img_dir" ]; then
    echo "SKIP $cond: $img_dir not found"
    continue
  fi

  echo ""
  echo "=== [$cond] Copying box results ==="
  copy_box_results "results/$cond" "$OUT_ROOT/$cond/box"

  for flt in "${NEW_FILTERS[@]}"; do
    echo ""
    echo "=== [$cond] filter=$flt (scale-aware) ==="
    python src/sdnp_detector.py \
      --images "$img_dir" --bp "$BP" --labels "$LABELS" --beta 0.0072 \
      --filter "$flt" --scale-aware \
      --output "$OUT_ROOT/$cond/$flt/sdnp_results.csv"
    python src/evaluate.py \
      --pred "$OUT_ROOT/$cond/$flt/sdnp_results.csv" \
      --labels "$LABELS" \
      --output "$OUT_ROOT/$cond/$flt/"
  done
done

# =============================================================================
# 4. Generate comparison summary
# =============================================================================
echo ""
echo "============================================="
echo " Generating comparison summary..."
echo "============================================="
python src/compare_filters.py \
  --results-dir "$OUT_ROOT" \
  --output "$OUT_ROOT/comparison_summary.csv"

echo ""
echo "Done! All results in: $OUT_ROOT/"
echo "Summary table:        $OUT_ROOT/comparison_summary.csv"
