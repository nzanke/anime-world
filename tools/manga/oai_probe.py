"""国会図書館サーチ OAI-PMH で、指定した1日に登録・更新された書誌を取り、件数・問い合わせ回数・時間・断られた回数を測る（試し用）。
使い方: python3 oai_probe.py 2026-11-14 [セット名]
問い合わせは最大40回・間隔20秒で打ち切る。
"""
import re, sys, time, urllib.parse, urllib.request

DAY = sys.argv[1]
SET = sys.argv[2] if len(sys.argv) > 2 else "iss-ndl-opac"
API = "https://ndlsearch.ndl.go.jp/api/oaipmh"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
params = {"verb": "ListRecords", "metadataPrefix": "dcndl", "from": DAY, "until": DAY, "set": SET}
t0 = time.time()
req_n = rej = total = comics = comics_isbn = 0
size = None
samples = []
while req_n < 40:
    url = API + "?" + urllib.parse.urlencode(params)
    t = time.time()
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read().decode("utf-8", "replace")
    except Exception as e:
        req_n += 1
        rej += "429" in str(e)
        print(f"問い合わせ{req_n}: エラー {e}（{time.time()-t:.0f}秒）", flush=True)
        if rej >= 2:
            break
        time.sleep(120)
        continue
    req_n += 1
    recs = re.findall(r"<record>(.*?)</record>", x, re.S)
    total += len(recs)
    for r in recs:
        if re.search(r"ndc\d*/726\.1|NDC\d*[^<]*726\.1|>726\.1<", r):
            comics += 1
            if re.search(r"ISBN", r):
                comics_isbn += 1
                if len(samples) < 5:
                    m = re.search(r"<dcterms:title>(.*?)</dcterms:title>", r)
                    samples.append(m.group(1) if m else "?")
    m = re.search(r'<resumptionToken[^>]*completeListSize="(\d+)"', x)
    if m:
        size = int(m.group(1))
    tok = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", x)
    print(f"問い合わせ{req_n}: {len(recs)}件（{time.time()-t:.0f}秒、{len(x)//1024}KB）累計{total}件／全体{size}", flush=True)
    if req_n == 1 and not recs:
        print("  応答の先頭:", re.sub(r"\s+", " ", x[:600]))
    if not tok:
        break
    params = {"verb": "ListRecords", "resumptionToken": tok.group(1)}
    time.sleep(20)
print(f"結果 {DAY}（{SET}）: 全{size}件中 {total}件取得、うち漫画（726.1）{comics}件・ISBNあり{comics_isbn}件、"
      f"問い合わせ{req_n}回、断られた{rej}回、{time.time()-t0:.0f}秒")
print("見本:", samples)
