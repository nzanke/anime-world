"""配信カレンダー用：fetch.py が取ってきた生データを読み、作品ごと・サービスごとの配信日時の一覧を作る
  python3 tools/haishin/build_schedule.py RAWDIR data/haishin/schedule.json

作品ごとに、各サービス（と地上波の局）の「何話がいつ見られるか」を並べる。
  e … [サービス, 日時(ISO・日本時間), 話数の通し番号, 話数が確かか(1/0)]
同じ通し番号どうしを比べれば、どのサービスが一番早いかがわかる。
  ・しょぼいカレンダー（地上波）… 実際の放送予定（話数つき）
  ・dアニメストア … 最新話の公開日時と話数から、毎週同じ曜日・時刻として先を出す
  ・U-NEXT・gamebiz … 配信開始日（第1話）から毎週として出す（休止は反映されない）
  ・DMM TV … 次回の配信日時から毎週として出す
"""
import json, os, re, sys, glob, hashlib, unicodedata, html, urllib.parse, datetime as dt
from difflib import SequenceMatcher

RAW, OUTF = sys.argv[1], sys.argv[2]
JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(JST)
LO, HI = NOW - dt.timedelta(days=10), NOW + dt.timedelta(days=36)
WEEK = dt.timedelta(days=7)
notes = []

def R(name):
    p = os.path.join(RAW, name)
    return open(p, encoding='utf-8', errors='replace').read() if os.path.exists(p) else None

# ------------------------------------------------------------ 作品名の照合
ROMAN = {'Ⅰ': '1', 'Ⅱ': '2', 'Ⅲ': '3', 'Ⅳ': '4', 'Ⅴ': '5', 'Ⅵ': '6'}
def season_split(t, want_explicit=False):
    """作品名を（もとの名前, 期）に分ける"""
    s = unicodedata.normalize('NFKC', html.unescape(t)).lower()
    for k, v in ROMAN.items(): s = s.replace(k.lower(), ' ' + v)
    s = re.sub(r'第([一二三四五六七八九])(期|シリーズ|シーズン)', lambda m: '第' + str('一二三四五六七八九'.index(m.group(1)) + 1) + m.group(2), s)
    s = re.sub(r'【[^】]*】|\[[^\]]*\]', ' ', s)
    m = re.match(r'^(?:tv|テレビ)?アニメ\s*[「『](.+?)[」』](.*)$', s)
    if m: s = m.group(1) + m.group(2)
    s = re.sub(r'^(?:tv|テレビ)アニメ\s*', '', s)
    s = re.sub(r'[（(]\s*(第\s*\d+\s*(?:期|シリーズ|シーズン)|season\s*\d+)\s*[)）]', r' \1 ', s)
    no, explicit = 1, False
    pats = [r'第\s*(\d+)\s*(?:期|シリーズ|シーズン)', r'season\s*(\d+)', r'(\d+)(?:st|nd|rd|th)\s*season', r'(\d+)期',
            r'\s(\d)\s*$', r'\s(i{2,3})\s*$']
    for p in pats:
        m = re.search(p, s)
        if m:
            v = m.group(1); no = {'ii': 2, 'iii': 3}.get(v) or int(v)
            s = s[:m.start()] + ' ' + s[m.end():]
            explicit = True
            break
    s = re.sub(r'第\s*\d+\s*クール|\d+(?:st|nd|rd|th)\s*cour|\(?第2部\)?|オンエア版|オンエアver\.?|地上波版', ' ', s)
    base = re.sub(r'[^0-9a-z\u3040-\u30ff\u3400-\u9fff\u30fc]', '', s)
    return (base, no, explicit) if want_explicit else (base, no)

