"""
EXIF metadata helpers used by the website.
"""
from pathlib import Path

import piexif
import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

# piexif trả về integer cho CustomRendered (0xA401).
# EXIF chuẩn (CIPA/JEITA) chỉ định nghĩa 0=Normal, 1=Custom.
# Apple mở rộng riêng, không tài liệu hoá chính thức:
#   2=HDR (no original), 3=HDR (original saved), 4=HDR original,
#   6=Panorama, 7=Portrait HDR, 8=Portrait
# Vendor khác (Samsung, Huawei) không dùng trường này — họ dùng MakerNote riêng.
_CR_INT_TO_STR = {
    2: "HDR", 3: "HDR+Original", 4: "HDR-Original",
    6: "Panorama", 7: "Portrait HDR", 8: "Portrait",
}


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
