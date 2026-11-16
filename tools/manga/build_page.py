"""新刊リストのページ（index.html）を作る。
土台：国会図書館の全国書誌データ（ndl_tsv.jsonl.gz、NDC 726.1、2024〜2026年）
補助：ほんのひきだしの発売日一覧（hikidashi.csv）
  - 同じISBNの本：発売日（日まで）・予価・巻数（国会図書館の書名に巻数がないとき）を補う
  - 国会図書館にない本：成人向け（書名に「（成）」）を除いて足す（発売前の本、通常版、小さな出版社の本など）
最新巻は特装版なども含めて数える（一覧の「特装版などを除く」は表示だけに効く）。
"""
import csv, gzip, json, re, unicodedata
from collections import defaultdict

NDL = "/home/claude/anime-world/data/manga/ndl_tsv.jsonl.gz"
HK = "hikidashi.csv"
nf = lambda s: unicodedata.normalize("NFKC", s or "").strip()
SPECIAL = re.compile(r"特装|限定|同梱|特別版|プレミアム|DVD付|Blu-ray付|小冊子付|フィギュア付|グッズ付|付き")


def pub_norm(p):
    p = nf(p)
    if "発行/" in p:
        p = p.split("発行/")[0]
    p = re.sub(r"^(株式会社|\(株\))|株式会社$", "", p)
    return re.sub(r"\s+", "", p).strip()


def lab_norm(l):
    l = nf(l).split(" = ")[0].strip()
    return l.upper() if re.fullmatch(r"[\x20-\x7e]+", l) else l


def key_of(t):
    t = re.sub(r"\([^)]{1,15}\)", "", nf(t))
    return re.sub(r"[\s・･:=\-‐―ー~〜!?.,、。「」『』()\[\]【】★☆♡♥'\"]", "", nf(t).lower())


def vnum(v):
    return {"上": 1, "中": 2, "下": 3, "前編": 1, "後編": 2}.get(v) or (int(v) if v.isdigit() else None)


pubs, labs = {}, {}
P = lambda p: pubs.setdefault(p, len(pubs))
L = lambda l: labs.setdefault(l, len(labs))

# ---- ほんのひきだし ----
src = [r for r in csv.DictReader(open(HK, encoding="utf-8-sig")) if r["予価"] != "予価" and "発" not in r["日"]]
known = set()
for r in src:
    lines = [l.strip() for l in r["書名"].split("\n") if l.strip()]
    l0 = nf(r["レーベル"]) or (nf(lines[0]) if len(lines) > 1 else "")
    if len(l0) >= 3:
        known.add(l0)
known = sorted(known, key=len, reverse=True)
hk = {}
for r in src:
    lines = [l.strip() for l in r["書名"].split("\n") if l.strip()]
    title = nf(lines[-1]) if lines else ""
    lab = nf(r["レーベル"]) or (nf(lines[0]) if len(lines) > 1 else "")
    if not lab:
        for k in known:
            if title.startswith(k) and len(title) > len(k) + 1:
                lab, title = k, title[len(k):].strip()
                break
    d = nf(r["日"]).split("/")[-1]
    m = re.search(r"[（(]\s*(\d+|上|中|下|前編|後編)\s*[）)]\s*$", title)
    if m and re.fullmatch(r"(19|20)\d\d", m.group(1)):
        m = None
    hk.setdefault(r["ISBN"] or (r["年月"], title), {
        "ym": r["年月"], "day": int(d) if d.isdigit() else 0, "pub": pub_norm(r["出版社"]), "lab": lab,
        "name": title[:m.start()].strip() if m else title, "vol": m.group(1) if m else "",
        "auth": nf(r["著者"]), "price": nf(r["予価"]), "isbn": r["ISBN"],
        "sp": 1 if SPECIAL.search(title) else 0, "adult": "(成)" in title or "（成）" in r["書名"]})

