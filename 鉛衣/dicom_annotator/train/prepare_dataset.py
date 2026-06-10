import os
import json
import sys
import shutil
import random
import numpy as np
import pydicom
from PIL import Image
from pathlib import Path

# 強制 UTF-8 輸出
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

def convert_dicom_to_jpg(dcm_path: Path, out_path: Path):
    """將 DICOM 影像轉換並歸一化為 8-bit JPG 格式"""
    try:
        ds = pydicom.dcmread(str(dcm_path), force=True)
        pixel_array = ds.pixel_array.astype(float)
        
        # 歸一化
        p_min, p_max = pixel_array.min(), pixel_array.max()
        if p_max > p_min:
            img_8 = ((pixel_array - p_min) / (p_max - p_min) * 255.0).astype(np.uint8)
        else:
            img_8 = np.zeros(pixel_array.shape, dtype=np.uint8)
            
        img = Image.fromarray(img_8, mode="L")
        img.save(out_path, format="JPEG")
        return img.size # (width, height)
    except Exception as e:
        print(f"[-] 轉換 DICOM 失敗 {dcm_path}: {e}")
        return None

def prepare_yolo_dataset(val_split=0.2):
    """
    從系統內部的 data/annotations/*.json 以及上傳的 DICOM 檔案，
    自動生成 YOLO 分割 (Segmentation) 格式的訓練與驗證資料集。
    """
    print("=== 開始準備 YOLO 分割訓練資料集 ===")
    
    # 專案根目錄
    project_dir = Path(__file__).parent.parent
    annotations_dir = project_dir / "data" / "annotations"
    
    if not annotations_dir.exists() or not any(annotations_dir.glob("*.json")):
        print(f"[-] 警告: 找不到標註檔案目錄，或目錄為空。請先在前端標註影像！\n路徑: {annotations_dir}")
        return False
        
    # 定義輸出 YOLO 目錄 (置於 train/dataset)
    dataset_dir = Path(__file__).parent / "dataset"
    img_train_dir = dataset_dir / "images" / "train"
    img_val_dir = dataset_dir / "images" / "val"
    lbl_train_dir = dataset_dir / "labels" / "train"
    lbl_val_dir = dataset_dir / "labels" / "val"
    
    # 重置/清理舊的訓練集目錄
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
        
    for d in [img_train_dir, img_val_dir, lbl_train_dir, lbl_val_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    # 定義類別對映 (對標專案需求: 破洞-0, 裂痕-1)
    class_map = {"hole": 0, "crack": 1, "defect": 0, "void": 0}
    inv_map = {0: "hole", 1: "crack"}
    
    valid_samples = []
    
    # 遍歷所有標註 JSON
    for json_file in annotations_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            anns = data.get("annotations", [])
            if not anns:
                continue # 跳過沒有標註的影像
                
            img_path_str = data.get("image_path")
            if not img_path_str:
                continue
                
            # 解析影像檔案路徑
            img_path = Path(img_path_str)
            # 若為相對路徑，則以專案根目錄進行解析
            if not img_path.is_absolute():
                img_path = project_dir / img_path
                
            if not img_path.exists():
                # 嘗試在 backend/uploads 目錄尋找
                alt_path = project_dir / "backend" / "uploads" / img_path.name
                if alt_path.exists():
                    img_path = alt_path
                else:
                    print(f"[-] 找不到對應的影像檔案，跳過: {img_path_str}")
                    continue
                    
            valid_samples.append({
                "json_file": json_file,
                "image_path": img_path,
                "annotations": anns
            })
        except Exception as e:
            print(f"[-] 讀取標註檔 {json_file.name} 失敗: {e}")
            
    if not valid_samples:
        print("[-] 找不到任何有效的標註樣本 (需同時具有 JSON 標註與實體 DICOM 影像)！")
        return False
        
    print(f"[+] 找到 {len(valid_samples)} 個有效標註樣本，開始進行隨機劃分 (驗證集比例: {val_split})...")
    
    # 隨機打亂並劃分
    random.shuffle(valid_samples)
    val_count = int(len(valid_samples) * val_split)
    if val_count == 0 and len(valid_samples) > 1:
        val_count = 1
        
    val_set = valid_samples[:val_count]
    train_set = valid_samples[val_count:]
    
    def process_set(samples, img_dest, lbl_dest):
        count = 0
        for sample in samples:
            img_path = sample["image_path"]
            anns = sample["annotations"]
            stem = img_path.stem
            
            # 1. 轉換 DICOM 並儲存至對應 images 目錄
            jpg_name = f"{stem}.jpg"
            out_jpg_path = img_dest / jpg_name
            size = convert_dicom_to_jpg(img_path, out_jpg_path)
            if not size:
                continue
                
            W, H = size
            
            # 2. 轉換多邊形座標至 YOLO 分割格式
            yolo_lines = []
            for ann in anns:
                cls_name = ann.get("class", "hole")
                cls_id = class_map.get(cls_name, 0) # 預設為破洞 0
                
                polygon = ann.get("polygon", [])
                if len(polygon) < 3:
                    # 若多邊形點小於 3，則嘗試用 bbox 轉成 4 點多邊形
                    bbox = ann.get("bbox")
                    if bbox and len(bbox) == 4:
                        bx, by, bw, bh = bbox
                        polygon = [[bx, by], [bx+bw, by], [bx+bw, by+bh], [bx, by+bh]]
                    else:
                        continue
                        
                # 歸一化坐標
                norm_coords = []
                for pt in polygon:
                    # 限制範圍在 0 ~ 1 之間
                    nx = max(0.0, min(1.0, pt[0] / W))
                    ny = max(0.0, min(1.0, pt[1] / H))
                    norm_coords.append(f"{nx:.6f} {ny:.6f}")
                    
                yolo_lines.append(f"{cls_id} {' '.join(norm_coords)}")
                
            if yolo_lines:
                # 寫入 YOLO labels 檔案
                out_txt_path = lbl_dest / f"{stem}.txt"
                out_txt_path.write_text("\n".join(yolo_lines), encoding="utf-8")
                count += 1
        return count

    train_ok = process_set(train_set, img_train_dir, lbl_train_dir)
    val_ok = process_set(val_set, img_val_dir, lbl_val_dir)
    
    print(f"[+] 成功導出 {train_ok} 張訓練影像，{val_ok} 張驗證影像！")
    
    # 3. 寫入 data.yaml
    yaml_content = f"""path: {dataset_dir.absolute().as_posix()}
train: images/train
val: images/val
nc: 2
names:
  0: hole
  1: crack
"""
    (dataset_dir / "data.yaml").write_text(yaml_content, encoding="utf-8")
    print(f"[+] 成功生成 YOLO 設定檔: {dataset_dir / 'data.yaml'}")
    return True

if __name__ == "__main__":
    prepare_yolo_dataset()
