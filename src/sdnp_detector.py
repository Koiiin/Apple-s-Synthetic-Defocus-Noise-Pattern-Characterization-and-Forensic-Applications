"""
sdnp_detector.py
BP detection: residual → NCC với tất cả BP + 4 rotations → threshold β.

Dùng BP_utils.py từ repo chính thức (Apache 2.0).
CSV columns (default): filename, sha256, label, pred_label, rho, beta, bp_ref, rotation_k, latency_ms.
With --scale-aware: adds image_size (HxW); each BP row is resized to the image grid before NCC.
Forensics: scale-aware scores are not directly comparable to paper β (BP modified by resize).

Usage:
    python src/sdnp_detector.py --images data/raw --bp data/bp \
        --labels data/labels.csv --beta 0.0072 --output results/original/sdnp_results.csv

    python src/sdnp_detector.py --images data/processed/resize_05 --bp data/bp \
        --labels data/labels.csv --beta 0.0072 --output results/resize_05/sdnp_results.csv \
        --scale-aware
"""
import argparse
import csv
import hashlib
import time
from pathlib import Path

from BP_utils import build_P_mat_from_mat_folder, load_image, correlation_with_rows
import cv2
import numpy as np

SUPPORTED = {".jpg", ".heic"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_labels(labels_path: Path) -> dict:
    labels = {}

    if not labels_path.exists():
        return labels

    with open(labels_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            filename = row.get("filename", "").strip()
            label_raw = row.get("label", "").strip()

            if not filename:
                continue

            if label_raw == "":
                labels[filename] = ""
            else:
                labels[filename] = int(label_raw)

    return labels


BP_H, BP_W = 4032, 3024


def _p_row_to_2d(row: np.ndarray, rotation_k: int) -> np.ndarray:
    """Reshape a P_mat row to 2D using the same layout as build_P_mat_from_mat_folder (C order)."""
    if rotation_k % 2 == 0:
        return row.reshape(BP_H, BP_W, order="C")
    return row.reshape(BP_W, BP_H, order="C")


def _resize_bp_2d_to_hw(pattern_2d: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Resize BP plane to image size; INTER_AREA when downscaling (aligned with sdnp_localizer)."""
    p = np.asarray(pattern_2d, dtype=np.float64)
    interp = cv2.INTER_AREA if p.shape[0] > out_h else cv2.INTER_LINEAR
    return cv2.resize(p, (out_w, out_h), interpolation=interp)


def _p_mat_for_shape(P_mat: np.ndarray, meta: list, out_h: int, out_w: int) -> np.ndarray:
    rows = []
    for i, m in enumerate(meta):
        p2 = _p_row_to_2d(P_mat[i], int(m["rotation_k"]))
        rows.append(_resize_bp_2d_to_hw(p2, out_h, out_w).ravel(order="C").astype(np.float32, copy=False))
    return np.stack(rows, axis=0)


def run_detector(images_dir: Path, bp_dir: Path, labels_path: Path, beta: float, output_path: Path,
                 no_rotation: bool = False, batch_size: int = 50, scale_aware: bool = False):
    print(f"Loading BP patterns from {bp_dir} ...")
    P_mat, meta = build_P_mat_from_mat_folder(bp_dir)
    print(f"  {len(meta)} BP variants loaded (including rotations)")

    if no_rotation:
        keep = [i for i, m in enumerate(meta) if m["rotation_k"] == 0]
        P_mat = P_mat[keep]
        meta = [meta[i] for i in keep]
        print(f"  [NO-ROTATION BASELINE] Chỉ dùng 0° — bỏ qua 90°/180°/270° ({len(meta)} variants còn lại)")

    if scale_aware:
        print("  [SCALE-AWARE] BP templates resized per image before NCC; image_size column in CSV; "
              "ρ not directly comparable to paper β.")

    # Get all image paths without loading into memory
    all_images = sorted(p for p in images_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    total_images = len(all_images)
    labels = load_labels(labels_path)

    # 5x5 box filter — same as BP_utils.detect_BP
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["filename", "sha256", "label", "pred_label", "rho", "beta", "bp_ref", "rotation_k", "latency_ms"]
    if scale_aware:
        fieldnames = ["filename", "image_size", "sha256", "label", "pred_label", "rho", "beta", "bp_ref", "rotation_k", "latency_ms"]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Process in batches to reduce memory usage
        for batch_start in range(0, total_images, batch_size):
            batch_end = min(batch_start + batch_size, total_images)
            batch_images = all_images[batch_start:batch_end]
            print(f"\n[BATCH] Processing images {batch_start + 1}-{batch_end}/{total_images} ({len(batch_images)} images)...")

            for img_path in batch_images:
                t0 = time.perf_counter()
                rel_name = str(img_path.relative_to(images_dir))
                label = labels.get(rel_name, "")

                I = load_image(img_path)

                # Căn chỉnh portrait → landscape như pipeline 12MP
                if I.shape[:2] == (BP_W, BP_H):
                    I = np.rot90(I, k=1)

                h_i, w_i = I.shape[:2]
                image_size_str = f"{h_i}x{w_i}"

                if not scale_aware and I.shape[:2] != (BP_H, BP_W):
                    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                    row_out = {
                        "filename": rel_name,
                        "sha256": sha256(img_path),
                        "label": label,
                        "pred_label": "",
                        "rho": "",
                        "beta": beta,
                        "bp_ref": "",
                        "rotation_k": "",
                        "latency_ms": latency_ms,
                    }
                    writer.writerow(row_out)
                    print(f"  SKIP {rel_name}: image size={I.shape[:2]}, expected {(BP_H, BP_W)} (use --scale-aware for other sizes)")
                    continue

                W = np.float64(I) - np.float64(
                    cv2.filter2D(np.float64(I), -1, kernel, cv2.BORDER_REFLECT_101)
                )

                if scale_aware and (h_i, w_i) != (BP_H, BP_W):
                    P_use = _p_mat_for_shape(P_mat, meta, h_i, w_i)
                else:
                    P_use = P_mat

                rho_mat = correlation_with_rows(W, P_use)

                rho = float(np.max(rho_mat))
                idx = int(np.argmax(rho_mat))
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)

                if scale_aware and (h_i, w_i) != (BP_H, BP_W):
                    # Scale-aware mode: rho is for signal-degradation analysis only.
                    # Do not make a hard detection decision using paper beta.
                    pred = ""
                    bp_ref = meta[idx]["BP_ref"]
                    rot_k = meta[idx]["rotation_k"]
                else:
                    pred = 1 if rho > beta else 0
                    bp_ref = meta[idx]["BP_ref"] if pred else None
                    rot_k = meta[idx]["rotation_k"] if pred else None

                if scale_aware:
                    writer.writerow({
                        "filename": rel_name,
                        "image_size": image_size_str,
                        "sha256": sha256(img_path),
                        "label": label,
                        "pred_label": pred,
                        "rho": round(rho, 6),
                        "beta": beta,
                        "bp_ref": bp_ref or "",
                        "rotation_k": rot_k if rot_k is not None else "",
                        "latency_ms": latency_ms,
                    })
                else:
                    writer.writerow({
                        "filename": rel_name,
                        "sha256": sha256(img_path),
                        "label": label,
                        "pred_label": pred,
                        "rho": round(rho, 6),
                        "beta": beta,
                        "bp_ref": bp_ref or "",
                        "rotation_k": rot_k if rot_k is not None else "",
                        "latency_ms": latency_ms,
                    })

                if pred == "":
                    status = f"SCALE-AWARE SCORE ONLY (best BP={bp_ref}, rot={rot_k})"
                else:
                    status = f"DETECTED (BP={bp_ref}, rot={rot_k})" if pred else "not detected"
                print(f"  {rel_name}: rho={rho:.4f} → {status}  [{latency_ms} ms]")

    print(f"\nResults saved → {output_path}  ({total_images} images, β={beta})")


def main():
    parser = argparse.ArgumentParser(description="SDNP/BP detector.")
    parser.add_argument("--images", required=True, help="Folder with images to analyse")
    parser.add_argument("--bp", required=True, help="Folder with BP .mat files")
    parser.add_argument("--labels", default="data/labels.csv", help="Ground truth labels CSV")
    parser.add_argument("--beta", type=float, default=0.0072, help="Detection threshold β (default: 0.0072)")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing (default: 50)")
    parser.add_argument("--no-rotation", action="store_true",
                        help="No-rotation baseline: only test BP at 0°, skip 90°/180°/270°")
    parser.add_argument("--scale-aware", action="store_true",
                        help="Resize BP templates to each image size before NCC (robustness / non-12MP); adds image_size column")
    args = parser.parse_args()

    run_detector(Path(args.images), Path(args.bp), Path(args.labels), args.beta, Path(args.output),
                 no_rotation=args.no_rotation, batch_size=args.batch_size, scale_aware=args.scale_aware)


if __name__ == "__main__":
    main()