# 鉛衣 DICOM 標註與訓練系統架構與開發統整指南

本指南旨在為**人類開發者**與**人工智慧 (AI) 協同代理**提供全盤的系統架構說明，以便能無縫地在此基礎上繼續修改程式或添加新功能。

---

## 1. 系統整體架構 (System Architecture)

本系統是一套專為「鉛衣防護完整性檢測」設計的 DICOM 影像標註、自動分割、以及 YOLO 機器學習訓練一體化工作平台。

```mermaid
graph TD
    subgraph 瀏覽器前端 (Frontend)
        A[HTML/CSS/Vanilla JS] -->|滑動/點擊標記| B(DicomViewer)
        B -->|標註列表/備註| C(AnnotationManager)
    end

    subgraph 後端 API 服務 (FastAPI Backend)
        C -->|POST /annotations| D[backend/api/annotation.py]
        D -->|儲存實體 JSON| E[backend/core/annotation_store.py]
        E -->|同步快取指標| F[backend/core/db.py]
        F -->|SQLite 檔案| G[(index.db)]
    end

    subgraph 本地訓練模組 (YOLO Training Suite)
        H[train/train.py] -->|調用| I[train/prepare_dataset.py]
        I -->|讀取實體 JSON & DB 快取| E
        I -->|讀取原始 DICOM 轉 JPG| J[backend/uploads]
        I -->|生成 YOLO 分割格式| K[train/dataset]
        H -->|加載 YOLOv8| L(yolov8n-seg.pt)
        L -->|極速/生產訓練| M[train/runs/train/weights/best.pt]
    end
```

---

## 2. 核心檔案與模組職責說明 (Core Components)

### 2.1 瀏覽器前端 (frontend/)
- **[index.html](file:///D:/project/鉛衣/dicom_annotator/frontend/index.html)**：
  - 核心排版。左側是上傳區與檔案列表（包含檔名、標註總數、有無備註三個欄位）；中間是 Canvas 檢視器與工具列；右側是標註物件列表、瑕疵分類選擇器及影像備註欄。
- **[js/main.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/main.js)**：
  - 前端控制中樞 (`AppController` 類別)。綁定所有快速鍵（B 框選、R 筆刷、E 編輯、S 儲存等）、滑桿與按鈕事件，並驅動 `Viewer` 與 `AnnotationManager` 的同步。
- **[js/viewer.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/viewer.js)**：
  - 醫學影像 Canvas 檢視器 (`DicomViewer` 類別)。處理 DICOM 矩陣的像素級繪製、縮放、平移與視窗調窗（Windowing）。
  - **色彩渲染規範**：未被選中的**破洞** (`hole`/`defect`/`void`) 會渲染為**淺藍色** (`#40c4ff`)，**裂痕** (`crack`) 渲染為**紅色** (`#ff5252`)，選中物件則一律為高亮黃色。
- **[js/annotations.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/annotations.js)**：
  - 前端標註狀態管理器 (`AnnotationManager` 類別)。維護當前影像的標註陣列，執行新增、修改、刪除、及與後端 API 進行存取互動。

### 2.2 後端 API 服務 (backend/)
- **[main.py](file:///D:/project/鉛衣/dicom_annotator/backend/main.py)**：
  - FastAPI 入口，配置路由與自動初始化 SQLite 資料庫。
- **[api/annotation.py](file:///D:/project/鉛衣/dicom_annotator/backend/api/annotation.py)**：
  - 定義標註傳輸模型 (`AnnotationDoc`) 且包含協同備註屬性 `notes`。
- **[core/db.py](file:///D:/project/鉛衣/dicom_annotator/backend/core/db.py)**：
  - SQLite 資料庫連線與指令封裝。包含 `files`、`path_cache` 及 `annotations` 表的維護。其中 `annotations` 表快取了 `annotation_count` (標註數量) 與 `has_notes` (有無備註) 欄位，方便前端快速取得清單詳情。
- **[core/annotation_store.py](file:///D:/project/鉛衣/dicom_annotator/backend/core/annotation_store.py)**：
  - 實體標註 JSON 存取。當呼叫 `save()` 時，一方面將標註以 Atomically (原子寫入) 存入實體硬碟 `data/annotations/<safe_id>.json`，另一方面提取統計資訊寫入 SQLite 進行快取。

---

## 3. YOLO 訓練管線整合 (YOLO Training Integration)

為確保標註的座標能被無縫用來訓練機器學習模型，我們在本地建立了 `./train` 模組：

### 3.1 [train/prepare_dataset.py](file:///D:/project/鉛衣/dicom_annotator/train/prepare_dataset.py) (資料轉換流)
1. **讀取標註**：遍歷載入系統內所有的 JSON 標註。
2. **DICOM 8-bit JPG 轉換**：使用 `pydicom` 提取原始醫學影像像素，自動歸一化至 `0~255` 的 8-bit 灰階影像並儲存為 JPG。
3. **多邊形頂點歸一化**：
   將多邊形中的頂點 `[X, Y]` 依據影像的寬度 $W$ 與高度 $H$ 進行歸一化：
   $$x_{norm} = \max\left(0, \min\left(1, \frac{X}{W}\right)\right), \quad y_{norm} = \max\left(0, \min\left(1, \frac{Y}{H}\right)\right)$$
4. **劃分資料集**：預設以 80% / 20% 的比例隨機劃分為 `train` 和 `val`，並自動輸出 `data.yaml`。

### 3.2 [train/train.py](file:///D:/project/鉛衣/dicom_annotator/train/train.py) (模型訓練流)
- 調用 Ultralytics 載入 `yolov8n-seg.pt` 分割模型。
- 可接收命令列參數，例如：
  ```bash
  python train/train.py --epochs 100 --batch 16 --imgsz 640 --device 0
  ```
- 訓練完成後，最佳模型權重會自動備份於 `train/runs/train/weights/best.pt`。

---

## 4. 如何繼續修改或新增功能 (Developer's Extension Guide)

### 4.1 新增一個標註瑕疵類別 (e.g., "變形")
1. **前端色彩配置**：
   - 在 [annotations.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/annotations.js#L22) 的 `_colours` 字典與 [viewer.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/viewer.js#L302) 的 `colors` 字典中新增類別名稱與對應的十六進位色碼。
2. **標籤對照名稱**：
   - 在 [annotations.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/annotations.js#L291) 的 `dispNames` 加上該類別的中文描述，供側邊欄顯示。
3. **YOLO 類別對映**：
   - 在 [prepare_dataset.py](file:///D:/project/鉛衣/dicom_annotator/train/prepare_dataset.py) 的 `class_map` 新增類別名稱對應的數字 ID（如數字 `2`），並修改 `data.yaml` 的 `nc` (變為 3) 與 `names` 清單。

### 4.2 更換或增加新的前端自動分割演算法
1. **後端分割核心**：
   - 在 [backend/core/segmentation.py](file:///D:/project/鉛衣/dicom_annotator/backend/core/segmentation.py) 中，新增一個自訂的分割函式 `seg_my_method(roi)`，並在 `run_segmentation()` 的映射字典中註冊。
2. **前端演算法清單**：
   - 修改 [index.html](file:///D:/project/鉛衣/dicom_annotator/frontend/index.html#L84) 在 `select id="seg-method"` 下方加上對應的 `<option>` 選項。
   - 若要加入快捷鍵切換的輪替序列中，可將名稱加入 [main.js](file:///D:/project/鉛衣/dicom_annotator/frontend/js/main.js#L19) 的 `SEG_CYCLE_BOX` 或 `SEG_CYCLE_BRUSH` 陣列。
