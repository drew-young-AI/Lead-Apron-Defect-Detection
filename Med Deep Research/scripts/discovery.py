import os
import requests
import json
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class ResearchDiscovery:
    def __init__(self, api_key=None):
        self.s2_api_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.api_key = api_key

    def search_semantic_scholar(self, query, limit=20):
        """透過 Semantic Scholar 搜尋學術論文"""
        logger.info(f"正在搜尋 Semantic Scholar: {query}")
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,abstract,citationCount,externalIds,url,isOpenAccess,openAccessPdf"
        }
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        
        try:
            response = requests.get(self.s2_api_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"搜尋出錯: {e}")
            return []

    def save_results(self, results, filename):
        path = os.path.join("Med Deep Research", filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"搜尋結果已儲存至 {path}")

if __name__ == "__main__":
    discovery = ResearchDiscovery()
    
    # 範例題目：AI 在醫療影像中的最新應用與挑戰
    topic = "Latest applications and challenges of AI in medical imaging"
    
    results = discovery.search_semantic_scholar(topic, limit=12)
    if results:
        discovery.save_results(results, "discovery_results.json")
        print(f"\n成功找到 {len(results)} 篇相關論文！")
        for i, paper in enumerate(results):
            print(f"[{i+1}] {paper.get('title')} ({paper.get('year')})")
            print(f"    - Citations: {paper.get('citationCount')}")
    else:
        print("未找到相關文獻，請檢查網路或關鍵字。")
