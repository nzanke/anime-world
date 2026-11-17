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
    def rank(u):
        path = urllib.parse.unquote(u.split(host, 1)[-1]).lower()
        if re.search(r'news|topics|blog|info/\d|\d{6,}', path): return 3
        if re.search(r'on_?air|on-air|broadcast|stream', path): return 0
        return 1
    cand.sort(key=rank)
    if not cand or rank(cand[0]) > 1:
        cand = [urllib.parse.urljoin(top if top.endswith('/') else top + '/', g) for g in GUESS[:2]] + cand
    for u in cand[:4]:
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
        if not m:   # 「公式」のリンクがなければ、SNS・配信サービス・百科事典以外の最初のリンク（放送局の番組ページなど）
            for m2 in re.finditer(r'\[\[([^\]]*?)\s+(https?://[^\]\s]+)\]\]', c):
                if not re.search(r'x\.com|twitter|youtube|instagram|tiktok|abema|wikipedia|b-ch|at-x|nicovideo|amazon|netflix|unext|dmm|anime-store|animestore|hulu|lemino|fod|line', m2.group(2) + m2.group(1), re.I):
                    m = m2; break
            if m: res[g['TID']] = (html.unescape(g['Title']), m.group(2)); continue
        if m: res[g['TID']] = (html.unescape(g['Title']), m.group(1))
    return res

def thin(v):
    t = '\n'.join(p['text'] for p in v['pages'])
    return v['pages'] and (len(t) < 1500 or '[[' in t or '{{' in t)

