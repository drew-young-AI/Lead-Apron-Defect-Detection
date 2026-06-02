import asyncio
import os
import sys
# 將根目錄加入路徑以便導入 utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from utils.downloader.elite_download import UniversalDownloader

# 全域超時保護
TOTAL_TASK_TIMEOUT = 120.0 

async def main(target_tasks=None):
    folder = "Med Deep Research/papers"
    os.makedirs(folder, exist_ok=True)
    
    # 初始化萬能下載引擎
    downloader = UniversalDownloader(folder=folder)
    
    if target_tasks is None:
        # 針對 v9.9 矩陣中的核心文獻與之前失敗的文獻進行修補
        tasks_to_run = [
            ("https://doi.org/10.30699/fhi.v13i7.1284", "2024_Lead_Apron_ML_Kim.pdf"),
            ("https://doi.org/10.1093/rpd/ncae041", "2024_Lead_Apron_CT_Lin.pdf"),
            ("https://doi.org/10.4236/ojrad.2024.141002", "2024_Lead_Apron_Survey_Dagbe.pdf"),
            # 之前的頑固文獻
            ("https://www.mdpi.com/1424-8220/25/9/2650", "2025_PatchCTG_Full_Text.pdf"),
            ("https://www.researchgate.net/publication/381144431_Prediction_Model_for_Defects_in_Lead_and_Lead-free_Aprons", "2024_Kellens_Apron_Defects.pdf")
        ]
    else:
        tasks_to_run = target_tasks

    print(f"==== 啟動 Universal Downloader v10.0 (任務數: {len(tasks_to_run)}) ====")
    
    # 這裡我們選擇順序執行以確保 Stealth 效果與避免被連鎖封鎖
    # 但如果任務多，也可以考慮 asyncio.gather (限制 semaphore)
    results = []
    for url, fn in tasks_to_run:
        res = await downloader.download(url, fn)
        results.append(res)
        
    success_count = sum(1 for r in results if r.get("success"))
    print(f"==== 下載結束: 成功 {success_count} / 總數 {len(tasks_to_run)} ====")
    for r in results:
        status = "✅" if r.get("success") else "❌"
        print(f"{status} {os.path.basename(r.get('path'))}: {r.get('msg')} ({r.get('type')})")

if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=300.0))
    except asyncio.TimeoutError:
        print("[!!!] 全域任務超時。")
        sys.exit(1)
