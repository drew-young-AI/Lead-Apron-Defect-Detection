import os
import sys
from pathlib import Path
import numpy as np
import pydicom
from PIL import Image

def generate_dataset():
    print("=== 開始生成 YOLO 訓練資料集 ===")
    
    # 定義目錄
    base_dir = Path(__file__).parent / "yolo_dataset"
    img_train_dir = base_dir / "images" / "train"
    img_val_dir = base_dir / "images" / "val"
    lbl_train_dir = base_dir / "labels" / "train"
    lbl_val_dir = base_dir / "labels" / "val"
    
    for d in [img_train_dir, img_val_dir, lbl_train_dir, lbl_val_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    # 1. 載入原始 DICOM 檔案
    dcm_path = Path(__file__).parent.parent / "data" / "test_image.dcm"
    if not dcm_path.exists():
        print(f"錯誤: 找不到原始 DICOM 檔案 {dcm_path}")
        sys.exit(1)
        
    ds = pydicom.dcmread(str(dcm_path), force=True)
    pixel_array = ds.pixel_array.astype(float)
    
    # 歸一化至 8-bit
    p_min, p_max = pixel_array.min(), pixel_array.max()
    if p_max > p_min:
        img_8 = ((pixel_array - p_min) / (p_max - p_min) * 255.0).astype(np.uint8)
    else:
        img_8 = np.zeros(pixel_array.shape, dtype=np.uint8)
        
    H, W = img_8.shape
    print(f"原始影像尺寸: {W} x {H}")
    
    # 2. 將影像存為 JPG
    img = Image.fromarray(img_8, mode="L")
    img.save(img_train_dir / "test_image.jpg", format="JPEG")
    img.save(img_val_dir / "test_image.jpg", format="JPEG")
    print("-> 影像檔案生成成功 [OK]")
    
    # 3. 模擬使用者點擊所產生的多邊形座標（包含破洞與裂痕兩種）
    # 破洞 (Class 0): 圓形/氣孔型 (在 128x128 的範圍內)
    poly_hole = np.array([[20, 20], [30, 15], [40, 25], [35, 40], [15, 30]], dtype=float)
    # 裂痕 (Class 1): 細長型 (在 128x128 的範圍內)
    poly_crack = np.array([[80, 80], [90, 75], [110, 110], [105, 115]], dtype=float)
    
    # 歸一化座標公式: x / W, y / H
    norm_hole = []
    for p in poly_hole:
        norm_hole.append(f"{p[0]/W:.6f} {p[1]/H:.6f}")
        
    norm_crack = []
    for p in poly_crack:
        norm_crack.append(f"{p[0]/W:.6f} {p[1]/H:.6f}")
        
    # YOLO seg 格式: [class_id] [x1] [y1] [x2] [y2] ...
    line_hole = f"0 {' '.join(norm_hole)}"
    line_crack = f"1 {' '.join(norm_crack)}"
    
    # 寫入 labels 檔案
    label_content = f"{line_hole}\n{line_crack}"
    (lbl_train_dir / "test_image.txt").write_text(label_content, encoding="utf-8")
    (lbl_val_dir / "test_image.txt").write_text(label_content, encoding="utf-8")
    print("-> 標註座標標籤檔案生成成功 [OK]")
    
    # 4. 生成 data.yaml
    yaml_content = f"""path: {base_dir.absolute().as_posix()}
train: images/train
val: images/val
nc: 2
names:
  0: hole
  1: crack
"""
    (base_dir / "data.yaml").write_text(yaml_content, encoding="utf-8")
    print("-> data.yaml 訓練配置檔案生成成功 [OK]")
    print(f"資料集路徑: {base_dir.absolute()}")

if __name__ == "__main__":
    generate_dataset()
