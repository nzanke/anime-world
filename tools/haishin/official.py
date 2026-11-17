"""配信カレンダー：作品の公式サイトから放送・配信情報のページを取ってくる（fetch.py から呼ぶ）
  ・公式サイトのURLは、しょぼいカレンダーの作品情報の「公式」リンク
  ・トップページと、ON AIR・放送・配信情報のページ（リンクからたどる。なければよくある場所を試す）
  ・サービスのロゴ画像の alt（「dアニメストア」など）も文字として残す
"""
import re, html, urllib.parse, urllib.request, concurrent.futures as cf

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
KEY = re.compile(r'on_?air|on-air|broadcast|stream|haishin|housou|放送|配信', re.I)
GUESS = ['onair/', 'on-air/', 'onair.html', 'broadcast/', 'streaming/']

def get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read(3_000_000)
        enc = r.headers.get_content_charset() or ''
    if not enc:
        m = re.search(rb'charset=["\']?([\w-]+)', b[:3000])
        enc = m.group(1).decode() if m else 'utf-8'
    try: return b.decode(enc, 'replace')
    except LookupError: return b.decode('utf-8', 'replace')

def text_of(h):
    h = re.sub(r'(?is)<(script|style|noscript|svg)\b.*?</\1>', ' ', h)
    h = re.sub(r'(?is)<!--.*?-->', ' ', h)
    h = re.sub(r'(?is)<img\b[^>]*?\balt=["\']([^"\']+)["\'][^>]*>', r' \1 ', h)
    h = re.sub(r'(?is)<(br|/p|/li|/div|/h\d|/tr|/dt|/dd|/td|/th|/section|/table|/ul|/dl)\b[^>]*>', '\n', h)
    h = re.sub(r'(?s)<[^>]+>', ' ', h)
    h = html.unescape(h)
    lines = [re.sub(r'[ \t　\xa0]+', ' ', l).strip() for l in h.split('\n')]
    return '\n'.join(l for l in lines if l)

def pages_for(top):
    out, seen = [], set()
    try: h = get(top)
    except Exception as e: return [], f'ERR {type(e).__name__}'
    out.append({'url': top, 'text': text_of(h)[:60000]}); seen.add(top.rstrip('/'))
    cand = []
    host = urllib.parse.urlparse(top).netloc
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h):
        u = urllib.parse.urljoin(top, html.unescape(m.group(1)))
        label = re.sub(r'<[^>]+>', ' ', m.group(2))
        alt = ' '.join(re.findall(r'alt=["\']([^"\']+)', m.group(2)))
        if urllib.parse.urlparse(u).netloc != host or not u.startswith('http'): continue
        if KEY.search(u.split(host, 1)[-1]) or KEY.search(label + ' ' + alt):
            if u.rstrip('/') not in seen and u not in cand: cand.append(u)
    if not cand: cand = [urllib.parse.urljoin(top if top.endswith('/') else top + '/', g) for g in GUESS[:3]]
    for u in cand[:3]:
        try:
            t = text_of(get(u))
            if len(t) > 200: out.append({'url': u, 'text': t[:60000]}); seen.add(u.rstrip('/'))
        except Exception: pass
    return out, 'ok'

def official_urls(titles_xml):
    """しょぼいカレンダーの作品情報から {TID: (作品名, 公式URL)}"""
    res = {}
    for it in re.findall(r'<TitleItem\b.*?</TitleItem>', titles_xml, re.S):
        g = dict(re.findall(r'<(\w+)>(.*?)</\1>', it, re.S))
        if g.get('Cat') not in ('1', '10', '7'): continue
        c = html.unescape(g.get('Comment') or '')
        m = re.search(r'\[\[公式(?:サイト)?\s+(https?://[^\]\s]+)', c)
        if m: res[g['TID']] = (html.unescape(g['Title']), m.group(1))
    return res

def fetch_all(urls, workers=10):
    out = {}
    def one(kv):
        tid, (title, u) = kv
        pg, st = pages_for(u)
        return tid, {'title': title, 'url': u, 'status': st, 'pages': pg}
    with cf.ThreadPoolExecutor(workers) as ex:
        for tid, v in ex.map(one, urls.items()):
            out[tid] = v
    return out
