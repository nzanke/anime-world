import re, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
for u in ["https://hon-hikidashi.jp/news/215903/", "https://hon-hikidashi.jp/news/176678/"]:
    try:
        x = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
        print(f"ひきだし {u}: {len(x)}字 表の行={x.count('<tr>')} 題={re.search(r'<title>(.*?)</title>', x, re.S).group(1)[:60]}")
    except Exception as e:
        print("ひきだし", u, "エラー", e)
    time.sleep(3)
try:
    x = urllib.request.urlopen(urllib.request.Request("https://hon-hikidashi.jp/news/215903/", headers={"User-Agent": "Python-urllib"}), timeout=60).read()
    print("ひきだし（素のUA）", len(x))
except Exception as e:
    print("ひきだし（素のUA）エラー", e)
API = "https://ndlsearch.ndl.go.jp/api/sru"
M = 'ndc="726.1" AND from="2025-12" AND until="2025-12" AND dpid="iss-ndl-opac"'
for name, q in [("全体", M), ("講談社以外", M + ' NOT publisher="講談社"'),
                ("大手4社以外", M + ' NOT publisher="講談社" NOT publisher="KADOKAWA" NOT publisher="小学館" NOT publisher="集英社"')]:
    time.sleep(15)
    url = API + "?" + urllib.parse.urlencode({"operation": "searchRetrieve", "maximumRecords": "1", "recordSchema": "dc", "recordPacking": "xml", "query": q})
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", "replace")
        n = re.search(r"<numberOfRecords>(\d+)", x); msg = re.search(r"<message>(.*?)</", x)
        print(f"国会図書館 {name}: 件数={n.group(1) if n else '?'} {msg.group(1) if msg else ''}")
        if name == "全体":
            print("  絞り込みの種類:", re.findall(r'<lst name="([^"]+)"', x))
            pub = re.search(r'<lst name="PUBLISHER">(.*?)</lst>', x, re.S)
            if pub: print("  出版社:", re.findall(r'<int name="([^"]+)">(\d+)', pub.group(1))[:40])
    except Exception as e:
        print("国会図書館", name, "エラー", e)
