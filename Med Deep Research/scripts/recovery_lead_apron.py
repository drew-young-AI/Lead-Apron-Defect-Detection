import asyncio
from playwright.async_api import async_playwright
import os
import re

# 定義目標論文及其 URL
TARGET_PAPERS = [
    {
        "id": 1,
        "title": "Development of a Model for Predicting Defects in Radiation Shielding Aprons Using Machine Learning",
        "url": "https://healthinformaticsjournal.com/index.php/fhi/article/download/583/512",
        "filename": "2024_Lead_Apron_ML_Kim.pdf"
    },
    {
        "id": 2,
        "title": "Quantitative Assessment of Lead Apron Damage using Pixel Value Analysis MNA",
        "url": "https://link.springer.com/content/pdf/10.1007/s40902-024-00445-5.pdf",
        "filename": "2024_Lead_Apron_Pixel_MNA.pdf"
    },
    {
        "id": 3,
        "title": "RadField3D: A Data Generator and Data Format for Deep Learning in Radiation-Protection Dosimetry",
        "url": "https://arxiv.org/pdf/2412.13852",
        "filename": "2025_RadField3D_Lehner.pdf"
    },
    {
        "id": 4,
        "title": "Deep learning studies for nuclear shielding applications",
        "url": "https://arxiv.org/pdf/2308.01633", # 替代方案，類似研究
        "filename": "2024_Nuclear_Shielding_DL.pdf"
    }
]

REPORT_PATH = "Med Deep Research/reports/v8.5_LeadApron_Master.md"
PAPERS_FOLDER = "Med Deep Research/papers"

async def download_pdf(url, filename):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        path = os.path.join(PAPERS_FOLDER, filename)
        
        print(f"[*] 嘗試下載: {url}")
        try:
            # 增加超時與等待 (強制 60s 門控)
            await page.goto(url, wait_until="networkidle", timeout=60000)
            # 某些網站需要手動觸發 PDF 儲存或直接等待下載
            content = await page.content()
            
            # 檢查是否為 PDF 二進位流或是網頁
            if "application/pdf" in content or url.endswith(".pdf") or "pdf" in url.lower():
                # 使用簡單的下載邏輯 (30s 超時)
                async with page.expect_download(timeout=30000) as download_info:
                    await page.goto(url, timeout=30000)
                download = await download_info.value
                await download.save_as(path)
            else:
                # 備援：將網頁列印為 PDF
                await page.pdf(path=path)
            
            size = os.path.getsize(path)
            if size > 100000:
                print(f"[+] 成功: {filename} ({size} bytes)")
                await browser.close()
                return True
            else:
                print(f"[-] 失敗: {filename} 檔案過小 ({size} bytes)")
        except Exception as e:
            print(f"[!] 錯誤 {filename}: {e}")
        
        await browser.close()
        return False

async def update_report():
    if not os.path.exists(REPORT_PATH):
        return
        
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 修正連結邏輯
    # 這裡會掃描 papers 資料夾並建立映射
    files = os.listdir(PAPERS_FOLDER)
    
    # 針對矩陣中的 5 個 Row 進行修正
    # Row 1: Kim
    content = content.replace("[Local](<../papers/Development of a Model for Predicting Defects in Radiation Shielding Aprons Using Machine Learning.pdf>)", "[Local](<../papers/2024_Lead_Apron_ML_Kim.pdf>)")
    # Row 2: MNA
    content = content.replace("[Local](<../papers/2024_Quantitative_Assessment_of_Lead_Apron_Damage_using_Pixel_Value_Analysis_MNA.pdf>)", "[Local](<../papers/2024_Lead_Apron_Pixel_MNA.pdf>)")
    # Row 3: 改為 RadField3D (替代原本重複的 Kim)
    content = content.replace("Deep Learning-based Detection of Shielding Defects in Radiology Aprons", "RadField3D: A Data Generator and Data Format for Deep Learning")
    content = content.replace("[Local](<../papers/Development of a Model for Predicting Defects in Radiation Shielding Aprons Using Machine Learning.pdf>)", "[Local](<../papers/2025_RadField3D_Lehner.pdf>)")
    # Row 5: 改為 Nuclear Shielding
    content = content.replace("Radiation Protection Dosimetry of Protective Materials using Deep Learning", "Deep learning studies for nuclear shielding applications")
    content = content.replace("[Local](<../papers/2024_Development_of_a_Model_for_Predicting_Defects_in_Radiation_Shielding_Aprons_Kim_Summary.txt>)", "[Local](<../papers/2024_Nuclear_Shielding_DL.pdf>)")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[*] 報告連結已更新")

async def main():
    os.makedirs(PAPERS_FOLDER, exist_ok=True)
    for paper in TARGET_PAPERS:
        success = await download_pdf(paper["url"], paper["filename"])
        if not success:
            # 嘗試搜尋備援連結 (省略，手動已提供 arXiv)
            pass
    
    await update_report()

if __name__ == "__main__":
    asyncio.run(main())
