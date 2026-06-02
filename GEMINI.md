## 4. 決策權重與記憶規範 (Decision Weight & Memory Mandates) - *NEW*
為了確保作業品質不因對話長度而產生「語義漂移」，Agent 必須遵循以下權重邏輯：

- **層級 1：系統法律 (The Anchor)**：`GEMINI.md` 中的所有規範（如欄位數、Row 數、認證協議）具有最高優先權。
    - **Med Research 硬約束**：所有報告必須符合 **JCR (Q1/Q2)** 與實體 **IF** 認證。
    - **1:1 數據誠信**：強制執行「DOI -> 標題 -> 技術細節」實體驗證，嚴禁幻覺。
    - **統一矩陣規範**：強制執行 **10 欄位** 標準（# / DOI / JCR, 標題, 算法, 數據規模, 臨床挑戰, 技術巧思, 實驗結果, 數據流 Logic, 瓶頸, 專案對標）。
- **層級 2：任務增量 (The Delta)**：對話中的新需求應視為「功能累加」。Agent 必須維持 **「只增不減」** 原則，除非用戶明確下達「精簡」或「重置」指令。
- **層級 3：品質審核 (The Scrutiny)**：每一輪 Master 產出前，必須回溯 `PROGRESS.md` 中記錄的前版規格，確保數據密度與結構的一致性。
- **層級 4：效率壓縮 (The Optim)**：Context 壓縮僅限於寒暄與冗長敘述。**嚴禁壓縮表格 (Table)、數據 (Data) 或方法論細節 (Methodology)**。

## 7. 自主觸發與技能編排 (Agentic Trigger Mandate) - *NEW v10.0*
- **能力自我檢核**：每當接受新任務（如 Deep Research, 打卡, 下載）時，Agent 必須自我檢核是否具備對應的 Skill 或 MCP。優先調度 `med-research/SKILL.md` v10.0 協議。
- **缺失補救**：若發現缺失，Agent 不得執行低效的替代方案，必須明確提供該 Skill 的安裝指令給使用者。
- **MCP 優先權**：對於數據採礦，強制優先調度 `mcp_registry.md` 中已註冊的伺望器，確保數據品質與溯源。

## 8. Antigravity / cdoex 整合矩陣 (Integration Hub)
為了確保搬遷後功能完整，Agent 應優先調度以下模組：

### A. 自動打卡與服務管理
- **指令**: `python etc/cych_check_login/scheduler_punch.py --status`
- **啟動**: `powershell -File etc/start_all_services.ps1`
- **密碼熱鍵**: `Alt + P + P` (由 `hotkey_sample.py` 維護)

### B. Med Deep Research (醫學研究)
- **核心入口**: `med-research/scripts/discovery.py`
- **文獻下載**: `med-research/scripts/download_papers.py`
- **數據目錄**: `Med Deep Research/papers/`
- **Python 環境**: `etc/dev/Scripts/python.exe` (依賴庫已預裝)

### C. Systemprompt 同步
- **同步指令**: `bash systemprompt-manager/scripts/update-systemprompt.sh`
- **配置目錄**: `systemprompt-manager/config/`
- **憲法文件**: `systemprompt-manager/skills/systemprompt.md`

## 9. 關鍵路徑保護 (Path Guardians)
- **環境變數**: 強制讀取 `etc/.env`。
- **相對路徑**: 優先使用相對路徑執行，確保在 `D:\project` 根目錄下可直接調用。
