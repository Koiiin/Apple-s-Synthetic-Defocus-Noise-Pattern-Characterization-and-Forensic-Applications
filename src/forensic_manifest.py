"""
forensic_manifest.py
Tính SHA-256 cho mỗi ảnh và lưu manifest CSV.

Usage:
    python src/forensic_manifest.py --input data/raw --labels data/labels.csv --output results/manifest.csv
"""
import argparse
import csv
import hashlib
from datetime import datetime
from pathlib import Path

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
    with open(labels_path, newline="") as f:
        for row in csv.DictReader(f):
            labels[row["filename"]] = row
    return labels


def build_manifest(input_dir: Path, labels_path: Path, output_path: Path):
    labels = load_labels(labels_path)
    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "sha256", "size_bytes", "collected_time", "source", "label", "notes"])
        writer.writeheader()
        for img in images:
            meta = labels.get(img.name, {})
            writer.writerow({
                "filename": img.name,
                "sha256": sha256(img),
                "size_bytes": img.stat().st_size,
                "collected_time": datetime.utcfromtimestamp(img.stat().st_mtime).isoformat(),
                "source": meta.get("source", ""),
                "label": meta.get("label", ""),
                "notes": meta.get("notes", ""),
            })
            print(f"  hashed: {img.name}")

    print(f"\nManifest saved → {output_path}  ({len(images)} files)")


def main():
    parser = argparse.ArgumentParser(description="Build forensic manifest with SHA-256 hashes.")
    parser.add_argument("--input", required=True, help="Folder containing images")
    parser.add_argument("--labels", default="data/labels.csv", help="labels.csv with ground truth")
    parser.add_argument("--output", default="results/manifest.csv", help="Output manifest CSV")
    args = parser.parse_args()

    build_manifest(Path(args.input), Path(args.labels), Path(args.output))


if __name__ == "__main__":
    main()
