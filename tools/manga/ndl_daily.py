"""国会図書館サーチ OAI-PMH から、1日に登録・更新された書誌のうち、漫画（NDC 726.1）でISBNのあるものを取る。
GitHub Actions で1日1回動かす。取り終えた日は data/manga/ndl_daily/YYYY-MM-DD.jsonl.gz に保存し、
まだ取れていない日（最大14日前まで）を古い順に取る。止まっても次の回に続きから取る。

保存する項目は、全国書誌データ検索のTSV（ndl_tsv.jsonl.gz）と同じ名前にそろえてある。
使い方: python3 ndl_daily.py [YYYY-MM-DD]  （日付を渡すとその日だけ取る）
"""
import datetime as dt, gzip, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

API = "https://ndlsearch.ndl.go.jp/api/oaipmh"
OUT = "data/manga/ndl_daily"
SET = "iss-ndl-opac"
PACE = 60          # 問い合わせの間隔（秒）
REJECT_WAIT = 300  # 断られたら休む時間（秒）
LIMIT = 5 * 3600   # 1回の実行で使う時間の上限（秒）
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
T0 = time.time()
stat = {"req": 0, "rej": 0}


def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for _ in range(12):
        if time.time() - T0 > LIMIT:
            raise TimeoutError("時間の上限")
        try:
            stat["req"] += 1
            x = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read().decode("utf-8", "replace")
            time.sleep(PACE)
            return x
        except Exception as e:
            if "429" in str(e):
                stat["rej"] += 1
            print(f"  断られた・エラー（{e}）。{REJECT_WAIT // 60}分休みます", flush=True)
            time.sleep(REJECT_WAIT)
    raise RuntimeError("取れませんでした: " + url)


def text(pat, s):
    m = re.search(pat, s, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def parse(rec):
    if 'status="deleted"' in rec[:400]:
        return None
    if not re.search(r'ndc\d*/726\.1["/]', rec):
        return None
    isbn = text(r'<dcterms:identifier rdf:datatype="http://ndl.go.jp/dcndl/terms/ISBN">(.*?)</dcterms:identifier>', rec)
    if not isbn:
        return None
    bib = rec[rec.find("<dcndl:BibResource"):]
    title = text(r"<dcterms:title>(.*?)</dcterms:title>", bib)
    vol = text(r"<dcndl:volume>.*?<rdf:value>(.*?)</rdf:value>", bib)
    if vol and not title.endswith(vol):
        title = f"{title}. {vol}"
    about = re.search(r'<dcndl:BibResource rdf:about="([^"]+)"', rec)
    return {
        "ID": about.group(1) if about else "",
        "タイトル": title,
        "版": text(r"<dcndl:edition>(.*?)</dcndl:edition>", bib),
        "シリーズタイトル": text(r"<dcndl:seriesTitle>.*?<rdf:value>(.*?)</rdf:value>", bib),
        "責任表示": text(r"<dc:creator>(.*?)</dc:creator>", bib),
        "出版者": text(r"<dcterms:publisher>.*?<foaf:name>(.*?)</foaf:name>", bib),
        "出版年月日等": text(r"<dcterms:date>(.*?)</dcterms:date>", bib) or text(r"<dcterms:issued[^>]*>(.*?)</dcterms:issued>", bib),
        "ISBN": isbn,
        "アクセスURL": about.group(1).replace("#material", "") if about else "",
    }


def harvest(day):
    params = {"verb": "ListRecords", "metadataPrefix": "dcndl", "from": day, "until": day, "set": SET}
    got, total, size, n = {}, 0, None, 0
    while True:
        x = get(params)
        n += 1
        recs = re.findall(r"<record>(.*?)</record>", x, re.S)
        total += len(recs)
        for r in recs:
            d = parse(r)
            if d:
                got[d["ISBN"]] = d
        m = re.search(r'completeListSize="(\d+)"', x)
        size = int(m.group(1)) if m else size
        tok = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", x)
        print(f"  {day} {n}回目：{total}/{size}件、漫画（ISBNあり）{len(got)}件（経過{(time.time()-T0)/60:.0f}分、断られた{stat['rej']}回）", flush=True)
        if "noRecordsMatch" in x or not tok:
            return got, total, size
        params = {"verb": "ListRecords", "resumptionToken": tok.group(1)}


def save(day, got, commit):
    os.makedirs(OUT, exist_ok=True)
    path = f"{OUT}/{day}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for d in got.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    if commit:
        subprocess.run(["git", "add", path])
        subprocess.run(["git", "commit", "-qm", f"国会図書館の新着コミック書誌（{day}）[skip ci]"])
        for _ in range(5):
            if subprocess.run(["git", "pull", "-q", "--rebase"]).returncode == 0 and subprocess.run(["git", "push", "-q"]).returncode == 0:
                break
            time.sleep(15)


def main():
    commit = os.environ.get("COMMIT") == "1"
    jst = dt.datetime.utcnow() + dt.timedelta(hours=9)
    if len(sys.argv) > 1 and sys.argv[1]:
        days = [sys.argv[1]]
    else:
        days = [(jst - dt.timedelta(days=k)).strftime("%Y-%m-%d") for k in range(14, 0, -1)]
        days = [d for d in days if not os.path.exists(f"{OUT}/{d}.jsonl.gz")]
    print("取る日:", days, flush=True)
    for day in days:
        t = time.time()
        try:
            got, total, size = harvest(day)
        except TimeoutError:
            print(f"時間の上限に達したので {day} は次の回に回します", flush=True)
            break
        save(day, got, commit)
        print(f"{day}：全{size}件を見て、漫画（ISBNあり）{len(got)}件を保存（{(time.time()-t)/60:.0f}分）", flush=True)
    print(f"終了：問い合わせ{stat['req']}回、断られた{stat['rej']}回、{(time.time()-T0)/60:.0f}分", flush=True)


if __name__ == "__main__":
    main()
