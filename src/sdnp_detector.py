"""
sdnp_detector.py
BP detection: residual → NCC với tất cả BP + 4 rotations → threshold β.

Dùng BP_utils.py từ repo chính thức (Apache 2.0).
Output columns: filename, sha256, label, pred_label, rho, beta, bp_ref, rotation_k, latency_ms

Usage:
    python src/sdnp_detector.py --images data/raw --bp data/bp \
        --labels data/labels.csv --beta 0.0072 --output results/original/sdnp_results.csv
"""
import argparse
import csv
import hashlib
import time
from pathlib import Path

from BP_utils import build_P_mat_from_mat_folder, load_image, correlation_with_rows
import cv2
import numpy as np

SUPPORTED = {".jpg", ".jpeg", ".png", ".heic"}


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


def run_detector(images_dir: Path, bp_dir: Path, labels_path: Path, beta: float, output_path: Path,
                 no_rotation: bool = False):
    print(f"Loading BP patterns from {bp_dir} ...")
    P_mat, meta = build_P_mat_from_mat_folder(bp_dir)
    print(f"  {len(meta)} BP variants loaded (including rotations)")

    if no_rotation:
        keep = [i for i, m in enumerate(meta) if m["rotation_k"] == 0]
        P_mat = P_mat[keep]
        meta = [meta[i] for i in keep]
        print(f"  [NO-ROTATION BASELINE] Chỉ dùng 0° — bỏ qua 90°/180°/270° ({len(meta)} variants còn lại)")

    images = sorted(p for p in images_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    labels = load_labels(labels_path)

    # 5x5 box filter — same as BP_utils.detect_BP
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["filename", "sha256", "label", "pred_label", "rho", "beta", "bp_ref", "rotation_k", "latency_ms"]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for img_path in images:
            t0 = time.perf_counter()
            rel_name = str(img_path.relative_to(images_dir))
            label = labels.get(rel_name, "")

            I = load_image(img_path)

            # Chỉ dùng ảnh khớp BP 12MP: 4032x3024 hoặc ảnh xoay 3024x4032
            BP_H, BP_W = 4032, 3024

            if I.shape[:2] == (BP_H, BP_W):
                pass
            elif I.shape[:2] == (BP_W, BP_H):
                I = np.rot90(I, k=1)
            else:
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)

                writer.writerow({
                    "filename": rel_name,
                    "sha256": sha256(img_path),
                    "label": label,
                    "pred_label": "",
                    "rho": "",
                    "beta": beta,
                    "bp_ref": "",
                    "rotation_k": "",
                    "latency_ms": latency_ms,
                })

                print(f"  SKIP {rel_name}: image size={I.shape[:2]}, expected {(BP_H, BP_W)}")
                continue

            W = np.float64(I) - np.float64(
                cv2.filter2D(np.float64(I), -1, kernel, cv2.BORDER_REFLECT_101)
            )

            rho_mat = correlation_with_rows(W, P_mat)

            rho = float(np.max(rho_mat))
            idx = int(np.argmax(rho_mat))
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            pred = 1 if rho > beta else 0
            bp_ref = meta[idx]["BP_ref"] if pred else None
            rot_k = meta[idx]["rotation_k"] if pred else None

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

            status = f"DETECTED (BP={bp_ref}, rot={rot_k})" if pred else "not detected"
            print(f"  {rel_name}: rho={rho:.4f} → {status}  [{latency_ms} ms]")

    print(f"\nResults saved → {output_path}  ({len(images)} images, β={beta})")


def main():
    parser = argparse.ArgumentParser(description="SDNP/BP detector.")
    parser.add_argument("--images", required=True, help="Folder with images to analyse")
    parser.add_argument("--bp", required=True, help="Folder with BP .mat files")
    parser.add_argument("--labels", default="data/labels.csv", help="Ground truth labels CSV")
    parser.add_argument("--beta", type=float, default=0.0072, help="Detection threshold β (default: 0.0072)")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--no-rotation", action="store_true",
                        help="No-rotation baseline: only test BP at 0°, skip 90°/180°/270°")
    args = parser.parse_args()

    run_detector(Path(args.images), Path(args.bp), Path(args.labels), args.beta, Path(args.output),
                 no_rotation=args.no_rotation)


if __name__ == "__main__":
    main()