def render(items):
    """JavaScript で中身を組み立てるサイトを、ブラウザ（Actions の Chrome）で表示してから読む"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return 0
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome')
        pg = b.new_page(user_agent=UA, locale='ja-JP')
        for v in items:
            urls = [v['url']] + [x['url'] for x in v['pages'][1:]]
            host = urllib.parse.urlparse(v['url']).netloc
            new = []
            for u in urls[:1]:
                try:
                    pg.goto(u, timeout=30000, wait_until='networkidle')
                    h = pg.content()
                    new.append({'url': u, 'text': text_of(h)[:60000]})
                    links = pg.eval_on_selector_all('a[href]', 'as => as.map(a => [a.href, a.innerText + " " + Array.from(a.querySelectorAll("img")).map(i=>i.alt).join(" ")])')
                    cand = [l[0] for l in links if urllib.parse.urlparse(l[0]).netloc == host and (KEY.search(l[0].split(host, 1)[-1]) or KEY.search(l[1]))]
                    cand = sorted(dict.fromkeys(c.split('#')[0] for c in cand), key=lambda c: 0 if re.search(r'on_?air|on-air|broadcast|stream', c, re.I) else 1)
                    for c in [c for c in cand if c.rstrip('/') != u.rstrip('/')][:2]:
                        pg.goto(c, timeout=30000, wait_until='networkidle')
                        new.append({'url': c, 'text': text_of(pg.content())[:60000]})
                except Exception:
                    pass
            if sum(len(x['text']) for x in new) > sum(len(x['text']) for x in v['pages']):
                v['pages'] = new; v['status'] = 'rendered'; n += 1
        b.close()
    return n

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


# ------------------------------------------------------------ 文面から「サービス → 配信開始日時」を読む
import unicodedata, datetime as dt
JST = dt.timezone(dt.timedelta(hours=9))
SVC = [('danime', r'dアニメストア(?!\s*(for|ニコニコ|forPrime))'), ('unext', r'u-?next'), ('netflix', r'netflix'),
       ('prime', r'(?<!for )(amazon\s*)?prime\s*video|amazon\s*プライム|プライム・?ビデオ|amazonビデオ'), ('dmm', r'dmm\s*tv'),
       ('abema', r'abema'), ('hulu', r'hulu'), ('lemino', r'lemino'), ('fod', r'^fod|フジテレビオンデマンド|\bfod\b'),
       ('animetimes', r'アニメタイムズ'), ('anihoudai', r'アニメ放題'), ('disney', r'disney\s*\+|ディズニープラス'), ('niconico', r'ニコニコ(生放送|動画|チャンネル)|niconico')]
WJ = '月火水木金土日'

def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'(?<=\d)\s+(?=[\d年月日時分:/])|(?<=[年月日時/:])\s+(?=\d)', '', s)
    return s

DATE = re.compile(r'(?:(\d{4})[年./])?\s*(\d{1,2})[月/](\d{1,2})日?\s*(?:[(（][月火水木金土日祝・]+[)）])?')
TIME = re.compile(r'(深夜|夜|よる|午前|午後|朝|あさ|昼)?\s*(\d{1,2})(?::|時)(\d{2}|半)?(?:分)?')

def parse_dt(line, base_year):
    """1行から（日付, 時刻）を読む。時刻がなければ時刻は None"""
    m = DATE.search(line)
    if not m: return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31): return None
    rest = line[m.end():]
    rest = re.sub(r'※\s*\d{1,2}[(（][月火水木金土日][)）]', '', rest)    # 「※3(土)深夜」などの言い換えは飛ばす
    tm = TIME.search(rest[:40])
    hh = mm = None
    if tm and not re.match(r'\s*\d{1,2}\s*[月/]', rest[tm.start():tm.start() + 4]):
        pre, hh, mm = tm.group(1), int(tm.group(2)), tm.group(3)
        mm = 30 if mm == '半' else int(mm or 0)
        if pre in ('夜', 'よる', '午後') and hh < 12: hh += 12
        if pre == '深夜' and hh < 6 and '午前' not in rest[:tm.start() + 4]: hh += 24
        if hh > 30 or mm > 59: hh = None
    try:
        yy = int(y) if y else base_year
        day = dt.datetime(yy, mo, d, tzinfo=JST)
    except ValueError: return None
    return day, hh, mm

def services_in(line):
    out = []
    l = line.lower()
    for part in re.split(r'[、,，/／|｜]|\s{2,}|・(?=[a-zA-Zァ-ヶ])', l):
        p = part.strip(' ・■□◆◇●○★☆▼▽※【】[]()（）')
        for k, pat in SVC:
            if re.search(pat, p) and k not in out: out.append(k)
    return out

BAD = re.compile(r'レンタル|都度課金|tvod|ppv|単品|個別課金|購入|\best\b', re.I)
TVL = re.compile(r'放送(?!・配信|/配信)(?!.*配信)')

def parse_official(text, first):
    """first: 作品の放送開始の年月（しょぼいカレンダー）の datetime。これより1か月以上前・5か月以上後の日付は前のシーズンの残りなので捨てる"""
    lines = [norm(l) for l in text.split('\n')]
    found = {}
    ctx, ctx_age, rental = None, 99, False
    def ok(t):
        return first - dt.timedelta(days=40) <= t <= first + dt.timedelta(days=160)
    def mk(p):
        day, hh, mm = p
        if hh is None: return None
        t = day + dt.timedelta(hours=hh, minutes=mm)
        if not ok(t):  # 年が書いていない日付は、放送開始の年の前後も試す
            for k in (-1, 1):
                try: t2 = day.replace(year=day.year + k) + dt.timedelta(hours=hh, minutes=mm)
                except ValueError: continue
                if ok(t2): return t2
            return None
        return t
    pending = []   # 日時より前に並んだサービス（日時があとに来る書き方）
    # 放送の日時（「放送直後」「地上波同時」「毎週木曜0:15」など、日付のない配信の基準）
    tv = []
    for l in lines:
        if re.search(r'配信', l) and not re.search(r'放送', l): continue
        p = parse_dt(l, first.year)
        if p and p[1] is not None:
            t0 = mk(p)
            if t0: tv.append(t0)
    base = min(tv) if tv else None
    WK = re.compile(r'毎週\s*([月火水木金土日])曜?日?\s*(深夜|夜|よる|午前|午後|あさ|朝)?\s*(\d{1,2})(?::|時)(\d{2}|半)?')
    def relative(l):
        if not base: return None
        if re.search(r'地上波同時|放送と同時|同時配信|放送同時', l): return base
        if re.search(r'放送直後|放送終了後|放送後|放送終了直後', l): return base + dt.timedelta(minutes=30)
        m = WK.search(l)
        if m and not DATE.search(l):
            hh = int(m.group(3)); mm = 30 if m.group(4) == '半' else int(m.group(4) or 0)
            if m.group(2) in ('夜', 'よる', '午後') and hh < 12: hh += 12
            if m.group(2) == '深夜' and hh < 6: hh += 24
            wd = WJ.index(m.group(1))
            day = base.replace(hour=0, minute=0)
            day += dt.timedelta(days=(wd - day.weekday()) % 7)
            t2 = day + dt.timedelta(hours=hh, minutes=mm)
            if t2 < base - dt.timedelta(hours=12): t2 += dt.timedelta(days=7)
            return t2
        return None
    for i, l in enumerate(lines):
        if not l: continue
        p = parse_dt(l, first.year)
        if p and p[1] is None and i + 1 < len(lines):      # 日付だけの行＋次の行に時刻
            nx = lines[i + 1]
            tm = TIME.search(nx)
            if tm and not DATE.search(nx) and len(nx) < 40:
                p = parse_dt(l + ' ' + nx, first.year)
        t = mk(p) if p else None
        if not t and re.search(r'配信', l): t = relative(l)
        sv = services_in(l)
        head = len(l) <= 30 and not sv and not t
        if head and re.search(r'配信|放送|on ?air|streaming|サイト|svod|avod|見放題', l, re.I):
            rental = bool(BAD.search(l)) or bool(re.search(r'無料|avod|fvod', l, re.I))
            # 「配信情報」「STREAMING」など節の頭では日時を捨てる。「見放題配信」「先行配信」などの小見出しでは引き継ぐ
            if re.search(r'情報|^streaming$|on ?air|^配信$|^放送$', l, re.I) and not re.search(r'見放題|先行|一般|最速|svod', l, re.I):
                ctx = None; pending = []
            continue
        if t:
            is_tv = bool(TVL.search(l)) and not sv
            if pending and not is_tv and not rental:
                for k in pending: found.setdefault(k, []).append(t)
            pending = []
            ctx, ctx_age = (None if is_tv else t), 0
            if BAD.search(l): ctx = None
        if sv and not rental and not BAD.search(l):
            if t: 
                for k in sv: found.setdefault(k, []).append(t)
            elif ctx and ctx_age <= 25:
                for k in sv: found.setdefault(k, []).append(ctx)
            else:
                pending += [k for k in sv if k not in pending]
        ctx_age += 1
    out = {}
    for k, ts in found.items():
        ts.sort()
        last = ts[-1]
        out[k] = min(t for t in ts if (last - t).days <= 60)   # いちばん新しいシーズンの中でいちばん早い日時
    return out
