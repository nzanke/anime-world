"""配信カレンダー：購読用の .ics を作る（build.py から呼ぶ）
  選んだサービスの中で、各話をいちばん早く見られる日時を予定にする。
  設定は content/haishin_my.json：{"services": [...], "works": [作品ID...] または "all"}
"""
import datetime as dt

JST = dt.timezone(dt.timedelta(hours=9))

def esc(s):
    return s.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

def fold(line):
    b = line.encode('utf-8')
    if len(b) <= 74: return line
    out, cur = [], b''
    for ch in line:
        c = ch.encode('utf-8')
        if len(cur) + len(c) > 73: out.append(cur.decode('utf-8')); cur = b' '
        cur += c
    out.append(cur.decode('utf-8'))
    return '\r\n'.join(out)

def episodes(work, services):
    """選んだサービスで、話ごとにいちばん早い配信 [(日時, 話数, サービス, 確か, ほかのサービス)]"""
    by = {}
    for svc, t, n, sure in work['e']:
        if svc in services: by.setdefault(n, []).append((t, svc, sure))
    out = []
    for n, lst in by.items():
        lst.sort()
        t, svc, sure = lst[0]
        out.append((t, n, svc, sure, lst[1:]))
    return sorted(out)

def make_ics(sched, my, page_url):
    names = dict(sched['services'])
    services = set(my.get('services') or [])
    sel = my.get('works') or []
    now = dt.datetime.now(JST)
    stamp = now.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//nzanke//anime-haishin//JA', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
         'X-WR-CALNAME:アニメ配信カレンダー', 'X-WR-TIMEZONE:Asia/Tokyo', 'REFRESH-INTERVAL;VALUE=DURATION:PT12H', 'X-PUBLISHED-TTL:PT12H']
    for w in sched['works']:
        if sel != 'all' and w['id'] not in sel: continue
        for t, n, svc, sure, others in episodes(w, services):
            st = dt.datetime.fromisoformat(t).replace(tzinfo=JST)
            if st < now - dt.timedelta(days=7): continue
            ep = f' 第{n}話' if sure and n is not None and n < 1000 else ''
            desc = f'{names.get(svc, svc)}がいちばん早い（{t[5:].replace("T", " ")}）'
            if others:
                desc += '\nほか：' + '、'.join(f'{names.get(s, s)} {x[5:].replace("T", " ")}' for x, s, _ in others[:6])
            desc += f'\n{page_url}'
            u = st.astimezone(dt.timezone.utc)
            L += ['BEGIN:VEVENT', f'UID:{w["id"]}-{n}@nzanke.github.io', f'DTSTAMP:{stamp}',
                  'DTSTART:' + u.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:' + (u + dt.timedelta(minutes=30)).strftime('%Y%m%dT%H%M%SZ'),
                  fold('SUMMARY:' + esc(f'{w["t"]}{ep}（{names.get(svc, svc).replace("tv:", "")}）')),
                  fold('DESCRIPTION:' + esc(desc)), 'END:VEVENT']
    L.append('END:VCALENDAR')
    return '\r\n'.join(L) + '\r\n'
