"""アニメ評論サイトを組み立てる（Python の標準ライブラリだけで動く）。

  python3 build.py            → _site/ にサイト一式を書き出す

読むもの
  data/works.tsv ほか      基礎データ（anime-database の tools/hyoron/export.py で書き出したもの）
  content/site.txt         サイト名・説明など
  content/about.md         「このサイトについて」の本文
  content/links.csv        関連記事のリンク（評論・インタビュー・記事。自分の評論も含む）
"""
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
            w = find_work(r.get('番組ID', ''), r.get('番組名', ''), f'links.csv {i}行目')
            if not w:
                continue
            r['work'] = w
            links[w].append(r)
            all_links.append(r)
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
NAV = [('index.html', 'インタビュー'), ('column.html', 'レビュー'), ('news.html', '制作決定'), ('tools.html', 'ツール集'), ('about.html', 'このサイトについて')]
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDMincho&family=BIZ+UDPMincho:wght@400;700&family=BIZ+UDPGothic:wght@400;700&display=swap">')

# 書き換えたら古いものがブラウザに残らないよう、ファイルの中身から番号を付ける
CSS_V = hashlib.sha1(open(D('static', 'style.css'), 'rb').read()).hexdigest()[:8]
JS_V = hashlib.sha1(open(D('static', 'add.js'), 'rb').read()).hexdigest()[:8]
SEARCH_V = hashlib.sha1(open(D('static', 'search.js'), 'rb').read()).hexdigest()[:8]

def page(path, title, body, crumbs=(), current=None, desc='', script='', head=''):
    depth = path.count('/')
    r = '../' * depth
    site = CONF['サイト名']
    nav = ''.join(f'<a href="{r}{u}"{" class=on" if u == current else ""}>{esc(t)}</a>' for u, t in NAV)
    cr = ''
    if crumbs:
        cr = '<nav class="crumbs">' + ' › '.join(
            [f'<a href="{r}index.html">トップ</a>'] + [f'<a href="{r}{u}">{esc(t)}</a>' if u else esc(t) for u, t in crumbs]) + '</nav>'
    full = f'{esc(title)}｜{esc(site)}' if title != site else esc(site)
    src = f'（{FETCHED}取得）' if FETCHED else ''
    doc = f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full}</title>{f'<meta name="description" content="{esc(desc)}">' if desc else ''}
{FONTS}<link rel="stylesheet" href="{r}style.css?v={CSS_V}">{head}</head>
<body><div class="wrap">
<nav class="nav" aria-label="サイト内">{nav}</nav>
<main>{cr}
{body.replace('{R}', r)}
</main>
<footer class="site"><p>番組・スタッフ・各話の基礎データは日本語版ウィキペディアの各記事{src}をもとに加工したもので、<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a> で提供します（<a href="{r}about.html#data">出典と加工について</a>）。</p></footer>
</div>{script}</body></html>
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
         'k': l.get('種類') or 'インタビュー', 'w': [l['work']], 'p': []}
    if l.get('筆者'): e['a'] = l['筆者']
    auto.append(e)
auto.sort(key=lambda e: e.get('d') or '0000', reverse=True)
used_w = {w for e in auto for w in e.get('w', [])}
films = {}   # 記事に出てくる映画（anime-database の tag.py が書き出す）
if os.path.exists(D('data', 'films.tsv')):
    for r in csv.DictReader(open(D('data', 'films.tsv'), encoding='utf-8'), delimiter='\t'): films[r['work_id']] = [r['title'], r['year']]
index = {'items': auto, 'works': {w: ([works[w]['title'], year_of(w) or ''] if w in works else films[w]) for w in used_w if w in works or w in films}}
with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, separators=(',', ':'))
IDX_V = hashlib.sha1(json.dumps(index, ensure_ascii=False).encode('utf-8')).hexdigest()[:8]
art_count = Counter(p for e in auto for p in e.get('p', []))

# ---------------------------------------------------------------- 記事検索（インタビュー＝トップ、コラム＝別ページ）
IS_IV = lambda e: (e.get('k') or 'インタビュー') == 'インタビュー'
# 一覧の印（放送・公開前のアニメと同じ見た目）：インタビューはサイト、レビューは種類
SITE_ICON = [('Febri', 'Fe', 250), ('アキバ総研', '秋', 70), ('アニメ！アニメ！', 'AA', 15), ('アニメイトタイムズ', 'AT', 330),
             ('コミックナタリー', 'ナ', 140), ('MANTANWEB', 'MW', 50), ('アニメハック', 'AH', 200), ('リアルサウンド', 'RS', 290), ('WebNewtype', 'NT', 100)]
