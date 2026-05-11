"""
report_case.py
Tạo forensic case report từ kết quả detection.
Output: case_report.json + case_report.md

Ngôn ngữ kết luận dùng xác suất/hỗ trợ, không định danh tuyệt đối.

Usage:
    python src/report_case.py \
        --manifest results/manifest.csv \
        --pred results/original/sdnp_results.csv \
        --baseline results/exif_baseline.csv \
        --output results/original/
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def load_csv_as_dict(path: Path, key: str = "filename") -> dict:
    rows = {}
    if not path or not path.exists():
        return rows
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows[row[key]] = row
    return rows


def forensic_conclusion(pred_row: dict, exif_row: dict | None) -> str:
    rho = float(pred_row.get("rho", 0))
    beta = float(pred_row.get("beta", 0.0072))
    detected = int(pred_row.get("pred_label", 0)) == 1
    bp_ref = pred_row.get("bp_ref", "")
    rotation_k = pred_row.get("rotation_k", "")
    exif_pred = int(exif_row.get("exif_prediction", -1)) if exif_row else -1
    cr = exif_row.get("custom_rendered", "") if exif_row else ""

    if detected:
        rot_deg = {0: "0°", 1: "90°", 2: "180°", 3: "270°"}.get(int(rotation_k) if rotation_k else 0, "?")
        conclusion = (
            f"Ảnh có dấu hiệu tương thích với Base Pattern tham chiếu '{bp_ref}' "
            f"(NCC = {rho:.4f} > β = {beta}, rotation = {rot_deg}). "
            f"Kết quả hỗ trợ giả thuyết ảnh đã qua pipeline Apple Portrait Mode. "
        )
        if exif_pred == 1:
            conclusion += f"EXIF xác nhận: CustomRendered = '{cr}'."
        elif exif_pred == 0 and cr == "":
            conclusion += "EXIF không còn thông tin Portrait (có thể đã bị xoá hoặc stripped)."
        elif exif_pred == 0:
            conclusion += f"EXIF không chỉ thị Portrait (CustomRendered = '{cr}')."
    else:
        conclusion = (
            f"Không phát hiện dấu vết SDNP/BP trong ảnh (NCC max = {rho:.4f} ≤ β = {beta}). "
            f"Không đủ bằng chứng để khẳng định ảnh là Apple Portrait Mode. "
        )
        if exif_pred == 1:
            conclusion += f"Lưu ý: EXIF vẫn chỉ thị CustomRendered = '{cr}' — cần đánh giá thêm."

    conclusion += " Kết luận này không định danh tuyệt đối thiết bị nguồn."
    return conclusion


def build_report(manifest_path: Path, pred_path: Path, baseline_path: Path | None, output_dir: Path):
    manifest = load_csv_as_dict(manifest_path)
    preds = load_csv_as_dict(pred_path)
    baseline = load_csv_as_dict(baseline_path) if baseline_path else {}

    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    report = {
        "report_generated": now,
        "tool": "sdnp-forensic-toolkit",
        "items": []
    }
    md_lines = [
        "# Forensic Case Report",
        f"Generated: {now}",
        "",
        "---",
        "",
    ]

    for filename, pred_row in preds.items():
        mf = manifest.get(filename, {})
        exif_row = baseline.get(filename)

        item = {
            "filename": filename,
            "sha256": mf.get("sha256", ""),
            "size_bytes": mf.get("size_bytes", ""),
            "label_ground_truth": pred_row.get("label", ""),
            "bp_detection": {
                "pred_label": pred_row.get("pred_label", ""),
                "rho": pred_row.get("rho", ""),
                "beta": pred_row.get("beta", ""),
                "bp_ref": pred_row.get("bp_ref", ""),
                "rotation_k": pred_row.get("rotation_k", ""),
            },
            "exif_baseline": {
                "exif_make": exif_row.get("exif_make", "") if exif_row else "",
                "exif_model": exif_row.get("exif_model", "") if exif_row else "",
                "custom_rendered": exif_row.get("custom_rendered", "") if exif_row else "",
                "exif_prediction": exif_row.get("exif_prediction", "") if exif_row else "",
            },
            "conclusion": forensic_conclusion(pred_row, exif_row),
        }
        report["items"].append(item)

        # Markdown entry
        detected = pred_row.get("pred_label", "0") == "1"
        status = "**DETECTED**" if detected else "not detected"
        md_lines += [
            f"## {filename}",
            f"- SHA-256: `{mf.get('sha256', 'N/A')}`",
            f"- Size: {mf.get('size_bytes', 'N/A')} bytes",
            f"- Ground truth label: {pred_row.get('label', 'N/A')}",
            f"- BP detection: {status} | rho = {pred_row.get('rho', '')} | BP = {pred_row.get('bp_ref', '') or '—'}",
            f"- EXIF: Make={exif_row.get('exif_make','') if exif_row else ''} | Model={exif_row.get('exif_model','') if exif_row else ''} | CustomRendered={exif_row.get('custom_rendered','') if exif_row else ''}",
            "",
            f"> **Kết luận:** {item['conclusion']}",
            "",
            "---",
            "",
        ]

    json_path = output_dir / "case_report.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Case report (JSON) → {json_path}")

    md_path = output_dir / "case_report.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"Case report (MD)   → {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate forensic case report.")
    parser.add_argument("--manifest", required=True, help="manifest.csv from forensic_manifest.py")
    parser.add_argument("--pred", required=True, help="sdnp_results.csv from sdnp_detector.py")
    parser.add_argument("--baseline", default=None, help="exif_baseline.csv (optional)")
    parser.add_argument("--output", required=True, help="Output folder")
    args = parser.parse_args()

    baseline = Path(args.baseline) if args.baseline else None
    build_report(Path(args.manifest), Path(args.pred), baseline, Path(args.output))


if __name__ == "__main__":
    main()
