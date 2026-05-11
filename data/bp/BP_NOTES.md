# BP Reference Notes

Nguồn: TABLE I, trang 10, paper arXiv 2505.07380 (IEEE TIFS 2026).

---

## Bảng mapping BP ↔ iPhone model / iOS version (12MP rear camera)

| File `.mat` | BP | iPhone model | iOS version |
|-------------|-----|-------------|-------------|
| `BP01_12MP_NL_JPEG.mat` | BP① | iPhone 7 Plus | iOS 10 |
| `BP02_12MP_NL_JPEG.mat` | BP② | iPhone 7 Plus | iOS 11 |
| `BP03_12MP_NL_JPEG.mat` | BP③ | iPhone 8 Plus, iPhone X | iOS 11 |
| `BP04_12MP_NL_JPEG.mat` | BP④ | iPhone X, XR, XS, XS Max; iPhone 11, 11 Pro, 11 Pro Max; SE (2nd gen); iPhone 12, 13 | iOS 11–17 |
| `BP05_12MP_NL_HEIC.mat` | BP⑤ | iPhone 12 Pro Max, 12, 12 Pro, 12 mini; iPhone 13 series, SE (3rd gen); iPhone 11, 11 Pro, 11 Pro Max; iPhone 14 (trên iOS 17) | iOS 12–17 |
| `BP05_12MP_SLM_HEIC.mat` | BP⑤ | (cùng model, trích xuất bằng Stage Light Mono) | iOS 12–17 |
| `BP06_12MP_NL_HEIC.mat` | BP⑥ | iPhone 13 Pro, 14 Plus, 14 Pro, 14 Pro Max; iPhone 13, 13 mini, 13 Pro Max; iPhone 15, 15 Plus | iOS 16–26 |
| `BP06_12MP_SLM_HEIC.mat` | BP⑥ | (cùng model, trích xuất bằng Stage Light Mono) | iOS 16–26 |
| `BP07_12MP_SLM_HEIC.mat` | BP⑦ | iPhone 15 Pro, 15 Pro Max; iPhone 16, 16 Plus, 16 Pro, 16 Pro Max, 16e; iPhone 17, 17 Pro, 17 Pro Max, Air | iOS 17–26 |
| `BP08_12MP_NL_JPEG.mat` | BP⑧ | **Loại trừ khỏi bảng chính** — có thể từ Apple Photos app, không phải camera pipeline | — |

### 24MP (iPhone 15+ rear camera)

| File `.mat` | BP | Ghi chú |
|-------------|-----|---------|
| `BP06_24MP_NL_HEIC.mat` | BP⑥ 24MP | Spatially aligned + scaled version của BP⑥ 12MP |
| `BP06_24MP_SLM_HEIC.mat` | BP⑥ 24MP | (Stage Light Mono) |
| `BP07_24MP_SLM_HEIC.mat` | BP⑦ 24MP | Spatially aligned + scaled version của BP⑦ 12MP |

---

## Ký hiệu trong bảng gốc

| Ký hiệu | Nghĩa |
|---------|-------|
| ✓ | Full match — các model/iOS cùng BP index dùng chính xác cùng BP |
| ✗ | Incompatible — không có tương quan |
| (↔) | Horizontal flip — cần lật BP ngang mới thấy tương quan |

---

## Lưu ý quan trọng khi dùng

1. **Cùng model, khác iOS → có thể khác BP.** Ví dụ: iPhone 7 Plus dùng BP① (iOS 10) và BP② (iOS 11). iPhone X dùng BP③ (iOS 11) và BP④ (iOS 12+).

2. **BP④ và BP⑤ overlap nhiều model** — một số iPhone 11/12/13 có thể match cả hai tùy iOS version.

3. **BP⑧ bị loại** khỏi detection vì có thể là artifact của Apple Photos app (phần mềm), không phải camera Portrait Mode pipeline.

4. **24MP BP** là scaled version của 12MP BP — cùng structure, khác resolution.

5. **NL vs SLM:** Cùng BP, hai phương pháp trích xuất khác nhau. Dùng được cả hai cho detection; SLM thường sạch hơn vì nền đen đồng nhất.

6. **Detector thử 4 rotations (0°, 90°, 180°, 270°)** vì ảnh có thể bị xoay do EXIF orientation.
