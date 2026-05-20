from scholarly import scholarly
import json
import os

class ScholarClient:
    def search_papers(self, query, limit=10):
        """Search Google Scholar for papers and metrics"""
        search_query = scholarly.search_pubs(query)
        results = []
        for i, item in enumerate(search_query):
            if i >= limit:
                break
            
            pub = item['bib']
            results.append({
                "title": pub.get('title', 'N/A'),
                "author": pub.get('author', 'N/A'),
                "year": pub.get('pub_year', 'N/A'),
                "citations": item.get('num_citations', 0),
                "url": item.get('pub_url', '#'),
                "source": "Google Scholar"
            })
        return results

if __name__ == "__main__":
    import sys
    client = ScholarClient()
    query = sys.argv[1] if len(sys.argv) > 1 else "fetal heart rate deep learning 2024"
    print(f"[*] 正在搜尋 Google Scholar: {query}")
    results = client.search_papers(query, limit=10)
    for r in results:
        print(f"- {r['title']} (Citations: {r['citations']})")
