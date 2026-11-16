import json, re, time, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (anime-world manga volume list)"}
def get(u, t=120):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "replace")
# ほんのひきだし：WordPressの記事検索
for u in ["https://hon-hikidashi.jp/wp-json/wp/v2/posts?search=%E3%82%B3%E3%83%9F%E3%83%83%E3%82%AF%E6%96%B0%E5%88%8A%E7%99%BA%E5%A3%B2%E6%97%A5%E4%B8%80%E8%A6%A7&per_page=100&_fields=id,link,title,date",
          "https://hon-hikidashi.jp/news/lineup/page/5/"]:
    try:
        x = get(u)
        if x.lstrip().startswith("["):
            d = json.loads(x); print("ひきだし記事検索:", len(d), "件", [i["title"]["rendered"] for i in d[-3:]])
        else:
            print("ひきだし一覧p5:", len(x), re.findall(r'(\d{4}年\d+月発売のコミック新刊発売日一覧[^<]*)', x)[:4])
    except Exception as e:
        print("ひきだし", u[:60], "エラー", e)
    time.sleep(3)
# 国会図書館 OpenSearch の深いページ
time.sleep(60)
for idx in (1, 1001):
    u = "https://ndlsearch.ndl.go.jp/api/opensearch?" + urllib.parse.urlencode({"ndc": "726.1", "from": "2025-12", "until": "2025-12", "dpid": "iss-ndl-opac", "cnt": "500", "idx": str(idx)})
    t = time.time()
    try:
        x = get(u, 180)
        tot = re.search(r"<openSearch:totalResults>(\d+)", x)
        print(f"国会図書館OpenSearch idx={idx}: {time.time()-t:.0f}秒 全{tot.group(1) if tot else '?'}件 今回{x.count('<item>')}件", re.findall(r"<title>(.*?)</title>", x)[1:3])
    except Exception as e:
        print("国会図書館OpenSearch", idx, "エラー", e, f"{time.time()-t:.0f}秒")
    time.sleep(30)
