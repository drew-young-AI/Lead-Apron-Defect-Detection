#!/usr/bin/env python3
import json
import re
import pandas as pd
from pathlib import Path

EXCEL_DIR = Path("D:/project/鉛衣/Image Dataset/label資料/[核醫科標記]鉛衣檢測紀錄")
OUTPUT_JSON = Path("D:/project/鉛衣/dicom_annotator/data/lead_master.json")

# 挑選關鍵的 2024/2025 年檢測登記表，避免解析全部 42 個 Excel
TARGET_EXCELS = [
    "2024半年度鉛衣年測登記表-開刀房-1.xlsx",
    "2024年度鉛衣年測登記表-開刀房.xlsx",
    "2025年度鉛衣年測登記表-心導管.xlsx",
    "2023戴德森醫療財團法人嘉義基督教醫院鉛衣年測登記表-核醫科.xlsx",
    "2025年度鉛衣半年追蹤登記表-核醫科.xlsx"
]

def build_lead_master():
    print("Building Lead Wear Master Map from target Excel files...")
    
    master_map = {}
    
    # 用來提取如 Orth A-01-1, CVS 11-3, NM02 等核心編號代碼的正則表達式
    code_pattern = re.compile(r"([a-zA-Z0-9\-\s]+)", re.I)
    
    for path in EXCEL_DIR.rglob("*.xlsx"):
        if path.name not in TARGET_EXCELS:
            continue
            
        print(f"Processing target Excel: {path.name}")
        try:
            xl = pd.ExcelFile(str(path))
            for sheet in xl.sheet_names:
                df = xl.parse(sheet)
                df = df.dropna(how='all')
                
                for idx, row in df.iterrows():
                    row_vals = [str(x).strip() for x in row.values if pd.notna(x)]
                    if not row_vals:
                        continue
                        
                    # 搜尋行中可能包含的編號特徵與部位特徵
                    # 部位特徵通常包含 "鉛衣", "鉛裙", "鉛頸", "連身", "半身"
                    part_type = "–"
                    for val in row_vals:
                        if any(k in val for k in ["鉛衣", "鉛裙", "鉛頸", "連身", "半身"]):
                            part_type = val
                            break
                    
                    # 嘗試抓取編號代碼，例如 "Orth A-01-1" 或 "NM16"
                    # 在每一行中尋找可能的標籤代號
                    lead_code = None
                    property_no = "–"
                    extra_info = []
                    
                    for val in row_vals:
                        # 檢查是否含有科別編號前綴 (如 Orth, CVS, NM, D, ORTH)
                        val_clean = val.replace("\n", " ").strip()
                        
                        # 尋找 32060707 這種常見財產編號格式
                        if "32060707" in val_clean:
                            property_no = val_clean
                            continue
                            
                        # 尋找括號編號如 (E040647) 或 (D944302)
                        barcode_match = re.search(r"\(([E|D]\d+)\)", val_clean, re.I)
                        if barcode_match:
                            property_no = barcode_match.group(0) # 包含括號如 (E040647)
                            
                        # 尋找科別編號代碼 (如 Orth A-01-2, CVS 11-3, NM02)
                        for prefix in ["Orth", "CVS", "NM", "D", "ORTH"]:
                            if prefix in val_clean:
                                # 提取例如 "Orth A-01-2" 或 "CVS 11-3"
                                match = re.search(rf"({prefix}\s*[A-Z0-9\-\_]+)", val_clean, re.I)
                                if match:
                                    lead_code = match.group(1).strip()
                                    # 整理多餘空白
                                    lead_code = re.sub(r"\s+", " ", lead_code)
                                    break
                        
                        # 如果是單獨的數字編號如 "15-2"
                        if not lead_code and re.match(r"^\d+-\d+$", val_clean):
                            lead_code = val_clean
                            
                    # 如果找到了鉛衣編號，進行關聯存儲
                    if lead_code:
                        # 整理整行所有非空資訊做備用
                        combined_content = " | ".join(row_vals)
                        
                        # 提取狀態：合格、堪用、報廢
                        status = "–"
                        if "報廢" in combined_content:
                            status = "報廢"
                        elif "合格" in combined_content:
                            status = "合格"
                        elif "堪用" in combined_content:
                            status = "堪用"
                            
                        master_map[lead_code] = {
                            "part_type": part_type,
                            "property_no": property_no,
                            "status": status,
                            "excel_source": path.name,
                            "full_row": row_vals
                        }
        except Exception as e:
            print(f"  Error reading {path.name}: {e}")
            
    # 寫入 JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(master_map, f, ensure_ascii=False, indent=4)
        
    print(f"Master Map built successfully! Saved {len(master_map)} entries to {OUTPUT_JSON}.")

if __name__ == "__main__":
    build_lead_master()
