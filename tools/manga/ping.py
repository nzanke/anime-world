import re, urllib.request
u = "https://ndlsearch.ndl.go.jp/api/opensearch?ndc=726.1&from=2024-04&until=2024-04&dpid=iss-ndl-opac&cnt=1"
try:
    x = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}), timeout=60).read().decode()
    print("国会図書館 応答あり 件数", re.search(r"<openSearch:totalResults>(\d+)", x).group(1))
except Exception as e:
    print("国会図書館 エラー", e)
