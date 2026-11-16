"""ほんのひきだしの発売日一覧（hikidashi.csv）から、新刊リストのページ（index.html）を作る。"""
import csv, json, re, sys, unicodedata
from collections import defaultdict

nf = lambda s: unicodedata.normalize("NFKC", s or "").strip()
SPECIAL = re.compile(r"特装版|限定版|同梱版|特別版|プレミアム版|DVD付|Blu-ray付|小冊子付|フィギュア付|グッズ付")


def pub_norm(p):
    p = nf(p)
    if "発行/" in p:
        p = p.split("発行/")[0]
    p = re.sub(r"^(株式会社|\(株\))|株式会社$", "", p)
    return re.sub(r"\s+", "", p).strip()


def key_of(t):
    return re.sub(r"[\s・･:=\-‐―ー~〜!?.,、。「」『』()\[\]【】★☆♡♥'\"]", "", nf(t).lower())


src = list(csv.DictReader(open("hikidashi.csv", encoding="utf-8-sig")))
known = set()
for r in src:
    lines = [l.strip() for l in r["書名"].split("\n") if l.strip()]
    l0 = nf(r["レーベル"]) or (nf(lines[0]) if len(lines) > 1 else "")
    if len(l0) >= 3:
        known.add(l0)
known = sorted(known, key=len, reverse=True)
stripped = 0
rows = []
pubs, labs = {}, {}
for r in src:
    if r["予価"] == "予価" or "発" in r["日"]:
        continue
    lines = [l.strip() for l in r["書名"].split("\n") if l.strip()]
    title = nf(lines[-1]) if lines else ""
    lab = nf(r["レーベル"]) or (nf(lines[0]) if len(lines) > 1 else "")
    if not lab:
        for k in known:
            if title.startswith(k) and len(title) > len(k) + 1:
                lab, title = k, title[len(k):].strip()
                stripped += 1
                break
    d = nf(r["日"]).split("/")[-1]
    day = int(d) if d.isdigit() else 0  # 0 = 日付未定（下旬など）
    m = re.search(r"[（(]\s*(\d+|上|中|下|前編|後編)\s*[）)]\s*$", title)
    vol = m.group(1) if m else ""
    name = title[:m.start()].strip() if m else title
    p = pub_norm(r["出版社"])
    rows.append([r["年月"], day, pubs.setdefault(p, len(pubs)), labs.setdefault(lab, len(labs)), name, vol,
                 nf(r["著者"]), nf(r["予価"]), r["ISBN"], 1 if SPECIAL.search(title) else 0])

# 国会図書館の書誌（全国書誌データ検索のTSV、2024〜2026年）から、ほんのひきだしにない本を足す（発売日は年月まで → 日は -1）
import gzip
hk_isbn = {x[8] for x in rows if x[8]}
ndl_add = 0
for line in gzip.open("/home/claude/anime-world/data/manga/ndl_tsv.jsonl.gz", "rt", encoding="utf-8"):
    d = json.loads(line)
    isbn = d["ISBN"].replace("-", "").split(";")[0].strip()
    if not isbn or isbn in hk_isbn:
        continue
    m = re.match(r"(\d{4})\.(\d{1,2})", d["出版年月日等"])
    if not m:
        continue
    hk_isbn.add(isbn)
    t = nf(d["タイトル"])
    t = re.sub(r"[.．]?\s*(?:Volume|VOLUME|Vol\.?|VOL\.?|vol\.?|第)\s*(\d+)\s*巻?$", r" \1", t)
    vm = re.search(r"(?:[.．]\s*|\s+)(\d+|上|中|下|前編|後編)$", t)
    vol = vm.group(1) if vm else ""
    name = t[:vm.start()].strip() if vm else t
    name = name.split(" = ")[0].split(" : ")[0].strip()
    lab = nf(d["シリーズタイトル"]).split(";")[0].strip()
    lab = re.sub(r"[\s.．]*\d+$", "", lab).strip()
    cr = re.sub(r"\s*(著|作|画|漫画|原作|絵|編|原案|キャラクター原案|作画|ネーム)(?=\s|$|,|;)", "", nf(d["責任表示"])).replace(";", "／").strip()
    p = pub_norm(d["出版者"])
    sp = 1 if SPECIAL.search(t + nf(d["版"])) or re.search(r"限定|特装|付き|付録", nf(d["版"])) else 0
    rows.append([f"{m.group(1)}-{int(m.group(2)):02d}", -1, pubs.setdefault(p, len(pubs)), labs.setdefault(lab, len(labs)), name, vol,
                 cr, "", isbn, sp])
    ndl_add += 1
print("国会図書館から足した", ndl_add, "冊")

# 同じISBNの重複を除く
seen, uniq = set(), []
for x in rows:
    k = x[8] or (x[0], x[4], x[5])
    if k in seen:
        continue
    seen.add(k); uniq.append(x)
rows = sorted(uniq, key=lambda x: (x[0], x[1] if x[1] > 0 else (99 if x[1] == 0 else 100), x[2], x[4]))

# 作品ごとの最新巻（特装版などは除く）
def vnum(v):
    return {"上": 1, "中": 2, "下": 3, "前編": 1, "後編": 2}.get(v) or (int(v) if v.isdigit() else None)

works = defaultdict(list)
for i, x in enumerate(rows):
    if x[9]:
        continue
    works[(key_of(x[4]), x[2])].append(i)
W = []
for (k, p), idx in works.items():
    num = [i for i in idx if vnum(rows[i][5]) is not None]
    if num:
        top = max(num, key=lambda i: (vnum(rows[i][5]), rows[i][0], rows[i][1]))
        W.append([top, len({vnum(rows[i][5]) for i in num})])
    else:
        W.append([max(idx, key=lambda i: (rows[i][0], rows[i][1])), 0])

data = {"pubs": list(pubs), "labs": list(labs), "rows": rows, "works": W}
js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
html = open("template.html", encoding="utf-8").read().replace("/*DATA*/null", js)
open("index.html", "w", encoding="utf-8").write(html)
print("レーベルを切り離した", stripped, "冊");print(len(rows), "冊", len(W), "作品", round(len(html) / 1e6, 2), "MB")
