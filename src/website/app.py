"""
app.py — FastAPI backend for SDNP Forensic Analyzer web interface.

Run:
    cd src/website
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
import sys
import uuid
import hashlib
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.io import loadmat

# Ensure src/ is on the path so we can import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import pillow_heif
from PIL import Image as PILImage
pillow_heif.register_heif_opener()

from BP_utils import build_P_mat_from_mat_folder, load_image, correlation_with_rows, BP_driven_NCC_map
from exif_baseline import read_custom_rendered, read_make_model

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent.parent
BP_DIR = PROJECT_ROOT / "data" / "bp"
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "static"

TEMP_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BP_H, BP_W = 4032, 3024
BETA = 0.0072
SUPPORTED_EXTS = {".jpg", ".jpeg", ".heic", ".png"}

BP_DEVICE_MAP: dict[str, tuple[str, str, str]] = {
    "BP01": ("BP①", "iPhone 7 Plus", "iOS 10"),
    "BP02": ("BP②", "iPhone 8 Plus", "iOS 11"),
    "BP03": ("BP③", "iPhone X", "iOS 11"),
    "BP04": ("BP④", "iPhone X", "iOS 12+"),
    "BP05": ("BP⑤", "iPhone 12 Pro", "iOS 14+"),
    "BP06": ("BP⑥", "iPhone 14+", "iOS 16+"),
    "BP07": ("BP⑦", "iPhone 15 Pro", "iOS 17+"),
    "BP08": ("BP⑧", "iPhone (2024+)", "iOS 18+"),
}

# ---------------------------------------------------------------------------
# Load BP patterns once at startup (12MP only — mixed-size dirs would break np.stack)
# ---------------------------------------------------------------------------
_P_mat: np.ndarray | None = None
_bp_meta: list | None = None

def _load_bp_12mp(bp_dir: Path):
    """Load only 12MP BP files so all rows have the same element count."""
    from scipy.io import loadmat as _loadmat
    files = sorted(bp_dir.glob("*.mat"))
    rows, meta = [], []
    expected_size = BP_H * BP_W  # 4032 * 3024 = 12,192,768
    for fp in files:
        data = _loadmat(fp)
        BP = data["BP"]
        if BP.size != expected_size:
            print(f"  [startup] skip {fp.name} — shape {BP.shape} not 12MP")
            continue
        for k in (0, 1, 2, 3):
            rot = np.rot90(BP, k=k)
            rows.append(rot.ravel(order="C").astype(np.float32, copy=False))
            meta.append({"BP_ref": fp.name, "rotation_k": k})
    if not rows:
        raise RuntimeError("No 12MP BP files found")
    return np.stack(rows, axis=0), meta

try:
    _P_mat, _bp_meta = _load_bp_12mp(BP_DIR)
    uniq = len({m["BP_ref"] for m in _bp_meta})
    print(f"[startup] {uniq} 12MP BP files · {len(_bp_meta)} variants (incl. rotations) loaded")
except Exception as _e:
    print(f"[startup] WARNING: BP load failed — {_e}")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="SDNP Forensic Analyzer", version="1.0.0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_bp_info(bp_ref: str) -> dict:
    for key, (sym, dev, os_) in BP_DEVICE_MAP.items():
        if bp_ref.startswith(key):
            return {"symbol": sym, "device": dev, "os": os_}
    return {"symbol": bp_ref[:6], "device": "Unknown", "os": "Unknown"}


def _p_row_to_2d(row: np.ndarray, rotation_k: int) -> np.ndarray:
    """Reshape a flattened P_mat row back to 2D (mirrors sdnp_detector logic)."""
    if rotation_k % 2 == 0:
        return row.reshape(BP_H, BP_W, order="C")
    return row.reshape(BP_W, BP_H, order="C")


def _resize_bp(bp_2d: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    interp = cv2.INTER_AREA if bp_2d.shape[0] > out_h else cv2.INTER_LINEAR
    return cv2.resize(bp_2d.astype(np.float64), (out_w, out_h), interpolation=interp)


def _detect(img_path: Path) -> dict:
    """Run BP detection on a single image. Returns result dict (includes image array)."""
    t0 = time.perf_counter()
    I = load_image(img_path)

    # Align portrait→landscape as paper pipeline does
    if I.shape[:2] == (BP_W, BP_H):
        I = np.rot90(I, k=1)

    h_i, w_i = I.shape[:2]
    is_native = (h_i, w_i) == (BP_H, BP_W)

    kernel = np.ones((5, 5), np.float32) / 25
    W_res = np.float64(I) - np.float64(
        cv2.filter2D(np.float64(I), -1, kernel, borderType=cv2.BORDER_REFLECT_101)
    )

    if not is_native:
        # Scale-aware: resize each BP template to image size before NCC
        rows = [
            _resize_bp(_p_row_to_2d(_P_mat[i], int(m["rotation_k"])), h_i, w_i)
            .ravel(order="C")
            .astype(np.float32)
            for i, m in enumerate(_bp_meta)
        ]
        P_use = np.stack(rows)
    else:
        P_use = _P_mat

    rho_mat = correlation_with_rows(W_res, P_use)
    rho = float(np.max(rho_mat))
    idx = int(np.argmax(rho_mat))
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    best_ref = _bp_meta[idx]["BP_ref"]
    best_rot = int(_bp_meta[idx]["rotation_k"])

    if is_native:
        detected = rho > BETA
        bp_ref = best_ref if detected else None
        rot_k = best_rot if detected else None
    else:
        # Scale-aware: score only, no hard threshold decision
        detected = None
        bp_ref = best_ref
        rot_k = best_rot

    return {
        "image_array": I,
        "image_size": f"{h_i}x{w_i}",
        "rho": round(rho, 6),
        "beta": BETA,
        "detected": detected,
        "bp_ref": bp_ref,
        "rotation_k": rot_k,
        "latency_ms": latency_ms,
        "scale_aware": not is_native,
    }


def _localize(I: np.ndarray, bp_ref: str, rot_k: int, out_dir: Path) -> dict:
    """Compute NCC localization map and save result images to out_dir."""
    data = loadmat(str(BP_DIR / bp_ref))
    BP = data["BP"].astype(np.float64)
    if rot_k:
        BP = np.rot90(BP, k=rot_k)
    if BP.shape != I.shape:
        interp = cv2.INTER_AREA if BP.shape[0] > I.shape[0] else cv2.INTER_LINEAR
        BP = cv2.resize(BP, (I.shape[1], I.shape[0]), interpolation=interp)

    # BP_driven_NCC_map uses view_as_blocks(21x21) which requires dims divisible by 21
    BLOCK = 21
    h_orig, w_orig = I.shape[:2]
    ch = (h_orig // BLOCK) * BLOCK
    cw = (w_orig // BLOCK) * BLOCK
    I_use  = I[:ch, :cw]
    BP_use = BP[:ch, :cw]

    NCCmap, Mask = BP_driven_NCC_map(BP_use, I_use, alpha=0.07)

    # Resize outputs back to original image dimensions
    if (ch, cw) != (h_orig, w_orig):
        NCCmap = cv2.resize(NCCmap, (w_orig, h_orig), interpolation=cv2.INTER_LINEAR)
        Mask   = (cv2.resize(Mask.astype(np.float32), (w_orig, h_orig),
                             interpolation=cv2.INTER_NEAREST) > 0.5).astype(int)

    out_dir.mkdir(parents=True, exist_ok=True)
    sid = out_dir.name

    # NCC heat map (jet colormap)
    ncc_range = float(NCCmap.max() - NCCmap.min())
    ncc_norm = ((NCCmap - NCCmap.min()) / (ncc_range + 1e-9) * 255).astype(np.uint8)
    cv2.imwrite(str(out_dir / "ncc_map.png"), cv2.applyColorMap(ncc_norm, cv2.COLORMAP_JET))

    # Binary mask (white = bokeh region)
    cv2.imwrite(str(out_dir / "mask.png"), (Mask * 255).astype(np.uint8))

    # Overlay: grayscale image + NCC heatmap
    H, W = I.shape
    figsize = (10, 10 * H / W) if W >= H else (10 * W / H, 10)
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(I, cmap="gray")
    im = ax.imshow(NCCmap, alpha=0.6, extent=(0, W, H, 0), cmap="jet")
    plt.colorbar(im, ax=ax, label="NCC")
    ax.set_title(f"BP Localization — {bp_ref}", fontsize=11)
    ax.axis("off")
    fig.savefig(str(out_dir / "overlay.png"), bbox_inches="tight", dpi=150)
    plt.close(fig)

    return {
        "bokeh_ratio": round(float(Mask.mean()), 4),
        "ncc_map_url": f"/temp/{sid}/ncc_map.png",
        "mask_url": f"/temp/{sid}/mask.png",
        "overlay_url": f"/temp/{sid}/overlay.png",
    }


def _conclusion(det: dict, exif: dict) -> str:
    rho, beta = det["rho"], det["beta"]
    bp_ref = det.get("bp_ref", "")
    rot_k = det.get("rotation_k")
    rot_deg = {0: "0°", 1: "90°", 2: "180°", 3: "270°"}.get(rot_k, "?")
    cr = exif.get("custom_rendered", "")
    exif_pred = exif.get("prediction", 0)

    if det["scale_aware"]:
        txt = (
            f"[Scale-aware] Ảnh không ở độ phân giải 12MP chuẩn. "
            f"ρ = {rho:.4f} với pattern '{bp_ref}' (rotation = {rot_deg}). "
            f"Trong chế độ này ρ không so sánh trực tiếp với β = {beta}. "
            f"Cần đánh giá thêm để kết luận chính xác. "
        )
    elif det["detected"]:
        txt = (
            f"Ảnh có dấu hiệu tương thích với Base Pattern tham chiếu '{bp_ref}' "
            f"(NCC = {rho:.4f} > β = {beta}, rotation = {rot_deg}). "
            f"Kết quả hỗ trợ giả thuyết ảnh đã qua pipeline Apple Portrait Mode. "
        )
        if exif_pred:
            txt += f"EXIF xác nhận: CustomRendered = '{cr}'. "
        elif not cr:
            txt += "EXIF không còn thông tin Portrait (có thể đã bị xoá hoặc stripped). "
        else:
            txt += f"EXIF không chỉ thị Portrait (CustomRendered = '{cr}'). "
    else:
        txt = (
            f"Không phát hiện dấu vết SDNP/BP trong ảnh (NCC max = {rho:.4f} ≤ β = {beta}). "
            f"Không đủ bằng chứng để khẳng định ảnh là Apple Portrait Mode. "
        )
        if exif_pred:
            txt += f"Lưu ý: EXIF vẫn chỉ thị CustomRendered = '{cr}' — cần đánh giá thêm. "

    txt += "Kết luận này không định danh tuyệt đối thiết bị nguồn."
    return txt


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/temp", StaticFiles(directory=str(TEMP_DIR)), name="temp")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
def status():
    bp_count = len({m["BP_ref"] for m in _bp_meta}) if _bp_meta else 0
    return {
        "bp_loaded": _P_mat is not None,
        "bp_count": bp_count,
        "beta": BETA,
        "bp_dir": str(BP_DIR),
    }


@app.post("/api/analyze")
def analyze(file: UploadFile = File(...)):
    if _P_mat is None:
        raise HTTPException(503, "BP patterns not loaded — check data/bp/ directory")

    ext = Path(file.filename or "img.jpg").suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(400, f"Unsupported format '{ext}'. Use JPEG, HEIC, or PNG.")

    sid = str(uuid.uuid4())[:8]
    out_dir = TEMP_DIR / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / f"input{ext}"

    try:
        with open(img_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Thumbnail (convert to JPEG for browser display, max 800px)
        thumb_url = None
        try:
            img_pil = PILImage.open(img_path).convert("RGB")
            img_pil.thumbnail((800, 800))
            img_pil.save(str(out_dir / "thumb.jpg"), "JPEG", quality=85)
            thumb_url = f"/temp/{sid}/thumb.jpg"
        except Exception:
            pass

        sha256 = _sha256(img_path)
        size_bytes = img_path.stat().st_size

        # EXIF analysis
        make, model = read_make_model(img_path)
        cr = read_custom_rendered(img_path)
        exif_pred = 1 if cr and cr in {"Portrait", "Portrait HDR"} else 0
        exif = {"make": make, "model": model, "custom_rendered": cr or "", "prediction": exif_pred}

        # BP detection
        det = _detect(img_path)
        I = det.pop("image_array")

        bp_ref = det.get("bp_ref")
        rot_k = det.get("rotation_k") or 0
        bp_info = _get_bp_info(bp_ref) if bp_ref else {}

        # Localization (when we have a matched BP)
        loc: dict = {"available": False}
        if bp_ref:
            try:
                loc = {"available": True, **_localize(I, bp_ref, rot_k, out_dir)}
            except Exception as e:
                loc = {"available": False, "error": str(e)}

        verdict = (
            "SCALE_AWARE" if det["detected"] is None
            else "DETECTED" if det["detected"]
            else "NOT_DETECTED"
        )

        return {
            "session_id": sid,
            "filename": file.filename,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "image_size": det["image_size"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thumbnail_url": thumb_url,
            "exif": exif,
            "detection": {
                "rho": det["rho"],
                "beta": det["beta"],
                "detected": det["detected"],
                "bp_ref": bp_ref,
                "bp_info": bp_info,
                "rotation_k": det.get("rotation_k"),
                "rotation_deg": {0: "0°", 1: "90°", 2: "180°", 3: "270°"}.get(
                    det.get("rotation_k"), "N/A"
                ),
                "latency_ms": det["latency_ms"],
                "scale_aware": det["scale_aware"],
                "filter": "box 5×5 (paper default)",
            },
            "localization": loc,
            "verdict": verdict,
            "conclusion": _conclusion(det, exif),
        }

    except HTTPException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(500, f"Analysis failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
