# Báo Cáo Đánh Giá Thực Nghiệm SDNP/BP Detector

## 1. Tóm Tắt Điều Hành

Báo cáo này tổng hợp kết quả thực nghiệm của pipeline phát hiện dấu vết **Apple Synthetic Defocus Noise Pattern (SDNP)** bằng **Base Pattern (BP)**. Trực giác đơn giản: detector giống như một thiết bị so khớp "vân nhiễu" trong ảnh. Nếu vân nhiễu trong residual của ảnh khớp với BP tham chiếu và điểm tương quan `rho` vượt ngưỡng `beta = 0.0072`, ảnh được dự đoán là có dấu vết Apple Portrait/SDNP.

Kết quả chính:

- Detector đạt **Recall/TPR cao trên ảnh Apple Portrait**: `97.81%` trên ảnh gốc.
- Xóa EXIF gần như **không làm giảm khả năng phát hiện**: `98.02%` recall.
- JPEG recompression làm giảm tín hiệu theo mức nén: Q95 tốt, Q80 giảm nhẹ, Q60 giảm rõ.
- Resize làm suy yếu SDNP, đặc biệt resize `0.25`.
- Kiểm tra 4 rotation là cần thiết: bỏ rotation làm recall giảm từ `97.81%` xuống `73.60%`.
- FPR strict trên negative controls matched-resolution đạt `0%` trên `85` ảnh hợp lệ; tuy nhiên coverage FPR còn hạn chế vì `365/450` ảnh negative khác resolution với BP 12MP.

Kết luận cần viết cẩn thận:

> Pipeline cho thấy khả năng phát hiện SDNP rất tốt trên ảnh Apple Portrait và có tính bền vững với EXIF stripping/JPEG nhẹ. Kết quả FPR strict là 0% trên tập negative có cùng resolution, nhưng chưa nên mở rộng kết luận FPR = 0% cho toàn bộ 450 ảnh negative vì phần lớn ảnh khác kích thước với BP 12MP.

## 2. Nguồn Dữ Liệu Và Phạm Vi Đánh Giá

### 2.1 Positive Dataset

Tập positive là official Apple Portrait Image Dataset đã được tải từ README của repo tác giả. Trong project hiện tại:

| Thành phần | Số lượng |
|---|---:|
| Ảnh raw official | 1277 |
| `.jpg` | 759 |
| `.jpeg` | 133 |
| `.heic` | 385 |
| Label positive | 1277 |

Lưu ý quan trọng: benchmark `results/original` hiện chỉ chạy trên `1144` ảnh, vì detector hiện tại chỉ nhận `.jpg` và `.heic`, không nhận `.jpeg`.

### 2.2 Processed Benchmark

Mỗi condition processed có `1260` ảnh:

| Condition | Số ảnh |
|---|---:|
| `exif_stripped` | 1260 |
| `jpeg_q95` | 1260 |
| `jpeg_q80` | 1260 |
| `jpeg_q60` | 1260 |
| `resize_05` | 1260 |
| `resize_025` | 1260 |

Tổng file processed là `7560` file, nhưng đây là 6 biến thể của cùng tập ảnh, không phải 7560 mẫu độc lập.

Lý do processed có `1260` thay vì `1277`: có `17` duplicate filename stem trong raw dataset. Khi transform, `.jpg`, `.jpeg`, `.heic` đều được lưu thành `.jpg`, nên các ảnh trùng stem bị overwrite.

### 2.3 Negative Controls Cho FPR

Tập negative lấy từ PrnuModernDevices, chỉ dùng `C01-C18` làm non-Apple negative controls. `C19-C22` bị loại khỏi FPR negative vì là Apple iPhone devices.

| Thành phần | Số lượng |
|---|---:|
| Negative images downloaded | 450 |
| Valid matched-resolution for strict FPR | 85 |
| Skipped do size mismatch | 365 |
| False positives | 0 |

Phân bố 85 ảnh strict-size:

| Device | Số ảnh hợp lệ |
|---|---:|
| C10 | 10 |
| C14 | 25 |
| C15 | 25 |
| C16 | 25 |

Theo loại ảnh:

| Mode | Số ảnh hợp lệ |
|---|---:|
| bokeh | 40 |
| flat | 15 |
| nat | 30 |

### 2.4 Ghi Chú Thuật Ngữ

Để tránh nhầm lẫn khi đọc báo cáo:

