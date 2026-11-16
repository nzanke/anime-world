"""ほんのひきだしの「コミック新刊発売日一覧」（発売日順）を、サイト内検索でたどって指定期間分すべて取り、
data/manga/hikidashi.csv に保存する。
使い方: python3 hikidashi_harvest.py 2024-01 2026-12
"""
import csv, html, os, re, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
a, b = sys.argv[1], sys.argv[2]


def get(u):
    for w in (0, 10, 30, 60):
        time.sleep(w + 2)
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            print("  再試行", u, e, flush=True)
    raise RuntimeError(u)


arts = {}
q = urllib.parse.quote("コミック新刊発売日一覧")
for page in range(1, 60):
    x = get(f"https://hon-hikidashi.jp/page/{page}/?s={q}" if page > 1 else f"https://hon-hikidashi.jp/?s={q}")
    found = re.findall(r'href="(https://hon-hikidashi\.jp/news/\d+/)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*発売日一覧[^<]*)', x)
    if not found:
        break
    oldest = "9999-99"
    for u, t in found:
        m = re.search(r"(\d{4})年(\d+)月発売", t)
        if not m:
            continue
        ym = f"{m.group(1)}-{int(m.group(2)):02d}"
        oldest = min(oldest, ym)
        if a <= ym <= b and "発売日順" in t:
            arts[u] = (ym, html.unescape(t).strip())
    print(f"検索{page}ページ目：いちばん古い月 {oldest}（対象の記事 累計{len(arts)}本）", flush=True)
    if oldest < a:
        break

rows = []
cl = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
for u, (ym, t) in sorted(arts.items(), key=lambda kv: kv[1]):
    s = get(u)
    n = 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) != 5 or "発売日" in tds[0]:
            continue
        isbn = re.search(r"(?:k=|isbn=)(97[89]\d{10})", tds[2])
        lab = re.search(r"<span[^>]*>(.*?)</span>", tds[2], re.S)
        title = cl(re.sub(r"<span.*?</span>", "", tds[2], flags=re.S))
        rows.append({"年月": ym, "日": cl(tds[0]), "出版社": cl(tds[1]), "レーベル": cl(lab.group(1)) if lab else "",
                     "書名": title, "著者": cl(tds[3]), "予価": cl(tds[4]), "ISBN": isbn.group(1) if isbn else "", "記事": u})
        n += 1
    print(f"{t}：{n}件", flush=True)

os.makedirs("data/manga", exist_ok=True)
with open("data/manga/hikidashi.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print("合計", len(rows), "件", len(arts), "本")
