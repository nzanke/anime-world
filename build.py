"""アニメ評論サイトを組み立てる（Python の標準ライブラリだけで動く）。

  python3 build.py            → _site/ にサイト一式を書き出す

読むもの
  data/works.tsv ほか      基礎データ（anime-database の tools/hyoron/export.py で書き出したもの）
  content/site.txt         サイト名・説明など
  content/about.md         「このサイトについて」の本文
  content/reviews/*.md     自分の評論（1本1ファイル。名前が _ で始まるファイルは読まない）
  content/links.csv        他人の評論・記事のリンク
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
    conf = {'サイト名': 'アニメ評論資料室', '説明': '', '筆者': ''}
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
    for part in re.split(r'[、／]', s or ''):
        part = re.sub(r'[（(][^）)]*[）)]', '', part).strip()
        part = re.sub(r'\s+', ' ', part)
        if part and part not in out and part not in ('-', '－', '―', '不明', '?'):
            out.append(part)
    return out

studios_of = {w: split_studio(works[w]['studio']) for w in works}
studio_works = defaultdict(list)
for w in order:
    for s in studios_of[w]:
        studio_works[s].append(w)

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

# ---------------------------------------------------------------- 評論・リンク
def parse_review(path):
    text = open(path, encoding='utf-8-sig').read().replace('\r\n', '\n')
    meta, body = {}, text
    m = re.match(r'---\n(.*?)\n---\n?(.*)', text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body

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

reviews = defaultdict(list)       # work → [review]
all_reviews = []
rdir = D('content', 'reviews')
for fn in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
    if not fn.endswith('.md') or fn.startswith('_'):
        continue
    meta, body = parse_review(os.path.join(rdir, fn))
    w = find_work(meta.get('番組ID', meta.get('work', '')), meta.get('番組', ''), f'reviews/{fn}')
    if not w:
        continue
    rv = {'work': w, 'title': meta.get('題名', meta.get('title', '')) or works[w]['title'],
          'date': meta.get('日付', meta.get('date', '')), 'body': body, 'file': fn,
          'note': meta.get('初出', '')}
    rv['anchor'] = 'r-' + re.sub(r'\W', '', os.path.splitext(fn)[0])[:40]
    reviews[w].append(rv)
    all_reviews.append(rv)
for w in reviews:
    reviews[w].sort(key=lambda r: r['date'])

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
KIND_ORDER = ['評論', '批評', 'インタビュー', '対談', '記事', 'コラム', '感想', '資料']
for w in links:
    links[w].sort(key=lambda r: (KIND_ORDER.index(r.get('種別')) if r.get('種別') in KIND_ORDER else 99, r.get('日付', '')))

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
NAV = [('index.html', 'トップ'), ('reviews.html', '評論'), ('links.html', '記事・評論リンク'),
       ('years/index.html', '年代別'), ('staff/index.html', 'スタッフ別'), ('studios/index.html', '制作会社別'),
       ('search.html', '番組名で探す'), ('about.html', 'このサイトについて')]
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDMincho&family=BIZ+UDPMincho:wght@400;700&family=BIZ+UDPGothic:wght@400;700&display=swap">')

def page(path, title, body, crumbs=(), current=None, desc='', script=''):
    depth = path.count('/')
    r = '../' * depth
    site = CONF['サイト名']
    nav = ''.join(f'<li{" class=cur" if u == current else ""}><a href="{r}{u}">{esc(t)}</a></li>' for u, t in NAV)
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
{FONTS}<link rel="stylesheet" href="{r}style.css"></head>
<body><div class="wrap">
<header class="site"><a class="sitename" href="{r}index.html">{esc(site)}</a></header>
<nav class="menu" aria-label="サイト内"><ul>{nav}</ul></nav>
<main>{cr}
{body.replace('{R}', r)}
</main>
<footer class="site"><p>番組・スタッフ・各話の基礎データは日本語版ウィキペディアの各記事{src}をもとに加工したもので、<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a> で提供します（<a href="{r}about.html#data">出典と加工について</a>）。評論の著作権は各筆者に属します。</p></footer>
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
    return f'<a href="{r}{S_URL[s]}">{esc(s)}</a>' if s in S_URL else esc(s)

def wlink(w, r='{R}'):
    return f'<a href="{r}w/{w}.html">{esc(works[w]["title"])}</a>'

def fmt_date(s):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s or '')
    if m:
        return f'{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日'
    m = re.match(r'(\d{4})-(\d{2})', s or '')
    return f'{int(m.group(1))}年{int(m.group(2))}月' if m else (s or '')

def period(w):
    a, b = works[w]['start_date'], works[w]['end_date']
    if not a:
        return '不明'
    return fmt_date(a) + ('' if b == a else ' ～ ' + (fmt_date(b) if b else ''))

def marks(w):
    m = ''
    if reviews.get(w):
        m += '<span class="mk" title="評論あり">評</span>'
    if links.get(w):
        m += f'<span class="mk2" title="記事・評論リンク">資{len(links[w])}</span>'
    return m

def roles_of(w, names):
    seen = []
    for r in staff.get(w, []):
        if r['role'] in names and r['person'] not in seen:
            seen.append(r['person'])
    return seen

def link_line(l, kind=False):
    """日付／題名／筆者／「媒体」（ないものは省く）"""
    t = esc(l.get('題名') or l.get('URL'))
    if l.get('URL'):
        t = f'<a href="{esc(l["URL"])}">{t}</a>'
    parts = [fmt_date(l.get('日付', '')), t, esc(l.get('筆者', '')), f'「{esc(l["媒体"])}」' if l.get('媒体') else '']
    if kind and l.get('種別'):
        parts.append(f'（{esc(l["種別"])}）')
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
open(os.path.join(OUT, '.nojekyll'), 'w').close()

# 番組ページ
EP_INLINE = 60
for w in order:
    wk = works[w]
    y = year_of(w)
    crumbs = [('years/index.html', '年代別')] + ([(f'years/{y}.html', f'{y}年')] if y else []) + [(None, wk['title'])]
    info = [('放送期間', period(w))]
    if studios_of[w]:
        info.append(('制作', '、'.join(slink(s) for s in studios_of[w])))
    for label, names in [('総監督', {'総監督'}), ('監督', {'監督'}), ('シリーズ構成', {'シリーズ構成'}),
                         ('キャラクターデザイン', {'キャラクターデザイン'}), ('原作', {'原作'})]:
        ps = roles_of(w, names)
        if ps:
            info.append((label, '、'.join(plink(p) for p in ps)))
    if episodes.get(w):
        info.append(('各話リスト', f'{len(episodes[w])}回分'))
    if wk['article']:
        art = wk['article'].split('｜')[0]
        info.append(('出典', f'ウィキペディア「<a href="https://ja.wikipedia.org/wiki/{esc(art.replace(" ", "_"))}">{esc(art)}</a>」'
                           f'（<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a>）'))
    body = [f'<h1>{esc(wk["title"])}</h1>',
            '<table class="info">' + ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in info) + '</table>']
    # 自分の評論
    body.append('<h2 id="hyoron">評論</h2>')
    if reviews.get(w):
        for rv in reviews[w]:
            body.append(f'<article class="review" id="{rv["anchor"]}"><h3>{esc(rv["title"])}</h3>'
                        f'<p class="meta">{fmt_date(rv["date"])}{"　" + esc(rv["note"]) if rv["note"] else ""}</p>'
                        f'<div class="text">{render_body(rv["body"], "{R}")}</div></article>')
    else:
        body.append('<p class="none">まだありません。</p>')
    # 他人の評論・記事
    body.append('<h2 id="links">評論・記事</h2>')
    if links.get(w):
        items, cur = [], None
        for l in links[w]:
            k = l.get('種別') or 'その他'
            if k != cur:
                if items: items.append('</ul>')
                items.append(f'<h3 class="kind">{esc(k)}</h3><ul class="links">'); cur = k
            ex = f'<blockquote>{esc(l["抜粋・メモ"])}</blockquote>' if l.get('抜粋・メモ') else ''
            items.append(f'<li>{link_line(l)}{ex}</li>')
        items.append('</ul>')
        body.append(''.join(items))
    else:
        body.append('<p class="none">まだありません。</p>')
    # スタッフ
    if staff.get(w):
        grp = {}
        for r in staff[w]:
            g = grp.setdefault(r['role_raw'], [])
            if r['kubun'] in COMPANY_KUBUN:
                x = slink(r['person'])
            else:
                x = plink(r['person'], cred=r['credited_as'] if r['credited_as'] and r['credited_as'] != r['person'] else None)
            if r['note']:
                x += f'<span class="note">（{esc(r["note"])}）</span>'
            if x not in g:
                g.append(x)
        body.append(fold('スタッフ', '<dl class="staff">' +
                    ''.join(f'<dt>{esc(k)}</dt><dd>{"、".join(v)}</dd>' for k, v in grp.items()) + '</dl>', len(grp), 'staff', '項目'))
    # 各話
    eps = episodes.get(w, [])
    if eps:
        used = [r for r in EP_ROLES if any(e[r] for e in eps)]
        segs = len({e['segment'] for e in eps}) > 1
        def ep_rows(rr):
            for e in eps:
                cells = [esc((e['segment'] + ' ' if segs and e['segment'] else '') + e['episode']),
                         esc(e['subtitle']), esc(fmt_date(e['air_date']))]
                for role in used:
                    cells.append('、'.join(plink(p, rr, cred or None) for p, cred in ep_names(e[role])))
                yield cells
        head = ['話数', 'サブタイトル', '放送日'] + used
        if len(eps) <= EP_INLINE:
            body.append(fold('各話スタッフ', table(head, ep_rows('{R}'), 'eps'), len(eps), 'eps', '回', limit=13))
        else:
            body.append(f'<h2 id="eps">各話スタッフ</h2><p><a href="{w}-eps.html">各話スタッフの一覧（{len(eps)}回分）</a></p>')
            page(f'w/{w}-eps.html', f'{wk["title"]} 各話スタッフ',
                 f'<h1>{esc(wk["title"])}　各話スタッフ</h1><p><a href="{w}.html">番組のページに戻る</a></p>' + table(head, ep_rows('{R}'), 'eps'),
                 crumbs=crumbs[:-1] + [(f'w/{w}.html', wk['title']), (None, '各話スタッフ')])
    page(f'w/{w}.html', wk['title'], '\n'.join(body), crumbs=crumbs,
         desc=f'{wk["title"]}（{period(w)}）の評論・記事とスタッフ')

# 年代別
years = defaultdict(list)
unknown = []
for w in order:
    y = year_of(w)
    (years[y] if y else unknown).append(w)
QUARTERS = [('1月～3月', (1, 3)), ('4月～6月', (4, 6)), ('7月～9月', (7, 9)), ('10月～12月', (10, 12))]
ylist = sorted(years)
for i, y in enumerate(ylist):
    parts = [f'<h1>{y}年に始まった番組</h1>',
             '<p class="pager">' + (f'<a href="{ylist[i-1]}.html">← {ylist[i-1]}年</a>' if i else '') +
             f'<span>{len(years[y])}番組</span>' + (f'<a href="{ylist[i+1]}.html">{ylist[i+1]}年 →</a>' if i + 1 < len(ylist) else '') + '</p>']
    for label, (a, b) in QUARTERS:
        ws = [w for w in years[y] if a <= int(works[w]['start_date'][5:7] or 0) <= b] if True else []
        if not ws:
            continue
        rows = [[esc(works[w]['start_date'][5:].replace('-', '/')), wlink(w) + marks(w),
                 '、'.join(slink(s) for s in studios_of[w]),
                 '、'.join(plink(p) for p in roles_of(w, {'総監督', '監督'}))] for w in ws]
        parts.append(fold(label, table(['開始', '番組', '制作', '監督'], rows, 'list'), len(rows), unit='番組', limit=60))
    page(f'years/{y}.html', f'{y}年の番組', '\n'.join(parts), crumbs=[('years/index.html', '年代別'), (None, f'{y}年')], current='years/index.html')
decs = defaultdict(list)
for y in ylist:
    decs[decade(y)].append(y)
parts = ['<h1>年代別</h1><p>放送が始まった年ごとの一覧です。数字は番組数。</p>']
for d, ys in decs.items():
    parts.append(f'<h2>{d}</h2><ul class="years">' + ''.join(f'<li><a href="{y}.html">{y}年</a><span>{len(years[y])}</span></li>' for y in ys) + '</ul>')
if unknown:
    parts.append('<h2>放送開始日が不明</h2><ul class="cols">' + ''.join(f'<li>{wlink(w)}</li>' for w in unknown) + '</ul>')
page('years/index.html', '年代別', '\n'.join(parts), crumbs=[(None, '年代別')], current='years/index.html')

# スタッフ（人のページ）
for p, ws in people.items():
    wl = sorted(ws, key=lambda w: (works[w]['start_date'] or '9999', w))
    def prow(w):
        rl = list(p_staff[p].get(w, []))
        for role in EP_ROLES:
            n = p_eps[p][w][role] if w in p_eps[p] else 0
            if n:
                rl.append(f'{role}<span class="n">（{n}話）</span>' if role not in rl else role)
        cred = p_cred[p].get(w)
        y = year_of(w)
        return [str(y or ''), wlink(w) + marks(w) + (f'<span class="cred">（{esc("・".join(sorted(cred)))}名義）</span>' if cred else ''),
                '、'.join(x if '<' in x else esc(x) for x in rl)]
    ys = [year_of(w) for w in wl if year_of(w)]
    summ = f'{len(wl)}番組' + (f'（{min(ys)}年～{max(ys)}年）' if ys else '')
    rc = Counter()
    for w in wl:
        for x in p_staff[p].get(w, []):
            rc[x] += 1
        for role in EP_ROLES:
            if w in p_eps[p] and p_eps[p][w][role]:
                rc['各話の' + role] += 1
    top = '、'.join(f'{esc(k)} {v}' for k, v in rc.most_common(6))
    page(P_URL[p], p, f'<h1>{esc(p)}</h1><table class="info"><tr><th>番組数</th><td>{summ}</td></tr>'
         f'<tr><th>主な役職</th><td>{top}</td></tr></table>'
         '<h2>担当した番組</h2>' + by_decade(wl, lambda ws: [prow(w) for w in ws], ['年', '番組', '役職']),
         crumbs=[('staff/index.html', 'スタッフ別'), (None, p)], current='staff/index.html')

ROLE_GROUPS = [
    ('director', '監督・総監督', ['監督', '総監督']),
    ('composition', 'シリーズ構成', ['シリーズ構成']),
    ('script', '脚本', ['脚本', '各話:脚本']),
    ('conte', '絵コンテ', ['絵コンテ', '各話:絵コンテ']),
    ('enshutsu', '演出', ['演出', '各話:演出']),
    ('chara', 'キャラクターデザイン', ['キャラクターデザイン', 'キャラクター原案']),
    ('mecha', 'メカニックデザイン', ['メカニックデザイン']),
    ('sakkan', '総作画監督・作画監督', ['総作画監督', '作画監督', '各話:総作画監督', '各話:作画監督']),
    ('art', '美術監督', ['美術監督']),
    ('color', '色彩設計', ['色彩設計']),
    ('photo', '撮影監督', ['撮影監督']),
    ('sound', '音響監督', ['音響監督']),
    ('music', '音楽', ['音楽']),
    ('original', '原作', ['原作']),
    ('producer', 'プロデューサー', ['プロデューサー', 'チーフプロデューサー', 'アニメーションプロデューサー']),
]
gl = []
for key, label, roles in ROLE_GROUPS:
    rowsp = []
    for p in people:
        ws = set().union(*[p_roles[p].get(r, set()) for r in roles])
        ys = [year_of(w) for w in ws if year_of(w)]
        if ws and ys:
            rowsp.append((min(ys), -len(ws), p, len(ws), max(ys)))
    if not rowsp:
        continue
    rowsp.sort()
    parts = [f'<h1>スタッフ別：{esc(label)}</h1><p>{len(rowsp)}人。初めてこの役職を担当した年の順に並べています（数字は番組数）。</p>']
    dmap = defaultdict(list)
    for r in rowsp:
        dmap[decade(r[0])].append(r)
    parts.append('<p class="jump">' + '　'.join(f'<a href="#d{d[:4]}">{d}</a>' for d in dmap) + '</p>')
    for d, rs in dmap.items():
        parts.append(fold(f'{d}から', '<ul class="names">' + ''.join(
            f'<li>{plink(p)}<span>{n}・{a}～{b}</span></li>' for a, _, p, n, b in rs) + '</ul>', len(rs), 'd' + d[:4], '人', limit=60))
    page(f'staff/{key}.html', label, '\n'.join(parts), crumbs=[('staff/index.html', 'スタッフ別'), (None, label)], current='staff/index.html')
    gl.append((key, label, len(rowsp)))
page('staff/index.html', 'スタッフ別',
     '<h1>スタッフ別</h1><p>役職ごとに、担当した人を年代順に並べています。人のページでは担当した番組を年代順に一覧できます（2番組以上を担当した人と、監督・シリーズ構成・キャラクターデザインを担当した人）。</p><ul class="menu-list">' +
     ''.join(f'<li><a href="{k}.html">{esc(l)}</a><span>{n}人</span></li>' for k, l, n in gl) + '</ul>',
     crumbs=[(None, 'スタッフ別')], current='staff/index.html')

# 制作会社
for s, ws in studio_works.items():
    srow = lambda ww: [[str(year_of(w) or ''), wlink(w) + marks(w), '、'.join(plink(p) for p in roles_of(w, {'総監督', '監督'}))] for w in ww]
    ys = [year_of(w) for w in ws if year_of(w)]
    page(S_URL[s], s, f'<h1>{esc(s)}</h1><p>{len(ws)}番組' + (f'（{min(ys)}年～{max(ys)}年）' if ys else '') + '</p>' +
         by_decade(ws, srow, ['年', '番組', '監督']), crumbs=[('studios/index.html', '制作会社別'), (None, s)], current='studios/index.html')
sl = sorted(studio_works, key=lambda s: (min([year_of(w) or 9999 for w in studio_works[s]]), s))
dmap = defaultdict(list)
for s in sl:
    y = min([year_of(w) or 9999 for w in studio_works[s]])
    dmap['不明' if y == 9999 else decade(y)].append(s)
parts = ['<h1>制作会社別</h1><p>最初の番組が始まった年代ごとに並べています（数字は番組数）。共同制作は両方の会社に入ります。</p>',
         '<p class="jump">' + '　'.join(f'<a href="#d{d[:4]}">{d}</a>' for d in dmap) + '</p>']
for d, ss in dmap.items():
    parts.append(fold(f'{d}から', '<ul class="names">' + ''.join(f'<li>{slink(s)}<span>{len(studio_works[s])}</span></li>' for s in ss) + '</ul>', len(ss), 'd' + d[:4], '社', limit=60))
page('studios/index.html', '制作会社別', '\n'.join(parts), crumbs=[(None, '制作会社別')], current='studios/index.html')

# 評論の一覧・リンク集
rows = sorted(all_reviews, key=lambda r: r['date'], reverse=True)
parts = ['<h1>評論</h1>']
if rows:
    parts.append('<ul class="rlist">' + ''.join(
        f'<li><span class="d">{fmt_date(r["date"])}</span><a href="w/{r["work"]}.html#{r["anchor"]}">{esc(r["title"])}</a>'
        f'<span class="w">{esc(works[r["work"]]["title"])}</span></li>' for r in rows) + '</ul>')
else:
    parts.append('<p class="none">まだありません。</p>')
page('reviews.html', '評論', '\n'.join(parts), crumbs=[(None, '評論')], current='reviews.html')

lw = sorted({l['work'] for l in all_links}, key=lambda w: (works[w]['start_date'] or '9999'))
parts = [f'<h1>記事・評論リンク</h1><p>{len(all_links)}件。番組の放送順です。</p>']
for w in lw:
    parts.append(f'<h2>{wlink(w)}<span class="sub">{esc(str(year_of(w) or ""))}</span></h2><ul class="links">' + ''.join(
        f'<li>{link_line(l, True)}</li>' for l in links[w]) + '</ul>')
if not lw:
    parts.append('<p class="none">まだありません。</p>')
page('links.html', '記事・評論リンク', '\n'.join(parts), crumbs=[(None, '記事・評論リンク')], current='links.html')

# 番組名で探す
with open(os.path.join(OUT, 'titles.json'), 'w', encoding='utf-8') as f:
    json.dump([[w, works[w]['title'], year_of(w) or '', 1 if reviews.get(w) else 0] for w in order], f, ensure_ascii=False, separators=(',', ':'))
SEARCH_JS = '''<script>
(function(){var q=document.getElementById('q'),o=document.getElementById('res'),d=null;
function norm(s){return s.normalize('NFKC').toLowerCase().replace(/[\\s・!！?？:：\\-－〜～☆★♪]/g,'').replace(/[ァ-ン]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-96)})}
function run(){if(!d)return;var k=norm(q.value);if(!k){o.innerHTML='';return}
var h=[];for(var i=0;i<d.length&&h.length<200;i++){if(d[i][4].indexOf(k)>=0)h.push(d[i])}
o.innerHTML=h.length?h.map(function(x){return '<li><a href="w/'+x[0]+'.html">'+x[1].replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})+'</a><span>'+x[2]+(x[3]?'　<b class="mk">評</b>':'')+'</span></li>'}).join(''):'<li>見つかりません</li>'}
fetch('titles.json').then(function(r){return r.json()}).then(function(j){d=j;j.forEach(function(x){x[4]=norm(x[1])});run()});
q.addEventListener('input',run);})();
</script>'''
page('search.html', '番組名で探す', '<h1>番組名で探す</h1><p><input id="q" type="search" placeholder="番組名の一部（ひらがな・カタカナどちらでも）" autofocus></p><ul id="res" class="names"></ul>',
     crumbs=[(None, '番組名で探す')], current='search.html', script=SEARCH_JS)

# このサイトについて
about = open(D('content', 'about.md'), encoding='utf-8-sig').read() if os.path.exists(D('content', 'about.md')) else ''
page('about.html', 'このサイトについて', '<h1>このサイトについて</h1><div class="text">' + render_body(about, '', 2) + '</div>',
     crumbs=[(None, 'このサイトについて')], current='about.html')

# トップ
news = sorted([(r['date'], 'r', r) for r in all_reviews] + [(l.get('日付', ''), 'l', l) for l in all_links], key=lambda x: x[0], reverse=True)[:15]
nl = []
for d, t, x in news:
    if t == 'r':
        nl.append(f'<li><span class="d">{fmt_date(d)}</span><b class="mk">評</b><a href="w/{x["work"]}.html#{x["anchor"]}">{esc(x["title"])}</a><span class="w">{esc(works[x["work"]]["title"])}</span></li>')
    else:
        nl.append(f'<li><span class="d">{fmt_date(d)}</span><b class="mk2">資</b><a href="w/{x["work"]}.html#links">{esc(x.get("題名", ""))}</a><span class="w">{esc(works[x["work"]]["title"])}</span></li>')
rw = sorted(reviews, key=lambda w: works[w]['start_date'] or '9999')
top = [f'<h1 class="top">{esc(CONF["サイト名"])}</h1>']
if CONF.get('説明'):
    top.append(f'<p class="lead">{esc(CONF["説明"])}</p>')
top.append('<h2>入口</h2><ul class="menu-list">'
           f'<li><a href="years/index.html">年代別</a><span>{len(ylist)}年・{len(works)}番組</span></li>'
           f'<li><a href="staff/index.html">スタッフ別</a><span>{len(people)}人</span></li>'
           f'<li><a href="studios/index.html">制作会社別</a><span>{len(studio_works)}社</span></li>'
           '<li><a href="search.html">番組名で探す</a></li></ul>')
top.append('<h2>新着</h2>' + (f'<ul class="rlist">{"".join(nl)}</ul>' if nl else '<p class="none">まだありません。</p>'))
if rw:
    top.append('<h2>評論のある番組</h2><ul class="names">' + ''.join(f'<li>{wlink(w, "")}<span>{year_of(w) or ""}</span></li>' for w in rw) + '</ul>')
page('index.html', CONF['サイト名'], '\n'.join(top), current='index.html', desc=CONF.get('説明', ''))

n = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(OUT) for f in fs)
print(f'{n}ファイル　{size / 1e6:.1f}MB　番組{len(works)}・人{len(people)}・制作会社{len(studio_works)}・評論{len(all_reviews)}・リンク{len(all_links)}')
for m in warnings:
    print('注意:', m)
