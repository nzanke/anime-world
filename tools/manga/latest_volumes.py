"""国会図書館のコミック書誌（data/manga/ndl/*.jsonl.gz）と、ほんのひきだしの発売日一覧（data/manga/hikidashi.csv）から、
作品ごとの最新巻の一覧を作る。
- 同じ本はISBNでつなぐ（発売日はほんのひきだしの日付を優先、国会図書館は年月まで）
- 作品のまとまりは「作品名（巻数を除いた書名）＋出版社」
使い方: python3 latest_volumes.py 出力.csv
"""
import csv, glob, gzip, json, re, sys, unicodedata
from collections import defaultdict

SPECIAL = re.compile(r"特装版|限定版|同梱版|特別版|プレミアム版|DVD付|Blu-ray付|小冊子付|フィギュア付|グッズ付")
KANJI = {"上": 1, "中": 2, "下": 3, "前編": 1, "後編": 2, "前": 1, "後": 2}


def nf(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def key_of(t):
    return re.sub(r"[\s・･:=\-‐―ー~〜!?.,、。「」『』()\[\]【】★☆♡♥'\"]", "", nf(t).lower())


def vol_num(v):
    v = nf(v)
    if v in KANJI:
        return KANJI[v]
    m = re.search(r"(\d+)", v)
    return int(m.group(1)) if m else None


def clean_creator(c):
    c = re.sub(r",\s*\d{4}-(\d{4})?", "", nf(c))
    return re.sub(r",\s*", "", c)


def main():
    out = sys.argv[1]
    books = {}  # ISBN -> 本
    for p in sorted(glob.glob("data/manga/ndl/*.jsonl.gz")):
        for line in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(line)
            isbn = r["isbn"].replace("-", "")
            if not isbn or SPECIAL.search(r["title"] + r["volume"]):
                continue
            name = nf(r["title"])
            books[isbn] = {"作品名": name.split(" : ")[0].split(" = ")[0].strip(), "巻": nf(r["volume"]),
                           "出版社": nf(r["publisher"]), "レーベル": nf(r["series"]).split(";")[0].split(". ")[0].strip(),
                           "著者": clean_creator(r["creator"]), "発売": r["issued"].replace(".", "-"),
                           "国会図書館": r["id"].replace("#material", ""), "ひきだし": False}
    for r in csv.DictReader(open("data/manga/hikidashi.csv", encoding="utf-8-sig")):
        isbn = r["ISBN"]
        title = nf(r["書名"]).split("\n")[-1].strip()
        if not isbn or SPECIAL.search(title):
            continue
        m = re.search(r"[（(]\s*(\d+|上|中|下|前編|後編)\s*[）)]\s*$", title)
        vol = m.group(1) if m else ""
        name = title[:m.start()].strip() if m else title
        d = nf(r["日"]).split("/")[-1]
        date = f"{r['年月']}-{int(d):02d}" if d.isdigit() else r["年月"]
        lab = nf(r["レーベル"]) or (nf(r["書名"]).split("\n")[0] if "\n" in r["書名"] else "")
        if isbn in books:  # 国会図書館にもある本：発売日とレーベル・著者の表記を補う
            b = books[isbn]
            b["発売"] = date
            b["ひきだし"] = True
            b["著者"] = nf(r["著者"]) or b["著者"]
            if not b["巻"]:
                b["巻"] = vol
        else:
            books[isbn] = {"作品名": name, "巻": vol, "出版社": nf(r["出版社"]), "レーベル": lab, "著者": nf(r["著者"]),
                           "発売": date, "国会図書館": "", "ひきだし": True}
    works = defaultdict(list)
    for isbn, b in books.items():
        b["ISBN"] = isbn
        b["n"] = vol_num(b["巻"])
        pub = re.sub(r"^(株式会社|\(株\))|株式会社$", "", b["出版社"])
        works[(key_of(b["作品名"]), key_of(pub)[:4])].append(b)
    rows = []
    for items in works.values():
        num = [b for b in items if b["n"] is not None]
        if num:
            mx = max(b["n"] for b in num)
            top = [b for b in num if b["n"] == mx]
            latest = max(top, key=lambda b: (b["ひきだし"], b["発売"]))
            nvol = len({b["n"] for b in num})
        else:
            latest = max(items, key=lambda b: b["発売"])
            nvol = 0
        rows.append({"": "", "作品名": latest["作品名"], "最新巻": latest["巻"] or "（巻数なし）", "最新巻の発売": latest["発売"],
                     "出版社": latest["出版社"], "レーベル": latest["レーベル"], "著者": latest["著者"],
                     "期間内の巻数": nvol, "ISBN": latest["ISBN"], "国会図書館": latest["国会図書館"],
                     "出典": "・".join(x for x, f in (("ほんのひきだし", any(b["ひきだし"] for b in items)),
                                                      ("国会図書館", any(b["国会図書館"] for b in items))) if f)})
    rows.sort(key=lambda r: (r["作品名"]))
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(books), "冊 →", len(rows), "作品")


if __name__ == "__main__":
    main()