| Thuật ngữ | Cách hiểu trong báo cáo |
|---|---|
| Positive | Ảnh Apple Portrait có kỳ vọng chứa dấu vết SDNP |
| Negative | Ảnh đối chứng không phải Apple Portrait, dùng để đo báo nhầm |
| Strict FPR | FPR chỉ tính trên ảnh negative có cùng kích thước với BP 12MP |
| Matched-resolution | Ảnh có đúng grid `4032x3024` hoặc tương đương sau xoay |
| Scale-aware | Chế độ resize BP theo kích thước ảnh; dùng để khảo sát robustness, không hoàn toàn tương đương benchmark paper |

### 2.5 Phạm Vi BP Sử Dụng

Detector trong các benchmark chính dùng BP 12MP có grid `4032x3024`. Các BP 24MP trong `data/bp` không được dùng cho benchmark này vì official positive dataset hiện chỉ có ảnh 12MP (`3024x4032` hoặc `4032x3024`). Việc tách 12MP/24MP là cần thiết để tránh so khớp BP sai kích thước.

Với FPR strict, ảnh negative cũng chỉ được hard-decision nếu có cùng grid 12MP. Đây là lý do nhiều ảnh PrnuModernDevices bị skip do resolution mismatch.

## 3. Giải Thích Metrics Sử Dụng

### 3.1 `rho`

`rho` là điểm tương quan cao nhất giữa residual của ảnh và các BP reference. Có thể hiểu là "độ khớp vân nhiễu". `rho` càng cao thì khả năng ảnh có dấu vết SDNP càng lớn.

Trong pipeline:

```text
Ảnh -> luminance -> residual -> NCC với BP variants -> rho_max
```

### 3.2 `beta`

`beta` là ngưỡng quyết định. Thực nghiệm dùng:

```text
beta = 0.0072
```

Rule:

```text
rho > beta  -> detected SDNP
rho <= beta -> not detected
```

### 3.3 Accuracy

`Accuracy` là tỷ lệ dự đoán đúng trên toàn bộ mẫu được evaluate.

```text
Accuracy = (TP + TN) / (TP + TN + FP + FN)
```

Trong positive-only benchmark, accuracy gần với recall vì tất cả mẫu đều là label `1`.

### 3.4 Precision

`Precision` trả lời: trong những ảnh detector báo detected, bao nhiêu ảnh thật sự là positive.

```text
Precision = TP / (TP + FP)
```

Trong positive-only benchmark, precision `1.0` không nên được diễn giải quá mạnh, vì không có negative sample để tạo false positive.

### 3.5 Recall / TPR

`Recall` hay `TPR` là metric quan trọng nhất trên tập positive. Nó trả lời: trong các ảnh Apple Portrait thật, detector bắt được bao nhiêu.

```text
Recall = TP / (TP + FN)
```

### 3.6 FPR

`FPR` là tỷ lệ báo nhầm positive trên ảnh negative.

```text
FPR = FP / (FP + TN)
```

FPR chỉ có ý nghĩa khi có tập negative. Do đó, FPR trong positive-only benchmark không đủ để kết luận; FPR nên lấy từ `results/fpr_controls`.

### 3.7 F1-score

`F1` là trung bình điều hòa giữa precision và recall.

```text
F1 = 2 * precision * recall / (precision + recall)
```

Trong báo cáo này, F1 dùng để tóm tắt performance detection, nhưng recall và FPR vẫn quan trọng hơn về mặt forensic.

### 3.8 ROC-AUC

`ROC-AUC` cần có cả positive và negative để có ý nghĩa. Trong các benchmark positive-only hoặc negative-only, `roc_auc = null` là đúng và không phải lỗi.

### 3.9 Latency

`avg_latency_ms` là thời gian xử lý trung bình mỗi ảnh. Metric này phụ thuộc CPU/RAM, số BP variants, kích thước ảnh, và filter residual.

### 3.10 Calibrated Beta

Một số `metrics.json` có trường `at_calibrated_beta`. Đây là ngưỡng được fit từ chính test set, ví dụ chọn theo negative scores để đạt FPR thấp nhất trên tập đó. Metric này hữu ích để tham khảo upper-bound, nhưng **không dùng làm kết luận forensic chính** vì có test-set bias. Báo cáo này ưu tiên ngưỡng paper `beta = 0.0072`.

## 4. Kết Quả Main Benchmark

### 4.1 Bảng Metrics Chính

