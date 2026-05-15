for c in original exif_stripped jpeg_q95 jpeg_q80 jpeg_q60 no_rotation_control resize_05 resize_025; do
  case "$c" in
    exif_stripped)        baseline_arg="--baseline results/$c/exif_baseline_stripped.csv" ;;
    resize_05|resize_025) baseline_arg="" ;;
    *)                    baseline_arg="--baseline results/exif_baseline.csv" ;;
  esac
  python3 src/evaluate.py \
    --pred results/$c/sdnp_results.csv \
    --labels data/labels.csv \
    $baseline_arg \
    --output results/$c/
done