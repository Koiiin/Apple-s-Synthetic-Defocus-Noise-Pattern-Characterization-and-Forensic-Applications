"""
compare_filters.py
Aggregate filter comparison results from results_residual/ into a summary CSV
and print a formatted comparison table.

Usage:
    python src/compare_filters.py --results-dir results_residual --output results_residual/comparison_summary.csv
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def collect_rho_stats(csv_path: Path) -> dict:
    """Read sdnp_results.csv and compute rho statistics split by label."""
    rho_all, rho_portrait, rho_nonportrait = [], [], []

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            rho_raw = row.get("rho", "").strip()
            label_raw = row.get("label", "").strip()

            if rho_raw == "":
                continue

            rho = float(rho_raw)
            rho_all.append(rho)

            if label_raw == "1":
                rho_portrait.append(rho)
            elif label_raw == "0":
                rho_nonportrait.append(rho)

    return {
        "rho_mean": round(float(np.mean(rho_all)), 6) if rho_all else None,
        "rho_std": round(float(np.std(rho_all)), 6) if rho_all else None,
        "rho_portrait_mean": round(float(np.mean(rho_portrait)), 6) if rho_portrait else None,
        "rho_nonportrait_mean": round(float(np.mean(rho_nonportrait)), 6) if rho_nonportrait else None,
        "n_images": len(rho_all),
    }


def _fmt(val, width=8):
    """Format a value for table display."""
    if val is None:
        return "-".rjust(width)
    if isinstance(val, float):
        return f"{val:.4f}".rjust(width)
    return str(val).rjust(width)


def main():
    parser = argparse.ArgumentParser(description="Aggregate filter comparison results.")
    parser.add_argument("--results-dir", required=True, help="Root results directory (results_residual/)")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_path = Path(args.output)

    rows = []

    # Walk through condition/filter directories
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

            # Read metrics.json
            if metrics_path.exists():
                with open(metrics_path) as f:
                    metrics = json.load(f)

                if metrics.get("mode") == "hard_decision":
                    bp = metrics.get("bp_detector", {})
                    row["accuracy"] = bp.get("accuracy")
                    row["precision"] = bp.get("precision")
                    row["recall_tpr"] = bp.get("recall_tpr")
                    row["fpr"] = bp.get("fpr")
                    row["f1"] = bp.get("f1")
                    row["roc_auc"] = bp.get("roc_auc")
                elif metrics.get("mode") == "rho_only":
                    row["rho_mean"] = metrics.get("rho_mean")
                    row["rho_std"] = metrics.get("rho_std")

            # Read per-image rho stats from CSV
            if results_path.exists():
                stats = collect_rho_stats(results_path)
                row["rho_mean"] = stats["rho_mean"]
                row["rho_std"] = stats["rho_std"]
                row["rho_portrait_mean"] = stats["rho_portrait_mean"]
                row["rho_nonportrait_mean"] = stats["rho_nonportrait_mean"]
                row["n_images"] = stats["n_images"]

            rows.append(row)

    if not rows:
        print("No results found in", results_dir)
        return

    # Write summary CSV
    fieldnames = [
        "condition", "filter", "n_images", "accuracy", "precision",
        "recall_tpr", "fpr", "f1", "roc_auc",
        "rho_mean", "rho_std", "rho_portrait_mean", "rho_nonportrait_mean",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Print formatted table
    header = (
        f"{'Condition':<20} {'Filter':<10} {'N':>5} "
        f"{'Acc':>8} {'Prec':>8} {'Recall':>8} {'FPR':>8} {'F1':>8} {'AUC':>8} "
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
            f"{_fmt(row.get('accuracy'))} "
            f"{_fmt(row.get('precision'))} "
            f"{_fmt(row.get('recall_tpr'))} "
            f"{_fmt(row.get('fpr'))} "
            f"{_fmt(row.get('f1'))} "
            f"{_fmt(row.get('roc_auc'))} "
            f"{_fmt(row.get('rho_mean'), 10)} "
            f"{_fmt(row.get('rho_portrait_mean'), 10)} "
            f"{_fmt(row.get('rho_nonportrait_mean'), 10)}"
        )

    print("=" * len(header))
    print(f"\nSummary saved → {output_path}")


if __name__ == "__main__":
    main()
