"""
evaluate.py
Tính metrics từ prediction CSV và labels CSV.
Metrics: Accuracy, Precision, Recall/TPR, FPR, F1, ROC-AUC, avg Latency/image.
Output: metrics.json + confusion_matrix.png + roc_curve.png

Usage:
    python src/evaluate.py \
        --pred results/original/sdnp_results.csv \
        --baseline results/exif_baseline.csv \
        --labels data/labels.csv \
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


def load_predictions(csv_path: Path, pred_col: str, label_col: str = "label") -> tuple[list, list, list]:
    filenames, labels, preds = [], [], []

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            label_raw = row.get(label_col, "").strip()
            pred_raw = row.get(pred_col, "").strip()

            # Bỏ qua dòng không có label hoặc bị skip detector
            if label_raw == "" or pred_raw == "":
                continue

            filenames.append(row["filename"])
            labels.append(int(label_raw))
            preds.append(int(pred_raw))

    return filenames, labels, preds


def load_rho(csv_path: Path) -> dict:
    rho_map = {}

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            rho_raw = row.get("rho", "").strip()
            filename = row.get("filename", "").strip()

            if filename and rho_raw != "":
                rho_map[filename] = float(rho_raw)

    return rho_map


def load_latency(csv_path: Path) -> list[float]:
    latencies = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if "latency_ms" in row and row["latency_ms"]:
                latencies.append(float(row["latency_ms"]))
    return latencies


def compute_fpr(y_true, y_pred) -> float:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return fp / (fp + tn) if (fp + tn) > 0 else 0.0


def evaluate(pred_path: Path, baseline_path: Path | None, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load BP detector results
    filename, y_true, y_pred = load_predictions(pred_path, pred_col="pred_label")

    rho_map = load_rho(pred_path)
    latencies = load_latency(pred_path)

    # ------------------------------------------------------------------
    # SCALE-AWARE / RHO-ONLY MODE
    # ------------------------------------------------------------------
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
            "note": (
                "Scale-aware robustness experiment. "
                "BP templates were resized to image resolution before NCC. "
                "Scores are not directly comparable to paper threshold beta=0.0072."
            ),
        }

        metrics_path = output_dir / "metrics.json"

        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"Metrics saved → {metrics_path}")
        print(json.dumps(metrics, indent=2))

        return

    # ------------------------------------------------------------------
    # NORMAL DETECTOR EVALUATION
    # ------------------------------------------------------------------
    y_scores = [rho_map.get(fn, 0.0) for fn in filename]

    metrics = {
        "mode": "hard_decision",
        "n_samples": len(y_true),
        "n_positive": int(sum(y_true)),
        "bp_detector": {
            "accuracy": round(accuracy_score(y_true, y_pred), 4),
            "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
            "recall_tpr": round(recall_score(y_true, y_pred, zero_division=0), 4),
            "fpr": round(compute_fpr(y_true, y_pred), 4),
            "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(y_true, y_scores), 4)
            if len(set(y_true)) > 1 else None,
            "avg_latency_ms": round(np.mean(latencies), 1) if latencies else None,
        }
    }

    # EXIF baseline metrics — inner join theo filename
    if baseline_path and baseline_path.exists():
        exif_pred_map: dict[str, int] = {}

        with open(baseline_path, newline="") as bf:
            for row in csv.DictReader(bf):
                if row.get("exif_prediction", "") != "":
                    exif_pred_map[row["filename"]] = int(row["exif_prediction"])

        aligned = [
            (yt, exif_pred_map[fn])
            for fn, yt in zip(filename, y_true)
            if fn in exif_pred_map
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

    # Save metrics JSON
    metrics_path = output_dir / "metrics.json"

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Metrics saved → {metrics_path}")
    print(json.dumps(metrics, indent=2))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(4, 4))

    ConfusionMatrixDisplay(
        cm,
        display_labels=["Non-Portrait", "Portrait"]
    ).plot(ax=ax, colorbar=False)

    ax.set_title("BP Detector — Confusion Matrix")

    fig.tight_layout()

    cm_path = output_dir / "confusion_matrix.png"

    fig.savefig(str(cm_path), dpi=150)

    plt.close(fig)

    print(f"Confusion matrix → {cm_path}")

    # ROC curve
    if len(set(y_true)) > 1:
        fpr_arr, tpr_arr, _ = roc_curve(y_true, y_scores)

        fig, ax = plt.subplots(figsize=(5, 5))

        ax.plot(
            fpr_arr,
            tpr_arr,
            label=f"BP Detector (AUC={metrics['bp_detector']['roc_auc']:.3f})"
        )

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
    parser.add_argument("--labels", default="data/labels.csv", help="Ground truth labels CSV (unused if label col in pred)")
    parser.add_argument("--output", required=True, help="Output folder for metrics and plots")
    args = parser.parse_args()

    baseline = Path(args.baseline) if args.baseline else None
    evaluate(Path(args.pred), baseline, Path(args.output))


if __name__ == "__main__":
    main()