| Experiment | N | Positive | Accuracy | Precision | Recall/TPR | FPR | F1 | Avg latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original | 1144 | 1144 | 97.81% | 100.00%* | 97.81% | N/A | 98.90% | 3238.3 ms |
| No-rotation control | 1144 | 1144 | 73.60% | 100.00%* | 73.60% | N/A | 84.79% | 975.9 ms |
| EXIF stripped | 1260 | 1260 | 98.02% | 100.00%* | 98.02% | N/A | 99.00% | 3293.7 ms |
| JPEG Q95 | 1260 | 1260 | 98.02% | 100.00%* | 98.02% | N/A | 99.00% | 3097.3 ms |
| JPEG Q80 | 1260 | 1260 | 95.87% | 100.00%* | 95.87% | N/A | 97.89% | 3195.7 ms |
| JPEG Q60 | 1260 | 1260 | 88.65% | 100.00%* | 88.65% | N/A | 93.98% | 3064.1 ms |
| Resize 0.5 | 1260 | 1260 | 96.90% | 100.00%* | 96.90% | N/A | 98.43% | 1883.6 ms |
| Resize 0.25 | 1260 | 1260 | 79.05% | 100.00%* | 79.05% | N/A | 88.30% | 964.4 ms |
| FPR controls strict | 85 | 0 | 100.00% | N/A | N/A | 0.00% | N/A | 801.9 ms |

Ghi chú:

- `Original`, robustness, resize là positive-only experiments; metric quan trọng nhất là Recall/TPR.
- `FPR controls strict` là negative-only experiment; metric quan trọng nhất là FPR.
- `N/A` nghĩa là metric không có ý nghĩa trong experiment đó. Ví dụ: positive-only không đo được FPR; negative-only không đo được recall.
- Dấu `*` ở Precision nghĩa là giá trị này được tính từ positive-only dataset, không dùng để kết luận detector không báo nhầm.

### 4.2 False Negative Theo Condition

| Experiment | N | FN | Recall |
|---|---:|---:|---:|
| Original | 1144 | 25 | 97.81% |
| No-rotation control | 1144 | 302 | 73.60% |
| EXIF stripped | 1260 | 25 | 98.02% |
| JPEG Q95 | 1260 | 25 | 98.02% |
| JPEG Q80 | 1260 | 52 | 95.87% |
| JPEG Q60 | 1260 | 143 | 88.65% |
| Resize 0.5 | 1260 | ~39 | 96.90% |
| Resize 0.25 | 1260 | ~264 | 79.05% |

Với resize, detector chạy scale-aware và output hard label được evaluate lại theo `rho > beta`; do đó nên xem resize là robustness exploratory, không phải benchmark paper-threshold hoàn toàn tương đương.

## 5. Nhận Định Theo Từng Experiment

### 5.1 Original

Kết quả:

```text
Recall = 97.81%
FN = 25 / 1144
F1 = 98.90%
```

Nhận định:

- Detector phát hiện được phần lớn ảnh Apple Portrait trong official dataset.
- `rho` trên ảnh positive cao hơn nhiều so với ngưỡng `beta = 0.0072`; median rho trên original là khoảng `0.1105`.
- Kết quả này ủng hộ giả thuyết rằng SDNP/BP là dấu vết có tính lặp lại trong ảnh Portrait.

Nguyên nhân có thể tạo FN:

- Ảnh có dấu vết SDNP yếu hoặc vùng bokeh không đủ mạnh.
- Ảnh bị nén/chỉnh sửa trước khi vào dataset.
- Một số ảnh có orientation/texture/noise làm NCC với BP thấp hơn ngưỡng.

Lưu ý: `.jpeg` bị bỏ qua trong original benchmark là vấn đề coverage của experiment, không phải nguyên nhân trực tiếp tạo FN. Các ảnh `.jpeg` không nằm trong 1144 mẫu được evaluate.

### 5.2 No-rotation Control

Kết quả:

```text
Full rotation recall = 97.81%
No-rotation recall   = 73.60%
FN no-rotation       = 302
```

Nhận định:

- Kiểm tra 4 rotation là cần thiết.
- Bỏ rotation làm detector nhanh hơn (`975.9 ms/ảnh` so với `3238.3 ms/ảnh`) nhưng recall giảm mạnh.
- Về forensic, tradeoff này không đáng để dùng no-rotation làm detector chính.

