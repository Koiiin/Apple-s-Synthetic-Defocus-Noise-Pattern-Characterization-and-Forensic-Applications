"""
transform_images.py
Tạo biến thể ảnh cho robustness experiment.

Flags (có thể kết hợp nhiều cái):
  --strip-exif          xoá toàn bộ EXIF
  --jpeg-quality Q      recompress JPEG với quality Q
  --resize SCALE        downscale theo tỷ lệ (0.0–1.0)

Output: <output_dir>/<original_filename>  (giữ tên, đổi nội dung)

Usage:
    python src/transform_images.py --input data/raw --output data/processed/jpeg_q80 --jpeg-quality 80
    python src/transform_images.py --input data/raw --output data/processed/exif_stripped --strip-exif
    python src/transform_images.py --input data/raw --output data/processed/resize_05 --resize 0.5
"""
import argparse
from pathlib import Path

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

SUPPORTED = {".jpg", ".jpeg", ".png", ".heic"}


def process_image(img_path: Path, output_dir: Path, strip_exif: bool, jpeg_quality: int | None, resize_scale: float | None):
    img = Image.open(img_path)

    # Resize
    if resize_scale is not None:
        new_w = max(1, int(img.width * resize_scale))
        new_h = max(1, int(img.height * resize_scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Determine output path (always save as JPEG for processed images, except PNG stays PNG)
    ext = img_path.suffix.lower()
    out_ext = ".jpg" if ext in {".jpg", ".jpeg", ".heic"} else ext
    out_path = output_dir / (img_path.stem + out_ext)

    save_kwargs = {}

    if out_ext == ".jpg":
        save_kwargs["format"] = "JPEG"
        save_kwargs["quality"] = jpeg_quality if jpeg_quality is not None else 95
        save_kwargs["subsampling"] = 0

        if not strip_exif:
            # Preserve original EXIF if available
            try:
                exif_bytes = img.info.get("exif", b"")
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
            except Exception:
                pass
        # strip_exif: simply omit exif kwarg → no EXIF in output
    elif out_ext == ".png":
        save_kwargs["format"] = "PNG"

    img.save(str(out_path), **save_kwargs)
    return out_path


def run_transform(input_dir: Path, output_dir: Path, strip_exif: bool, jpeg_quality: int | None, resize_scale: float | None):
    images = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    ops = []
    if strip_exif:
        ops.append("strip-exif")
    if jpeg_quality is not None:
        ops.append(f"jpeg-q{jpeg_quality}")
    if resize_scale is not None:
        ops.append(f"resize-{resize_scale}")
    print(f"Operations: {', '.join(ops) or 'none'}")

    for img_path in images:
        out = process_image(img_path, output_dir, strip_exif, jpeg_quality, resize_scale)
        print(f"  {img_path.name} → {out.name}")

    print(f"\nDone. {len(images)} images → {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Image transform for robustness experiments.")
    parser.add_argument("--input", required=True, help="Input image folder")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--strip-exif", action="store_true", help="Remove all EXIF metadata")
    parser.add_argument("--jpeg-quality", type=int, default=None, help="JPEG quality (1–95)")
    parser.add_argument("--resize", type=float, default=None, help="Resize scale factor (e.g. 0.5)")
    args = parser.parse_args()

    run_transform(Path(args.input), Path(args.output), args.strip_exif, args.jpeg_quality, args.resize)


if __name__ == "__main__":
    main()
