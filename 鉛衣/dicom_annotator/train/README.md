# YOLOv8-seg 訓練基礎程式碼

本資料夾為「鉛衣瑕疵檢測 (破洞與裂痕)」的 YOLOv8-seg 影像分割模型訓練基礎框架。

## 目錄結構

```text
train/
├── README.md             # 本文件
├── prepare_dataset.py    # 資料集轉換工具 (DICOM 標註 -> YOLO 歸一化 Seg txt)
├── train.py              # 訓練主入口 (封裝 Ultralytics API)
└── dataset/              # [自動生成] YOLO 訓練影像與標籤儲存區
```

## 功能特點

1. **DICOM 影像自動歸一化與轉檔**：
   自動將專案內內建/上傳的 `.dcm` 原始影像讀取出來，歸一化至 8-bit 並轉存成標準 `.jpg` 格式，免去手動前處理的麻煩。
2. **多邊形標記歸一化 (Poly-Seg)**：
   讀取位於 `data/annotations/*.json` 的標註多邊形點，自動進行比例變換與歸一化，輸出為標準的 YOLO Seg 多邊形標籤。
3. **資料集隨機劃分**：
   提供自訂比例（預設 `80/20`）隨機將所有有效標註樣本劃分為訓練集（`train`）與驗證集（`val`）。
4. **極速/自訂訓練切換**：
   `train.py` 支援命令列參數。預設執行 1 epoch 的 CPU 訓練以快速驗證管線，亦可指定 GPU `device=0` 與更高的 epochs 執行實體生產環境訓練。

## 快速開始

### 1. 確保相依套件已安裝
```bash
pip install ultralytics pydicom pillow numpy
```

### 2. 生成資料集並啟動 1 epoch 冒煙測試 (確認管線可通)
直接執行 `train.py` 會自動判斷有無資料集。若無，將先執行 `prepare_dataset.py`：
```bash
python train.py
```

### 3. 生產環境下使用 GPU 進行正式訓練
```bash
python train.py --epochs 100 --batch 16 --imgsz 640 --device 0
```
*(其中 `--device 0` 代表使用第一張顯示卡。)*