class Works:
    def __init__(self):
        self.items = []   # {key, base, no, titles, src}
    def find(self, title):
        base, no = season_split(title)
        if not base: return None
        best, bs = None, 0
        for w in self.items:
            if w['no'] != no: continue
            if w['base'] == base: return w
            a, b = sorted((w['base'], base), key=len)
            if len(a) >= 5 and b.startswith(a) and len(a) / len(b) >= 0.45: sc = 0.9 + len(a) / len(b) / 100
            else:
                sc = SequenceMatcher(None, w['base'], base).ratio()
            if sc > bs: best, bs = w, sc
        return best if bs >= 0.86 else None
    def get(self, title, src):
        w = self.find(title)
        if not w:
            base, no, ex = season_split(title, True)
            if not base: return None
            w = {'base': base, 'no': no, 'ex': ex, 'titles': {}, 'ev': {}, 'info': {}}
            self.items.append(w)
        w['titles'].setdefault(src, title)
        return w

W = Works()

def add(w, svc, events, info=None, prio=1):
    """events: [(datetime, 話数 or None, 確か)]。同じサービスは prio の大きいほう（公式）を使う"""
    if not w or not events: return
    cur = w['ev'].get(svc)
    if cur and cur[0] > prio: return
    w['ev'][svc] = (prio, events)
    if info: w['info'][svc] = info

