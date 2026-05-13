import os
import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS
from pillow_heif import register_heif_opener

register_heif_opener()

def get_device_info(img_path):
    try:
        with Image.open(img_path) as image:
            exif = image.getexif()
            info = {}
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    info[tag] = str(value).strip()
            
            make = info.get("Make", "Unknown")
            model = info.get("Model", "Unknown")
            software = info.get("Software", "Unknown")
            return make, model, software
    except Exception:
        return "Unknown", "Unknown", "Unknown"

dataset_path = "Dataset"
label_output = "data/labels.csv" 

data_list = []

print(f"🔍 Đang thu thập thông tin từ file ảnh trong {dataset_path}...")

for root, dirs, files in os.walk(dataset_path):
    for filename in files:
        if filename.lower().endswith(('.heic', '.jpg')):
            img_path = os.path.join(root, filename)
            
            make, model, software = get_device_info(img_path)
            rel_path = os.path.relpath(root, dataset_path)
            path_parts = rel_path.split(os.sep)
            
            category = path_parts[0] if path_parts[0] != '.' else "Unknown"
            sub_folder = path_parts[1] if len(path_parts) > 1 else ""

            data_list.append({
                "filename": filename,
                "label": "",
                "source": category,   
                "notes": f"Folder: {sub_folder}" if sub_folder else "",
                "device_make": make,
                "device_model": model,
                "os_version": software
            })

df_new = pd.DataFrame(data_list)
df_new.to_csv(label_output, index=False, encoding='utf-8-sig')

print("-" * 40)
print(f"✅ Hoàn tất! Đã điền xong file vào {label_output}")
print(f"📂 Các cột hiện có: {list(df_new.columns)}")
print("-" * 40)