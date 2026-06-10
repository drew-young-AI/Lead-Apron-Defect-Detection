import argparse
import sys
from pathlib import Path
from prepare_dataset import prepare_yolo_dataset

# 強制 UTF-8 輸出
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

def parse_args():
    parser = argparse.ArgumentParser(description="鉛衣 DICOM YOLOv8-seg 訓練腳本")
    parser.add_argument("--epochs", type=int, default=1, help="訓練的 Epochs 數量 (預設: 1，用於冒煙測試)")
    parser.add_argument("--batch", type=int, default=8, help="Batch 大小 (預設: 8)")
    parser.add_argument("--imgsz", type=int, default=640, help="影像大小 (預設: 640)")
    parser.add_argument("--device", type=str, default="cpu", help="訓練硬體，例如 cpu 或 0, 1 (預設: cpu)")
    parser.add_argument("--pretrained", type=str, default="yolov8n-seg.pt", help="預訓練權重路徑")
    parser.add_argument("--val-split", type=float, default=0.2, help="驗證集劃分比例 (預設: 0.2)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 確保資料集已轉換
    yaml_path = Path(__file__).parent / "dataset" / "data.yaml"
    if not yaml_path.exists():
        print("[*] 偵測到資料集尚未生成，正在自動執行資料集轉換...")
        success = prepare_yolo_dataset(val_split=args.val_split)
        if not success:
            print("[-] 無法建立資料集，終止訓練。")
            sys.exit(1)
            
    # 載入 Ultralytics
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[-] 錯誤: 尚未安裝 ultralytics 函式庫，請執行: pip install ultralytics")
        sys.exit(1)
        
    print(f"[*] 正在初始化 YOLOv8 模型: {args.pretrained}")
    model = YOLO(args.pretrained)
    
    print(f"[*] 開始執行 YOLO 訓練: epochs={args.epochs}, batch={args.batch}, imgsz={args.imgsz}, device={args.device}")
    
    # 執行訓練
    try:
        results = model.train(
            data=str(yaml_path.absolute().as_posix()),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            workers=0,  # 避免 Windows 平台多線程崩潰
            project=str((Path(__file__).parent / "runs").absolute().as_posix())
        )
        
        print("=== 訓練成功完成！ ===")
        best_weight = Path(__file__).parent / "runs" / "train" / "weights" / "best.pt"
        if best_weight.exists():
            print(f"[+] 最佳模型權重已儲存於: {best_weight.absolute()}")
            
    except Exception as e:
        print(f"[-] 訓練過程中發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
