"""
sdnp_localizer.py
BP localization: tính NCC map cục bộ và tạo binary mask vùng SDNP.

Lưu ý: BP và ảnh phải cùng kích thước — script tự resize BP nếu khác.
Output: ncc_map_<name>.png, mask_<name>.png, overlay_<name>.png

Usage:
    python src/sdnp_localizer.py --image data/raw/img.JPG \
        --bp data/bp/BP06_12MP_NL_HEIC.mat \
        --rotation 0 \
        --output results/original/localization/
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import loadmat

from BP_utils import load_image, BP_driven_NCC_map


def localize(image_path: Path, bp_path: Path, rotation_k: int, output_dir: Path, alpha: float = 0.07):
    # Load BP
    data = loadmat(bp_path)
    BP = data["BP"].astype(np.float64)
    if rotation_k != 0:
        BP = np.rot90(BP, k=rotation_k)

    # Load image (grayscale)
    I = load_image(image_path)

    # Resize BP to match image if needed (INTER_AREA when downscaling reduces aliasing vs bilinear)
    if BP.shape != I.shape:
        print(f"  [scale] BP {BP.shape} → resize to image {I.shape}")
        interp = cv2.INTER_AREA if BP.shape[0] > I.shape[0] else cv2.INTER_LINEAR
        BP = cv2.resize(BP, (I.shape[1], I.shape[0]), interpolation=interp)

    # Compute NCC map and binary mask
    NCCmap, Mask = BP_driven_NCC_map(BP, I, alpha=alpha)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = image_path.stem

    # Save NCC map
    ncc_norm = ((NCCmap - NCCmap.min()) / (NCCmap.ptp() + 1e-9) * 255).astype(np.uint8)
    ncc_path = output_dir / f"ncc_map_{stem}.png"
    cv2.imwrite(str(ncc_path), cv2.applyColorMap(ncc_norm, cv2.COLORMAP_JET))

    # Save binary mask
    mask_path = output_dir / f"mask_{stem}.png"
    cv2.imwrite(str(mask_path), (Mask * 255).astype(np.uint8))

    # Save overlay (image + NCC heatmap)
    overlay_path = output_dir / f"overlay_{stem}.png"
    H, W = I.shape
    figsize = (10, 10 * H / W) if W >= H else (10 * W / H, 10)
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(I, cmap="gray")
    im = ax.imshow(NCCmap, alpha=0.6, extent=(0, W, H, 0), cmap="jet")
    plt.colorbar(im, ax=ax, label="NCC")
    ax.set_title(f"BP localization — {image_path.name}")
    ax.axis("off")
    fig.savefig(str(overlay_path), bbox_inches="tight", dpi=150)
    plt.close(fig)

    print(f"  NCC map  → {ncc_path}")
    print(f"  Mask     → {mask_path}")
    print(f"  Overlay  → {overlay_path}")

    # Quick stats
    bokeh_ratio = float(Mask.mean())
    print(f"  Mask coverage (bokeh fraction): {bokeh_ratio:.1%}")

    return NCCmap, Mask


def main():
    parser = argparse.ArgumentParser(description="SDNP/BP localizer — NCC map + binary mask.")
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--bp", required=True, help="Path to BP .mat file")
    parser.add_argument("--rotation", type=int, default=0, choices=[0, 1, 2, 3],
                        help="Rotation index from detector (0=0°, 1=90°, 2=180°, 3=270°)")
    parser.add_argument("--alpha", type=float, default=0.07,
                        help="NCC threshold for binary mask (default: 0.07)")
    parser.add_argument("--output", required=True, help="Output folder for NCC map / mask / overlay")
    args = parser.parse_args()

    localize(Path(args.image), Path(args.bp), args.rotation, Path(args.output), args.alpha)


if __name__ == "__main__":
    main()