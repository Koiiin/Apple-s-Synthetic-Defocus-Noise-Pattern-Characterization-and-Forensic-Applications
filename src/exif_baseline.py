"""
exif_baseline.py
EXIF-only detector: predict Portrait nếu CustomRendered == "Portrait" hoặc "Portrait HDR".

Usage:
    python src/exif_baseline.py --input data/raw --output results/exif_baseline.csv
"""
import argparse
import csv
from pathlib import Path

import piexif
import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

SUPPORTED = {".jpg", ".jpeg", ".png", ".heic"}

# piexif trả về integer cho CustomRendered (0xA401).
# Apple dùng 6 = Portrait, 7 = Portrait HDR — không phải chuỗi "Portrait".
_CR_INT_TO_STR = {6: "Portrait", 7: "Portrait HDR"}
PORTRAIT_CR_VALUES = {"Portrait", "Portrait HDR"}


def read_custom_rendered(path: Path) -> str | None:
    """Trả về chuỗi human-readable của CustomRendered, hoặc None nếu không có."""
    try:
        img = Image.open(path)
        exif_bytes = img.info.get("exif", b"")
        if not exif_bytes:
            return None
        exif = piexif.load(exif_bytes)
        val = exif.get("Exif", {}).get(piexif.ExifIFD.CustomRendered)
        if val is None:
            return None
        return _CR_INT_TO_STR.get(val, str(val))
    except Exception:
        return None


def read_make_model(path: Path) -> tuple[str, str]:
    try:
        img = Image.open(path)
        exif_bytes = img.info.get("exif", b"")
        if not exif_bytes:
            return "", ""
        exif = piexif.load(exif_bytes)
        make = exif.get("0th", {}).get(piexif.ImageIFD.Make, b"")
        model = exif.get("0th", {}).get(piexif.ImageIFD.Model, b"")
        make = make.decode(errors="replace").strip("\x00") if isinstance(make, bytes) else str(make)
        model = model.decode(errors="replace").strip("\x00") if isinstance(model, bytes) else str(model)
        return make, model
    except Exception:
        return "", ""


def run_exif_baseline(input_dir: Path, output_path: Path):
    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "exif_make", "exif_model", "custom_rendered", "exif_prediction"])
        writer.writeheader()
        for img in images:
            make, model = read_make_model(img)
            cr = read_custom_rendered(img)
            pred = 1 if (cr and cr in PORTRAIT_CR_VALUES) else 0
            writer.writerow({
                "filename": img.name,
                "exif_make": make,
                "exif_model": model,
                "custom_rendered": cr or "",
                "exif_prediction": pred,
            })
            status = "Portrait" if pred else "non-Portrait"
            print(f"  {img.name}: CustomRendered={cr!r} → {status}")

    print(f"\nEXIF baseline saved → {output_path}  ({len(images)} images)")


def main():
    parser = argparse.ArgumentParser(description="EXIF-only Portrait Mode detector.")
    parser.add_argument("--input", required=True, help="Folder containing images")
    parser.add_argument("--output", default="results/exif_baseline.csv", help="Output CSV")
    args = parser.parse_args()

    run_exif_baseline(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
