import os
from PIL import Image
import shutil

def process_recursive_dataset(source_root, output_folder="Checked_image"):
    target_resolutions = [(4032, 3024), (3024, 4032)]
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"--- [!] Đã tạo thư mục đầu ra: {output_folder} ---")

    valid_count = 0
    skipped_count = 0
    error_count = 0

    print(f"{'STATUS':<10} | {'FILENAME':<35} | {'RESOLUTION/INFO'}")
    print("-" * 70)

    for root, dirs, files in os.walk(source_root):
        if os.path.abspath(root) == os.path.abspath(output_folder):
            continue

        for filename in files:
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.bmp', '.tif')):
                file_path = os.path.join(root, filename)
                
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                        res_str = f"{width}x{height}"
                        
                        if (width, height) in target_resolutions:
                            # Xử lý trùng tên
                            dest_filename = filename
                            base, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(os.path.join(output_folder, dest_filename)):
                                dest_filename = f"{base}_{counter}{ext}"
                                counter += 1
                                
                            shutil.copy2(file_path, os.path.join(output_folder, dest_filename))
                            
                            # Hiển thị trạng thái ADD
                            print(f"{'[+] ADD':<10} | {filename[:33]+'..' if len(filename)>33 else filename:<35} | {res_str}")
                            valid_count += 1
                        else:
                            # Hiển thị trạng thái SKIP
                            print(f"{'[-] SKIP':<10} | {filename[:33]+'..' if len(filename)>33 else filename:<35} | {res_str}")
                            skipped_count += 1
                except Exception as e:
                    print(f"{'[!] ERR':<10} | {filename[:33]+'..' if len(filename)>33 else filename:<35} | {str(e)[:30]}")
                    error_count += 1
    
    print("-" * 70)
    print(f"TỔNG KẾT:")
    print(f"  * Thành công: {valid_count} ảnh")
    print(f"  * Bỏ qua:    {skipped_count} ảnh")
    print(f"  * Lỗi:       {error_count} ảnh")
    print(f"Dữ liệu đã được gom tại: {os.path.abspath(output_folder)}")

# --- CẤU HÌNH ---
input_dir = 'Dataset' # Thay bằng tên folder của bạn
process_recursive_dataset(input_dir)