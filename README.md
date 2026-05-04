# Apple-s-Synthetic-Defocus-Noise-Pattern-Characterization-and-Forensic-Applications
NT334.Q21.ANTT - Digital Forensics

## 📌 Giới thiệu (Overview)
Đây là đồ án môn học **Pháp chứng kỹ thuật số (Digital Forensics)**. Đề tài tập trung vào việc nghiên cứu và thực nghiệm dựa trên bài báo: *"Apple’s Synthetic Defocus Noise Pattern: Characterization and Forensic Applications"*.

Dự án này tập trung vào việc phân tích nhiễu giả lập **SDNP** trong chế độ chụp Chân dung (Portrait Mode) của iPhone và ảnh hưởng của nó đối với kỹ thuật xác thực nguồn gốc camera bằng dấu vân tay cảm biến (**PRNU**).

## ⚖️ Bài toán & Mô hình đe dọa
* **Vấn đề:** Các thuật toán PRNU truyền thống thường bị nhầm lẫn giữa nhiễu vật lý (phần cứng) và nhiễu SDNP (phần mềm Apple chèn vào vùng bokeh). Điều này dẫn đến hiện tượng **Fingerprint Collision** (nhiều máy khác nhau bị nhận diện nhầm là một máy).
* **Mục tiêu:** Xây dựng quy trình trích xuất PRNU cải tiến bằng cách áp dụng **Masking** (che vùng nhiễu SDNP) để tăng độ chính xác trong điều tra số.

## 🛠 Môi trường & Công cụ
* **Ngôn ngữ:** Python 3.x
* **Thư viện chính:** OpenCV, NumPy, SciPy, Matplotlib.
* **Dữ liệu thực nghiệm:** Dataset tự thu thập gồm ảnh chụp từ các dòng iPhone (iPhone 13, iPhone 15...) ở chế độ Normal và Portrait.

## 🚀 Quy trình thực hiện (Pipeline)
1.  **Data Collection:** Thu thập ảnh phẳng (flat-field) để tạo Fingerprint chuẩn cho thiết bị.
2.  **Noise Extraction:** Trích xuất Noise Residual bằng bộ lọc Wiener/Wavelet.
3.  **SDNP Masking:** Sử dụng thuật toán phân vùng (Segmentation/Defocus Estimation) để xác định và loại bỏ vùng chứa nhiễu giả lập Apple.
4.  **Verification:** Tính toán chỉ số tương quan **PCE (Peak Correlation Energy)** để xác minh nguồn gốc.
5.  **Evaluation:** So sánh kết quả giữa phương pháp Baseline (truyền thống) và phương pháp cải tiến (Masking).

## 📊 Kết quả thực nghiệm
* Giảm tỷ lệ **False Positive Rate (FPR)** khi đối soát các thiết bị cùng dòng máy.
* Duy trì độ chính xác cao trong việc xác thực nguồn gốc camera đối với ảnh chụp Chế độ Chân dung.

## 📜 Tài liệu tham khảo
> David Vázquez-Padín, Fernando Pérez-González, and Pablo Pérez-Miguélez. "Apple’s Synthetic Defocus Noise Pattern: Characterization and Forensic Applications". IEEE TIFS/arXiv. <link>https://ieeexplore.ieee.org/document/11346806