# ---- 国会図書館（土台） ----
rows, seen = [], set()
stat = {"ndl": 0, "day": 0, "vol": 0, "hk_add": 0, "adult": 0}
for line in gzip.open(NDL, "rt", encoding="utf-8"):
    d = json.loads(line)
    isbn = d["ISBN"].replace("-", "").strip()
    m = re.match(r"(\d{4})\.(\d{1,2})", d["出版年月日等"])
    if not isbn or isbn in seen or not m:
        continue
    seen.add(isbn)
    t = nf(d["タイトル"])
    t = re.sub(r"[.．]?\s*(?:Volume|VOLUME|Vol\.?|VOL\.?|vol\.?|第)\s*(\d+)\s*巻?$", r" \1", t)
    vm = re.search(r"(?:[.．]\s*|\s+)(\d+|上|中|下|前編|後編)$", t)
    if vm and re.fullmatch(r"(19|20)\d\d", vm.group(1)):
        vm = None  # 「2026」などの年号は巻数ではない
    vol = vm.group(1) if vm else ""
    name = (t[:vm.start()] if vm else t).split(" = ")[0].split(" : ")[0].strip()
    lab = re.sub(r"[\s.．]*\d+$", "", nf(d["シリーズタイトル"]).split(";")[0]).strip()
    auth = re.sub(r"\s*(著|作|画|漫画|原作|絵|編|原案|キャラクター原案|作画|ネーム|構成)(?=\s|$|,|;)", "", nf(d["責任表示"])).replace(";", "／").strip()
    ym, day, price = f"{m.group(1)}-{int(m.group(2)):02d}", -1, ""
    h = hk.get(isbn)
    if h:
        ym, day, price = h["ym"], h["day"], h["price"]
        stat["day"] += 1
        if not vol and h["vol"] and not re.fullmatch(r"(19|20)\d\d", h["vol"]):
            vol = h["vol"]; stat["vol"] += 1
        lab = lab or h["lab"]
    sp = 1 if SPECIAL.search(t + nf(d["版"])) else 0
    rows.append([ym, day, P(pub_norm(d["出版者"])), L(lab_norm(lab)), name, vol, auth, price, isbn, sp])
    stat["ndl"] += 1

# ---- ほんのひきだしにしかない本を足す（成人向けは除く） ----
for k, h in hk.items():
    if h["isbn"] and h["isbn"] in seen:
        continue
    if h["adult"]:
        stat["adult"] += 1
        continue
    rows.append([h["ym"], h["day"], P(h["pub"]), L(lab_norm(h["lab"])), h["name"], h["vol"], h["auth"], h["price"], h["isbn"], h["sp"]])
    stat["hk_add"] += 1

rows.sort(key=lambda x: (x[0], x[1] if x[1] > 0 else (99 if x[1] == 0 else 100), x[2], x[4]))

# ---- 作品ごとの最新巻（特装版も数える。表示は同じ巻の通常版を優先） ----
works = defaultdict(list)
for i, x in enumerate(rows):
    works[(key_of(x[4]), x[2])].append(i)
W = []
for idx in works.values():
    num = [i for i in idx if vnum(rows[i][5]) is not None]
    if num:
        mx = max(vnum(rows[i][5]) for i in num)
        top = [i for i in num if vnum(rows[i][5]) == mx]
        rep = min(top, key=lambda i: (rows[i][9], -(rows[i][1] > 0), rows[i][0]))
        W.append([rep, len({vnum(rows[i][5]) for i in num})])
    else:
        W.append([max(idx, key=lambda i: (rows[i][0], rows[i][1])), 0])

data = {"pubs": list(pubs), "labs": list(labs), "rows": rows, "works": W}
js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
html = open("template.html", encoding="utf-8").read().replace("/*DATA*/null", js)
open("index.html", "w", encoding="utf-8").write(html)
print(f"国会図書館 {stat['ndl']}冊（うち発売日を補った {stat['day']}、巻数を補った {stat['vol']}）"
      f"＋ほんのひきだしだけ {stat['hk_add']}冊（成人向け {stat['adult']}冊は除外）＝{len(rows)}冊、{len(W)}作品、{len(html)/1e6:.2f}MB")
