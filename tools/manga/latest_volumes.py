"""国会図書館のコミック書誌（ndl_comics.jsonl.gz）とほんのひきだしの発売日一覧（CSV、任意）から、
作品ごとの最新巻の一覧を作る。
使い方: python3 latest_volumes.py ndl_comics.jsonl.gz 出力.csv [ほんのひきだし.csv]
"""
import csv, gzip, json, re, sys, unicodedata
from collections import defaultdict

KANJI_VOL = {"上": 1, "中": 2, "下": 3, "前": 1, "後": 2, "前編": 1, "後編": 2, "上巻": 1, "下巻": 3}
SPECIAL = re.compile(r"特装版|限定版|同梱版|特別版|プレミアム版|アニメDVD付|小冊子付")


def nf(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def key_of(title):
    t = nf(title).lower()
    t = re.sub(r"[\s・･:：=＝\-‐―ー~〜!！?？.,、。「」『』()（）\[\]【】]", "", t)
    return t


def vol_num(v):
    v = nf(v)
    if v in KANJI_VOL:
        return KANJI_VOL[v]
    m = re.search(r"(\d+)", v)
    return int(m.group(1)) if m else None


def split_title(title, volume):
    """書名の末尾の巻次を落として作品名にする。"""
    t = nf(title)
    v = nf(volume)
    if v:
        t = re.sub(r"[\s.．]*" + re.escape(v) + r"\s*$", "", t)
    t = re.sub(r"\s*[.．]\s*$", "", t)
    return t.strip()


def main():
    src, out = sys.argv[1], sys.argv[2]
    hk = sys.argv[3] if len(sys.argv) > 3 else None
    works = defaultdict(list)
    for line in gzip.open(src, "rt", encoding="utf-8"):
        r = json.loads(line)
        if SPECIAL.search(r["title"] + r["volume"]):
            continue
        n = vol_num(r["volume"])
        name = split_title(r["title"], r["volume"])
        main_name = name.split(" : ")[0].split(" = ")[0].strip()
        works[(key_of(main_name), r["publisher"])].append({
            "作品名": main_name, "書名": name, "巻": r["volume"], "n": n, "発行": r["date"] or r["issued"],
            "出版社": r["publisher"], "レーベル": r["series"].split(";")[0].strip(), "著者": r["creator"],
            "ISBN": r["isbn"].replace("-", ""), "リンク": r["id"].replace("#material", ""), "出典": "国会図書館"})
    if hk:
        for r in csv.DictReader(open(hk, encoding="utf-8-sig")):
            title = nf(r["書名"]).split("\n")[-1]
            m = re.search(r"[（(]\s*(\d+|上|中|下)\s*[）)]\s*$", title)
            v = m.group(1) if m else ""
            name = title[:m.start()].strip() if m else title
            if SPECIAL.search(title):
                continue
            pub = nf(r["出版社"])
            k = key_of(name)
            tgt = next((kk for kk in works if kk[0] == k and (pub in kk[1] or kk[1] in pub)), (k, pub))
            works[tgt].append({
                "作品名": name, "書名": name, "巻": v, "n": vol_num(v), "発行": f"{r['年月']}-{int(r['日']):02d}" if r["日"].isdigit() else r["年月"],
                "出版社": pub, "レーベル": nf(r["レーベル"]) or (nf(r["書名"]).split("\n")[0] if "\n" in r["書名"] else ""),
                "著者": r["著者"], "ISBN": r["ISBN"], "リンク": "", "出典": "ほんのひきだし"})
    rows = []
    for k, items in works.items():
        numbered = [i for i in items if i["n"] is not None]
        if numbered:
            mx = max(i["n"] for i in numbered)
            latest = sorted([i for i in numbered if i["n"] == mx], key=lambda i: (i["出典"] != "国会図書館", i["発行"]))[0]
            # 発売日が分かればそちらを使う
            hkd = [i["発行"] for i in numbered if i["n"] == mx and i["出典"] == "ほんのひきだし"]
            date = hkd[0] if hkd else latest["発行"]
            nvol = len({i["n"] for i in numbered})
        else:
            latest = sorted(items, key=lambda i: i["発行"])[-1]
            mx, date, nvol = "", latest["発行"], 0
        rows.append({"": "", "作品名": latest["作品名"], "最新巻": latest["巻"] if numbered else "（巻数なし）",
                     "最新巻の発売": date, "出版社": latest["出版社"], "レーベル": latest["レーベル"],
                     "著者": latest["著者"], "期間内に確認できた巻数": nvol, "ISBN": latest["ISBN"],
                     "国会図書館": latest["リンク"],
                     "出典": "・".join(sorted({i["出典"] for i in items}))})
    rows.sort(key=lambda r: r["作品名"])
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "作品")


if __name__ == "__main__":
    main()
