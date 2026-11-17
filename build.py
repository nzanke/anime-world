"""アニメ評論サイトを組み立てる（Python の標準ライブラリだけで動く）。

  python3 build.py            → _site/ にサイト一式を書き出す

読むもの
  data/works.tsv ほか      基礎データ（anime-database の tools/hyoron/export.py で書き出したもの）
  content/site.txt         サイト名・説明など
  content/about.md         「このサイトについて」の本文
  content/links.csv        関連記事のリンク（評論・インタビュー・記事。自分の評論も含む）
"""
import urllib.parse
import csv, gzip, hashlib, html, json, os, re, shutil, sys
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '_site')
D = lambda *p: os.path.join(ROOT, *p)
esc = html.escape
warnings = []

# ---------------------------------------------------------------- 設定
def read_conf():
    conf = {'サイト名': 'アニメインタビュー検索', '説明': '', '筆者': ''}
    if os.path.exists(D('content', 'site.txt')):
        for line in open(D('content', 'site.txt'), encoding='utf-8-sig'):
            if ':' in line and not line.startswith('#'):
                k, v = line.split(':', 1)
                conf[k.strip()] = v.strip()
    return conf

CONF = read_conf()
FETCHED = ''
if os.path.exists(D('data', 'meta.txt')):
    for line in open(D('data', 'meta.txt'), encoding='utf-8'):
        k, _, v = line.rstrip('\n').partition('\t')
        if k == '取得日':
            FETCHED = v

# ---------------------------------------------------------------- 基礎データ
def tsv(name):
    path = D('data', name)
    f = gzip.open(path, 'rt', encoding='utf-8') if name.endswith('.gz') else open(path, encoding='utf-8')
    with f:
        yield from csv.DictReader(f, delimiter='\t')

works = {r['work_id']: r for r in tsv('works.tsv')}
order = sorted(works, key=lambda w: (works[w]['start_date'] or '9999', w))
by_title = defaultdict(list)
for w in order:
    by_title[works[w]['title']].append(w)

def year_of(w):
    s = works[w]['start_date']
    return int(s[:4]) if re.match(r'\d{4}', s or '') else None

def split_studio(s):
    out = []
    for part in re.split(r'[、／→⇒]', s or ''):
        part = re.sub(r'[（(][^）)]*[）)]', '', part).strip()
        part = re.sub(r'\s+', ' ', part)
        if part and part not in out and part not in ('-', '－', '―', '不明', '?'):
            out.append(part)
    return out

# 制作会社の統合（content/制作会社の統合.csv：元の表記 → 統合先。連鎖もたどる）
S_MERGE, S_KIND = {}, {}
if os.path.exists(D('content', '制作会社の統合.csv')):
    with open(D('content', '制作会社の統合.csv'), encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('元の表記') and r.get('統合先'):
                S_MERGE[r['元の表記'].strip()] = r['統合先'].strip()
                S_KIND[r['元の表記'].strip()] = (r.get('種類') or '').strip()

def canon(s):
    seen = set()
    while s in S_MERGE and s not in seen:
        seen.add(s); s = S_MERGE[s]
    return s

studios_of = {w: split_studio(works[w]['studio']) for w in works}   # 記事の表記
studio_works = defaultdict(list)                                     # 統合先 → 番組
studio_names = defaultdict(lambda: defaultdict(set))                 # 統合先 → 番組 → 当時の表記（表記ゆれ以外）
studio_alias = defaultdict(set)                                      # 統合先 → 旧名・別の表記
for w in order:
    for s in studios_of[w]:
        c = canon(s)
        if w not in studio_works[c]:
            studio_works[c].append(w)
        if s != c:
            studio_alias[c].add(s)
            if S_KIND.get(s) != '表記ゆれ':
                studio_names[c][w].add(s)

COMPANY_KUBUN = {'制作会社・製作', '宣伝・配給・放送', '制作協力（参考）'}
staff = defaultdict(list)                    # work → [(role_raw, role, kubun, person, credited_as, note)]
for r in tsv('staff.tsv.gz'):
    staff[r['work_id']].append(r)

EP_ROLES = ['脚本', '絵コンテ', '演出', '総作画監督', '作画監督']
episodes = defaultdict(list)
for r in tsv('episodes.tsv.gz'):
    episodes[r['work_id']].append(r)

def ep_names(cell):
    """「名前=名義」を (名前, 名義) に分ける"""
    for x in cell.split('、') if cell else []:
        p, _, cred = x.partition('=')
        yield p, cred

# 人ごとの仕事
p_staff = defaultdict(lambda: defaultdict(list))     # person → work → [役職]
p_eps = defaultdict(lambda: defaultdict(Counter))    # person → work → Counter(役職→話数)
p_cred = defaultdict(lambda: defaultdict(set))       # person → work → {名義}
p_roles = defaultdict(lambda: defaultdict(set))      # person → 正規化した役職 → {work}
for w, rows in staff.items():
    for r in rows:
        if r['kubun'] in COMPANY_KUBUN:
            continue
        p = r['person']
        if r['role_raw'] not in p_staff[p][w]:
            p_staff[p][w].append(r['role_raw'])
        p_roles[p][r['role']].add(w)
        if r['credited_as'] and r['credited_as'] != p:
            p_cred[p][w].add(r['credited_as'])
for w, rows in episodes.items():
    for r in rows:
        for role in EP_ROLES:
            for p, cred in ep_names(r[role]):
                p_eps[p][w][role] += 1
                p_roles[p]['各話:' + role].add(w)
                if cred:
                    p_cred[p][w].add(cred)

MAIN_ROLES = {'監督', '総監督', 'シリーズ構成', 'キャラクターデザイン'}
people = {}
for p in set(p_staff) | set(p_eps):
    ws = set(p_staff[p]) | set(p_eps[p])
    if len(ws) >= 2 or any(r in MAIN_ROLES for r in p_roles[p]):
        people[p] = ws

def slug(prefix, name):
    return prefix + hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]

P_URL = {p: f'p/{slug("", p)}.html' for p in people}
S_URL = {s: f's/{slug("", s)}.html' for s in studio_works}

# ---------------------------------------------------------------- 関連記事
def find_work(wid, title, where):
    if wid and wid in works:
        return wid
    if wid:
        warnings.append(f'{where}: 番組ID「{wid}」が見つかりません')
        return None
    cands = by_title.get(title, [])
    if len(cands) == 1:
        return cands[0]
    warnings.append(f'{where}: 番組名「{title}」' + ('が見つかりません' if not cands else f'は候補が複数あります（{"・".join(cands)}）。番組IDを書いてください'))
    return None

links = defaultdict(list)
all_links = []
lpath = D('content', 'links.csv')
if os.path.exists(lpath):
    with open(lpath, encoding='utf-8-sig', newline='') as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            r = {k.strip(): (v or '').strip() for k, v in r.items() if k}
            if not any(r.values()):
                continue
            if re.match(r'^f\d+$', r.get('番組ID', '')):   # 映画の作品番号（data/films.tsv）：検索のタグにだけ使う（映画には番組のページがない）
                r['work'] = r['番組ID']; all_links.append(r); continue
            w = find_work(r.get('番組ID', ''), r.get('番組名', ''), f'links.csv {i}行目') if (r.get('番組ID') or r.get('番組名')) else ''
            r['work'] = w
            if w: links[w].append(r)
            all_links.append(r)   # 番組が決まっていない記事（URL だけで足したもの）も索引には載せる
