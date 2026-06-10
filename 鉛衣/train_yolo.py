import os
import sys
from pathlib import Path

def train():
    # 指向專案內部的 data.yaml
    yaml_path = Path(__file__).parent / "dicom_annotator" / "tests" / "yolo_dataset" / "data.yaml"
    if not yaml_path.exists():
        print(f"錯誤: 找不到資料集設定檔 {yaml_path}")
        print("請先執行 dicom_annotator/tests/generate_mock_yolo_dataset.py 生成資料集！")
        sys.exit(1)
        
    try:
        from ultralytics import YOLO
    except ImportError:
        print("錯誤: 尚未安裝 ultralytics 函式庫，請先安裝！ (pip install ultralytics)")
        sys.exit(1)
        
    # 載入 YOLOv8n-seg 預訓練模型
    print("正在載入 YOLOv8 分割模型...")
    model = YOLO("yolov8n-seg.pt")
    
    # 執行極速訓練測試 (1 epoch, CPU, imgsz 640)
    print("=== 開始 YOLO 模擬訓練測試 ===")
    results = model.train(
        data=str(yaml_path.absolute().as_posix()),
        epochs=1,
        imgsz=640,
        device="cpu",  # 強制使用 CPU 以利穩定測試
        workers=0
    )
    print("=== YOLO 模擬訓練測試完成！ ===")
    print("座標訓練完全可行！")

if __name__ == "__main__":
    train()
