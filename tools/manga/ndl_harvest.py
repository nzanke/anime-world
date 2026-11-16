"""国会図書館サーチSRUで、指定期間に出たコミック（NDC 726.1 または NDLC Y84、国会図書館所蔵分）を月ごとに全部取る。
使い方: python3 ndl_harvest.py 2024-01 2026-12 out/
出力: out/ndl_comics.jsonl.gz（1件1行）
"""
import gzip, html, json, re, sys, time, urllib.parse, urllib.request

API = "https://ndlsearch.ndl.go.jp/api/sru"
start, end, outdir = sys.argv[1], sys.argv[2], sys.argv[3].rstrip("/")


def months(a, b):
    y, m = map(int, a.split("-"))
    Y, M = map(int, b.split("-"))
    while (y, m) <= (Y, M):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def get(q, startrec):
    url = API + "?" + urllib.parse.urlencode({
        "operation": "searchRetrieve", "maximumRecords": "500", "startRecord": str(startrec),
        "recordSchema": "dcndl", "recordPacking": "xml", "query": q})
    for wait in (0, 10, 30, 60, 120):
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "anime-world manga volume list"})
            return urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
        except Exception as e:
            print("  再試行", wait, e, file=sys.stderr)
    raise RuntimeError("取得できず: " + q)


def first(pat, s):
    m = re.search(pat, s, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def parse(rec):
    bib = rec[rec.find("<dcndl:BibResource"):]
    bib = bib[:bib.find("</dcndl:BibResource>")]
    about = re.search(r'<dcndl:BibResource rdf:about="([^"]+)"', rec)
    return {
        "id": about.group(1) if about else "",
        "title": first(r"<dcterms:title>(.*?)</dcterms:title>", bib),
        "title_yomi": first(r"<dc:title>.*?<dcndl:transcription>(.*?)</dcndl:transcription>", bib),
        "volume": first(r"<dcndl:volume>.*?<rdf:value>(.*?)</rdf:value>", bib),
        "series": first(r"<dcndl:seriesTitle>.*?<rdf:value>(.*?)</rdf:value>", bib),
        "publisher": first(r"<dcterms:publisher>.*?<foaf:name>(.*?)</foaf:name>", bib),
        "creator": first(r"<dc:creator>(.*?)</dc:creator>", bib),
        "issued": first(r"<dcterms:issued[^>]*>(.*?)</dcterms:issued>", bib),
        "date": first(r"<dcterms:date>(.*?)</dcterms:date>", bib),
        "isbn": first(r'<dcterms:identifier rdf:datatype="http://ndl.go.jp/dcndl/terms/ISBN">(.*?)</', bib),
        "extent": first(r"<dcterms:extent>(.*?)</dcterms:extent>", bib),
    }


seen = set()
n_all = 0
with gzip.open(f"{outdir}/ndl_comics_{start}_{end}.jsonl.gz", "wt", encoding="utf-8") as out:
    for ym in months(start, end):
        for cond in ('ndc="726.1"', 'ndlc="Y84"'):
            q = f'{cond} AND from="{ym}" AND until="{ym}" AND dpid="iss-ndl-opac"'
            s, total, got = 1, None, 0
            while True:
                x = get(q, s)
                if total is None:
                    m = re.search(r"<numberOfRecords>(\d+)", x)
                    total = int(m.group(1)) if m else 0
                recs = re.findall(r"<recordData>(.*?)</recordData>", x, re.S)
                for r in recs:
                    d = parse(r)
                    key = d["id"] or (d["title"], d["volume"], d["isbn"])
                    if key in seen:
                        continue
                    seen.add(key)
                    d["month"] = ym
                    out.write(json.dumps(d, ensure_ascii=False) + "\n")
                    n_all += 1
                got += len(recs)
                time.sleep(2)
                if not recs or got >= total:
                    break
                s += len(recs)
            print(f"{ym} {cond}: {total}件中 {got}件取得（重複を除いた累計 {n_all}）", flush=True)
print("合計", n_all)
