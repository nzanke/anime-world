"""国立国会図書館サーチ（OpenSearch API）で、漫画作品の既刊の最新巻を調べる。
使い方: python3 ndl_volumes.py "作品名1|作品名2|..." [出力先.json]
"""
import json, re, sys, time, unicodedata, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

API = "https://ndlsearch.ndl.go.jp/api/opensearch"
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "dcterms": "http://purl.org/dc/terms/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
EXCLUDE = re.compile(r"特装|同梱|限定版|ガイド|ファンブック|画集|公式|設定資料|小説|ノベライズ|アンソロジー|総集編|カラー版|英語|BOX|ボックス|セット")


def norm(s):
    return unicodedata.normalize("NFKC", s or "").strip()


def vol_number(vol, title):
    for s in (vol, title):
        s = norm(s)
        m = re.search(r"(\d+)\s*(?:巻)?\s*$", s) or re.search(r"第?\s*(\d+)\s*巻", s)
        if m:
            return int(m.group(1))
    return None


def fetch(title):
    q = urllib.parse.urlencode({"title": title, "cnt": "500"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "anime-world manga volume check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def check(title):
    raw = fetch(title)
    root = ET.fromstring(raw)
    rows = []
    for it in root.iter("item"):
        t = norm(it.findtext("dc:title", "", NS) or it.findtext("title", ""))
        vol = norm(it.findtext("dcndl:volume", "", NS))
        pub = norm(it.findtext("dc:publisher", "", NS))
        issued = norm(it.findtext("dcterms:issued", "", NS))
        isbn = ""
        for idf in it.findall("dc:identifier", NS):
            if "ISBN" in (idf.get(f"{{{NS['xsi']}}}type") or ""):
                isbn = norm(idf.text)
        series = norm(it.findtext("dcndl:seriesTitle", "", NS))
        rows.append({"title": t, "volume": vol, "publisher": pub, "issued": issued,
                     "isbn": isbn, "series": series, "link": norm(it.findtext("link", ""))})
    key = norm(title).replace(" ", "")
    hits = []
    for r in rows:
        if not r["title"].replace(" ", "").startswith(key):
            continue
        if EXCLUDE.search(r["title"] + r["volume"]):
            continue
        n = vol_number(r["volume"], r["title"])
        if n is None:
            continue
        hits.append({**r, "n": n})
    # 同じ巻は1件に
    by_n = {}
    for h in hits:
        if h["n"] not in by_n or (h["isbn"] and not by_n[h["n"]]["isbn"]):
            by_n[h["n"]] = h
    vols = sorted(by_n)
    latest = by_n[vols[-1]] if vols else None
    missing = [i for i in range(1, vols[-1] + 1) if i not in by_n] if vols else []
    if not rows:
        print("応答の先頭:", raw[:800].decode("utf-8", "replace"), file=sys.stderr)
    elif not vols:
        print("先頭3件:", json.dumps(rows[:3], ensure_ascii=False), file=sys.stderr)
    return {"query": title, "records": len(rows), "volumes_found": len(vols),
            "latest": latest, "missing": missing[:50]}


def main():
    titles = [t.strip() for t in sys.argv[1].split("|") if t.strip()]
    out = sys.argv[2] if len(sys.argv) > 2 else "manga_volumes.json"
    res = []
    for t in titles:
        try:
            res.append(check(t))
        except Exception as e:
            res.append({"query": t, "error": str(e)})
        time.sleep(1)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    lines = ["| 作品 | 最新巻 | 発行 | 出版社 | 見つかった巻数 | 抜け |", "|---|---|---|---|---|---|"]
    for r in res:
        if r.get("error"):
            lines.append(f"| {r['query']} | エラー: {r['error']} | | | | |")
        elif r["latest"]:
            L = r["latest"]
            lines.append(f"| {r['query']} | {L['n']} | {L['issued']} | {L['publisher']} | {r['volumes_found']} | {','.join(map(str, r['missing'][:10]))} |")
        else:
            lines.append(f"| {r['query']} | 見つからず（{r['records']}件中） | | | | |")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
