"""番号の前後を当たって、抜けている「コミック新刊」一覧記事の表を hikidashi.csv に足す。
使い方: python3 hikidashi_add.py 101998 108479"""
import csv, html, re, sys, time, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
path = "data/manga/hikidashi.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
have = {r["記事"] for r in rows}
cl = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
add = 0
for base in map(int, sys.argv[1:]):
    for n in range(base - 4, base + 5):
        u = f"https://hon-hikidashi.jp/news/{n}/"
        if u in have:
            continue
        try:
            s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            print(n, "なし", e); time.sleep(2); continue
        t = html.unescape(re.search(r"<title>(.*?)</title>", s, re.S).group(1))
        m = re.search(r"(\d{4})年(\d+)月発売のコミック新刊(?:発売日一覧|ラインアップ)（発売日順", t)
        print(n, t[:70], "→ 対象" if m else "")
        time.sleep(2)
        if not m:
            continue
        ym = f"{m.group(1)}-{int(m.group(2)):02d}"
        k = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) != 5 or "発売日" in tds[0] or "発" in cl(tds[0])[:1]:
                continue
            isbn = re.search(r"(?:k=|isbn=)(97[89]\d{10})", tds[2])
            lab = re.search(r"<span[^>]*>(.*?)</span>", tds[2], re.S)
            rows.append({"年月": ym, "日": cl(tds[0]), "出版社": cl(tds[1]), "レーベル": cl(lab.group(1)) if lab else "",
                         "書名": cl(re.sub(r"<span.*?</span>", "", tds[2], flags=re.S)), "著者": cl(tds[3]),
                         "予価": cl(tds[4]), "ISBN": isbn.group(1) if isbn else "", "記事": u})
            k += 1
        print("   ", k, "件を追加"); add += k; have.add(u)
with open(path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("追加 合計", add, "件 → 全", len(rows), "件")