KIND_ICON = [('レビュー', '評', 25), ('評論', '評', 25), ('感想', '感', 150), ('資料', '資', 70)]
def search_page(path, mode, h1, lead, ph):
    L = [e for e in auto if IS_IV(e) == (mode == 'interview')]
    if mode == 'interview':
        have = Counter(e['s'] for e in L)
        icons = [x for x in SITE_ICON if x[0] in have]
        legend = ' '.join(f'<span class="ic" style="--h:{h}">{esc(i)}</span>{esc(n)}' for n, i, h in icons)
        castopt = '<label><input type="checkbox" id="cast" checked> キャスト（声優）のインタビューも出す（<span class="sq">声</span>の印）</label>'
    else:
        have = Counter(e['k'] for e in L)
        icons = [x for x in KIND_ICON if x[0] in have]
        legend = ' '.join(f'<span class="ic" style="--h:{h}">{esc(i)}</span>{esc(n)}' for n, i, h in icons if n != '評論')
        castopt = ''
    page(path, h1 if path != 'index.html' else CONF['サイト名'], f'''<h1>{esc(h1)}</h1>
<p class="lead">{esc(lead)} {legend}</p>
<div class="seg" id="seg"></div>
<div class="sbar"><input type="search" id="q" placeholder="{esc(ph)}" autofocus></div>
<div class="opts"><label><input type="checkbox" id="old"> 古い順</label>{castopt}</div>
<p class="count" id="count"></p>
<ul class="ulist" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>''', current=path,
         script=f'<script>window.IDX="index.json?v={IDX_V}";window.MODE="{mode}";window.ICONS={json.dumps({n: [i, h] for n, i, h in icons}, ensure_ascii=False)}</script><script src="search.js?v={SEARCH_V}"></script>')

search_page('index.html', 'interview', CONF['サイト名'], CONF.get('説明', ''), '番組名・スタッフ名・題名から検索（スペース区切りで AND）')
search_page('column.html', 'column', 'アニメレビュー検索', 'アニメのレビュー・感想・評論などの記事を、番組名・スタッフ名・題名で探せる索引です。', '番組名・スタッフ名・題名から検索（スペース区切りで AND）')

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
dets = ''.join(f'<details class="grp" data-d="{esc(d)}"{" open" if d == decs[-1] else ""}><summary>{esc(d)}<span class="n"></span></summary><ul class="list rank"></ul></details>' for d in decs)
page('ranking.html', 'スタッフランキング', f'''<h1>スタッフランキング</h1><p class="lead">年代ごとに、その年代に始まったテレビアニメに多く関わったスタッフを並べています（数字は番組数。スタッフ欄と各話リストの脚本・絵コンテ・演出・作画監督から数えています）。役職を押すと切り替わります。名前を押すと、その人が出てくる記事を検索します。</p>
<div class="seg" id="seg">{btns}</div>
<div id="rank">{dets}</div>''', crumbs=[('tools.html', 'ツール集'), (None, 'スタッフランキング')], current='tools.html',
     script=f'<script>window.RANK="ranking.json?v={RANK_V}"</script><script src="ranking.js?v={RJS_V}"></script>')


# 追加ページ用の各話の一覧（eps/<番組ID>.json）
os.makedirs(os.path.join(OUT, 'eps'), exist_ok=True)
for w in episodes:
    with open(os.path.join(OUT, 'eps', f'{w}.json'), 'w', encoding='utf-8') as f:
        json.dump(ep_names_of(w), f, ensure_ascii=False, separators=(',', ':'))

