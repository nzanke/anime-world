import re, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
arts = []
for page in (1, 2, 3):
    x = get(f"https://hon-hikidashi.jp/page/{page}/?s=" + urllib.parse.quote("コミック新刊ラインアップ"))
    f = re.findall(r'href="(https://hon-hikidashi\.jp/news/\d+/)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*ラインアップ[^<]*)', x)
    print("検索", page, [t.strip() for u, t in f][:12]); arts += f
    time.sleep(3)
for u, t in arts[:1] + [a for a in arts if "2024年" in a[1]][:1]:
    s = get(u); time.sleep(3)
    print("記事", t.strip(), u, len(s), "字 表", s.count("<table"), "行", s.count("<tr"))
    k = s.find("<table"); print("  ", re.sub(r"\s+", " ", s[k:k+1500]))
    print("  見出し:", [re.sub("<[^>]+>", "", h).strip() for h in re.findall(r"<h[234][^>]*>(.*?)</h[234]>", s, re.S)][:15])