KIND_ORDER = ['ブログ', 'ネットメディア', '雑誌', '書籍', '新聞', 'ウェブサイト', 'その他']   # 媒体の種類
kind = lambda r: r.get('分類') or r.get('種別') or 'その他'
for w in links:
    links[w].sort(key=lambda r: (KIND_ORDER.index(kind(r)) if kind(r) in KIND_ORDER else 99, r.get('日付', '')))

# ---------------------------------------------------------------- 本文の書式（簡単なマークダウン）
def inline(s, r):
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = re.sub(r'(?<!\[)\[([^\[\]]+)\]\(([\w][\w./-]*)\)', lambda m: f'<a href="{r}{m.group(2)}">{m.group(1)}</a>', s)   # サイト内のファイルへのリンク（credits/films/articles.tsv など）
    def internal(m):
        key = html.unescape(m.group(1))
        w = key if key in works else (by_title[key][0] if len(by_title.get(key, [])) == 1 else None)
        if w:
            return f'<a href="{r}w/{w}.html">{esc(works[w]["title"])}</a>'
        if key in P_URL:
            return f'<a href="{r}{P_URL[key]}">{esc(key)}</a>'
        warnings.append(f'本文のリンク [[{key}]] が見つかりません')
        return esc(key)
    s = re.sub(r'\[\[([^\]]+)\]\]', internal, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    return s

def render_body(text, r, hbase=4):
    """1行＝1段落。## 小見出し、> 引用、- 箇条書き、[文字](URL)、[[番組名]]"""
    out, lst, quote = [], [], []
    def flush():
        if lst:
            out.append('<ul>' + ''.join(f'<li>{x}</li>' for x in lst) + '</ul>'); lst.clear()
        if quote:
            out.append('<blockquote>' + ''.join(f'<p>{x}</p>' for x in quote) + '</blockquote>'); quote.clear()
    for line in text.split('\n'):
        t = line.strip()
        if not t:
            flush(); continue
        m = re.match(r'(#{2,4})\s+(.*)', t)
        if m:
            flush(); lv = min(6, hbase + len(m.group(1)) - 2)
            t2, hid = m.group(2), ''
            mm = re.match(r'(.*?)\s*\{#([\w-]+)\}$', t2)
            if mm:
                t2, hid = mm.group(1), f' id="{mm.group(2)}"'
            out.append(f'<h{lv}{hid}>{inline(t2, r)}</h{lv}>'); continue
        if t.startswith('>'):
            if lst: flush()
            quote.append(inline(t.lstrip('>').strip(), r)); continue
        if re.match(r'[-・]\s', t):
            if quote: flush()
            lst.append(inline(t[2:].strip(), r)); continue
        flush()
        out.append(f'<p>{inline(t, r)}</p>')
    flush()
    return '\n'.join(out)

# ---------------------------------------------------------------- ページの枠
NEWS_SITE = 'https://nzanke.github.io/anime-news/'   # 制作決定ニュースは独立したサイトに移した（2026-11）
NAV = [('index.html', 'インタビュー'), ('column.html', 'レビュー'), (NEWS_SITE, '制作決定'), ('tools.html', 'ツール集')]   # 「このサイトについて」は各ページの「？」の箱へまとめた
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap">'
         # 半角の数字・英字・記号は BIZ UDゴシック（「!」〜「~」だけを読み込む）
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDGothic:wght@400;700&display=swap&text=' + urllib.parse.quote(''.join(map(chr, range(33, 127))), safe='') + '">')
LEADS = {}   # ページごとの説明（「？」の箱の先頭に出す）。about.js に書き出す
ABOUT_HTML = ('<details class="about"><summary><span class="qi">?</span>このサイトについて</summary>'
              '<div class="aboutbox" id="aboutbox"></div></details>')

# 書き換えたら古いものがブラウザに残らないよう、ファイルの中身から番号を付ける
CSS_V = hashlib.sha1(open(D('static', 'style.css'), 'rb').read()).hexdigest()[:8]
JS_V = hashlib.sha1(open(D('static', 'add.js'), 'rb').read()).hexdigest()[:8]
ABOUT_V = hashlib.sha1(open(D('content', 'about.md'), 'rb').read() + open(__file__, 'rb').read()).hexdigest()[:8]
SEARCH_V = hashlib.sha1(open(D('static', 'search.js'), 'rb').read()).hexdigest()[:8]

def page(path, title, body, crumbs=(), current=None, desc='', script='', head=''):
    depth = path.count('/')
    r = '../' * depth
    site = CONF['サイト名']
    nav = ''.join(f'<a href="{"" if u.startswith("http") else r}{u}"{" class=on" if u == current else ""}>{esc(t)}</a>' for u, t in NAV)
    cr = ''
    if crumbs:
        cr = '<nav class="crumbs">' + ' › '.join(
            [f'<a href="{r}index.html">トップ</a>'] + [f'<a href="{r}{u}">{esc(t)}</a>' if u else esc(t) for u, t in crumbs]) + '</nav>'
    m = re.search(r'<p class="lead">(.*?)</p>', body, re.S)
    LEADS[path] = (title if title != site else 'インタビュー検索', re.sub(r'<span class="ic".*?</span>', '', m.group(1)).strip() if m else '')
    body = re.sub(r'<h1>.*?</h1>', '', body, count=1, flags=re.S)
    body = re.sub(r'\s*<p class="lead">.*?</p>', '', body, count=1, flags=re.S)
    cr = ''
    if '<p class="count" id="count"></p>' in body:
        body = body.replace('<p class="count" id="count"></p>', '<div class="cbar"><p class="count" id="count"></p>' + ABOUT_HTML + '</div>', 1)
    elif '<div class="outbar"><span class="count" id="count">' in body:
        body = re.sub(r'<div class="outbar">(<span class="count" id="count">.*?</span>)', lambda m_: '<div class="outbar cbar">' + m_.group(1) + ABOUT_HTML, body, count=1)
    else:
        body = '<div class="cbar"><p class="count"></p>' + ABOUT_HTML + '</div>' + body
    full = f'{esc(title)}｜{esc(site)}' if title != site else esc(site)
    src = f'（{FETCHED}取得）' if FETCHED else ''
    doc = f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full}</title>{f'<meta name="description" content="{esc(desc)}">' if desc else ''}
{FONTS}<link rel="stylesheet" href="{r}style.css?v={CSS_V}">{head}</head>
<body><div class="wrap">
<nav class="nav" aria-label="サイト内">{nav}</nav>
<h1 class="site"><a href="{r}index.html">{esc(site)}</a></h1>
<main>{cr}
{body.replace('{R}', r)}
</main>
<footer class="site"><p>番組・スタッフ・各話の基礎データは日本語版ウィキペディアの各記事{src}をもとに加工したもので、<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a> で提供します（<a href="{r}about.html#data">出典と加工について</a>）。</p>
<p>掲載内容の削除のご要望などは、X（<a href="https://x.com/bg75gf">@bg75gf</a>）までご連絡ください。</p></footer>
</div><script src="{r}about.js?v={ABOUT_V}" data-page="{esc(path)}"></script>{script}<script data-goatcounter="https://nzanke.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script></body></html>
'''
    dest = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as f:
        f.write(doc)

def plink(p, r='{R}', cred=None):
    label = esc(p) + (f'<span class="cred">（{esc(cred)}名義）</span>' if cred else '')
    return f'<a href="{r}{P_URL[p]}">{label}</a>' if p in P_URL else label

def slink(s, r='{R}'):
    c = canon(s)
    return f'<a href="{r}{S_URL[c]}">{esc(s)}</a>' if c in S_URL else esc(s)

def wlink(w, r='{R}'):
    return f'<a href="{r}w/{w}.html">{esc(works[w]["title"])}</a>'

def fmt_date(s):
    """日付は 2006-09-30 の形（月まで・年までのものはそのまま）"""
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s or '')
    if m:
        return m.group(0)
    m = re.match(r'(\d{4})-(\d{2})', s or '')
    return m.group(0) if m else (s or '')

def period(w):
    a, b = works[w]['start_date'], works[w]['end_date']
    if not a:
        return '不明'
    return fmt_date(a) + ('' if b == a else ' ～ ' + (fmt_date(b) if b else ''))

def marks(w):
    m = ''
    if links.get(w):
        m += f'<span class="mk2" title="関連記事">記事{len(links[w])}</span>'
    return m

def roles_of(w, names):
    seen = []
    for r in staff.get(w, []):
        if r['role'] in names and r['person'] not in seen:
            seen.append(r['person'])
    return seen

def ep_names_of(w):
    """番組の各話の表示名と並び順 → [(話数の表示, サブタイトル)]"""
    eps = episodes.get(w, [])
    segs = len({e['segment'] for e in eps}) > 1
    return [(((e['segment'] + ' ') if segs and e['segment'] else '') + e['episode'], e['subtitle']) for e in eps]

def ep_no(l):
    return (l.get('話数') or '').lstrip('#＃ ').strip()

def ep_index(w, l):
    names = [n for n, _ in ep_names_of(w)]
    return names.index(ep_no(l)) if ep_no(l) in names else 99999

def ep_label(w, l):
    """#話数「サブタイトル」（サブタイトルが空なら各話リストから補う）"""
    sub = l.get('サブタイトル') or dict(ep_names_of(w)).get(ep_no(l), '')
    return '#' + esc(ep_no(l)) + (f'「{esc(sub)}」' if sub else '')

def link_line(l, kind_label=False):
    """日付／題名／筆者／「媒体」（ないものは省く）"""
    t = esc(l.get('題名') or l.get('URL'))
    if l.get('URL'):
        t = f'<a href="{esc(l["URL"])}">{t}</a>'
    d = esc(l.get('日付', ''))
    parts = [f'<span class="ld">{d}</span>' if d else '', t, esc(l.get('筆者', '')), f'「{esc(l["媒体"])}」' if l.get('媒体') else '']
    if kind_label:
        parts.append(f'（{"#" + esc(ep_no(l)) + "・" if l.get("話数") else ""}{esc(kind(l))}）')
    return '／'.join(x for x in parts if x)

def table(head, rows, cls=''):
    h = ''.join(f'<th>{x}</th>' for x in head)
    b = ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

FOLD_AT = 30   # これより多い項目は閉じた状態で出す

def fold(title, content, n, hid='', unit='件', limit=FOLD_AT, level=2):
    """見出しを押すと開閉する。項目が limit 以下なら開いた状態"""
    op = '' if n > limit else ' open'
    i = f' id="{hid}"' if hid else ''
    return (f'<details class="fold"{op}{i}><summary><h{level}>{title}<span class="cnt">{n}{unit}</span></h{level}></summary>'
            f'{content}</details>')

def by_decade(ws, make_rows, head):
    """番組の一覧を年代ごとの開閉にまとめる（全体が少なければ1つの表）"""
    if len(ws) <= FOLD_AT:
        return table(head, make_rows(ws), 'list')
    g = defaultdict(list)
    for w in ws:
        y = year_of(w)
        g[decade(y) if y else '年不明'].append(w)
    return ''.join(fold(d, table(head, make_rows(v), 'list'), len(v), unit='番組', limit=15, level=3) for d, v in g.items())

def decade(y):
    return f'{y // 10 * 10}年代'

# ---------------------------------------------------------------- 出力
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
shutil.copy(D('static', 'style.css'), OUT)
shutil.copy(D('static', 'search.js'), OUT)
open(os.path.join(OUT, '.nojekyll'), 'w').close()

# ---------------------------------------------------------------- 記事の索引（自動で集めた記事＋手で足した記事）
auto = json.load(open(D('data', 'articles.json'), encoding='utf-8')) if os.path.exists(D('data', 'articles.json')) else []
seen = {e['u'] for e in auto}
for l in all_links:
    if l.get('URL') in seen:
        continue
    e = {'u': l.get('URL', ''), 't': l.get('題名') or l.get('URL', ''), 'd': l.get('日付', ''), 's': l.get('媒体') or kind(l),
         'k': l.get('種類') or 'インタビュー', 'w': [l['work']] if l['work'] else [], 'p': []}
    if l.get('筆者'): e['a'] = l['筆者']
    auto.append(e)
# レビュー検索（column.html）から外す記事：content/コラム除外.txt の URL（インタビューはそのまま）
_cx = D('content', 'コラム除外.txt')
COLUMN_EXCLUDE = {l.strip() for l in open(_cx, encoding='utf-8') if l.strip() and not l.startswith('#')} if os.path.exists(_cx) else set()
auto = [e for e in auto if not ((e.get('k') or 'インタビュー') != 'インタビュー' and e.get('u') in COLUMN_EXCLUDE)]
auto.sort(key=lambda e: e.get('d') or '0000', reverse=True)
# 手で直したタグ（content/tag_edits.json。検索ページの鉛筆ボタンから保存）：{URL: {"w": [作品番号], "p": [人の名前]}}
# 一覧に出すタグをこの内容に置き換える。外したタグは「本文まで探す」の範囲からも外す
_te = D('content', 'tag_edits.json')
TAG_EDITS = json.load(open(_te, encoding='utf-8')) if os.path.exists(_te) else {}
for e in auto:
    ov = TAG_EDITS.get(e.get('u'))
    if not ov: continue
    shown_w = e.get('w', [])[:e['wt'] if e.get('wt') is not None else 6]
    shown_p = [p for p in e.get('p', []) if p and p in e.get('t', '')]
    gone_w = set(shown_w) - set(ov.get('w', [])); gone_p = set(shown_p) - set(ov.get('p', []))
    e['w'] = ov.get('w', []) + [w for w in e.get('w', []) if w not in ov.get('w', []) and w not in gone_w]
    e['wt'] = len(ov.get('w', []))
    e['p'] = ov.get('p', []) + [p for p in e.get('p', []) if p not in ov.get('p', []) and p not in gone_p]
    e['pt'] = ov.get('p', []); e['ed'] = 1
    if ov.get('x'): e['x'] = ov['x']   # 新しく作ったタグ（作品・人以外の言葉）
used_w = {w for e in auto for w in e.get('w', [])}
films = {}   # 映画：記事に出てくるもの（anime-database の tag.py が書き出す）と、映画台帳の全作品（タグの候補用）
for fn in ('films_all.tsv', 'films.tsv'):
    if os.path.exists(D('data', fn)):
        for r in csv.DictReader(open(D('data', fn), encoding='utf-8'), delimiter='\t'): films[r['work_id']] = [r['title'], r['year']]
index = {'items': auto, 'works': {w: ([works[w]['title'], year_of(w) or ''] if w in works else films[w]) for w in used_w if w in works or w in films}}
with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, separators=(',', ':'))
IDX_V = hashlib.sha1(json.dumps(index, ensure_ascii=False).encode('utf-8')).hexdigest()[:8]
art_count = Counter(p for e in auto for p in e.get('p', []))
# タグ編集の予測変換の候補：全作品（番組・映画）と人（スタッフの台帳と記事に出てきた名前）。記事の多いものを先に
w_count = Counter(w for e in auto for w in e.get('w', []))
_roles = {r.get(k) for rows in staff.values() for r in rows for k in ('role', 'role_raw')}   # 役職名（名前の欄に役職が入った行がある）
_names = {p for p in set(p_staff) | set(art_count) if p and 2 <= len(p) <= 20 and p not in _roles and not re.search(r'[「」『』（）()]', p)}   # クレジット表記そのままのもの（「〜」より など）は外す
_by2 = defaultdict(list)
for p in _names: _by2[p[:2]].append(p)
t_count = Counter()   # 記事の題名に名前が出てくる回数（映画の監督など、テレビのスタッフに少ない人も上に来るように）
for e in auto:
    t = e.get('t', ''); hit = set()
    for i in range(len(t) - 1):
        for p in _by2.get(t[i:i + 2], ()):
            if t.startswith(p, i): hit.add(p)
    t_count.update(hit)
x_count = Counter(x for e in auto for x in e.get('x', []))   # 新しく作ったタグ（ほかの記事の編集でも候補に出す）
tagnames = {'x': sorted([[x, n] for x, n in x_count.items()], key=lambda y: -y[1]), 'w': sorted([[w, works[w]['title'], year_of(w) or '', w_count[w]] for w in works] + [[w, t[0], t[1], w_count[w]] for w, t in films.items()], key=lambda x: -x[3]),
            'p': sorted([[p, art_count[p] + t_count[p] * 3 + len(p_staff.get(p, {}))] for p in _names], key=lambda x: -x[1])}
with open(os.path.join(OUT, 'tagnames.json'), 'w', encoding='utf-8') as f:
    json.dump(tagnames, f, ensure_ascii=False, separators=(',', ':'))

# ---------------------------------------------------------------- 記事検索（インタビュー＝トップ、コラム＝別ページ）
IS_IV = lambda e: (e.get('k') or 'インタビュー') == 'インタビュー'
# 一覧の印（放送・公開前のアニメと同じ見た目）：インタビューはサイト、レビューは種類
# 媒体はジャンルごとに色分けする（媒体が増えたので、媒体ごとの色はやめる）。印は媒体の略称
GENRES = [('アニメ専門', 250), ('エンタメ総合', 25), ('カルチャー・その他', 150), ('閉鎖したサイト（保存ページ）', 70)]
SITE_GENRE = {'アニメ！アニメ！': ('アニメ専門', 'AA'), 'アニメイトタイムズ': ('アニメ専門', 'AT'), 'アニメハック': ('アニメ専門', 'AH'), 'WebNewtype': ('アニメ専門', 'NT'),
              'MANTANWEB': ('エンタメ総合', 'MW'), 'コミックナタリー': ('エンタメ総合', 'ナ'), '映画ナタリー': ('エンタメ総合', '映ナ'), 'リアルサウンド': ('エンタメ総合', 'RS'),
              'MOVIE WALKER PRESS': ('エンタメ総合', 'MV'), 'J:magazine!': ('エンタメ総合', 'J'), 'TBS INNOVATION LAND': ('エンタメ総合', 'TBS'),
              'クランクイン！': ('エンタメ総合', 'CI'), '映画.com': ('エンタメ総合', 'EC'), '日経エンタ！ANIME STUDY': ('エンタメ総合', '日経'), 'アニメージュプラス': ('アニメ専門', 'AP'),
 'ダ・ヴィンチWeb': ('カルチャー・その他', 'DV'), 'gamebiz': ('カルチャー・その他', 'gb'),
 'ファッションプレス': ('カルチャー・その他', 'FP'), 'ファミ通.com': ('カルチャー・その他', 'ファ'),
 'Mikiki': ('カルチャー・その他', 'Mk'), '美術手帖': ('カルチャー・その他', '美'), 'GIGAZINE': ('カルチャー・その他', 'GI'),
              'Febri': ('閉鎖したサイト（保存ページ）', 'Fe'), 'bonet': ('閉鎖したサイト（保存ページ）', 'bo'), 'アキバ総研': ('閉鎖したサイト（保存ページ）', '秋')}
KIND_ICON = [('レビュー', '評', 25), ('評論', '評', 25), ('感想', '感', 150), ('資料', '資', 70)]
def search_page(path, mode, h1, lead, ph):
    L = [e for e in auto if IS_IV(e) == (mode == 'interview')]
    if mode == 'interview':
        legend = '／'.join(f'<span class="ic" style="--h:{h}">　</span>{esc(g)}' for g, h in GENRES)
        icons = []
        castopt = '<label><input type="checkbox" id="cast" checked> 声優も</label>'
    else:   # レビュー検索は種類（評論・感想・資料）で分けない
        icons, legend, castopt = [], '', ''
    page(path, h1 if path != 'index.html' else CONF['サイト名'], f'''<h1>{esc(h1)}</h1>