# 記事リンクの追加（筆者用。メニューには出さず、検索にも載せない）
shutil.copy(D('static', 'add.js'), OUT)
page('add.html', '記事リンクの追加', '''<h1>記事リンクの追加</h1>
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
<div id="tokbox" class="tokbox" hidden><p>はじめにこのブラウザで一度だけ、GitHubの鍵（トークン）を貼ってください。以後は表示されません。</p>
<label>トークン<input id="tok" type="password" autocomplete="off"></label></div>
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

# 制作決定ニュース（anime-database の articles/news_tag.py が書き出す data/news.json。本文は持たない）
NEWS = json.load(open(D('data', 'news.json'), encoding='utf-8')) if os.path.exists(D('data', 'news.json')) else {'items': []}
nj = json.dumps(NEWS, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(OUT, 'news.json'), 'w', encoding='utf-8') as f: f.write(nj)
shutil.copy(D('static', 'news.js'), OUT)
NEWS_V = hashlib.sha1(nj.encode('utf-8')).hexdigest()[:8]
NJS_V = hashlib.sha1(open(D('static', 'news.js'), 'rb').read()).hexdigest()[:8]
nsites = [x for x, _ in Counter(s_ for e in NEWS['items'] for s_ in [e['s']] + [o[0] for o in e.get('o', [])]).most_common()]
NCATS = [('', 'すべて', 250), ('映画', 'アニメ映画', 25), ('テレビ', 'テレビアニメ', 250), ('その他', 'その他（OVA・配信・CM・動画）', 150), ('未定', '媒体の発表なし', 70)]
nbtn = ''.join(f'<button type="button" data-c="{c}" style="--h:{h}"{" class=on" if not c else ""}>{esc(t)}<span class="n"></span></button>' for c, t, h in NCATS)
UCATS = [('', 'すべて', 250), ('映画', '映画', 25), ('テレビ', 'テレビ', 250), ('その他', '配信・OVAなど', 150), ('未定', '媒体未発表', 70)]
ubtn = ''.join(f'<button type="button" data-c="{c}" style="--h:{h}"{" class=on" if not c else ""}>{esc(t)}<span class="n"></span></button>' for c, t, h in UCATS)
NSCRIPT = lambda mode: f'<script>window.NEWS="news.json?v={NEWS_V}";window.MODE="{mode}"</script><script src="news.js?v={NJS_V}"></script>'
page('news.html', 'アニメ制作決定ニュース', f'''<h1>アニメ制作決定ニュース</h1>
<p class="lead">アニメ映画・テレビアニメ・その他のアニメ（OVA・配信アニメ・CM・動画）の制作決定（新規のアニメ化、続編・新作・劇場版の発表）と、その放送日・放送局・公開日のニュースを集めた一覧です。同じ発表を複数のサイトが伝えたものは1行にまとめています。毎日更新します。</p>
<div class="seg" id="seg">{nbtn}</div>
<div class="sbar"><input type="search" id="q" placeholder="作品名・題名から検索（スペース区切りで AND）">
<select id="site"><option value="">すべてのサイト</option>{"".join(f'<option>{esc(x)}</option>' for x in nsites)}</select></div>
<p class="jump"><a href="upcoming.html">放送・公開前のアニメ一覧（アニメ化が決まり、まだ放送・公開されていない作品）→</a></p>
<div class="opts"><label><input type="checkbox" id="sched" checked> 放送日・放送局・公開日のニュースも出す</label><label><input type="checkbox" id="newonly"> 新規のアニメ化だけ（続編・新作を除く）</label><label><input type="checkbox" id="old"> 古い順</label></div>
<p class="count" id="count"></p>
<ul class="list" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>''', current='news.html', script=NSCRIPT('news'))
page('upcoming.html', '放送・公開前のアニメ', f'''<h1>放送・公開前のアニメ</h1>
<p class="lead">制作が決まり、まだ放送・公開されていない作品（予定の早い順、毎日更新）。<span class="ic" style="--h:25">映</span>映画 <span class="ic" style="--h:250">TV</span>テレビ <span class="ic" style="--h:150">配</span>配信・OVA・CM・動画 <span class="ic" style="--h:70">?</span>媒体未発表 <span class="sq">続</span>続編・新作。局名に指を置くと全局の日時が出ます。</p>
<div class="seg" id="seg">{ubtn}</div>
<div class="sbar"><input type="search" id="q" placeholder="作品名・局名で検索"></div>
<div class="opts"><label><input type="checkbox" id="newonly"> 新規のアニメ化だけ</label><a class="jump" href="news.html">制作決定ニュースの一覧 →</a></div>
<p class="count" id="count"></p>
<ul class="ulist" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>''', crumbs=[('news.html', '制作決定'), (None, '放送・公開前のアニメ')], current='news.html', script=NSCRIPT('upcoming'))

# ツール集（スタッフランキングとクレジット表への入口）
TOOLS = [('ranking.html', 'スタッフランキング', '年代ごとに、多くのテレビアニメに関わったスタッフを並べます。役職で切り替えられます。'),
         ('staff_season.html', 'シーズン別スタッフ表', 'テレビアニメを始まった季節ごとに並べ、選んだ役職のスタッフを書き出します。'),
         ('episode_credits.html', '各話クレジット', '各話リストの作画監督・脚本・絵コンテ・演出などを、季節ごとに書き出します。'),
         ('film_staff.html', 'アニメ映画スタッフ表', 'アニメ映画のスタッフを、公開年と役職で書き出します。')]
page('tools.html', 'ツール集', '<h1>ツール集</h1><p class="lead">番組・スタッフの基礎データを使った表とランキングです。</p><ul class="list tools">'
     + ''.join(f'<li><span class="title"><a href="{u}">{esc(t)}</a><span class="writer">{esc(d)}</span></span></li>' for u, t, d in TOOLS if os.path.exists(os.path.join(OUT, u)) or u == 'ranking.html')
     + '</ul>', current='tools.html')

# このサイトについて
about = open(D('content', 'about.md'), encoding='utf-8-sig').read() if os.path.exists(D('content', 'about.md')) else ''
page('about.html', 'このサイトについて', '<h1>このサイトについて</h1><div class="text">' + render_body(about, '', 2) + '</div>',
     crumbs=[(None, 'このサイトについて')], current='about.html')

n = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(OUT) for f in fs)
print(f'{n}ファイル　{size / 1e6:.1f}MB　番組{len(works)}・人{len(people)}・制作会社{len(studio_works)}・関連記事{len(all_links)}')
for m in warnings:
    print('注意:', m)
