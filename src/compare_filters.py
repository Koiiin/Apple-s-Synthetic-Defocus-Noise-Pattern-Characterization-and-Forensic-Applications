"""
compare_filters.py
Aggregate filter comparison results from results_residual/ into a summary CSV
and print a formatted comparison table.

Compatible with both metrics formats:
  1) old format: metrics["bp_detector"]
  2) new format: metrics["at_paper_beta"], metrics["at_calibrated_beta"],
                 metrics["exif_baseline"], top-level roc_auc / avg_latency_ms

Usage:
    python src/compare_filters.py \
      --results-dir results_residual \
      --output results_residual/comparison_summary.csv
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np


# Accepted column names for newer / older sdnp_results.csv variants.
RHO_COLUMNS = ("rho", "rho_score", "score", "sdnp_rho")
LABEL_COLUMNS = ("label", "true_label", "y_true", "gt", "is_portrait")


def _first_present(row: dict, names: tuple[str, ...]) -> str:
    """Return first non-empty value from possible CSV column names."""
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_label(value: str) -> Optional[int]:
    """Normalize common binary label strings to 0/1."""
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "portrait", "positive", "pos"}:
        return 1
    if v in {"0", "false", "no", "nonportrait", "non_portrait", "negative", "neg"}:
        return 0
    return None


def collect_rho_stats(csv_path: Path) -> dict:
    """Read sdnp_results.csv and compute rho statistics split by label.

    This is intentionally tolerant of small schema changes: rho may be stored
    as rho/rho_score/score/sdnp_rho and labels may be label/true_label/y_true/...
    """
    rho_all, rho_portrait, rho_nonportrait = [], [], []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rho_raw = _first_present(row, RHO_COLUMNS)
            rho = _to_float(rho_raw)
            if rho is None:
                continue

            rho_all.append(rho)

            label_raw = _first_present(row, LABEL_COLUMNS)
            label = _normalize_label(label_raw)
            if label == 1:
                rho_portrait.append(rho)
            elif label == 0:
                rho_nonportrait.append(rho)

    return {
        "rho_mean": round(float(np.mean(rho_all)), 6) if rho_all else None,
        "rho_std": round(float(np.std(rho_all)), 6) if rho_all else None,
        "rho_portrait_mean": round(float(np.mean(rho_portrait)), 6) if rho_portrait else None,
        "rho_nonportrait_mean": round(float(np.mean(rho_nonportrait)), 6) if rho_nonportrait else None,
        "n_images": len(rho_all),
    }


def extract_metrics(metrics: dict) -> dict:
    """Flatten old/new metrics.json formats into one summary row."""
    row = {}

    mode = metrics.get("mode")
    row["mode"] = mode
    row["n_images"] = _to_int(metrics.get("n_samples"))
    row["n_positive"] = _to_int(metrics.get("n_positive"))
    row["roc_auc"] = _to_float(metrics.get("roc_auc"))
    row["avg_latency_ms"] = _to_float(metrics.get("avg_latency_ms"))

    if mode == "rho_only":
        row["rho_mean"] = _to_float(metrics.get("rho_mean"))
        row["rho_std"] = _to_float(metrics.get("rho_std"))
        return row

    # Old format: metrics["bp_detector"] contains the main hard-decision metrics.
    # New format: metrics["at_paper_beta"] contains the comparable paper-threshold metrics.
    primary = metrics.get("bp_detector") or metrics.get("at_paper_beta") or {}
    if primary:
        row["beta"] = _to_float(primary.get("beta"))
        row["accuracy"] = _to_float(primary.get("accuracy"))
        row["precision"] = _to_float(primary.get("precision"))
        row["recall_tpr"] = _to_float(primary.get("recall_tpr"))
        row["fpr"] = _to_float(primary.get("fpr"))
        row["f1"] = _to_float(primary.get("f1"))
        # Some old files may store roc_auc inside bp_detector.
        row["roc_auc"] = row["roc_auc"] if row["roc_auc"] is not None else _to_float(primary.get("roc_auc"))

    calibrated = metrics.get("at_calibrated_beta") or {}
    if calibrated:
        row["calibrated_beta"] = _to_float(calibrated.get("beta"))
        row["calibrated_accuracy"] = _to_float(calibrated.get("accuracy"))
        row["calibrated_precision"] = _to_float(calibrated.get("precision"))
        row["calibrated_recall_tpr"] = _to_float(calibrated.get("recall_tpr"))
        row["calibrated_fpr"] = _to_float(calibrated.get("fpr"))
        row["calibrated_f1"] = _to_float(calibrated.get("f1"))

    exif = metrics.get("exif_baseline") or {}
    if exif:
        row["exif_accuracy"] = _to_float(exif.get("accuracy"))
        row["exif_precision"] = _to_float(exif.get("precision"))
        row["exif_recall_tpr"] = _to_float(exif.get("recall_tpr"))
        row["exif_fpr"] = _to_float(exif.get("fpr"))
        row["exif_f1"] = _to_float(exif.get("f1"))

    return row


def _fmt(val, width=8):
    """Format a value for table display."""
    if val is None or val == "":
        return "-".rjust(width)
    if isinstance(val, float):
        return f"{val:.4f}".rjust(width)
    return str(val).rjust(width)


def main():
    parser = argparse.ArgumentParser(description="Aggregate filter comparison results.")
    parser.add_argument("--results-dir", required=True, help="Root results directory, e.g. results_residual/")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_path = Path(args.output)

    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    rows = []

    # Walk through condition/filter directories:
    # results_residual/<condition>/<filter>/{metrics.json,sdnp_results.csv}
    for condition_dir in sorted(results_dir.iterdir()):
        if not condition_dir.is_dir():
            continue
        condition = condition_dir.name

        for filter_dir in sorted(condition_dir.iterdir()):
            if not filter_dir.is_dir():
                continue
            filter_type = filter_dir.name

            metrics_path = filter_dir / "metrics.json"
            results_path = filter_dir / "sdnp_results.csv"

            row = {"condition": condition, "filter": filter_type}

            if metrics_path.exists():
                with open(metrics_path, encoding="utf-8") as f:
                    metrics = json.load(f)
                row.update(extract_metrics(metrics))

            # Prefer per-image rho stats from CSV when available because it can
            # provide portrait/non-portrait split not present in metrics.json.
            if results_path.exists():
                stats = collect_rho_stats(results_path)
                for key, value in stats.items():
                    if value is not None:
                        row[key] = value

            # Keep rows that have at least one data file. This avoids creating
            # empty rows for accidentally-created folders.
            if metrics_path.exists() or results_path.exists():
                rows.append(row)

    if not rows:
        print("No results found in", results_dir)
        return

    fieldnames = [
        "condition", "filter", "mode", "n_images", "n_positive",
        "beta", "accuracy", "precision", "recall_tpr", "fpr", "f1", "roc_auc",
        "avg_latency_ms",
        "calibrated_beta", "calibrated_accuracy", "calibrated_precision",
        "calibrated_recall_tpr", "calibrated_fpr", "calibrated_f1",
        "exif_accuracy", "exif_precision", "exif_recall_tpr", "exif_fpr", "exif_f1",
        "rho_mean", "rho_std", "rho_portrait_mean", "rho_nonportrait_mean",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    header = (
        f"{'Condition':<20} {'Filter':<10} {'N':>5} "
        f"{'Beta':>8} {'Acc':>8} {'Prec':>8} {'Recall':>8} {'FPR':>8} "
        f"{'F1':>8} {'AUC':>8} {'Latency':>9} "
        f"{'rho_mean':>10} {'rho_port':>10} {'rho_non':>10}"
    )

    print("\n" + "=" * len(header))
    print("FILTER COMPARISON SUMMARY")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for row in rows:
        print(
            f"{row.get('condition', ''):<20} "
            f"{row.get('filter', ''):<10} "
            f"{str(row.get('n_images', '')):>5} "
            f"{_fmt(row.get('beta'))} "
            f"{_fmt(row.get('accuracy'))} "
            f"{_fmt(row.get('precision'))} "
            f"{_fmt(row.get('recall_tpr'))} "
            f"{_fmt(row.get('fpr'))} "
            f"{_fmt(row.get('f1'))} "
            f"{_fmt(row.get('roc_auc'))} "
            f"{_fmt(row.get('avg_latency_ms'), 9)} "
            f"{_fmt(row.get('rho_mean'), 10)} "
            f"{_fmt(row.get('rho_portrait_mean'), 10)} "
            f"{_fmt(row.get('rho_nonportrait_mean'), 10)}"
        )

    print("=" * len(header))
    print(f"\nSummary saved → {output_path}")


if __name__ == "__main__":
    main()