<p class="lead">{esc(lead)}</p>
<div class="sbar"><input type="search" id="q" placeholder="{esc(ph)}" autofocus><div class="mpick"><button type="button" id="mbtn" aria-haspopup="true" aria-expanded="false">{'媒体' if mode == 'interview' else '連載'}：すべて ▾</button><div id="mpop" class="mpop" hidden></div></div></div>
<div class="opts scope"><label><input type="radio" name="scope" value="title"> 題名だけ</label><label><input type="radio" name="scope" value="tag" checked> タグも</label><label><input type="radio" name="scope" value="all"> 本文も</label></div>
<div class="opts"><label><input type="checkbox" id="old"> 古い順</label>{castopt}</div>
<p class="count" id="count"></p>
<ul class="ulist" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>''', current=path,
         script=f'<script>window.IDX="index.json?v={IDX_V}";window.MODE="{mode}";window.ICONS={json.dumps({n: [i, h] for n, i, h in icons}, ensure_ascii=False)};window.GENRES={json.dumps(GENRES, ensure_ascii=False)};window.SITE_GENRE={json.dumps(SITE_GENRE, ensure_ascii=False)}</script><script src="search.js?v={SEARCH_V}"></script>')

search_page('index.html', 'interview', CONF['サイト名'], CONF.get('説明', ''), '作品・人・題名で検索')
search_page('column.html', 'column', 'アニメレビュー検索', 'アニメのレビュー・感想・評論などの記事を、番組名・スタッフ名・題名で探せる索引です。', '作品・人・題名で検索')

# ---------------------------------------------------------------- スタッフランキング（年代別・折り畳み）
SKIP_KUBUN = COMPANY_KUBUN | {'原作・原案'}
dec_works = defaultdict(lambda: defaultdict(set))      # 年代 → 人 → 作品
dec_roles = defaultdict(lambda: defaultdict(Counter))  # 年代 → 人 → 役職
for w, rows in staff.items():
    y = year_of(w)
    if not y: continue
    d = decade(y)
    for r in rows:
        if r['kubun'] in SKIP_KUBUN: continue
        dec_works[d][r['person']].add(w); dec_roles[d][r['person']][r['role']] += 1
for w, rows in episodes.items():
    y = year_of(w)
    if not y: continue
    d = decade(y)
    for r in rows:
        for role in EP_ROLES:
            for p, _ in ep_names(r[role]):
                dec_works[d][p].add(w); dec_roles[d][p][role] += 1
# 役職の切り替え（スタッフ欄の区分ごと。各話リストの役職は近い区分に入れる）
RANK_GROUPS = ['全役職', '監督', '脚本・構成', '演出・絵コンテ', '作画', 'デザイン', '美術', '色彩・仕上', '撮影', 'CG', '音響', '音楽', '編集・現像', '企画・プロデューサー']
EP_GROUP = {'脚本': '脚本・構成', '絵コンテ': '演出・絵コンテ', '演出': '演出・絵コンテ', '総作画監督': '作画', '作画監督': '作画'}
grp_works = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))      # 区分 → 年代 → 人 → 作品
grp_roles = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))  # 区分 → 年代 → 人 → 役職
def add_rank(g, d, p, w, role):
    for g_ in ('全役職', g):
        if g_ in RANK_GROUPS:
            grp_works[g_][d][p].add(w); grp_roles[g_][d][p][role] += 1
for w, rows in staff.items():
    y = year_of(w)
    if not y: continue
    for r in rows:
        if r['kubun'] not in SKIP_KUBUN: add_rank(r['kubun'], decade(y), r['person'], w, r['role'])
for w, rows in episodes.items():
    y = year_of(w)
    if not y: continue
    for r in rows:
        for role in EP_ROLES:
            for p, _ in ep_names(r[role]):
                add_rank(EP_GROUP[role], decade(y), p, w, role)
TOP = 50
decs = sorted(grp_works['全役職'])
rank = {}
for g in RANK_GROUPS:
    rank[g] = {d: [[p, len(ws), '・'.join(r for r, _ in grp_roles[g][d][p].most_common(2)), art_count.get(p, 0)]
                   for p, ws in sorted(grp_works[g][d].items(), key=lambda x: (-len(x[1]), x[0]))[:TOP]] for d in decs}
rj = json.dumps({'groups': RANK_GROUPS, 'decs': decs, 'rank': rank}, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(OUT, 'ranking.json'), 'w', encoding='utf-8') as f: f.write(rj)
RANK_V = hashlib.sha1(rj.encode('utf-8')).hexdigest()[:8]
shutil.copy(D('static', 'ranking.js'), OUT)
for _f in ('viewer.html', 'akiba.js'): shutil.copy(D('static', _f), OUT)   # アキバ総研の保存ページを読む閲覧ページ（febri-archive から）
RJS_V = hashlib.sha1(open(D('static', 'ranking.js'), 'rb').read()).hexdigest()[:8]
GHUE = {g: (250 + i * 360 // len(RANK_GROUPS)) % 360 for i, g in enumerate(RANK_GROUPS)}   # 役職ごとの色相（明るさ・彩度はそろえる）
btns = ''.join(f'<button type="button" data-g="{esc(g)}" style="--h:{GHUE[g]}"{" class=on" if g == "全役職" else ""}>{esc(g)}</button>' for g in RANK_GROUPS)
toc = ('<div class="toc">' + ''.join(f'<a class="cat" style="--h:{(200 + i * 25) % 360}" href="#d{i}">{esc(d)}</a>' for i, d in enumerate(decs))
       + '<span class="tocb"><button type="button" data-all="1">すべて開く</button><button type="button" data-all="0">すべて閉じる</button></span></div>')
TOCJS = ('<script>document.querySelectorAll(".toc a").forEach(a=>a.addEventListener("click",()=>{const d=document.querySelector(a.getAttribute("href"));if(d)d.open=true}));'
         'document.querySelectorAll(".tocb button").forEach(b=>b.addEventListener("click",()=>document.querySelectorAll("details.grp").forEach(d=>d.open=b.dataset.all==="1")));</script>')
dets = ''.join(f'<details class="grp" id="d{decs.index(d)}" data-d="{esc(d)}"><summary>{esc(d)}<span class="n"></span></summary><ul class="list rank"></ul></details>' for d in decs)
page('ranking.html', 'スタッフランキング', f'''<h1>スタッフランキング</h1><p class="lead">年代ごとに、その年代に始まったテレビアニメに多く関わったスタッフを並べています（数字は番組数。スタッフ欄と各話リストの脚本・絵コンテ・演出・作画監督から数えています）。役職を押すと切り替わります。名前を押すと、その人が出てくる記事を検索します。</p>
<div class="seg" id="seg">{btns}</div>
{toc}<div id="rank">{dets}</div>''', crumbs=[('tools.html', 'ツール集'), (None, 'スタッフランキング')], current='tools.html',
     script=f'<script>window.RANK="ranking.json?v={RANK_V}"</script><script src="ranking.js?v={RJS_V}"></script>' + TOCJS)


# 追加ページ用の各話の一覧（eps/<番組ID>.json）
os.makedirs(os.path.join(OUT, 'eps'), exist_ok=True)
for w in episodes:
    with open(os.path.join(OUT, 'eps', f'{w}.json'), 'w', encoding='utf-8') as f:
        json.dump(ep_names_of(w), f, ensure_ascii=False, separators=(',', ':'))

# 記事リンクの追加（筆者用。メニューには出さず、検索にも載せない）
shutil.copy(D('static', 'add.js'), OUT)
page('add.html', '記事リンクの追加', '''<h1>記事リンクの追加</h1>
<section class="add bulk">
<h2>まとめて追加（レビュー検索）</h2>
<label>記事のURL（1行に1つ）<textarea id="b-urls" rows="8" placeholder="https://…&#10;https://…"></textarea></label>
<p class="hint">題名・日付・媒体は、公開のときにページから自動で入ります。もう入っているURLと、同じURLの重複は除きます。番組とは結び付けません。</p>
<p class="go-row"><button id="b-push" class="btn big">まとめて追加して公開</button>　<span id="b-count" class="warn"></span></p>
<p id="b-msg" class="msg"></p>
</section>
<h2 class="add-one">1本ずつ追加（番組を選ぶ）</h2>
<div class="add">
<label>記事のURL<input id="f-url" type="url" placeholder="https://…" autofocus></label>
<p class="hint">URLだけで登録できます。題名・筆者・媒体・日付は空のままでよく、公開のときにページから自動で入ります（下の欄に書いたものが優先）。</p>
<label>番組<input id="q" type="search" placeholder="違うときは番組名で探す"><select id="f-work"></select></label>
<label>記事の対象<select id="f-scope"><option value="">番組全体（関連記事）</option><option value="ep">話数単位（関連記事（話数単位））</option></select></label>
<div id="ep-wrap" class="grid" hidden><label class="w2">各話リストから選ぶ<select id="f-ep"></select></label><label>話数（数字）<input id="f-epno" placeholder="1"></label><label>サブタイトル<input id="f-epsub"></label></div>
<div class="grid">
<label>種類<select id="f-type"><option>評論</option><option selected>感想</option><option>インタビュー</option><option>資料</option></select></label>
<label>分類（媒体）<select id="f-kind"><option>ブログ</option><option>ネットメディア</option><option>雑誌</option><option>書籍</option><option>新聞</option><option>ウェブサイト</option><option>その他</option></select></label>
<label>日付<input id="f-date" placeholder="2006-09-30"></label>
<label class="w2">題名（空なら自動）<input id="f-title"></label>
<label>筆者<input id="f-author"></label>
<label>媒体<input id="f-site"></label>
</div>
<details class="gh"><summary>URLで読めないサイトは、保存したHTMLから読み取る</summary><div id="drop" class="drop"><p>保存したHTMLをここに落とす　または　<label class="btn">ファイルを選ぶ<input id="file" type="file" accept=".html,.htm,.mhtml" hidden></label></p><p class="fname" id="fname"></p></div></details>
<p class="go-row"><button id="push" class="btn big">追加して公開</button>　<span id="chk" class="warn"></span></p>
<p id="msg" class="msg"></p>
<div id="tokbox" class="tokbox" hidden><p>GitHubの鍵（トークン）を貼って「このブラウザに保存」を押してください。ブラウザがパスワードとして保存するか聞いてきたら、保存してください（ブラウザが鍵を消しても、次から自動で入ります）。</p>
<form id="tokform" class="tokform"><input class="vh" type="text" name="username" autocomplete="username" value="anime-world" tabindex="-1" aria-hidden="true">
<label>トークン<input id="tok" name="password" type="password" autocomplete="current-password"></label> <button type="submit" class="btn">このブラウザに保存</button></form></div>
<p class="tokchange"><a href="#" id="tokedit">鍵を変える</a></p>
<details class="gh"><summary>手で足す（links.csv に1行を貼る）</summary>
<label>links.csv に足す1行<textarea id="line" rows="3" readonly></textarea></label>
<p><button id="copy" class="btn">この1行をコピー</button>　<a href="https://github.com/nzanke/anime-world/edit/main/content/links.csv">GitHubで links.csv を開く</a></p></details>

