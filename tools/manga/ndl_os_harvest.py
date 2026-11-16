"""国会図書館サーチ OpenSearch で、指定期間のコミック（NDC 726.1、国会図書館所蔵）を月ごとに全部取る。
1回で取れるのは500件までなので、ISBNの頭（978-4-06 など）で500件以下になるまで分けて取る。
月ごとに data/manga/ndl/YYYY-MM.jsonl.gz に保存し、COMMIT=1 なら月ごとにコミットする。
すでにある月は飛ばす（止まっても続きから取れる）。
使い方: python3 ndl_os_harvest.py 2024-01 2026-12
"""
import gzip, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

API = "https://ndlsearch.ndl.go.jp/api/opensearch"
NS = {"dc": "http://purl.org/dc/elements/1.1/", "dcndl": "http://ndl.go.jp/dcndl/terms/",
      "dcterms": "http://purl.org/dc/terms/", "xsi": "http://www.w3.org/2001/XMLSchema-instance",
      "openSearch": "http://a9.com/-/spec/opensearchrss/1.0/"}
OUT = "data/manga/ndl"
PACE = float(os.environ.get("PACE", "15"))
stats = {"req": 0, "429": 0}


def months(a, b):
    y, m = map(int, a.split("-")); Y, M = map(int, b.split("-"))
    while (y, m) <= (Y, M):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def fetch(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for wait in (0, 30, 60, 120, 240, 480, 600):
        if wait:
            stats["429"] += 1
            print(f"    待つ {wait}秒", flush=True)
        time.sleep(wait + PACE)
        try:
            stats["req"] += 1
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"})
            return ET.fromstring(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            print("    再試行", e, flush=True)
    raise RuntimeError("取得できず: " + url)


def total_of(root):
    t = root.find(".//openSearch:totalResults", NS)
    return int(t.text) if t is not None else 0


def items(root):
    for it in root.iter("item"):
        g = lambda p: (it.findtext(p, "", NS) or "").strip()
        isbn = ""
        for idf in it.findall("dc:identifier", NS):
            if "ISBN" in (idf.get(f"{{{NS['xsi']}}}type") or ""):
                isbn = (idf.text or "").strip()
        yield {"id": g("link") or g("guid"), "title": g("dc:title"), "volume": g("dcndl:volume"),
               "series": g("dcndl:seriesTitle"), "publisher": g("dc:publisher"), "creator": g("dc:creator"),
               "issued": g("dcterms:issued"), "isbn": isbn}


def harvest_month(ym):
    base = {"ndc": "726.1", "from": ym, "until": ym, "dpid": "iss-ndl-opac"}
    got = {}
    root = fetch({**base, "cnt": "500"})
    total = total_of(root)
    if total <= 500:
        for d in items(root):
            got[d["id"] or (d["title"], d["volume"], d["isbn"])] = d
        return total, got, 0
    q = [0]

    def take(p):
        """p で始まるISBNを全部取る。500件を超えたら1桁足して分ける。数字で分けきれない分（番号の区切り）だけハイフン付きで取る。"""
        r = fetch({**base, "isbn": p, "cnt": "500"}); q[0] += 1
        n = total_of(r)
        if n <= 500:
            for d in items(r):
                got[d["id"] or (d["title"], d["volume"], d["isbn"])] = d
            return n
        s = sum(take(p + str(d)) for d in range(10))
        if s < n and not p.endswith("-"):
            s += take(p + "-")
        return s

    for p in [f"978-4-{d}" for d in range(10)] + ["979-"]:
        take(p)
    return total, got, q[0]


def main():
    a, b = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for ym in months(a, b):
        path = f"{OUT}/{ym}.jsonl.gz"
        if os.path.exists(path):
            print(ym, "取得済み", flush=True)
            continue
        t = time.time()
        total, got, q = harvest_month(ym)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for d in got.values():
                d["month"] = ym
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"{ym}: 全{total}件 取得{len(got)}件 差{total - len(got)} 問い合わせ{q}回 {time.time()-t:.0f}秒"
              f"（累計 {time.time()-t0:.0f}秒・断られた{stats['429']}回）", flush=True)
        if os.environ.get("COMMIT") == "1":
            subprocess.run(["git", "add", path])
            subprocess.run(["git", "commit", "-qm", f"国会図書館のコミック書誌（{ym}）[skip ci]"])
            for _ in range(5):
                if subprocess.run(["git", "pull", "-q", "--rebase"]).returncode == 0 and subprocess.run(["git", "push", "-q"]).returncode == 0:
                    break
                time.sleep(10)


if __name__ == "__main__":
    main()
