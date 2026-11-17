import json, sys
sys.path.insert(0, 'tools/haishin')
import official as O
d = json.load(open('probe/official.json'))
thin = [v for v in d.values() if O.thin(v)]
print('薄いサイト', len(thin))
n = O.render(thin)
print('読み直せた', n)
json.dump(d, open('probe/official.json', 'w'), ensure_ascii=False)
for v in thin: print(v['status'], v['title'][:20], [len(p['text']) for p in v['pages']])