Cơ chế:

```text
Image orientation / sensor orientation / saved rotation
        -> BP trong ảnh có thể bị xoay
        -> cần test 0/90/180/270 degree
```

### 5.3 EXIF Stripped

Kết quả:

```text
Recall = 98.02%
FN = 25 / 1260
```

Nhận định:

- Xóa EXIF không làm detector suy giảm.
- Điều này rất quan trọng về forensic: pipeline không dựa vào metadata như camera model, maker note, Portrait flag, GPS, hay EXIF custom fields.
- Detector đang dựa vào artifact nội dung ảnh, cụ thể là residual pattern.

Truy vết nguyên nhân:

```text
Strip EXIF -> metadata mất
Residual pixel content -> gần như giữ nguyên
NCC với BP -> rho không giảm đáng kể
```

### 5.4 JPEG Recompression

Kết quả:

| Condition | Recall | FN | rho mean |
|---|---:|---:|---:|
| JPEG Q95 | 98.02% | 25 | 0.148990 |
| JPEG Q80 | 95.87% | 52 | 0.116564 |
| JPEG Q60 | 88.65% | 143 | 0.068421 |

Nhận định:

- JPEG Q95 gần như tương đương EXIF stripped.
- JPEG Q80 bắt đầu làm recall giảm nhưng detector vẫn khá bền vững.
- JPEG Q60 làm tín hiệu SDNP suy yếu rõ, FN tăng từ `25` lên `143`.

Truy vết nguyên nhân:

```text
JPEG compression
  -> quantization trong miền tần số
  -> mất bớt high-frequency residual
  -> rho giảm
  -> nhiều ảnh rơi xuống dưới beta
  -> FN tăng
```

Đây là kết quả hợp lý về mặt signal processing, vì SDNP/BP detector khai thác residual/noise-like pattern.

### 5.5 Resize

Kết quả:

| Condition | Recall | rho mean | Avg latency |
|---|---:|---:|---:|
| Resize 0.5 | 96.90% | 0.094968 | 1883.6 ms |
| Resize 0.25 | 79.05% | 0.030162 | 964.4 ms |

Nhận định:

- Resize 0.5 vẫn giữ recall cao, nhưng rho đã giảm so với original.
- Resize 0.25 làm recall giảm mạnh; dấu vết SDNP bị phá vỡ nhiều hơn.
- Latency giảm khi resize do ảnh nhỏ hơn, NCC tính trên vector ngắn hơn.

Truy vết nguyên nhân:

```text
Resize
  -> thay đổi spatial grid của ảnh
  -> BP gốc không còn align tự nhiên với residual
  -> scale-aware resize BP chỉ là xấp xỉ
  -> rho giảm, đặc biệt khi downscale mạnh
```

Lưu ý khoa học: resize experiment nên được trình bày là **exploratory robustness** vì scale-aware mode resize BP theo kích thước ảnh. `rho` và `beta` lúc này không hoàn toàn tương đương với benchmark paper trên grid 12MP gốc.

### 5.6 FPR Strict

Kết quả:

```text
Total negative images: 450
Valid strict-size:     85
Skipped mismatch:      365
False positives:       0
Strict FPR:            0.0%
```

Margin negative:

```text
max negative rho = 0.004209
paper beta       = 0.0072
max/beta         = 58.5%
```

Trong `metrics.json`, calibrated beta của FPR controls là khoảng `0.00421`. Giá trị này chỉ phản ánh ngưỡng fit trên chính negative set, không được dùng thay cho `beta = 0.0072` trong kết luận chính.

Nhận định:

- Trên 85 ảnh non-Apple có cùng resolution với BP 12MP, detector không tạo false positive.
- Negative rho cao nhất vẫn thấp hơn ngưỡng beta khá rõ, cho thấy separation margin tốt.
- Kết quả này là tín hiệu tốt cho forensic specificity, nhưng coverage còn hạn chế.

Không nên viết:

```text
FPR = 0% trên 450 ảnh.
```

Nên viết:

```text
Strict FPR = 0% trên 85 ảnh non-Apple matched-resolution.
365 ảnh còn lại bị loại khỏi hard-decision FPR do resolution mismatch.
```

Truy vết nguyên nhân skip:

```text
BP reference: 4032x3024
Negative controls: nhiều resolution khác nhau
Nếu khác grid -> detector strict skip để tránh so khớp sai kích thước
```

