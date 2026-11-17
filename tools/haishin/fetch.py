"""配信カレンダー用：各サービスの今期アニメの配信予定を取ってきて raw/ に置く（GitHub Actions で毎日動かす）
  python3 tools/haishin/fetch.py RAWDIR
取り先
  dアニメストア … 今期一覧の裏のAPI（曜日・時刻・最新話の公開日時）
  U-NEXT … 今期アニメ一覧ページ（曜日ごとに「○/○配信開始 以降0:30更新」）
  DMM TV … 配信カレンダーの裏のGraphQL（次回配信日時）
  gamebiz … 今期の「放送・配信情報一覧」記事（Netflix・Prime Video など）
  しょぼいカレンダー … 地上波キー局・TOKYO MX の放送予定
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse, re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
JST = dt.timezone(dt.timedelta(hours=9))
OUT = sys.argv[1] if len(sys.argv) > 1 else 'raw'
os.makedirs(OUT, exist_ok=True)
log = []

def get(url, data=None, headers=None, tries=2, timeout=40):
    h = {'User-Agent': UA, 'Accept-Language': 'ja'}
    h.update(headers or {})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    import gzip; b = gzip.decompress(b)
                return b
        except Exception as e:
            err = e
            time.sleep(3)
    raise err

def save(name, url, **kw):
    try:
        b = get(url, **kw)
        open(os.path.join(OUT, name), 'wb').write(b)
        log.append(f'{name}\t{len(b)}')
        return b
    except Exception as e:
        log.append(f'{name}\tFAIL {e}')
        return None

now = dt.datetime.now(JST)
def cour_of(d):  # (年, 1〜4)  1=冬(1-3月) 2=春 3=夏 4=秋
    return d.year, (d.month - 1) // 3 + 1
cy, cq = cour_of(now)
cours = [(cy, cq)]
py, pq = (cy, cq - 1) if cq > 1 else (cy - 1, 4)
cours.insert(0, (py, pq))                      # 前のクールから続く作品（2クール目など）
ny, nq = (cy, cq + 1) if cq < 4 else (cy + 1, 1)
if (dt.datetime(ny, nq * 3 - 2, 1, tzinfo=JST) - now).days <= 60:   # 次のクールまで2か月を切ったら、次のクールの新番組も
    cours.append((ny, nq))
SEASON = {1: 'winter', 2: 'spring', 3: 'summer', 4: 'autumn'}

# dアニメストア
for y, q in cours:
    save(f'danime_{y}{q:02d}.json', f'https://animestore.docomo.ne.jp/animestore/rest/WS000118?cours={y}{q:02d}&includeOthersFlag=1&tvProgramFlag=1&vodTypeList=svod_tvod')

# U-NEXT（今期一覧はクールの名前だけのURL。前のクールの作品も載る）
for y, q in cours[1:]:
    save(f'unext_{y}{q:02d}.html', f'https://www.video.unext.jp/season_anime/{SEASON[q]}')

# DMM TV
DMM_Q = '''query FetchCalendarVideos($device: Device!, $cour: Cour!, $dayOfWeek: DayOfWeek!, $first: Int = 100) {
  calendarVideos: searchVideos(device: $device, deliveryCour: {cour: $cour, dayOfWeek: $dayOfWeek}, isPersonalize: false, sort: DELIVERY_TIME_ASC, first: $first) {
    edges { node { id titleName seasonName seasonType viewingTypes customTag isExclusive nextDeliveryEpisode { isBeforeDelivered startDeliveryAt } } }
  }
}'''
DMM_COUR = {1: 'WINTER', 2: 'SPRING', 3: 'SUMMER', 4: 'FALL'}
for y, q in cours[1:]:
    res = {}
    for d in ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'):
        body = json.dumps({'operationName': 'FetchCalendarVideos', 'query': DMM_Q,
                           'variables': {'device': 'BROWSER', 'cour': DMM_COUR[q], 'dayOfWeek': d, 'first': 100}}).encode()
        try:
            b = get('https://api.tv.dmm.com/graphql', data=body, headers={'Content-Type': 'application/json', 'Origin': 'https://tv.dmm.com', 'Referer': 'https://tv.dmm.com/'})
            res[d] = json.loads(b)
        except Exception as e:
            res[d] = {'error': str(e)}
    json.dump(res, open(os.path.join(OUT, f'dmm_{y}{q:02d}.json'), 'w'), ensure_ascii=False)
    log.append(f'dmm_{y}{q:02d}.json\t' + ' '.join(f'{k[:3]}:{len(((v.get("data") or {}).get("calendarVideos") or {}).get("edges") or [])}' if 'data' in v else f'{k[:3]}:ERR' for k, v in res.items()))

# gamebiz の「○年○アニメの放送・配信情報一覧」記事（記事番号は sources.json。なければ新着から探す）
SRC = json.load(open(os.path.join(os.path.dirname(__file__), 'sources.json'), encoding='utf-8'))
for i, u in enumerate(SRC.get('gamebiz', [])):
    save(f'gamebiz_{i}.html', u, tries=3, timeout=90)

# しょぼいカレンダー（地上波キー局・TOKYO MX）
ch = save('syoboi_ch.xml', 'https://cal.syoboi.jp/db.php?Command=ChLookup')
want = ['NHK総合', 'NHK Eテレ', '日本テレビ', 'TBS', 'フジテレビ', 'テレビ朝日', 'テレビ東京', 'TOKYO MX']
ids = []
if ch:
    for it in re.findall(r'<ChItem\b.*?</ChItem>', ch.decode('utf-8'), re.S):
        g = dict(re.findall(r'<(\w+)>(.*?)</\1>', it, re.S))
        if g.get('ChName') in want: ids.append(g['ChID'])
a = (now - dt.timedelta(days=8)).strftime('%Y%m%d_000000'); b_ = (now + dt.timedelta(days=30)).strftime('%Y%m%d_000000')
pg = save('syoboi_prog.xml', f'https://cal.syoboi.jp/db.php?Command=ProgLookup&ChID={",".join(ids)}&Range={a}-{b_}')
if pg:
    tids = {m for m in re.findall(r'<TID>(\d+)</TID>', pg.decode('utf-8'))}
    # ウィキペディアの配信表を引くため、地上波以外（AT-X・BSなど）で放送中の作品も拾う
    a2, b2 = (now - dt.timedelta(days=7)).strftime('%Y%m%d_000000'), (now + dt.timedelta(days=7)).strftime('%Y%m%d_000000')
    try: tids |= set(re.findall(r'<TID>(\d+)</TID>', get(f'https://cal.syoboi.jp/db.php?Command=ProgLookup&Range={a2}-{b2}').decode('utf-8')))
    except Exception: pass
    tids = sorted(tids, key=int)
    # 今期〜次のクールに始まる作品（番組表にまだ入っていない新番組も）
    first = {(y, (q - 1) * 3 + m) for y, q in cours[1:] for m in (1, 2, 3)}
    try:
        lu = (now - dt.timedelta(days=150)).strftime('%Y%m%d_000000')
        allt = get(f'https://cal.syoboi.jp/db.php?Command=TitleLookup&TID=*&LastUpdate={lu}-', timeout=90).decode('utf-8')
        new_tids = [g['TID'] for g in (dict(re.findall(r'<(\w+)>(.*?)</\1>', it, re.S)) for it in re.findall(r'<TitleItem\b.*?</TitleItem>', allt, re.S))
                    if g.get('Cat') in ('1', '10') and (int(g.get('FirstYear') or 0), int(g.get('FirstMonth') or 0)) in first]
        tids = sorted(set(tids) | set(new_tids), key=int)
        log.append(f'syoboi 今期・次期に始まる作品\t{len(new_tids)}')
    except Exception as e:
        log.append(f'syoboi 新番組\tFAIL {e}')
    parts = []
    for i in range(0, len(tids), 50):
        b = get(f'https://cal.syoboi.jp/db.php?Command=TitleLookup&TID={",".join(tids[i:i+50])}')
        parts.append(b.decode('utf-8'))
        time.sleep(1)
    open(os.path.join(OUT, 'syoboi_titles.xml'), 'w', encoding='utf-8').write('\n'.join(parts))
    log.append(f'syoboi_titles.xml\t{len(tids)}作品')

    # ウィキペディアの作品記事の「配信開始日｜配信時間｜配信サイト」の表（Netflix・Prime Video など）
    WUA = {'User-Agent': 'anime-haishin-calendar/1.0 (https://nzanke.github.io/anime-world/haishin.html; X @bg75gf)'}
    def wraw(name):
        u = 'https://ja.wikipedia.org/w/index.php?' + urllib.parse.urlencode({'title': name, 'action': 'raw'})
        t = get(u, headers=WUA, tries=1, timeout=30).decode('utf-8', 'replace')
        m = re.match(r'\s*#(?:REDIRECT|転送)\s*\[\[([^\]#|]+)', t, re.I)
        return wraw(m.group(1)) if m else t
    wiki, ok = {}, 0
    for it in re.findall(r'<TitleItem\b.*?</TitleItem>', '\n'.join(parts), re.S):
        g = dict(re.findall(r'<(\w+)>(.*?)</\1>', it, re.S))
        if g.get('Cat') not in ('1', '10', '7'): continue
        kw = re.findall(r'wikipedia:([^,]+)', g.get('Keywords') or '')
        name = (kw[0] if kw else g['Title']).strip()
        try: t = wraw(name)
        except Exception: continue
        blocks = []
        for m in re.finditer(r'\{\{放送期間', t):   # 入れ子の {{ }} を数えて、ブロックの終わりまで取る
            d, i = 0, m.start()
            while i < len(t):
                if t.startswith('{{', i): d += 1; i += 2
                elif t.startswith('}}', i):
                    d -= 1; i += 2
                    if d == 0: break
                else: i += 1
            b = t[m.start():i]
            if re.search(r'media\s*=\s*インターネット', b) or '配信サイト' in b: blocks.append(b)
        if blocks: wiki[g['TID']] = {'title': g['Title'], 'page': name, 'blocks': blocks}; ok += 1
        time.sleep(0.3)
    json.dump(wiki, open(os.path.join(OUT, 'wiki.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    log.append(f'wiki.json\t配信表のある記事{ok}')

    # 公式サイトの放送・配信情報のページ（いちばん早く発表される取り先）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import official
    urls = official_urls = official.official_urls('\n'.join(parts))
    off = official.fetch_all(urls)
    json.dump(off, open(os.path.join(OUT, 'official.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    log.append(f'official.json\t公式サイト{len(urls)}・取得できた{sum(1 for v in off.values() if v["pages"])}')

open(os.path.join(OUT, '_log.txt'), 'w', encoding='utf-8').write(now.isoformat() + '\n' + '\n'.join(log) + '\n')
print('\n'.join(log))
