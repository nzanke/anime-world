"""国会図書館サーチSRUで、漫画を絞り込む条件の候補ごとに件数とサンプルを出す（試し用）。"""
import re, sys, time, urllib.parse, urllib.request

API = "https://ndlsearch.ndl.go.jp/api/sru"
M = sys.argv[1] if len(sys.argv) > 1 else "2025-01"
CANDS = [
    f'ndc="726.1" AND from="{M}" AND until="{M}"',
    f'ndc="726.1" AND from="{M}" AND until="{M}" AND dpid="iss-ndl-opac"',
    f'ndc="726" AND from="{M}" AND until="{M}" AND dpid="iss-ndl-opac"',
    f'ndlc="Y84" AND from="{M}" AND until="{M}" AND dpid="iss-ndl-opac"',
    f'subject="漫画" AND from="{M}" AND until="{M}" AND dpid="iss-ndl-opac"',
]
for q in CANDS:
    url = API + "?" + urllib.parse.urlencode({"operation": "searchRetrieve", "maximumRecords": "5",
                                              "recordSchema": "dcndl", "query": q})
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "anime-world manga check"}), timeout=60).read().decode("utf-8", "replace")
        n = re.search(r"<numberOfRecords>(\d+)", x)
        diag = re.search(r"<diag:message>(.*?)</", x) or re.search(r"<message>(.*?)</", x)
        titles = re.findall(r"<dcterms:title>(.*?)</dcterms:title>", x)[:5]
        print("■", q, "→", n.group(1) if n else "?", (diag.group(1) if diag else ""))
        for t in titles:
            print("   ", t)
        if titles and q is CANDS[1]:
            print("  見本:", x[x.find("<dcndl:BibResource"):][:2500].replace("\n", " "))
    except Exception as e:
        print("■", q, "エラー", e)
    time.sleep(3)