</div>''', crumbs=[(None, '記事リンクの追加')], script=f'<script src="add.js?v={JS_V}"></script>', head='<meta name="robots" content="noindex">')

# クレジット表（シーズン別スタッフ表・各話クレジット・アニメ映画スタッフ表）
# データは非公開の anime-database の tools/hyoron/export_credits.py で書き出した data/credits/（1年1ファイル。ページは選んだ年だけ読み込む）
if os.path.isdir(D('data', 'credits')):
    shutil.copytree(D('data', 'credits'), os.path.join(OUT, 'credits'), dirs_exist_ok=True)
    CV = {}
    for f in ('credits_staff.js', 'credits_episodes.js', 'credits_films.js'):
        shutil.copy(D('static', f), OUT); CV[f] = hashlib.sha1(open(D('static', f), 'rb').read()).hexdigest()[:8]
    # データを書き出し直したら古いファイルがブラウザに残らないよう、index.json の中身から番号を付ける
    DV = hashlib.sha1(b''.join(open(D('data', 'credits', s_, 'index.json'), 'rb').read() for s_ in ('staff', 'episodes', 'films'))).hexdigest()[:8]
    TABS = [('staff_season.html', 'シーズン別スタッフ表'), ('episode_credits.html', '各話クレジット'), ('film_staff.html', 'アニメ映画スタッフ表')]
    COPY = """<script>window.CREDITS_BASE='credits/';window.CREDITS_COPY=()=>{const b=document.getElementById('copy'),o=document.getElementById('out');b.onclick=()=>{const t=o.textContent;const done=()=>{b.textContent='コピーしました';setTimeout(()=>b.textContent='テキストをコピー',1500)};const sel=()=>{const r=document.createRange();r.selectNodeContents(o);const s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent='選択しました（Ctrl+C）'};try{navigator.clipboard.writeText(t).then(done,sel)}catch(e){sel()}}};</script>"""
    def cpage(path, title, lead, ctl, js):
        tabs = '<nav class="tabs" aria-label="クレジット表">' + ''.join(f'<a href="{u}"{" class=on" if u == path else ""}>{esc(t)}</a>' for u, t in TABS) + '</nav>'
        page(path, title, f"""<h1>{esc(title)}</h1>{tabs}<p class="lead">{lead}</p>
<div class="ctl">{ctl}</div>
<div class="outbar"><span class="count" id="count">読み込み中…</span><button id="copy" type="button" class="cbtn">テキストをコピー</button></div>
<pre id="out" class="out" tabindex="0"></pre>""", crumbs=[('tools.html', 'ツール集'), (None, title)], current='tools.html',
             script=COPY.replace("'credits/'", f"'credits/'") + f'<script src="{js}?v={CV[js]}&d={DV}"></script>')
    cpage('staff_season.html', 'シーズン別スタッフ表',
          'テレビアニメの番組を始まった季節（冬＝前年12月〜2月、春＝3〜5月、夏＝6〜8月、秋＝9〜11月）ごとに並べ、スタッフ欄の役職から選んだものを書き出します。年を2つ選ぶと、その間に始まった番組をまとめて出します。キーワードは名前・番組名・役職から探します。',
          '<label>年<select id="year"></select></label><label>まで<select id="year2"></select></label>'
          '<div class="ctlg"><span class="lb">季節</span><div class="seg" id="season" role="group" aria-label="季節"></div></div>'
          '<label>役職<select id="role"></select></label><label class="grow">キーワード<input id="q" type="search" placeholder="例：サンジゲン"></label>'
          '<label class="chk"><input type="checkbox" id="raw"> 元の役職表記を添える</label>', 'credits_staff.js')
    cpage('episode_credits.html', '各話クレジット',
          '各話リストの作画監督・総作画監督・専門作画監督・脚本・絵コンテ・演出・その他のコンテを、季節ごとに書き出します。「人ごと」は担当した話数（作画監督系は同じ回の人数で割り、脚本・絵コンテ・演出は共同を0.5話）で、★はその役職で初めて名前が出た季節、年はその役職の初出年（絵コンテ・演出はコンテデビュー年）です。',
          '<label>年<select id="year"></select></label>'
          '<div class="ctlg"><span class="lb">季節</span><div class="seg" id="season" role="group" aria-label="季節"></div></div>'
          '<div class="ctlg"><span class="lb">基準</span><div class="seg" id="by" role="group" aria-label="基準"></div></div>'
          '<label>役職<select id="role"></select></label>'
          '<div class="ctlg"><span class="lb">表示</span><div class="seg" id="mode" role="group" aria-label="表示"></div></div>', 'credits_episodes.js')
    cpage('film_staff.html', 'アニメ映画スタッフ表',
          '日本のアニメ映画（日本語版ウィキペディア「日本のアニメ映画作品一覧」の作品）のスタッフを、公開年と役職で書き出します。1作品＝1本で数えます。記事にスタッフが書かれていない作品は、一覧の監督・制作だけです。',
          '<label>公開年<select id="y"></select></label><label>まで<select id="y2"></select></label>'
          '<label>役職<select id="role"></select></label>'
          '<div class="ctlg"><span class="lb">表示</span><div class="seg" id="mode" role="group" aria-label="表示"></div></div>'
          '<label class="grow">キーワード<input id="q" type="search" placeholder="例：細田守"></label>', 'credits_films.js')

# 制作決定ニュースは独立したサイト（nzanke/anime-news）に移した。古いページは新しいサイトへ移す案内だけを置く
# （data/news.json は毎日の収集が置き、anime-news がここから取っていく）
for _old, _new in (('news.html', ''), ('upcoming.html', 'upcoming.html'), ('released.html', 'released.html')):
    with open(os.path.join(OUT, _old), 'w', encoding='utf-8') as f:
        f.write(f'<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><title>アニメ制作決定ニュース（移転しました）</title>'
                f'<meta http-equiv="refresh" content="0; url={NEWS_SITE}{_new}"><link rel="canonical" href="{NEWS_SITE}{_new}"></head>'
                f'<body><p>アニメ制作決定ニュースは <a href="{NEWS_SITE}{_new}">{NEWS_SITE}{_new}</a> に移転しました。</p></body></html>')

# アニメ配信カレンダー（data/haishin/schedule.json は毎日 .github/workflows/haishin.yml が更新する。購読の設定は content/haishin_my.json）
HAISHIN_CSS = """<style>
.hs-row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 8px}
.hs-k{font-size:12px;color:var(--muted);width:3.5em;flex:0 0 auto}
.hs-chip{font-size:13px;padding:3px 10px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--line);cursor:pointer;color:var(--muted);user-select:none;white-space:nowrap}
.hs-chip input{display:none}.hs-chip small{margin-left:4px;font-size:11px;opacity:.7}
.hs-chip.on{color:var(--fg);font-weight:700;box-shadow:inset 0 0 0 1.5px var(--accent);background:var(--pale)}
.hs-mini{font-family:var(--sans);font-size:12px;padding:3px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);cursor:pointer}
#hs-tabs{margin:14px 0 4px}
.hs-note{font-size:13px;color:var(--muted);margin:8px 0}
.hs-day{font-size:15px;margin:22px 0 4px;padding-bottom:4px;border-bottom:2px solid var(--fg)}
.hs-day.sat{color:#2a62b8}.hs-day.sun{color:var(--accent)}
.hs-day span{font-size:11px;margin-left:8px;padding:1px 8px;border-radius:999px;background:var(--accent);color:#fff;vertical-align:2px}
.hs-list{list-style:none;padding:0;margin:0}
.hs-list li{display:flex;gap:12px;padding:8px 0;border-bottom:1px solid var(--line);align-items:baseline}
.hs-list li.past{opacity:.45}
.hs-t{flex:0 0 3.2em;font-weight:700;font-variant-numeric:tabular-nums;text-align:right}
.hs-b{flex:1;min-width:0;font-size:14px}
.hs-s{display:inline-block;margin-left:6px;font-size:11px;padding:0 8px;border-radius:999px;color:oklch(0.46 0.12 260);background:oklch(0.955 0.03 260);white-space:nowrap}
.hs-s.tv{color:oklch(0.46 0.12 150);background:oklch(0.955 0.03 150)}
@media (prefers-color-scheme:dark){.hs-s{color:oklch(0.86 0.09 260);background:oklch(0.30 0.05 260)}.hs-s.tv{color:oklch(0.86 0.09 150);background:oklch(0.30 0.05 150)}}
.hs-oth{display:block;font-size:11px;color:var(--muted);margin-top:2px}
.hs-bar{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.hs-bar input{flex:1 1 220px;font-size:16px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
.hs-works{list-style:none;padding:0;margin:0}
.hs-works li{border-bottom:1px solid var(--line)}
.hs-works label{display:flex;gap:10px;padding:8px 0;cursor:pointer;align-items:flex-start}
.hs-works input{margin-top:5px;transform:scale(1.2)}
.hs-works li.na{opacity:.5}.hs-works li.on b{color:var(--accent)}
.hs-works b{font-size:14px;display:block}
.hs-slot{display:block;font-size:12px}
.hs-where{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px}
.hs-where i{font-style:normal;font-size:10px;padding:0 6px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--line);color:var(--muted)}
.hs-where i.on{color:var(--fg);box-shadow:inset 0 0 0 1px var(--muted)}
.hs-url code{font-size:12px;word-break:break-all;background:var(--pale);padding:2px 6px;border-radius:4px}
.hs-steps{font-size:13px;padding-left:1.4em}.hs-steps li{margin:4px 0}
.hs-btn{font-size:14px;padding:8px 18px}
.hs-src{font-size:12px;color:var(--muted);margin-top:28px}
.hs-wk{display:grid;grid-template-columns:1fr;gap:0 18px}
@media (min-width:1100px){.wrap{max-width:1180px}.hs-wk{grid-template-columns:repeat(4,1fr)}}
.hs-day small{font-size:11px;font-weight:400;color:var(--muted);margin-left:8px}
.hs-b small{font-size:11px;color:var(--muted)}
.hs-cmp{display:block;font-size:11px;color:var(--muted);margin-top:2px}.hs-cmp.up{color:var(--accent);font-weight:700}
</style>"""
if os.path.exists(D('data', 'haishin', 'schedule.json')):
    sys.path.insert(0, D('tools', 'haishin'))
    from make_ics import make_ics
    _hd = os.path.join(OUT, 'haishin')
    os.makedirs(_hd, exist_ok=True)
    shutil.copy(D('data', 'haishin', 'schedule.json'), _hd)
    _sched = json.load(open(D('data', 'haishin', 'schedule.json'), encoding='utf-8'))
    if os.path.exists(D('content', 'haishin_my.json')):
        _my = json.load(open(D('content', 'haishin_my.json'), encoding='utf-8'))
        json.dump(_my, open(os.path.join(_hd, 'my.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        with open(os.path.join(_hd, 'my.ics'), 'w', encoding='utf-8', newline='') as f:
            f.write(make_ics(_sched, _my, 'https://nzanke.github.io/anime-world/haishin.html'))
    shutil.copy(D('static', 'haishin.js'), OUT)
    HV = hashlib.sha1(open(D('static', 'haishin.js'), 'rb').read() + open(D('data', 'haishin', 'schedule.json'), 'rb').read()).hexdigest()[:8]
    page('haishin.html', 'アニメ配信カレンダー', f"""<h1>アニメ配信カレンダー</h1>
<p class="lead">契約している配信サービスと見る作品を選ぶと、各話をいちばん早く見られる日時で自分用の番組表を作ります。Googleカレンダーで購読もできます。深夜は28時までその日の番組として扱います。配信予定は毎日自動で取り直します。</p>
<p class="count" id="count"></p>
<div id="hs-svc"></div>
<nav class="tabs" id="hs-tabs"></nav>
<div id="hs-main"><p class="hs-note">読み込み中…</p></div>
<p class="hs-src">配信予定の出どころ：dアニメストア・U-NEXT・DMM TV の今期アニメ一覧（公式）、Netflix・Prime Video・ABEMA ほかは各作品のウィキペディア記事の配信表と gamebiz の「放送・配信情報一覧」記事、テレビ放送は<a href="https://cal.syoboi.jp/">しょぼいカレンダー</a>（<span id="hs-gen"></span>）。U-NEXT・Netflix・Prime Video などは配信開始日から毎週として出しているため、休止や時刻の変更は反映されないことがあります。視聴前に各サービスでご確認ください。</p>""",
         crumbs=[('tools.html', 'ツール集'), (None, 'アニメ配信カレンダー')], current='tools.html', head=HAISHIN_CSS,
         desc='契約中の配信サービスで、今期アニメの各話をいちばん早く見られる日時を並べる自分用の番組表。Googleカレンダーで購読できます。',
         script=f'<script src="haishin.js?v={HV}" data-v="{HV}"></script>')

# ツール集（スタッフランキングとクレジット表への入口）
TOOLS = [('haishin.html', 'アニメ配信カレンダー', '契約している配信サービスと見る作品を選ぶと、各話をいちばん早く見られる日時で自分用の番組表を作ります。Googleカレンダーで購読もできます。'),
         ('ranking.html', 'スタッフランキング', '年代ごとに、多くのテレビアニメに関わったスタッフを並べます。役職で切り替えられます。'),
         ('staff_season.html', 'シーズン別スタッフ表', 'テレビアニメを始まった季節ごとに並べ、選んだ役職のスタッフを書き出します。'),
         ('episode_credits.html', '各話クレジット', '各話リストの作画監督・脚本・絵コンテ・演出などを、季節ごとに書き出します。'),
         ('film_staff.html', 'アニメ映画スタッフ表', 'アニメ映画のスタッフを、公開年と役職で書き出します。'),
         ('https://nzanke.github.io/febri-archive/index.html', 'Febri・アキバ総研 記事アーカイブ索引', '閉鎖したアニメ情報サイト Febri とアキバ総研の記事を、インターネットアーカイブの保存ページへのリンクで探せます。連載一覧もあります。'),
         ('https://nzanke.github.io/anime-guide/index.html#golden-1990s', 'アニメ放送枠タイムテーブル', '1960〜2010年代のテレビアニメを、曜日・時間帯・局ごとの半年単位の番組表で見ます。'),
         ('https://nzanke.github.io/anime-guide/late.html#mx-2005', '深夜アニメ放送枠タイムテーブル', '1995〜2024年の深夜アニメを、局ごと・3か月ごとの放送枠の表で見ます。')]
page('tools.html', 'ツール集', '<h1>ツール集</h1><p class="lead">番組・スタッフの基礎データを使った表とランキングです。</p><ul class="list tools">'
     + ''.join(f'<li><span class="title"><a href="{u}">{esc(t)}</a><span class="writer">{esc(d)}</span></span></li>' for u, t, d in TOOLS if u.startswith('http') or os.path.exists(os.path.join(OUT, u)) or u == 'ranking.html')
     + '</ul>', current='tools.html')

# このサイトについて
about = open(D('content', 'about.md'), encoding='utf-8-sig').read() if os.path.exists(D('content', 'about.md')) else ''
page('about.html', 'このサイトについて', '<h1>このサイトについて</h1><div class="text">' + render_body(about, '', 2) + '</div>',
     crumbs=[(None, 'このサイトについて')], current='about.html')

HELP = [('検索と絞り込みの使い方', '<ul><li>言葉をスペースで区切ると、すべてを含む記事に絞ります。</li><li>探す範囲：「題名だけ」は題名から、「タグも」は題名と一覧に出ているタグから、「本文も」は記事の中に出てくる作品・人まで探します。</li>'
         '<li>「媒体」「連載」のボタンで、媒体や連載を選んで絞ります。複数選べます。</li><li>「古い順」で日付の古い記事から並べます。「声優も」を外すと、キャスト（声優）のインタビューを出しません。</li><li>タグを押すと、そのタグで検索します。</li></ul>'),
        ('表示の見方', '<ul><li>記事は月ごとにまとめ、日にちと曜日を添えています。日付が月までしかわからない記事は「頃」、わからない記事は「—」として「日付なし」にまとめています。</li>'
         '<li>題名のあとの札は掲載した媒体です。インタビュー検索では、色で媒体の種類（' + '・'.join(g for g, _ in GENRES) + '）を分けています。</li>'
         '<li>タグ：「#」付きは作品、そのほかは人です。レビュー検索の橙のタグは連載、紫のタグは手で付けたタグです。</li><li>声：キャスト（声優）のインタビューです。</li></ul>')]
_ab = {t.split(' {#')[0]: render_body(b, '', 3) for t, b in re.findall(r'^## (.+?)\n(.*?)(?=^## |\Z)', about, re.S | re.M)}
COLLECT = ('集めているもの', _ab.get('このサイトについて', ''))
NOTPUT = ('載せていないもの', '<ul><li>記事の本文・画像は載せていません。題名・日付・媒体・筆者と、掲載元へのリンクだけです。</li><li>インタビュー・レビュー以外の記事（ニュース・告知など）は載せていません。アニメの制作決定ニュースは<a href="' + NEWS_SITE + '">別のサイト</a>にあります。</li></ul>')
SOURCE = ('出典・連絡先', _ab.get('基礎データの出典と加工', '') + _ab.get('クレジット表', '') + _ab.get('ライセンス', '')
          + '<p>掲載内容の削除のご要望などは、X（<a href="https://x.com/bg75gf">@bg75gf</a>）までご連絡ください。</p>')
PAGES = [p_ for p_ in ('index.html', 'column.html', 'haishin.html', 'ranking.html', 'staff_season.html', 'episode_credits.html', 'film_staff.html', 'tools.html') if p_ in LEADS]
about_js = ('(function(){var S=document.currentScript,pg=S&&S.dataset.page;var L=' + json.dumps({p_: LEADS[p_] for p_ in PAGES}, ensure_ascii=False)
    + ',O=' + json.dumps(PAGES) + ',H=' + json.dumps([HELP[0], HELP[1], COLLECT, NOTPUT, SOURCE], ensure_ascii=False) + ';'
    + 'function init(){var b=document.getElementById("aboutbox");if(!b)return;var h="",me=L[pg];'
    + 'if(me&&me[1])h+="<h3>"+me[0]+"</h3><p>"+me[1]+"</p>";'
    + 'h+="<h3>ほかのページ</h3><ul>"+O.filter(function(p){return p!==pg}).map(function(p){return "<li><a href='"+p+"'>"+L[p][0]+"</a>："+L[p][1].replace(/<[^>]+>/g,"").split("。")[0]+"。</li>"}).join("")+"</ul>";'
    + 'H.forEach(function(x){h+="<h3>"+x[0]+"</h3>"+x[1]});b.innerHTML=h;var d=b.closest("details");'
    + 'document.addEventListener("click",function(e){if(d.open&&!d.contains(e.target))d.open=false});}'
    + 'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();})();\n')
with open(os.path.join(OUT, 'about.js'), 'w', encoding='utf-8') as f: f.write(about_js)

n = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(OUT) for f in fs)
print(f'{n}ファイル　{size / 1e6:.1f}MB　番組{len(works)}・人{len(people)}・制作会社{len(studio_works)}・関連記事{len(all_links)}')
for m in warnings:
    print('注意:', m)
