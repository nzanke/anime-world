import re, time, urllib.parse, urllib.request
API = "https://ndlsearch.ndl.go.jp/api/sru"
q = 'ndc="726.1" AND from="2025-12" AND until="2025-12" AND dpid="iss-ndl-opac"'
for start, mx, schema in ((501, 500, "dcndl"), (501, 100, "dcndl"), (1, 500, "dc")):
    url = API + "?" + urllib.parse.urlencode({"operation": "searchRetrieve", "maximumRecords": str(mx), "startRecord": str(start), "recordSchema": schema, "recordPacking": "xml", "query": q})
    t = time.time()
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "anime-world manga volume list"}), timeout=180).read().decode("utf-8", "replace")
        print(f"start={start} max={mx} {schema}: {time.time()-t:.1f}秒 {len(x)}字 records={len(re.findall('<recordData>', x))}")
        print("   ", re.sub(r"\s+", " ", x[:600]))
        tail = x[-600:]; print("   末尾", re.sub(r"\s+", " ", tail))
    except Exception as e:
        print(start, mx, schema, "エラー", e, f"{time.time()-t:.1f}秒")
    time.sleep(5)
