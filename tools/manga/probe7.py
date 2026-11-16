import re, time, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
for u in ["https://hon-hikidashi.jp/news/101998/", "https://hon-hikidashi.jp/news/108479/"]:
    s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
    print(u, re.search(r"<title>(.*?)</title>", s, re.S).group(1)[:70], "行", s.count("<tr"))
    print("  記事内のページ送り:", sorted(set(re.findall(re.escape(u) + r"(\d+)/", s))))
    print("  ほかの一覧記事へのリンク:", sorted(set(re.findall(r'href="(https://hon-hikidashi\.jp/news/\d+/)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*2026年[23]月発売のコミック[^<]*)', s)))[:6])
    time.sleep(3)
