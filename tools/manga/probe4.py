import re, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
def get(u, t=120):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "replace")
for u in ["https://hon-hikidashi.jp/?s=" + urllib.parse.quote("コミック新刊発売日一覧"),
          "https://hon-hikidashi.jp/page/3/?s=" + urllib.parse.quote("コミック新刊発売日一覧")]:
    try:
        x = get(u)
        t = re.findall(r'href="(https://hon-hikidashi\.jp/news/\d+/)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*発売日一覧[^<]*)', x)
        print("ひきだし検索", u[-30:], len(x), "字", len(t), "件", [b for a, b in t][:3], [b for a, b in t][-2:])
    except Exception as e:
        print("ひきだし検索 エラー", e)
    time.sleep(3)
base = {"from": "2025-12", "until": "2025-12", "dpid": "iss-ndl-opac", "cnt": "1"}
for name, extra in [("全体", {"ndc": "726.1"}), ("isbn=978406", {"ndc": "726.1", "isbn": "978406"}),
                    ("isbn=9784", {"ndc": "726.1", "isbn": "9784"}), ("isbn=978-4-06", {"ndc": "726.1", "isbn": "978-4-06"}),
                    ("publisher=講談社", {"ndc": "726.1", "publisher": "講談社"})]:
    time.sleep(8)
    try:
        x = get("https://ndlsearch.ndl.go.jp/api/opensearch?" + urllib.parse.urlencode({**base, **extra}))
        tot = re.search(r"<openSearch:totalResults>(\d+)", x)
        print("国会図書館", name, tot.group(1) if tot else "?", re.findall(r"<title>(.*?)</title>", x)[1:2])
    except Exception as e:
        print("国会図書館", name, "エラー", e)
