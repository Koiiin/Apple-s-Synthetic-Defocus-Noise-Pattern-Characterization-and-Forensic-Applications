#!/usr/bin/env python3
"""Prepare PrnuModernDevices C01-C18 as negative controls for FPR tests."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse


NEGATIVE_DEVICES = {
    "C01": ("Huawei", "P30 lite"),
    "C02": ("Huawei", "P20 pro"),
    "C03": ("Huawei", "P20 pro"),
    "C04": ("Huawei", "P20 pro"),
    "C05": ("Huawei", "P Smart 2019"),
    "C06": ("Huawei", "P Smart 2019"),
    "C07": ("Huawei", "P20 lite"),
    "C08": ("Huawei", "P20 lite"),
    "C09": ("Huawei", "P10"),
    "C10": ("Xiaomi", "Mi Note 10"),
    "C11": ("Xiaomi", "Redmi Note 8T"),
    "C12": ("Xiaomi", "Mi A3"),
    "C13": ("Samsung", "S6"),
    "C14": ("Samsung", "S9"),
    "C15": ("Samsung", "S9+"),
    "C16": ("Samsung", "A70"),
    "C17": ("OnePlus", "6T"),
    "C18": ("OnePlus", "6"),
}

EXCLUDED_APPLE_DEVICES = {
    "C19": ("Apple", "iPhone X"),
    "C20": ("Apple", "iPhone 11"),
    "C21": ("Apple", "iPhone 11"),
    "C22": ("Apple", "iPhone 11 Pro Max"),
}

SUPPORTED = {".jpg", ".jpeg", ".heic"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_urls(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def url_relpath(url: str) -> Path:
    raw_path = unquote(urlparse(url).path).lstrip("/")
    marker = "PrnuModernDevices/"
    if marker not in raw_path:
        raise ValueError(f"URL does not contain {marker!r}: {url}")
    return Path(raw_path.split(marker, 1)[1])


def device_id_from_relpath(rel: Path) -> str:
    if not rel.parts:
        raise ValueError(f"Cannot read device id from path: {rel}")
    return rel.parts[0]


def mode_from_relpath(rel: Path) -> str:
    return rel.parts[1] if len(rel.parts) > 1 else ""


def selected_url_rows(urls: list[str]) -> list[tuple[str, Path]]:
    rows = []
    for url in urls:
        rel = url_relpath(url)
        if device_id_from_relpath(rel) in NEGATIVE_DEVICES:
            rows.append((url, rel))
    return rows


def curl_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_curl_config(urls_path: Path, root: Path, config_path: Path) -> None:
    urls = read_urls(urls_path)
    rows = selected_url_rows(urls)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("# Generated from the official PrnuModernDevices dataset_download.txt\n")
        f.write("# Only C01-C18 are included as non-Apple negative controls.\n")
        for url, rel in rows:
            out = root / rel
            f.write(f'url = "{curl_quote(url)}"\n')
            f.write(f'output = "{curl_quote(str(out))}"\n')
    print(f"curl config -> {config_path} ({len(rows)} files)")


def write_url_list(urls_path: Path, list_path: Path) -> None:
    rows = selected_url_rows(read_urls(urls_path))
    list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(list_path, "w", encoding="utf-8") as f:
        for url, _ in rows:
            f.write(f"{url}\n")
    print(f"url list -> {list_path} ({len(rows)} files)")


def valid_image(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.verify()
        return True
    except ImportError:
        pass
    except OSError:
        return False

    try:
        with open(path, "rb") as f:
            head = f.read(12)
            if path.suffix.lower() in {".jpg", ".jpeg"}:
                if not head.startswith(b"\xff\xd8"):
                    return False
                f.seek(0)
                return b"\xff\xd9" in f.read()
            if path.suffix.lower() == ".heic":
                return b"ftyp" in head
        return False
    except OSError:
        return False


def image_rows(root: Path, validate: bool = True) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        if validate and not valid_image(path):
            continue
        rel = path.relative_to(root)
        device = device_id_from_relpath(rel)
        if device not in NEGATIVE_DEVICES:
            continue
        brand, model = NEGATIVE_DEVICES[device]
        mode = mode_from_relpath(rel)
        rows.append({
            "path": path,
            "filename": str(rel),
            "device": device,
            "brand": brand,
            "model": model,
            "mode": mode,
        })
    return rows


def write_labels(root: Path, labels_path: Path) -> None:
    rows = image_rows(root)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with open(labels_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["filename", "label", "source", "notes"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "filename": row["filename"],
                "label": 0,
                "source": "PrnuModernDevices_C01_C18",
                "notes": (
                    f"negative_control;device={row['device']};brand={row['brand']};"
                    f"model={row['model']};mode={row['mode']}"
                ),
            })
    print(f"labels -> {labels_path} ({len(rows)} rows)")


def write_manifest(root: Path, manifest_path: Path) -> None:
    rows = image_rows(root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["filename", "sha256", "bytes", "device", "brand", "model", "mode"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            path = row["path"]
            writer.writerow({
                "filename": row["filename"],
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "device": row["device"],
                "brand": row["brand"],
                "model": row["model"],
                "mode": row["mode"],
            })
    print(f"manifest -> {manifest_path} ({len(rows)} rows)")


def write_summary(urls_path: Path, root: Path, summary_path: Path) -> None:
    expected = selected_url_rows(read_urls(urls_path))
    expected_set = {str(rel) for _, rel in expected}
    present_rows = image_rows(root)
    present_set = {row["filename"] for row in present_rows}
    missing = sorted(expected_set - present_set)
    extra_apple = []
    invalid = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        rel = path.relative_to(root)
        if not valid_image(path):
            invalid.append(str(rel))
            continue
        device = device_id_from_relpath(rel)
        if device in EXCLUDED_APPLE_DEVICES:
            extra_apple.append(str(rel))

    by_device = Counter(row["device"] for row in present_rows)
    by_mode = Counter(row["mode"] for row in present_rows)
    summary = {
        "source": "https://lesc.dinfo.unifi.it/PrnuModernDevices/",
        "selection": "C01-C18 only; C19-C22 are Apple iPhone devices and are excluded from FPR negatives.",
        "expected_negative_files": len(expected_set),
        "present_negative_files": len(present_set),
        "missing_negative_files": len(missing),
        "invalid_or_partial_image_files": len(invalid),
        "present_by_device": dict(sorted(by_device.items())),
        "present_by_mode": dict(sorted(by_mode.items())),
        "excluded_apple_files_present_but_unused": len(extra_apple),
        "missing_examples": missing[:20],
        "invalid_examples": invalid[:20],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    print(f"summary -> {summary_path}")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare PrnuModernDevices negative controls.")
    parser.add_argument("--urls", default="data/raw/fpr_controls/PrnuModernDevices/dataset_download.txt")
    parser.add_argument("--root", default="data/raw/fpr_controls/PrnuModernDevices")
    parser.add_argument("--curl-config", default="data/raw/fpr_controls/prnu_modern_c01_c18.curl")
    parser.add_argument("--url-list", default="data/raw/fpr_controls/prnu_modern_c01_c18_urls.txt")
    parser.add_argument("--labels", default="data/labels_fpr_controls.csv")
    parser.add_argument("--manifest", default="data/raw/fpr_controls/PrnuModernDevices_C01_C18_manifest.csv")
    parser.add_argument("--summary", default="data/raw/fpr_controls/PrnuModernDevices_C01_C18_summary.json")
    parser.add_argument("--make-curl-config", action="store_true")
    parser.add_argument("--make-url-list", action="store_true")
    parser.add_argument("--write-labels", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--write-summary", action="store_true")
    args = parser.parse_args()

    urls = Path(args.urls)
    root = Path(args.root)

    if args.make_curl_config:
        write_curl_config(urls, root, Path(args.curl_config))
    if args.make_url_list:
        write_url_list(urls, Path(args.url_list))
    if args.write_labels:
        write_labels(root, Path(args.labels))
    if args.write_manifest:
        write_manifest(root, Path(args.manifest))
    if args.write_summary:
        write_summary(urls, root, Path(args.summary))


if __name__ == "__main__":
    main()
