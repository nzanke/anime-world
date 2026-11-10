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
NAV = [('index.html', 'インタビュー'), ('column.html', 'レビュー'), ('ranking.html', 'スタッフランキング'), ('about.html', 'このサイトについて')]
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
index = {'items': auto, 'works': {w: [works[w]['title'], year_of(w) or ''] for w in used_w if w in works}}
with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, separators=(',', ':'))
IDX_V = hashlib.sha1(json.dumps(index, ensure_ascii=False).encode('utf-8')).hexdigest()[:8]
art_count = Counter(p for e in auto for p in e.get('p', []))

# ---------------------------------------------------------------- 記事検索（インタビュー＝トップ、コラム＝別ページ）
IS_IV = lambda e: (e.get('k') or 'インタビュー') == 'インタビュー'
def search_page(path, mode, h1, lead, ph):
    L = [e for e in auto if IS_IV(e) == (mode == 'interview')]
    sites = [x for x, _ in Counter(e['s'] for e in L).most_common()]
    kinds = [x for x, _ in Counter(e['k'] for e in L).most_common()]
    ksel = '' if mode == 'interview' else '<select id="kind"><option value="">すべての種類</option>' + ''.join(f'<option>{esc(x)}</option>' for x in kinds) + '</select>'
    page(path, h1 if path != 'index.html' else CONF['サイト名'], f'''<h1>{esc(h1)}</h1>
<p class="lead">{esc(lead)}</p>
<div class="sbar"><input type="search" id="q" placeholder="{esc(ph)}" autofocus>
<select id="site"><option value="">すべてのサイト</option>{"".join(f'<option>{esc(x)}</option>' for x in sites)}</select>{ksel}</div>
<div class="opts"><label><input type="checkbox" id="old"> 古い順</label></div>
<p class="count" id="count"></p>
<ul class="list" id="list"></ul>
<button class="more" id="more" hidden>さらに表示</button>''', current=path,
         script=f'<script>window.IDX="index.json?v={IDX_V}";window.MODE="{mode}"</script><script src="search.js?v={SEARCH_V}"></script>')

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
TOP = 50
parts = ['<h1>スタッフランキング</h1><p class="lead">年代ごとに、その年代に始まったテレビアニメに多く関わったスタッフを並べています（数字は番組数。スタッフ欄と各話リストの脚本・絵コンテ・演出・作画監督から数えています）。名前を押すと、その人が出てくる記事を検索します。</p>']
decs = sorted(dec_works)
for d in decs:
    ranked = sorted(dec_works[d].items(), key=lambda x: (-len(x[1]), x[0]))[:TOP]
    rows = ''.join(f'<li><span class="date">{i}</span><span class="title"><a href="index.html?q={esc(p)}">{esc(p)}</a>'
                   f'<span class="writer">{esc("・".join(r for r, _ in dec_roles[d][p].most_common(2)))}</span></span>'
                   f'<span class="num">{len(ws)}番組</span><span class="art">{f"記事{art_count[p]}" if art_count.get(p) else ""}</span></li>'
                   for i, (p, ws) in enumerate(ranked, 1))
    parts.append(f'<details class="grp"{" open" if d == decs[-1] else ""}><summary>{d}<span class="n">上位{len(ranked)}人</span></summary><ul class="list rank">{rows}</ul></details>')
page('ranking.html', 'スタッフランキング', '\n'.join(parts), current='ranking.html')


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

# このサイトについて
about = open(D('content', 'about.md'), encoding='utf-8-sig').read() if os.path.exists(D('content', 'about.md')) else ''
page('about.html', 'このサイトについて', '<h1>このサイトについて</h1><div class="text">' + render_body(about, '', 2) + '</div>',
     crumbs=[(None, 'このサイトについて')], current='about.html')

n = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(OUT) for f in fs)
print(f'{n}ファイル　{size / 1e6:.1f}MB　番組{len(works)}・人{len(people)}・制作会社{len(studio_works)}・関連記事{len(all_links)}')
for m in warnings:
    print('注意:', m)