## 6. Filter Comparison

Filter comparison dùng để kiểm tra cách tạo residual có ảnh hưởng thế nào đến detection.

Ba filter:

- `box`: box filter 5x5, gần với default/paper-like pipeline.
- `gauss1`: Gaussian blur sigma 1.
- `gauss2`: Gaussian blur sigma 2.

### 6.1 Bảng So Sánh Recall

| Condition | Box | Gauss1 | Gauss2 | Filter tốt nhất |
|---|---:|---:|---:|---|
| Original | 97.81% | 97.38% | 98.08% | Gauss2 |
| EXIF stripped | 98.02% | 96.98% | 98.25% | Gauss2 |
| JPEG Q95 | 98.02% | 96.98% | 98.25% | Gauss2 |
| JPEG Q80 | 95.87% | 94.68% | 96.83% | Gauss2 |
| JPEG Q60 | 88.65% | 86.51% | 91.19% | Gauss2 |
| Resize 0.5 | 96.90% | 97.22% | 96.19% | Gauss1 |
| Resize 0.25 | 79.05% | 81.27% | 75.24% | Gauss1 |

### 6.2 Nhận Định Filter

Gauss2 thường tốt hơn trong điều kiện JPEG compression:

- JPEG Q80: Box `95.87%`, Gauss2 `96.83%`.
- JPEG Q60: Box `88.65%`, Gauss2 `91.19%`.

Giải thích hợp lý:

```text
JPEG compression tạo artifact và làm residual nhiễu hơn
Gaussian sigma 2 smoothing mạnh hơn
  -> residual sau khi trừ smooth có thể ổn định hơn
  -> rho tăng nhẹ ở một số condition
```

Resize lại cho kết quả khác:

- Resize 0.5: Gauss1 tốt nhất.
- Resize 0.25: Gauss1 tốt nhất, Gauss2 tệ nhất.

Giải thích:

```text
Resize đã làm mất nhiều high-frequency detail
Gauss2 smoothing thêm có thể làm mất tiếp tín hiệu SDNP
Gauss1 cân bằng hơn
```

Kết luận filter:

- `box` là baseline ổn định và gần với pipeline gốc.
- `gauss2` đáng cân nhắc nếu mục tiêu là robust với JPEG compression.
- `gauss1` phù hợp hơn cho resize experiments.
- Không nên đổi filter mặc định chỉ dựa trên positive recall; cần chạy FPR riêng cho từng filter nếu muốn đề xuất filter mới làm forensic default.

## 7. Phân Tích Rho

`rho` là tín hiệu gốc để ra quyết định. Khi các biến đổi ảnh làm `rho` giảm, detector có nguy cơ false negative.

| Condition | Median rho | Nhận định |
|---|---:|---|
| Original | 0.1105 | Tín hiệu SDNP mạnh |
| JPEG Q95 | 0.1010 | Giảm nhẹ |
| JPEG Q80 | 0.0738 | Giảm rõ nhưng vẫn cao hơn beta với đa số ảnh |
| JPEG Q60 | 0.0317 | Giảm mạnh, FN tăng |
| Resize 0.5 | 0.0657 | Còn detect được nhiều ảnh |
| Resize 0.25 | 0.0187 | Gần ngưỡng hơn, FN tăng mạnh |

Threshold:

```text
beta = 0.0072
```

Nhận định:

- Original/JPEG Q95 có margin cao.
- JPEG Q60 và resize 0.25 làm phân phối rho tiến gần ngưỡng hơn.
- Đây là nguyên nhân trực tiếp của việc recall giảm.

## 8. Phân Tích Forensic

### 8.1 Điểm Mạnh

Signal:

- Detector dựa vào residual pattern, không dựa vào EXIF.
- Recall cao trên Apple Portrait.
- Strict FPR trên matched-resolution negative controls bằng 0%.

Impact:

- Có thể phát hiện dấu vết Apple Portrait ngay cả khi metadata bị xóa.
- Có giá trị trong forensic triage khi cần nghi ngờ ảnh có synthetic bokeh/Portrait artifact.

Mitigation/Usage:

- Dùng detector như một signal kỹ thuật, không dùng như bằng chứng duy nhất.
- Kết hợp với manifest SHA-256, chain-of-custody, và phân tích ngữ cảnh ảnh.

### 8.2 Hạn Chế

Hạn chế chính:

- Phụ thuộc BP reference và resolution.
- Original benchmark chưa include `.jpeg`, nên N original là `1144` thay vì `1277`.
- Processed benchmark có `1260` ảnh do duplicate stem overwrite khi convert sang `.jpg`.
- Resize/scale-aware là exploratory, không phải benchmark paper-threshold hoàn toàn tương đương.
- FPR strict chỉ có `85` matched-resolution negative images.
- ROC-AUC không tính được trong các experiment positive-only/negative-only.

### 8.3 Rủi Ro Diễn Giải Sai

Không nên kết luận:

- "Precision = 100% nên detector không báo nhầm" trên positive-only dataset.
- "FPR = 0% trên 450 negative" khi chỉ có 85 ảnh được evaluate strict.
- "Resize result là forensic hard decision tương đương paper" vì scale-aware thay đổi BP grid.

Nên kết luận:

- Positive benchmark chứng minh recall/robustness.
- Negative matched-resolution benchmark chứng minh FPR strict trong phạm vi 85 ảnh.
- Cần thêm negative same-resolution nếu muốn tăng độ mạnh cho kết luận FPR.

## 9. Truy Vết Nguồn Kết Quả

| Hạng mục | File/Folder |
|---|---|
| Main benchmark | `results/*/metrics.json` |
| Prediction CSV | `results/*/sdnp_results.csv` |
| Filter comparison | `results_residual/comparison_summary.csv` |
| Filter metrics | `results_residual/<condition>/<filter>/metrics.json` |
| FPR strict | `results/fpr_controls/metrics.json` |
| FPR predictions | `results/fpr_controls/sdnp_results.csv` |
| Negative source summary | `data/raw/fpr_controls/PrnuModernDevices_C01_C18_summary.json` |
| Labels official | `data/labels.csv`, `data/labels_official.csv` |
| BP reference | `data/bp/*.mat` |

## 10. Kết Luận Chính Thức Để Đưa Vào Báo Cáo

Kết quả thực nghiệm cho thấy BP/SDNP detector có khả năng phát hiện mạnh trên official Apple Portrait dataset, với recall `97.81%` trên ảnh gốc và gần như không suy giảm khi EXIF bị xóa. Điều này xác nhận detector khai thác dấu vết trong nội dung ảnh, không phụ thuộc vào metadata. JPEG recompression làm suy yếu tín hiệu SDNP theo mức nén, đặc biệt ở Q60, trong khi resize mạnh làm giảm rho do thay đổi spatial grid của BP. Kiểm tra 4 rotation là thành phần bắt buộc vì nó giúp recall tăng từ `73.60%` lên `97.81%`.

Trên negative controls non-Apple có cùng resolution với BP 12MP, detector đạt strict FPR `0%` với `0/85` false positives. Negative rho cao nhất là `0.004209`, thấp hơn ngưỡng paper `0.0072`, cho thấy separation margin tốt trong phạm vi matched-resolution. Tuy nhiên, FPR strict chỉ bao phủ `85/450` ảnh negative do `365` ảnh còn lại khác resolution, nên không nên mở rộng kết luận FPR cho toàn bộ tập negative. Để tăng độ mạnh khoa học, cần bổ sung thêm negative images có resolution `4032x3024` hoặc thiết kế experiment score-only riêng cho ảnh khác resolution.

Tổng thể, pipeline phù hợp để chứng minh khả năng phát hiện SDNP/Apple Portrait artifact trong điều kiện forensic có kiểm soát, đặc biệt khi metadata bị xóa. Kết quả nên được trình bày như một detection signal có tính định lượng, cần kết hợp với các bằng chứng forensic khác thay vì dùng như kết luận định danh thiết bị tuyệt đối.

## 11. Câu Văn Khuyến Nghị Cho Slide/Report

Có thể dùng câu sau trong report:

> Detector SDNP dựa trên BP đạt recall cao trên official Apple Portrait dataset và vẫn hoạt động ổn định sau khi xóa EXIF, cho thấy tín hiệu phát hiện đến từ residual artifact trong nội dung ảnh thay vì metadata. JPEG recompression và resize mạnh làm giảm điểm tương quan SDNP, từ đó tăng số false negative. Kiểm tra 4 rotation là cần thiết để giữ recall cao. Trên negative controls non-Apple có cùng resolution với BP 12MP, strict FPR đạt 0%, nhưng coverage FPR còn hạn chế do nhiều ảnh negative khác resolution.
