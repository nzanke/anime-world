import re, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
for q in ["コミック新刊発売日一覧", "コミック 発売日一覧 2025年"]:
    for page in (5, 6):
        u = f"https://hon-hikidashi.jp/page/{page}/?s=" + urllib.parse.quote(q)
        try:
            x = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
            ts = re.findall(r'<h\d[^>]*>\s*(?:<[^>]+>\s*)*([^<]{6,80})', x)
            print(q, page, len(x), "字", [t.strip() for t in ts if "一覧" in t or "新刊" in t][:8])
            print("   件数表示:", re.findall(r"(\d+)\s*件", x)[:3], "最終ページ:", re.findall(r"/page/(\d+)/", x)[-3:])
        except Exception as e:
            print(q, page, "エラー", e)
        time.sleep(3)
