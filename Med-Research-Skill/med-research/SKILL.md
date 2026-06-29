---
name: med-research
description: |
  High-fidelity medical deep research engine (v12.0 Protocol).
  Enforces JCR Q1/Q2 gating, 1:1 DOI-Title data integrity, 8-column master matrix,
  and objective physics-level technical insight.
  Activates on: deep research / 深度研究 / literature review / 文獻回顧 / lead apron / 鉛衣 / CTG / DICOM / medical AI
---

# Medical Research Skill (v12.0 Master Protocol)

## 1. 三大硬約束 (Non-Negotiable Constraints)

### 約束 A：JCR 門控
- **驗證**：矩陣中每篇文獻必須標注 JCR 分區（Q1/Q2/Q3/Q4）與實體 IF 數值。
- **Q1/Q2**：優先納入，於欄位 1 以粗體標注（如 **Q2**）。
- **Q3/Q4**：允許納入但須附說明（如「唯一鉛衣 QC 方法論來源，無更高 JCR 替代」）。
- **Pre-print / ESCI**：若非使用者要求，嚴禁納入。

### 約束 B：1:1 數據誠信協議
- 每一 Row 的 DOI → 標題 → 技術細節必須來自同一篇論文。
- 若無法確認全文對應，該欄位必須標記：`REF recovery pending`。
- 嚴禁數據交叉污染。

### 約束 C：物理 / 工程精度要求
- 算法欄必須包含具體名稱（CNN, Random Forest, PVR）。
- 工程參數欄必須包含具體數值（n=4,482; 100 kVp; 150x150 px）。
- 若有物理公式，必須以 LaTeX 或明文呈現（如 `PVR = PI_apron / PI_2mmPb`）。
- 數據流 Logic 必須完整描述輸入→處理→輸出（如 `Gray Val → PVR Formula → Pb eq`）。

---

## 2. 標準矩陣規格 (8-Column Master Matrix v12.0)

| 欄 | 欄位名稱 | 要求格式 |
|---|---------|---------|
| 1 | **# / DOI / JCR (IF)** | `**01** / [10.xxxx/yyy](https://doi.org/10.xxxx/yyy) / **Q2 (IF: X.X)** (Year)` |
| 2 | **論文標題 (1:1 對標)** | 必須與出版商索引完全一致，不得截短 |
| 3 | **核心算法 / 物理邏輯** | 具體算法名稱 + 公式（如適用）|
| 4 | **工程參數 / 標定值** | 具體數值：樣本數、解析度、能量參數等 |
| 5 | **技術巧思 (How)** | 算法核心巧思，非防護服汎指，需揭露關鍵參數 |
| 6 | **實驗結果 (SOTA)** | 具體指標：Acc / F1 / Precision / AUC |
| 7 | **數據流 Logic** | `輸入 → 處理步驟 → 輸出` 完整鏈條 |
| 8 | **參考文獻 (PDF / Web)** | `[PDF](../papers/YYYY_Title.pdf) \| [Web](URL)` |

**Row 數規範**：精選 5 篇文獻；第 5 篇優先選「Overview」或「SOTA trend」類。

---

## 3. 深度剖析章節 (Deep Technical Insight) — 必備

矩陣之後必須附「深度技術剖析」，覆蓋：

### 3.1 物理維度 (Physics Dimension)
- 物理意義的方法（如 PVR 線性關係、Pb 等效厚度換算）。
- 必須包含關鍵數據（如 0.25mm Pb ≈ 0.8-1.2mm Cu）。

### 3.2 預測 / AI 維度 (AI/Prediction Dimension)
- 說明 AI 模型的意義。
- 揭露特徵重要性（如「品牌權重佔 35.1%」）。

### 3.3 落地實作路徑 (Action Plan)
1. **第一步（即時/短期）**：引用具體 Row + 技術描述。
2. **第二步（定期/中期）**：引用具體 Row + 協議說明。
3. **第三步（系統整合/長期）**：引用具體 Row + 整合方式。

---

## 4. 零情緒寫作規範 (Zero Emotional Bias)
- **語調客觀**：報告僅能使用中立、客觀、邏輯通順的學術與技術語言。
- **嚴禁自誇**：嚴禁出現任何自我讚揚或描述產出品質的詞彙（如「完美狀態」、「無懈可擊」、「數據誠信修復」）。
- **自測通過**：每次產生報告後，必須執行 `verify_integrity.py` 驗證其編碼、排版與連結。
