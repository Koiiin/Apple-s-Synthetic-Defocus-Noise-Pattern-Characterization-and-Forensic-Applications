"""
evaluate.py — metrics from prediction CSV + labels CSV.

Reports hard-decision metrics at two thresholds:
  - at_paper_beta: β = 0.0072 (paper benchmark, comparable across experiments).
  - at_calibrated_beta: β fitted on test-set negatives (FPR=0 upper bound,
    not for forensic decisions due to test-set bias).

Usage:
    python src/evaluate.py --pred results/original/sdnp_results.csv \
        --baseline results/exif_baseline.csv --labels data/labels.csv \
        --output results/original/
"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score, roc_curve, ConfusionMatrixDisplay,
)


def load_labels_by_stem(labels_path: Path | None) -> dict:
    """Stem-keyed so labels.csv entry ``foo.heic`` matches processed ``foo.jpg``."""
    out = {}
    if not labels_path or not labels_path.exists():
        return out
    with open(labels_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            fname = row.get("filename", "").strip()
            lab = row.get("label", "").strip()
            if fname and lab != "":
                out[Path(fname).stem] = int(lab)
    return out


def load_pred_rows(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "filename": r.get("filename", "").strip(),
                "label": r.get("label", "").strip(),
                "pred_label": r.get("pred_label", "").strip(),
                "rho": r.get("rho", "").strip(),
                "latency_ms": r.get("latency_ms", "").strip(),
            })
    return rows


def compute_fpr(y_true, y_pred) -> float:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return fp / (fp + tn) if (fp + tn) > 0 else 0.0


def _metrics_at_threshold(y_true: list, y_pred: list, beta: float) -> dict:
    return {
        "beta": round(beta, 6),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall_tpr": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "fpr": round(compute_fpr(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
    }


def evaluate(pred_path: Path, baseline_path: Path | None, output_dir: Path,
             labels_path: Path | None = None, beta_paper: float = 0.0072):
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_pred_rows(pred_path)
    stem_labels = load_labels_by_stem(labels_path)

    if stem_labels:
        for r in rows:
            stem = Path(r["filename"]).stem
            if stem in stem_labels:
                r["label"] = str(stem_labels[stem])

    # Recompute pred at paper β when rho is available; uniform across conditions.
    for r in rows:
        if r["rho"] != "":
            r["pred_label"] = "1" if float(r["rho"]) > beta_paper else "0"

    valid = [r for r in rows if r["label"] != "" and r["pred_label"] != ""]
    filename = [r["filename"] for r in valid]
    y_true = [int(r["label"]) for r in valid]
    y_pred_paper = [int(r["pred_label"]) for r in valid]

    rho_map = {r["filename"]: float(r["rho"]) for r in rows if r["rho"] != ""}
    latencies = [float(r["latency_ms"]) for r in rows if r["latency_ms"]]

    if not y_true:
        print("No hard-decision labels found. Running rho-only analysis.")

        rho_values = list(rho_map.values())

        if not rho_values:
            print("No rho values found.")
            return

        metrics = {
            "mode": "rho_only",
            "n_samples": len(rho_values),
            "rho_mean": round(float(np.mean(rho_values)), 6),
            "rho_std": round(float(np.std(rho_values)), 6),
            "rho_min": round(float(np.min(rho_values)), 6),
            "rho_max": round(float(np.max(rho_values)), 6),
            "avg_latency_ms": round(np.mean(latencies), 1) if latencies else None,
            "note": "No labels provided. Pass --labels for hard-decision metrics.",
        }

        metrics_path = output_dir / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"Metrics saved → {metrics_path}")
        print(json.dumps(metrics, indent=2))
        return

    y_scores = [rho_map.get(fn, 0.0) for fn in filename]
    has_rho = all(fn in rho_map for fn in filename)

    roc_auc = (round(roc_auc_score(y_true, y_scores), 4)
               if has_rho and len(set(y_true)) > 1 else None)

    metrics = {
        "mode": "hard_decision",
        "n_samples": len(y_true),
        "n_positive": int(sum(y_true)),
        "roc_auc": roc_auc,
        "avg_latency_ms": round(np.mean(latencies), 1) if latencies else None,
        "at_paper_beta": _metrics_at_threshold(y_true, y_pred_paper, beta_paper),
    }

    if has_rho:
        rho_neg = [rho_map[fn] for fn, t in zip(filename, y_true) if t == 0]
        if rho_neg:
            beta_cal = max(rho_neg) + 1e-6
            y_pred_cal = [1 if rho_map[fn] > beta_cal else 0 for fn in filename]
            calibrated = _metrics_at_threshold(y_true, y_pred_cal, beta_cal)
            calibrated["note"] = (
                "Threshold fitted on this test set (β = max ρ over negatives). "
                "Reports upper-bound metrics at FPR=0; not for forensic decisions."
            )
            metrics["at_calibrated_beta"] = calibrated

    if baseline_path and baseline_path.exists():
        exif_pred_by_stem: dict[str, int] = {}
        with open(baseline_path, newline="") as bf:
            for row in csv.DictReader(bf):
                if row.get("exif_prediction", "") != "":
                    fn = row.get("filename", "").strip()
                    if fn:
                        exif_pred_by_stem[Path(fn).stem] = int(row["exif_prediction"])

        aligned = [
            (yt, exif_pred_by_stem[Path(fn).stem])
            for fn, yt in zip(filename, y_true)
            if Path(fn).stem in exif_pred_by_stem
        ]

        if aligned:
            y_true_b = [a[0] for a in aligned]
            y_pred_b = [a[1] for a in aligned]
            metrics["exif_baseline"] = {
                "n_samples": len(aligned),
                "accuracy": round(accuracy_score(y_true_b, y_pred_b), 4),
                "precision": round(precision_score(y_true_b, y_pred_b, zero_division=0), 4),
                "recall_tpr": round(recall_score(y_true_b, y_pred_b, zero_division=0), 4),
                "fpr": round(compute_fpr(y_true_b, y_pred_b), 4),
                "f1": round(f1_score(y_true_b, y_pred_b, zero_division=0), 4),
            }

    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved → {metrics_path}")
    print(json.dumps(metrics, indent=2))

    cm = confusion_matrix(y_true, y_pred_paper, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 4))
    ConfusionMatrixDisplay(cm, display_labels=["Non-Portrait", "Portrait"]).plot(ax=ax, colorbar=False)
    ax.set_title(f"BP Detector — Confusion Matrix (β={beta_paper})")
    fig.tight_layout()
    cm_path = output_dir / "confusion_matrix.png"
    fig.savefig(str(cm_path), dpi=150)
    plt.close(fig)
    print(f"Confusion matrix → {cm_path}")

    if has_rho and len(set(y_true)) > 1:
        fpr_arr, tpr_arr, _ = roc_curve(y_true, y_scores)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(fpr_arr, tpr_arr, label=f"BP Detector (AUC={roc_auc:.3f})")
        ax.plot([0, 1], [0, 1], "k--", linewidth=0.8)
        ax.set_xlabel("FPR")
        ax.set_ylabel("TPR")
        ax.set_title("ROC Curve")
        ax.legend()
        roc_path = output_dir / "roc_curve.png"
        fig.savefig(str(roc_path), dpi=150)
        plt.close(fig)
        print(f"ROC curve → {roc_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection metrics.")
    parser.add_argument("--pred", required=True, help="sdnp_results.csv from sdnp_detector.py")
    parser.add_argument("--baseline", default=None, help="exif_baseline.csv (optional)")
    parser.add_argument("--labels", default=None,
                        help="Ground truth labels CSV. If provided, overrides labels in --pred via stem-based join "
                             "(fixes HEIC→JPG mismatch from transform_images.py).")
    parser.add_argument("--beta", type=float, default=0.0072,
                        help="Paper threshold β (default 0.0072). Always reported; calibrated β reported alongside.")
    parser.add_argument("--output", required=True, help="Output folder for metrics and plots")
    args = parser.parse_args()

    baseline = Path(args.baseline) if args.baseline else None
    labels = Path(args.labels) if args.labels else None
    evaluate(Path(args.pred), baseline, Path(args.output),
             labels_path=labels, beta_paper=args.beta)


if __name__ == "__main__":
    main()
