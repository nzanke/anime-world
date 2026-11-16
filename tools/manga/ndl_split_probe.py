import re, time, urllib.parse, urllib.request
API = "https://ndlsearch.ndl.go.jp/api/sru"
M = 'ndc="726.1" AND from="2025-12" AND until="2025-12" AND dpid="iss-ndl-opac"'
tests = [("start=500", M, 500), ("start=100", M, 100)]
for p in ["講談社", "集英社", "小学館", "KADOKAWA"]:
    tests.append((p, M + f' AND publisher="{p}"', 1))
tests.append(("講談社以外", M + ' NOT publisher="講談社"', 1))
tests.append(("12月1日〜15日", 'ndc="726.1" AND from="2025-12-01" AND until="2025-12-15" AND dpid="iss-ndl-opac"', 1))
tests.append(("sortBy", M + " sortBy title/sort.descending", 1))
for name, q, start in tests:
    url = API + "?" + urllib.parse.urlencode({"operation": "searchRetrieve", "maximumRecords": "1", "startRecord": str(start), "recordSchema": "dc", "recordPacking": "xml", "query": q})
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "anime-world manga volume list"}), timeout=120).read().decode("utf-8", "replace")
        n = re.search(r"<numberOfRecords>(\d+)", x); msg = re.search(r"<message>(.*?)</", x)
        t = re.search(r"<dc:title>(.*?)</dc:title>", x)
        print(f"{name}: 件数={n.group(1) if n else '?'} {msg.group(1) if msg else ''} {t.group(1) if t else ''}")
    except Exception as e:
        print(name, "エラー", e)
    time.sleep(3)