def weekly(anchor, ep, sure=True):
    """anchor（ep話）から毎週の配信を LO〜HI の範囲で並べる"""
    out = []
    k = (LO - anchor) // WEEK
    t = anchor + k * WEEK
    while t <= HI:
        n = (ep + (t - anchor) // WEEK) if ep is not None else None
        if t >= LO and (n is None or n >= 1): out.append((t, n, sure))
        t += WEEK
    return out

def iso(t): return t.astimezone(JST).strftime('%Y-%m-%dT%H:%M')

# ------------------------------------------------------------ しょぼいカレンダー（地上波）
SY_CH = {'NHK総合': 'NHK総合', 'NHK Eテレ': 'NHK Eテレ', '日本テレビ': '日本テレビ', 'TBS': 'TBS', 'フジテレビ': 'フジテレビ',
         'テレビ朝日': 'テレビ朝日', 'テレビ東京': 'テレビ東京', 'TOKYO MX': 'TOKYO MX'}
def tags(x, tag):
    return [dict(re.findall(r'<(\w+)>(.*?)</\1>', it, re.S)) for it in re.findall(rf'<{tag}\b.*?</{tag}>', x, re.S)]
ch, pg, ti = R('syoboi_ch.xml'), R('syoboi_prog.xml'), R('syoboi_titles.xml')
if ch and pg and ti:
    chname = {g['ChID']: g['ChName'] for g in tags(ch, 'ChItem')}
    titles = {g['TID']: g for g in tags(ti, 'TitleItem')}
    per = {}
    for g in tags(pg, 'ProgItem'):
        t = titles.get(g['TID'])
        if not t or t.get('Cat') not in ('1', '10', '7'): continue
        if int(g.get('Flag') or 0) & 8 or g.get('Deleted') == '1': continue      # 再放送
        c = chname.get(g['ChID'])
        if c not in SY_CH: continue
        st = dt.datetime.strptime(g['StTime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=JST) + dt.timedelta(seconds=int(g.get('StOffset') or 0))
        n = int(g['Count']) if (g.get('Count') or '').isdigit() else None
        per.setdefault((g['TID'], c), []).append((st, n, n is not None))
    for (tid, c), evs in per.items():
        title = html.unescape(titles[tid]['Title'])
        w = W.get(title, 'syoboi')
        evs.sort()
        add(w, 'tv:' + c, evs, {'url': f'https://cal.syoboi.jp/tid/{tid}'}, prio=3)
        if w: w.setdefault('tid', tid)
else:
    notes.append('しょぼいカレンダー：取得できず')

# ------------------------------------------------------------ dアニメストア
KN = {c: i for i, c in enumerate('〇一二三四五六七八九')}
def epnum(x):
    """「第7話」「#7」「第七話」「第二十三話」などから話数を読む"""
    x = unicodedata.normalize('NFKC', x or '').strip()
    m = re.match(r'^(?:第|#|episode\s*|ep\.?\s*)?(\d+)(?:話)?$', x, re.I)
    if m: return int(m.group(1))
    m = re.match(r'^第?([〇一二三四五六七八九十百]+)話$', x)
    if not m: return None
    v, cur = 0, 0
    for c in m.group(1):
        if c == '百': v += (cur or 1) * 100; cur = 0
        elif c == '十': v += (cur or 1) * 10; cur = 0
        else: cur = KN[c]
    return v + cur
WD = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
n_da = 0
seen = set()
for f in sorted(glob.glob(os.path.join(RAW, 'danime_*.json')), reverse=True):
    try: lst = json.load(open(f, encoding='utf-8'))['data']['workList']
    except Exception: notes.append(f'dアニメストア：{os.path.basename(f)} を読めず'); continue
    for x in lst:
        i = x['workInfo']
        if x['workId'] in seen: continue
        seen.add(x['workId'])
        lp = i.get('latestPartPublicDate')
        if not lp: continue
        t = dt.datetime.strptime(lp[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc).astimezone(JST)
        if t < NOW - dt.timedelta(days=16): continue        # 最新話が2週間以上前＝終わった（休止中）
        ep = epnum(i.get('endPartDispNumber'))
        if i.get('workWeek') not in WD: evs = [(t, ep, ep is not None)] if t >= LO else []
        else:
            if i.get('workTime') and re.match(r'\d\d:\d\d', i['workTime']):   # 決まった枠の時刻に合わせる
                hh, mm = map(int, i['workTime'].split(':'))
                t2 = t.replace(hour=hh, minute=mm)
                if abs((t2 - t).total_seconds()) < 6 * 3600: t = t2
            evs = weekly(t, ep, ep is not None)
        w = W.get(i['workTitle'], 'danime')
        add(w, 'danime', evs, {'url': i.get('link'), 'rental': i.get('vodType') == 'tvod'}, prio=2)
        n_da += 1

# ------------------------------------------------------------ U-NEXT
WJ = {'月': 0, '火': 1, '水': 2, '木': 3, '金': 4, '土': 5, '日': 6}
def md_date(mo, d):
    """月日だけの日付に年を補う（いまから見て近いほう）"""
    c = [dt.datetime(NOW.year + k, mo, d, tzinfo=JST) for k in (-1, 0, 1)]
    return min(c, key=lambda x: abs((x - NOW).days - 30))
n_un = 0
for f in sorted(glob.glob(os.path.join(RAW, 'unext_*.html'))):
    h = open(f, encoding='utf-8', errors='replace').read()
    day = None
    for m in re.finditer(r'<h2[^>]*>([^<]*)</h2>|<p class="[^"]*__lead">([^<]*)</p>\s*<h4[^>]*>([^<]*)</h4>', h):
        if m.group(1) is not None:
            hd = m.group(1).strip()
            day = WJ.get(hd[0]) if re.fullmatch(r'[月火水木金土日]曜日', hd) else None
            continue
        if day is None: continue
        lead, title = html.unescape(m.group(2)), html.unescape(m.group(3)).strip()
        mt = re.search(r'以降\s*(\d{1,2}):(\d{2})\s*更新', lead)
        if not mt: continue
        hh, mm = int(mt.group(1)), int(mt.group(2))
        ms = re.search(r'(\d{1,2})/(\d{1,2})\s*配信開始', lead)
        if ms:
            t = md_date(int(ms.group(1)), int(ms.group(2))).replace(hour=hh % 24, minute=mm) + dt.timedelta(days=hh // 24)
            if t.weekday() != day:   # 開始日の曜日と載っている曜日が違う（初回だけ別の日など）→ 載っている曜日の枠を使う
                t2 = t + dt.timedelta(days=(day - t.weekday()) % 7)
                evs = [(t, 1, True)] + [e for e in weekly(t2, 2, False)]
            else:
                evs = weekly(t, 1, False)
        else:
            base = (NOW - dt.timedelta(days=NOW.weekday() - day)).replace(hour=hh, minute=mm, second=0, microsecond=0)
            evs = weekly(base, None, False)
        w = W.get(title, 'unext')
        add(w, 'unext', [e for e in evs if e[1] is None or e[1] >= 1], {'url': 'https://video.unext.jp/', 'lead': lead.strip()}, prio=2)
        n_un += 1

# ------------------------------------------------------------ DMM TV
n_dm = 0
for f in sorted(glob.glob(os.path.join(RAW, 'dmm_*.json'))):
    d = json.load(open(f, encoding='utf-8'))
    for k, v in d.items():
        for e in (((v.get('data') or {}).get('calendarVideos') or {}).get('edges') or []):
            x = e['node']; nd = x.get('nextDeliveryEpisode') or {}
            if not nd.get('startDeliveryAt'): continue
            t = dt.datetime.strptime(nd['startDeliveryAt'][:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc).astimezone(JST)
            if t > NOW + dt.timedelta(days=9) and not nd.get('isBeforeDelivered'): continue   # 月1回などの作品は出さない
            ep = 1 if nd.get('isBeforeDelivered') else None
            tn, sn = x['titleName'], x.get('seasonName') or ''
            nm = sn if (season_split(tn)[0] and season_split(tn)[0] in season_split(sn)[0]) else (tn + ' ' + sn).strip()
            w = W.get(nm, 'dmm')
            add(w, 'dmm', weekly(t, ep, False) if ep else [e_ for e_ in weekly(t, None, False) if e_[0] >= t - WEEK],
                {'url': f'https://tv.dmm.com/vod/detail/?season={x["id"]}', 'rental': 'PREMIUM' not in (x.get('viewingTypes') or [])}, prio=2)
            n_dm += 1

# ------------------------------------------------------------ gamebiz（Netflix・Prime Video ほか）
SV = [('netflix', r'netflix'), ('prime', r'prime\s*video|amazon\s*プライム|プライムビデオ|amazonプライム'),
      ('danime', r'dアニメストア(?!\s*for)'), ('unext', r'u-next'), ('dmm', r'dmm\s*tv'), ('abema', r'abema'),
      ('hulu', r'hulu'), ('lemino', r'lemino'), ('fod', r'\bfod\b'), ('animetimes', r'アニメタイムズ'), ('disney', r'disney|ディズニープラス'),
      ('anihoudai', r'アニメ放題'), ('niconico', r'ニコニコ|niconico')]
def gb_time(s):
    """行の中の日時（第1話）を読む"""
    s = unicodedata.normalize('NFKC', s)
    m = re.search(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(?:\([^)]*\))?\s*(?:より|から)?\s*(?:毎週[月火水木金土日]曜(?:日)?)?\s*(\d{1,2})[:時](\d{2})?', s)
    if not m: return None
    y, mo, d, hh, mm = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5) or 0)
    base = dt.datetime(int(y), mo, d, tzinfo=JST) if y else md_date(mo, d)
    return base + dt.timedelta(hours=hh, minutes=mm)
n_gb = 0
for f in sorted(glob.glob(os.path.join(RAW, 'gamebiz_*.html'))):
    h = open(f, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'<h2[^>]*>■(.*?)</h2>(.*?)(?=<h2|\Z)', h, re.S):
        title = re.sub(r'<[^>]+>', '', html.unescape(m.group(1))).strip()
        body = html.unescape(m.group(2))
        i = body.find('配信情報')
        if i < 0: continue
        lines = [re.sub(r'<[^>]+>', '', l).strip(' ・\u3000') for l in re.split(r'<br\s*/?>|</p>', body[i:])]
        last = None
        found = {}
        for l in lines:
            if not l or '放送情報' in l: continue
            if '【' in l and '配信' not in l: break
            t = gb_time(l)
            low = unicodedata.normalize('NFKC', l).lower()
            svs = [k for k, p in SV if re.search(p, low)]
            if t: last = t
            if (t or last) and svs:
                for k in svs: found.setdefault(k, t or last)
        if not found: continue
        w = W.get(title, 'gamebiz')
        for k, t in found.items():
            add(w, k, weekly(t, 1, False), {'url': os.path.basename(f), 'src': 'gamebiz'}, prio=1)
        n_gb += 1

# ------------------------------------------------------------ ウィキペディアの配信表（Netflix・Prime Video・ABEMA ほか）
def wclean(x):
    x = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', x, flags=re.S)
    x = re.sub(r'\{\{nobr\|([^{}]*)\}\}', r'\1', x)
    x = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', x)
    x = re.sub(r'<br\s*/?>', '\n', x)
    return html.unescape(x)
def wrows(b):
    """{{放送期間}} の中を行・セルに分ける（{{ }}・[[ ]] の中の | は区切りにしない）"""
    rows, cur, cell, d, i = [], None, '', 0, 0
    while i < len(b):
        if b.startswith('{{', i) or b.startswith('[['  , i): d += 1; cell += b[i:i+2]; i += 2; continue
        if b.startswith('}}', i) or b.startswith(']]', i): d -= 1; cell += b[i:i+2]; i += 2; continue
        c = b[i]
        if c == '|' and d == 1:
            if i == 0 or b[i-1] == '\n' or (cur is None):
                if cur is not None and b[i-1] == '\n':
                    rows.append(cur); cur = []
                elif cur is None: cur = []
                else: cur.append(cell)
                cell = ''
            else:
                cur.append(cell); cell = ''
        else: cell += c
        i += 1
    if cur: rows.append(cur)
    return [[x.strip() for x in r] for r in rows]
WSV = [('netflix', r'^netflix'), ('prime', r'^(amazon\s*)?prime\s*video|^プライム・?ビデオ'), ('abema', r'^abema'), ('hulu', r'^hulu'),
       ('lemino', r'^lemino'), ('fod', r'^fod'), ('animetimes', r'^アニメタイムズ'), ('disney', r'^disney|^ディズニープラス'),
       ('anihoudai', r'^アニメ放題'), ('niconico', r'^ニコニコ'), ('danime', r'^dアニメストア'), ('unext', r'^u-next'), ('dmm', r'^dmm\s*tv')]
n_wk = 0
wk = R('wiki.json')
if wk:
    for tid, x in json.loads(wk).items():
        w = W.get(html.unescape(x['title']), 'syoboi')
        if not w: continue
        got = {}
        for b in x['blocks']:
            hdr, rows = None, wrows(b)
            for r in rows:
                cells = [wclean(c) for c in r]
                if hdr is None:
                    if any('配信サイト' in c for c in cells): hdr = cells
                    continue
                if len(cells) < len(hdr) - 1 or any(re.match(r'^\w+\s*=', c) for c in cells[:1]): continue
                col = lambda key: next((cells[k] for k, h in enumerate(hdr) if key in h and k < len(cells)), '')
                ds = unicodedata.normalize('NFKC', col('配信開始') or col('配信期間') or col('配信日'))
                ts = unicodedata.normalize('NFKC', col('配信時間') or col('更新'))
                md, mt = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', ds), re.search(r'([月火水木金土日])曜(?:日)?\s*(\d{1,2})[:時](\d{2})', ts)
                if not md or not mt: continue
                hh, mm = int(mt.group(2)), int(mt.group(3))
                wd = (WJ[mt.group(1)] + hh // 24) % 7
                t = dt.datetime(int(md.group(1)), int(md.group(2)), int(md.group(3)), hh % 24, mm, tzinfo=JST)
                if t.weekday() != wd: t += dt.timedelta(days=(wd - t.weekday()) % 7)
                for item in re.split(r'\n|・(?![^（(]*[)）])|、', col('配信サイト')):
                    item = re.sub(r'^[*\s]+|\{\{.*?\|', '', item).strip()
                    head = unicodedata.normalize('NFKC', re.split(r'[（(]', item)[0]).strip().lower()
                    for k, pat in WSV:
                        if head and re.search(pat, head):
                            if k not in got or t > got[k]: got[k] = t   # 期が複数あれば新しいほう
        for k, t in got.items():
            if t < NOW - dt.timedelta(days=200) or t > HI: continue
            add(w, k, weekly(t, 1, False), {'url': 'https://ja.wikipedia.org/wiki/' + urllib.parse.quote(x['page']), 'src': 'wiki'}, prio=1.5)
            w.setdefault('wiki', set()).add(k)
        if got: n_wk += 1

# ------------------------------------------------------------ 期の書いていない名前（dアニメストアの通し番号の作品など）を、話数と日時が合う○期にまとめる
def evlist(w): return [(t, n) for v in w['ev'].values() for t, n, _ in v[1] if n is not None]
for w in list(W.items):
    if w['ex'] or w not in W.items: continue
    best = None
    for o in W.items:
        if o is w or o['base'] != w['base'] or not o['ex']: continue
        hit = sum(1 for t, n in evlist(w) for t2, n2 in evlist(o) if abs((t - t2).total_seconds()) <= 3.6 * 86400 and abs(n - n2) <= 1)
        if hit and (not best or hit > best[0]): best = (hit, o)
    if best:
        o = best[1]
        for k, v in w['titles'].items(): o['titles'].setdefault(k, v)
        for svc, v in w['ev'].items():
            if svc not in o['ev'] or o['ev'][svc][0] < v[0]: o['ev'][svc] = v; o['info'][svc] = w['info'].get(svc)
        W.items.remove(w)

# ------------------------------------------------------------ 話数をそろえる（同じ話どうしを比べるため）
SRC_ORDER = lambda s: (0 if s.startswith('tv:') else 1 if s == 'danime' else 2)
works = []
for w in W.items:
    ev = {s: v[1] for s, v in w['ev'].items()}
    wsrc = {s for s, v in w['ev'].items() if v[0] == 1.5}
    if wsrc:
        span = [t for s, v in ev.items() if s not in wsrc for t, _, _ in v]
        for s in wsrc:
            ev[s] = [e for e in ev[s] if span and min(span) - WEEK - dt.timedelta(days=1) <= e[0] <= max(span) + WEEK]
            if not ev[s]: del ev[s]
    if not ev: continue
    # 話数が確かなサービス（地上波の番組表・dアニメストア）を全部まとめて基準にする
    # dアニメストアと番組表で数え方が違う作品（第0話の有無など）は、30時間以内に重なる回があれば番組表にそろえる
    tvref = sorted((t, n) for s in ev if s.startswith('tv:') for t, n, sure in ev[s] if sure and n is not None)
    if tvref:
        for s in list(ev):
            if s.startswith('tv:'): continue
            ds = sorted(min(((rn - n, abs((rt - t).total_seconds())) for rt, rn in tvref), key=lambda x: x[1])
                        for t, n, sure in ev[s] if sure and n is not None)
            ds = sorted(d for d, sec in ds if sec <= 30 * 3600)
            if ds and ds[len(ds) // 2]:
                k = ds[len(ds) // 2]
                ev[s] = [(t, n + k if (sure and n is not None) else n, sure) for t, n, sure in ev[s]]
    ref = sorted((t, n) for s in ev for t, n, sure in ev[s] if sure and n is not None)
    if not ref:
        for s in sorted(ev, key=SRC_ORDER):
            if any(e[1] is not None for e in ev[s]): ref = [(t, n) for t, n, _ in ev[s] if n is not None]; break
    def nearest(t):
        return min(ref, key=lambda r: abs((r[0] - t).total_seconds()))
    # 話数の数え方が基準と違うサービス（○期の第1話から数えるなど）は、ずれの分だけ足す。
    # 基準と1日以内に重なる回があれば、それで決める（同じ回とみなせる）
    shift = {}
    for s, evs in ev.items():
        close, near = [], []
        for t, n, sure in evs:
            if n is None or sure or not ref: continue
            rt, rn = nearest(t)
            dd = abs((rt - t).total_seconds())
            if dd <= 12 * 3600: close.append(rn - n)
            elif dd <= 3.6 * 86400: near.append(rn - n)
        for lst, need in ((close, 0), (near, 1)):
            if lst:
                lst.sort(); m = lst[len(lst) // 2]
                if abs(m) > need: shift[s] = m
                break
    # 話数のわからない回は、同じ日時に配信しているほかのサービスの話数を先に使う
    same_t = {}
    for s_, evs in ev.items():
        for t, n, sure in evs:
            if n is not None: same_t.setdefault(t, []).append(n + shift.get(s_, 0) if not sure else n)
    out = []
    for s, evs in ev.items():
        # このサービスの話数を、基準と比べて大きくずれていないか確かめてから使う（ずれていれば基準に合わせる）
        for t, n, sure in evs:
            if ref:
                rt, rn = nearest(t)
                near = abs((rt - t).total_seconds()) <= 3.6 * 86400
                if n is None and t in same_t:
                    l = sorted(same_t[t]); n = l[len(l) // 2]
                elif n is None:
                    # 配信がテレビより1日以上先に出ることはまれなので、直前（12時間後まで）の基準の回に当てる
                    before = [r for r in ref if r[0] <= t + dt.timedelta(hours=12)]
                    if before and t - before[-1][0] < WEEK: n = before[-1][1]
                    else: n = rn if near else rn + round((t - rt) / WEEK)
                elif not sure and s in shift:   # 数え方の違いは、そのサービスの全部の回に同じだけ足す
                    n = n + shift[s]
            out.append([s, iso(t), n, 1 if (n is not None) else 0])
    if not ref:   # どこにも話数がない作品：週ごとの通し番号で比べる
        base = min(dt.datetime.fromisoformat(e[1]) for e in out)
        for e in out:
            e[2] = int(((dt.datetime.fromisoformat(e[1]) - base).total_seconds() + 3.6 * 86400) // (7 * 86400)) + 1000
            e[3] = 0
    out.sort(key=lambda e: e[1])
    # 表示名：dアニメストア → U-NEXT → しょぼいカレンダー → DMM → gamebiz の順に使う
    name = next((w['titles'][k] for k in ('danime', 'unext', 'syoboi', 'dmm', 'gamebiz') if k in w['titles']), '')
    key = f'{w["base"]}#{w["no"]}'
    wid = hashlib.sha1(key.encode()).hexdigest()[:8]
    info = {s: v for s, v in w['info'].items() if v}
    works.append({'id': wid, 't': html.unescape(name).strip(), 'e': out, 'i': info, **({'tid': w['tid']} if w.get('tid') else {})})

# 取得に失敗した取り先は、前回の結果を引き継ぐ（その取り先の作品が丸ごと消えないように）
GROUP = {'danime': lambda s: s == 'danime', 'unext': lambda s: s == 'unext', 'dmm': lambda s: s == 'dmm',
         'syoboi': lambda s: s.startswith('tv:'), 'wiki': lambda s: False, 'gamebiz': lambda s: s in ('netflix', 'prime', 'abema', 'hulu', 'lemino', 'fod', 'animetimes', 'disney', 'anihoudai', 'niconico')}
counts = {'danime': n_da, 'unext': n_un, 'dmm': n_dm, 'gamebiz': n_gb, 'wiki': n_wk, 'syoboi': sum(1 for w in works if any(e[0].startswith('tv:') for e in w['e']))}
if os.path.exists(OUTF):
    prev = json.load(open(OUTF, encoding='utf-8'))
    byid = {w['id']: w for w in works}
    for g, f in GROUP.items():
        if counts.get(g): continue
        notes.append(f'{g}：取得できなかったので前回の結果を使用')
        for pw in prev['works']:
            old = [e for e in pw['e'] if f(e[0]) and e[1] >= iso(LO)]
            if not old: continue
            w = byid.get(pw['id'])
            if not w: w = {'id': pw['id'], 't': pw['t'], 'e': [], 'i': {}}; works.append(w); byid[w['id']] = w
            w['e'] = sorted(w['e'] + old, key=lambda e: e[1])
works = [w for w in works if w['e']]
works.sort(key=lambda w: season_split(w['t'])[0])
SERVICES = [['danime', 'dアニメストア'], ['unext', 'U-NEXT'], ['dmm', 'DMM TV'], ['netflix', 'Netflix'], ['prime', 'Prime Video'],
            ['abema', 'ABEMA'], ['hulu', 'Hulu'], ['lemino', 'Lemino'], ['fod', 'FOD'], ['animetimes', 'アニメタイムズ'],
            ['anihoudai', 'アニメ放題'], ['disney', 'ディズニープラス'], ['niconico', 'ニコニコ']] + [['tv:' + c, c] for c in SY_CH]
res = {'generated': NOW.strftime('%Y-%m-%dT%H:%M'), 'services': SERVICES, 'counts': counts, 'notes': notes, 'works': works}
os.makedirs(os.path.dirname(OUTF) or '.', exist_ok=True)
json.dump(res, open(OUTF, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'作品{len(works)}　', counts, notes)
