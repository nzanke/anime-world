"""サイト内検索で指定の月の「コミック新刊」一覧記事（発売日順・出版社別）を探し、
まだ hikidashi.csv にない本（ISBNで判定）を足す。
使い方: python3 hikidashi_add.py 2026-02 2026-03"""
import csv, html, re, sys, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
path = "data/manga/hikidashi.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
have_art = {r["記事"] for r in rows}
have_isbn = {r["ISBN"] for r in rows if r["ISBN"]}
cl = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
add = 0
for ym in sys.argv[1:]:
    y, m = ym.split("-"); label = f"{y}年{int(m)}月発売のコミック新刊"
    arts = {}
    for page in (1, 2):
        x = get(("https://hon-hikidashi.jp/" + (f"page/{page}/" if page > 1 else "")) + "?s=" + urllib.parse.quote(label))
        for u, t in re.findall(r'href="(https://hon-hikidashi\.jp/news/\d+/)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*' + label + r'[^<]*)', x):
            arts[u] = cl(t)
        time.sleep(2)
    print(ym, "見つかった記事:", [(u.split("/")[-2], t[len(label):]) for u, t in arts.items()])
    for u, t in arts.items():
        if u in have_art:
            continue
        s = get(u); time.sleep(2); k = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) != 5 or "発売日" in cl(tds[0]) or "発" in cl(tds[0])[:1]:
                continue
            isbn = re.search(r"(?:k=|isbn=)(97[89]\d{10})", tds[2])
            if not isbn or isbn.group(1) in have_isbn:
                continue
            lab = re.search(r"<span[^>]*>(.*?)</span>", tds[2], re.S)
            rows.append({"年月": ym, "日": cl(tds[0]), "出版社": cl(tds[1]), "レーベル": cl(lab.group(1)) if lab else "",
                         "書名": cl(re.sub(r"<span.*?</span>", "", tds[2], flags=re.S)), "著者": cl(tds[3]),
                         "予価": cl(tds[4]), "ISBN": isbn.group(1), "記事": u})
            have_isbn.add(isbn.group(1)); k += 1
        print("  ", t[len(label):], k, "件を追加"); add += k
with open(path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("追加 合計", add, "件 → 全", len(rows), "件")
