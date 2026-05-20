import os
import requests
import xml.etree.ElementTree as ET
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PubMedClient:
    def __init__(self, email="guest@example.com", api_key=None):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.email = email
        self.api_key = api_key

    def search(self, query, retmax=10):
        """Search PubMed for IDs"""
        url = f"{self.base_url}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "usehistory": "y",
            "email": self.email
        }
        if self.api_key:
            params["api_key"] = self.api_key
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ids = [id_el.text for id_el in root.findall(".//Id")]
        return ids

    def fetch_details(self, id_list):
        """Fetch details (Title, Abstract, Journal) for a list of PubMed IDs"""
        if not id_list:
            return []
        
        url = f"{self.base_url}efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "email": self.email
        }
        if self.api_key:
            params["api_key"] = self.api_key
            
        response = requests.get(url, params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        
        results = []
        for article in root.findall(".//PubmedArticle"):
            title = article.find(".//ArticleTitle").text
            abstract_el = article.find(".//AbstractText")
            abstract = abstract_el.text if abstract_el is not None else "No abstract available"
            journal = article.find(".//Title").text
            year = article.find(".//PubDate/Year")
            year = year.text if year is not None else "N/A"
            doi_el = article.find(".//ArticleId[@IdType='doi']")
            doi = doi_el.text if doi_el is not None else "N/A"
            
            results.append({
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": year,
                "doi": doi,
                "source": "PubMed"
            })
        return results

if __name__ == "__main__":
    import sys
    client = PubMedClient()
    query = sys.argv[1] if len(sys.argv) > 1 else "fetal heart rate deep learning"
    print(f"[*] 正在搜尋 PubMed: {query}")
    ids = client.search(query, retmax=10)
    details = client.fetch_details(ids)
    for i, d in enumerate(details):
        print(f"[{i+1}] {d['title']} ({d['journal']}, {d['year']})")
