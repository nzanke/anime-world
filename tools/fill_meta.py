"""links.csv で題名が空の行について、URL のページを読みに行き、題名・筆者・媒体・日付を埋める。
GitHub Actions（サイトの組み立ての前）で動く。読めなかった行はそのまま（次の組み立てでもう一度試す）。
標準ライブラリだけで動く。  python3 tools/fill_meta.py [links.csv]
"""
import csv, html, io, json, re, sys, urllib.request
from html.parser import HTMLParser

PATH = sys.argv[1] if len(sys.argv) > 1 else 'content/links.csv'
UA = 'Mozilla/5.0 (compatible; anime-world-linkbot/1.0; +https://nzanke.github.io/anime-world/)'

class Meta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self._t, self.ld, self._ld, self.times = {}, '', False, [], False, []
        self._tm = None   # 日時の属性がない <time> の中の文字（「2026.」「10.22」と分かれていても続けて読む）
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == 'meta':
            k = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if k and a.get('content') and k not in self.meta:
                self.meta[k] = a['content'].strip()
        elif tag == 'title': self._t = True
        elif tag == 'script' and (a.get('type') or '').lower() == 'application/ld+json': self._ld = True; self.ld.append('')
        elif tag == 'time':
            if a.get('datetime'): self.times.append(a['datetime'])
            else: self._tm = ''
    def handle_endtag(self, tag):
        if tag == 'title': self._t = False
        if tag == 'time' and self._tm is not None: self.times.append(self._tm.strip()); self._tm = None
        if tag == 'script': self._ld = False
    def handle_data(self, d):
        if self._t: self.title += d
        if self._tm is not None: self._tm += d.strip()
        if self._ld: self.ld[-1] += d

def pick_date(s):
    m = re.search(r'(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})', s or '')
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''

def parse(raw, url):
    p = Meta(); p.feed(raw)
    m = p.meta
    site = m.get('og:site_name', '')
    t = m.get('og:title') or (re.search(r'dc:title="([^"]+)"', raw) or [None, ''])[1] or p.title
    t = html.unescape(t).strip()
    if site:
        t = re.sub(r'\s*[:：|｜\-－]\s*' + re.escape(site) + r'\s*$', '', t)
        t = re.sub(r'^' + re.escape(site) + r'\s*[:：|｜\-－]\s*', '', t)   # 「TBS INNOVATION LAND | 題名」のように頭に付く場合
    ld_date = ld_author = ''
    for block in p.ld:
        try:
            j = json.loads(block)
        except Exception:
            continue
        for o in (j if isinstance(j, list) else [j]):
            if isinstance(o, dict):
                ld_date = ld_date or o.get('datePublished', '')
                a = o.get('author')
                if a and not ld_author:
                    a = a[0] if isinstance(a, list) else a
                    ld_author = a.get('name', '') if isinstance(a, dict) else str(a)
    author = m.get('author') or m.get('article:author') or ld_author or (re.search(r'dc:creator="([^"]+)"', raw) or [None, ''])[1] \
        or (re.search(r'posted by\s*([^<|｜\s]+)', raw, re.I) or [None, ''])[1]
    if author.startswith('http'): author = ''
    date = pick_date(m.get('article:published_time')) or pick_date(ld_date) or pick_date((re.search(r'dc:date="([^"]+)"', raw) or [None, ''])[1]) \
        or pick_date(p.times[0] if p.times else '') or pick_date((re.search(r'\d{4}年\d{1,2}月\d{1,2}日', re.sub(r'<[^>]+>', ' ', raw)) or [''])[0])
    return {'題名': t, '筆者': html.unescape(author).strip(), '媒体': html.unescape(site).strip(), '日付': date}

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.5'})
    with urllib.request.urlopen(req, timeout=20) as r:
        b = r.read(3_000_000)
        cs = r.headers.get_content_charset()
    for enc in [x for x in ('utf-8', cs, (re.search(rb'charset=["\']?([\w-]+)', b[:4000]) or [None, b''])[1].decode() or None, 'cp932') if x]:
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode('utf-8', 'replace')

def main():
    with open(PATH, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    head = rows[0]; ix = {k: i for i, k in enumerate(head)}
    changed = 0
    for r in rows[1:]:
        r += [''] * (len(head) - len(r))
        url = r[ix['URL']].strip()
        if not url or r[ix['題名']].strip():
            continue
        try:
            got = parse(fetch(url), url)
        except Exception as e:
            print('読めませんでした:', url, e); continue
        for k, v in got.items():
            if v and not r[ix[k]].strip():
                r[ix[k]] = v
        changed += 1
        print('埋めました:', url, got)
    if changed:
        out = io.StringIO(); csv.writer(out, lineterminator='\n').writerows(rows)
        open(PATH, 'w', encoding='utf-8', newline='').write(out.getvalue())
    print(changed, '行')

if __name__ == '__main__':
    main()
