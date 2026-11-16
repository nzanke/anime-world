// 記事検索：index.json（題名・サイト・日付・種類・番組・スタッフ）を読み、その場で絞り込む。
// 見た目は「放送・公開前のアニメ」と同じ（月ごとの見出し、日にちと印、題名は折り返して全部出す）
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var lastBase = [];
  var PAGE = 200, all = [], works = {}, res = [], shown = 0, sel = '', lastGroup = '';
  var IV = window.MODE !== 'column', ICONS = window.ICONS || {};
  var WD = '日月火水木金土';
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  function hash(k) { var h = 0; for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 360; return h; }
  function icon(name) { var x = ICONS[name] || [name.slice(0, 1), hash(name)]; return x; }
  // レビュー検索は種類で分けない：媒体名の頭2文字・1色（媒体名がなければ「記」）
  function eicon(e) { if (!IV) { var sn = site(e); return [sn && sn !== 'その他' ? sn.slice(0, 2) : '記', 25]; } var g = SG[site(e)]; return [g ? g[1] : site(e).slice(0, 2), GH[genre(e)] || 150]; }
  function phue(k) { return IV ? (GH[k] || 150) : icon(k)[1]; }
  // インタビューは媒体のジャンルで絞り込み・色分けし、媒体は選択欄で選ぶ。レビューは種類で
  var GH = {}; (window.GENRES || []).forEach(function (g) { GH[g[0]] = g[1]; });
  var SG = window.SITE_GENRE || {};
  function site(e) { return String(e.s || '').replace(/[（(].*$/, '').trim(); }   // 「MANTANWEB（まんたんウェブ）」→「MANTANWEB」
  function genre(e) { return (SG[site(e)] || ['カルチャー・その他'])[0]; }
  var key = function (e) { return IV ? genre(e) : (e.k === '評論' ? 'レビュー' : e.k); };   // 絞り込みのボタンの単位
  function day(e) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(e.d || '');
    if (!m) return '<span class="dq">—</span>';
    return +m[3] + '<small>' + WD[new Date(+m[1], +m[2] - 1, +m[3]).getDay()] + '</small>';
  }
  function group(e) { var m = /^(\d{4})-(\d{2})/.exec(e.d || ''); return m ? m[1] + '年' + (+m[2]) + '月' : '日付なし'; }
  // レビュー検索の連載タグ：題名から連載名を見分ける（連載を足すときはここに1行）
  // ［連載名, 題名で見分ける形, 書き手（選択パネルの段）］
  var SERIES = [['帰ってきたアニメの門', /帰ってきたアニメの門/, '藤津亮太'], ['四代目アニメの門', /四代目\s*アニメの門/, '藤津亮太'],
    ['アニメの門V', /アニメの門\s*V|藤津亮太のアニメの門\s*第\d/, '藤津亮太'],   // 「藤津亮太のアニメの門 第◯回」は公式の誤表記で、アニメの門V
    ['高瀬司のアニメ時評宣言', /アニメ時評宣言/, '高瀬司'],
    ['前Qの「いいアニメを見に行こう」', /いいアニメを見に(?:行|い)こう/, '前田久'],
    ['氷川竜介の「アニメに歴史あり」', /アニメに歴史あり/, '氷川竜介'],
    ['週末批評', null, '週末批評', '週末批評'],
    ['野の百合、空の鳥', null, '野の百合、空の鳥', '野の百合、空の鳥'],
    ['アニ録ブログ', null, 'アニ録ブログ', 'アニ録ブログ']];   // 4つ目があるものは題名ではなく媒体（サイト）単位でまとめる。選ぶボタンでは筆者の代わりにサイト名で束ねる
  var NOSER = '連載以外';
  function series(e) { if (IV) return ''; for (var i = 0; i < SERIES.length; i++) if (SERIES[i][3] ? e.s === SERIES[i][3] : SERIES[i][1].test(e.t || '')) return SERIES[i][0]; return ''; }
  // 一覧に出すタグ：作品は題名に関係するもの（最大6つ）、人は題名に出てくる人。手で直した記事（e.ed）はその内容をそのまま
  function shownW(e) { return (e.w || []).slice(0, e.ed ? e.wt : Math.min(6, e.wt == null ? 6 : e.wt)); }
  function shownP(e) { return e.ed ? (e.pt || []) : (e.p || []).filter(function (p) { return norm(e.t).indexOf(norm(p)) >= 0; }); }
  var TOKEN = ''; try { TOKEN = localStorage.getItem('gh-token') || ''; } catch (x) {}
  // 鉛筆ボタンは、鍵があるブラウザか、アドレスの最後に ?edit を付けたときだけ出す（ふつうの訪問者には見せない）
  var EDIT = !!TOKEN || /[?&]edit\b/.test(location.search);
  function row(e) {
    var sr = series(e);
    var tags = (sr ? '<a class="tg ts" data-q="' + esc(sr) + '">' + esc(sr) + '</a>' : '') + shownW(e).map(function (w) { var x = works[w]; return x ? '<a class="tg tw" data-q="' + esc(x[0]) + '">' + esc(x[0]) + '</a>' : ''; }).join('') +
      shownP(e).map(function (p) { return '<a class="tg tp" data-q="' + esc(p) + '">' + esc(p) + '</a>'; }).join('') +
      (e.x || []).map(function (x) { return '<a class="tg tx" data-q="' + esc(x) + '">' + esc(x) + '</a>'; }).join('');
    var ic = eicon(e);
    var meta = IV ? (e.a || '') : e.s + (e.a ? '／' + e.a : '');
    return '<li class="ur sr"><span class="ud">' + day(e) + '</span>' +
      '<span class="ic" style="--h:' + ic[1] + '" title="' + esc(IV ? e.s : e.k) + '">' + esc(ic[0]) + '</span>' +
      '<span class="sb"><a class="un" href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
      (EDIT ? '<button type="button" class="ed" data-u="' + esc(e.u) + '" title="タグを編集" aria-label="タグを編集">✎</button>' : '') +
      (e.c && IV ? '<span class="sq" title="キャスト（声優）のインタビュー">声</span>' : '') +
      (tags ? '<span class="tags">' + tags + '</span>' : '') + '</span>' +
      (meta ? '<span class="st">' + esc(meta) + '</span>' : '') + '</li>';
  }
  function render(more) {
    if (!more) { $('list').innerHTML = ''; shown = 0; lastGroup = ''; }
    var html = '';
    res.slice(shown, shown + PAGE).forEach(function (e) {
      var g = group(e); if (g !== lastGroup) { html += '<li class="ug">' + esc(g) + '</li>'; lastGroup = g; }
      html += row(e);
    });
    $('list').insertAdjacentHTML('beforeend', html);
    shown = Math.min(shown + PAGE, res.length);
    $('more').hidden = shown >= res.length;
  }
  function pills(base) {
    var n = {}; base.forEach(function (e) { n[key(e)] = (n[key(e)] || 0) + 1; });
    var GO = (window.GENRES || []).map(function (g) { return g[0]; });
    var names = Object.keys(n).sort(function (a, b) { return IV ? GO.indexOf(a) - GO.indexOf(b) : n[b] - n[a]; });   // ジャンルは決まった順
    $('seg').innerHTML = '<button type="button" data-c="" style="--h:250"' + (sel ? '' : ' class="on"') + '>すべて<span class="n"> ' + base.length.toLocaleString() + '</span></button>' +
      names.map(function (k) { return '<button type="button" data-c="' + esc(k) + '" style="--h:' + phue(k) + '"' + (sel === k ? ' class="on"' : '') + '>' + esc(k) + '<span class="n"> ' + n[k].toLocaleString() + '</span></button>'; }).join('');
  }
  // 媒体の選択パネル：ジャンルごとの行に、媒体を小さな札で横に並べる（縦に長くしない）。何も選ばなければすべて
  // 選択パネル：インタビュー検索は媒体（段はジャンル）、レビュー検索は連載（段は書き手）
  var PK = IV ? 'media-pick' : 'series-pick';
  function pkey(e) { return IV ? site(e) : (series(e) || NOSER); }
  var pick = {};
  try { (JSON.parse(localStorage.getItem(PK) || '[]')).forEach(function (x) { pick[x] = 1; }); } catch (x) {}
  function picked() { return Object.keys(pick); }
  function mlabel() {
    var p = picked();
    $('mbtn').textContent = (IV ? '媒体：' : '連載：') + (!p.length ? 'すべて' : p.length === 1 ? p[0] : p.length + 'つ') + ' ▾';
    $('mbtn').classList.toggle('on', p.length > 0);
  }
  function mgroups(n) {   // ［段の名前, 色, その段の選択肢］
    if (!IV) {
      var gs = [];
      SERIES.forEach(function (x) { if (!n[x[0]]) return; var g = gs.filter(function (y) { return y[0] === x[2]; })[0]; if (!g) gs.push(g = [x[2], 25, []]); g[2].push(x[0]); });
      if (n[NOSER]) gs.push(['その他', 70, [NOSER]]);
      return gs;
    }
    return (window.GENRES || []).map(function (g) {
      return [g[0], g[1], Object.keys(SG).concat(Object.keys(n)).filter(function (x, i, a) { return a.indexOf(x) === i && (SG[x] || ['カルチャー・その他'])[0] === g[0] && n[x]; })
        .sort(function (a, b) { return n[b] - n[a]; })];
    });
  }
  function mpanel(base) {
    var n = {}; base.forEach(function (e) { var k = pkey(e); n[k] = (n[k] || 0) + 1; });
    var html = '<div class="mtop"><button type="button" data-a="all">すべて選ぶ</button><button type="button" data-a="none">選ぶのをやめる（すべて）</button><button type="button" data-a="close" class="mx" aria-label="閉じる">×</button></div>';
    mgroups(n).forEach(function (g) {
      var ss = g[2];
      if (!ss.length) return;
      html += '<div class="mrow"><button type="button" class="mg" data-g="' + esc(g[0]) + '" style="--h:' + g[1] + '" title="' + (IV ? 'このジャンル' : 'この書き手の連載') + 'をまとめて選ぶ・外す">' + esc(g[0]) + '</button><div class="mchips">' +
        ss.map(function (x) {
          return '<button type="button" class="mc' + (pick[x] ? ' on' : '') + '" data-s="' + esc(x) + '" style="--h:' + g[1] + '">' + esc(x) + '<span class="n">' + n[x].toLocaleString() + '</span></button>';
        }).join('') + '</div></div>';
    });
    $('mpop').innerHTML = html;
  }
  function msave() { try { localStorage.setItem(PK, JSON.stringify(picked())); } catch (x) {} }
  function search() {
    var terms = $('q').value.split(/\s+/).map(norm).filter(Boolean);
    var cast = !$('cast') || $('cast').checked;   // キャスト（声優）のインタビューを出すか
    try { if ($('cast')) localStorage.setItem('show-cast', cast ? '1' : '0'); } catch (x) {}
    var scope = (document.querySelector('input[name=scope]:checked') || {}).value || 'tag';
    try { localStorage.setItem('search-scope', scope); } catch (x) {}
    var F = scope === 'title' ? '_ti' : scope === 'all' ? '_t' : '_tg';
    var base = all.filter(function (e) { return (cast || !e.c) && terms.every(function (t) { return e[F].indexOf(t) >= 0; }); });
    var p = $('mbtn') ? picked() : [];
    if ($('mbtn')) { mlabel(); if (!$('mpop').hidden) mpanel(base); lastBase = base; }
    var base2 = base.filter(function (e) { return !p.length || pick[pkey(e)]; });
    if ($('seg')) pills(base2);
    res = base2.filter(function (e) { return !sel || key(e) === sel; });
    if ($('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + ' 件 / 全 ' + all.length.toLocaleString() + ' 件';
    render(false);
    try { history.replaceState(null, '', $('q').value ? '?q=' + encodeURIComponent($('q').value) : location.pathname); } catch (x) {}
  }
  fetch(window.IDX).then(function (r) { return r.json(); }).then(function (j) {
    all = j.items.filter(function (e) { return ((e.k || 'インタビュー') === 'インタビュー') === IV; }); works = j.works;
    all.forEach(function (e) {
      // 探す範囲：題名だけ（_ti）／題名と表示中のタグ（_tg）／本文に出てくる作品・人まで（_t）
      keys(e);
    });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
  // 探す範囲：題名だけ（_ti）／題名と表示中のタグ（_tg）／本文に出てくる作品・人まで（_t）
  function keys(e) {
      var tw = (e.ed ? shownW(e) : (e.w || []).slice(0, e.wt == null ? 10 : e.wt)).map(function (w) { return works[w] ? works[w][0] : ''; });
      var tp = shownP(e).concat(e.x || []);
      e._ti = norm(e.t);
      e._tg = norm([e.t, e.s, e.a, series(e), tw.join(' '), tp.join(' ')].join(' '));
      e._t = norm([e.t, e.s, e.a, series(e), (e.x || []).join(' '), (e.w || []).map(function (w) { return works[w] ? works[w][0] : ''; }).join(' '), (e.p || []).join(' ')].join(' '));
  }
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  try { if ($('cast') && localStorage.getItem('show-cast') === '0') $('cast').checked = false; } catch (x) {}
  try { var sc = localStorage.getItem('search-scope'); if (sc) { var r = document.querySelector('input[name=scope][value=' + sc + ']'); if (r) r.checked = true; } } catch (x) {}
  [].forEach.call(document.querySelectorAll('input[name=scope]'), function (r) { r.addEventListener('change', search); });
  ['old', 'cast'].forEach(function (id) { if ($(id)) $(id).addEventListener('change', search); });
  if ($('seg')) $('seg').addEventListener('click', function (ev) { var b = ev.target.closest('button'); if (!b) return; sel = b.getAttribute('data-c'); search(); });
  if ($('mbtn')) {
    var open = function (on) { $('mpop').hidden = !on; $('mbtn').setAttribute('aria-expanded', on ? 'true' : 'false'); if (on) mpanel(lastBase); };
    $('mbtn').addEventListener('click', function (ev) { ev.stopPropagation(); open($('mpop').hidden); });
    $('mpop').addEventListener('click', function (ev) {
      ev.stopPropagation();
      var b = ev.target.closest('button'); if (!b) return;
      var a = b.getAttribute('data-a'), sname = b.getAttribute('data-s'), g = b.getAttribute('data-g');
      if (a === 'close') { open(false); return; }
      if (a === 'none') pick = {};
      if (a === 'all') [].forEach.call($('mpop').querySelectorAll('.mc'), function (c) { pick[c.getAttribute('data-s')] = 1; });
      if (sname) { if (pick[sname]) delete pick[sname]; else pick[sname] = 1; }
      if (g) {   // ジャンルの名前を押すと、その行をまとめて選ぶ（全部選ばれていれば外す）
        var cs = [].map.call(b.parentNode.querySelectorAll('.mc'), function (c) { return c.getAttribute('data-s'); });
        var allOn = cs.every(function (x) { return pick[x]; });
        cs.forEach(function (x) { if (allOn) delete pick[x]; else pick[x] = 1; });
      }
      msave(); search();
    });
    document.addEventListener('click', function () { if (!$('mpop').hidden) open(false); });
    document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && !$('mpop').hidden) { open(false); $('mbtn').focus(); } });
  }
  $('more').addEventListener('click', function () { render(true); });
  $('list').addEventListener('click', function (ev) {
    var b = ev.target.closest('.ed'); if (b) { ev.preventDefault(); ev.stopPropagation(); edOpen(b.getAttribute('data-u')); return; }
    var a = ev.target.closest('.tg'); if (!a) return;
    ev.preventDefault(); $('q').value = a.getAttribute('data-q'); search(); window.scrollTo(0, 0);
  });

  // ---------------------------------------------------------------- タグの編集（鍵を入れたブラウザだけ）
  // 保存先：content/tag_edits.json（{URL: {"w": [作品番号], "p": [人の名前]}}）。公開のときに索引に反映される
  var TN = null, TNW = [], TNP = [], TNX = [], ed = null, LAST = null;   // LAST：自分が最後に保存した版
  function kana(s) { return norm(s).replace(/[\u30a1-\u30f6]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x60); }); }   // カタカナ→ひらがな
  function loadNames() {
    if (TN) return TN;
    TN = fetch('tagnames.json').then(function (r) { return r.json(); }).then(function (j) {
      TNW = j.w.map(function (x) { return { id: x[0], t: x[1], y: x[2], n: x[3], k: kana(x[1]) }; });
      TNP = j.p.map(function (x) { return { t: x[0], n: x[1], k: kana(x[0]) }; });
      TNX = (j.x || []).map(function (x) { return { t: x[0], n: x[1], k: kana(x[0]) }; });
    });
    return TN;
  }
  function suggest(q) {   // 完全に一致するもの → 記事の多いもの → 頭が合うもの の順
    var k = kana(q); if (!k) return [];
    var out = [], take = function (list, kind, max) {
      var m = [];
      for (var i = 0; i < list.length; i++) { var x = list[i], at = x.k.indexOf(k); if (at >= 0) m.push([x.k === k ? 0 : 1, -x.n, at === 0 ? 0 : 1, x]); }
      m.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] || a[2] - b[2]; });
      m.slice(0, max).forEach(function (r) { out.push({ kind: kind, x: r[3] }); });
    };
    take(TNX, 'x', 4); take(TNW, 'w', 7); take(TNP, 'p', 5);
    // 候補にぴったり同じものがなければ、新しいタグ・人として足せるようにする
    var q2 = q.trim();
    if (q2 && !out.some(function (o) { return o.x.k === k; })) { out.push({ kind: 'nx', x: { t: q2 } }); out.push({ kind: 'np', x: { t: q2 } }); }
    return out;
  }
  function edRender() {
    var e = ed.e;
    $('ted').innerHTML = '<div class="tedh"><span class="tedt">' + esc(e.t) + '</span><button type="button" class="mx" data-a="close" aria-label="閉じる">×</button></div>' +
      '<div class="tedc">' + ed.w.map(function (w) { var x = works[w] || ['（不明な作品 ' + w + '）', '']; return '<span class="tg tw on">' + esc(x[0]) + (x[1] ? '<small>' + esc(x[1]) + '</small>' : '') + '<button type="button" data-rw="' + esc(w) + '" aria-label="外す">×</button></span>'; }).join('') +
      ed.p.map(function (p) { return '<span class="tg tp on">' + esc(p) + '<button type="button" data-rp="' + esc(p) + '" aria-label="外す">×</button></span>'; }).join('') +
      ed.x.map(function (x) { return '<span class="tg tx on">' + esc(x) + '<button type="button" data-rx="' + esc(x) + '" aria-label="外す">×</button></span>'; }).join('') +
      (ed.w.length || ed.p.length || ed.x.length ? '' : '<span class="hint">タグはありません</span>') + '</div>' +
      '<input id="tedq" type="search" autocomplete="off" placeholder="作品名・人の名前の一部を入れて足す">' +
      '<ul id="teds" class="teds"></ul>' +
      (TOKEN ? '' : '<form class="tokf" id="tedtf"><input class="vh" type="text" name="username" autocomplete="username" value="anime-world" tabindex="-1" aria-hidden="true">' +
        '<label>GitHubの鍵（トークン）<input id="tedtok" name="password" type="password" autocomplete="current-password" placeholder="パスワード管理から自動で入ります"></label></form>') +
      '<div class="tedf"><span id="tedm" class="msg"></span><button type="button" class="btn" data-a="close">やめる</button><button type="button" class="btn big" data-a="save">保存</button></div>';
    var inp = $('tedq'); inp.focus();
    inp.addEventListener('input', edSug); inp.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); var f = $('teds').querySelector('li'); if (f) f.click(); }
    });
  }
  function edSug() {
    var q = $('tedq').value;
    if (!TNW.length) { $('teds').innerHTML = q ? '<li class="hint">候補を読み込んでいます…</li>' : ''; loadNames().then(function () { if ($('tedq')) edSug(); }); return; }
    $('teds').innerHTML = suggest(q).map(function (s, i) {
      var x = s.x;
      if (s.kind === 'x') return '<li data-x="' + esc(x.t) + '"><span class="tk tkx">タグ</span>' + esc(x.t) + (x.n ? '<i>' + x.n + '件</i>' : '') + '</li>';
      if (s.kind === 'nx') return '<li data-x="' + esc(x.t) + '" class="new"><span class="tk tkx">新</span>「' + esc(x.t) + '」を新しいタグにする</li>';
      if (s.kind === 'np') return '<li data-p="' + esc(x.t) + '" class="new"><span class="tk tkp">新</span>「' + esc(x.t) + '」を人として足す</li>';
      return s.kind === 'w' ? '<li data-w="' + esc(x.id) + '" data-wt="' + esc(x.t) + '" data-wy="' + esc(x.y) + '"><span class="tk">作品</span>' + esc(x.t) + (x.y ? '<small>' + esc(x.y) + '</small>' : '') + (x.n ? '<i>' + x.n + '件</i>' : '') + '</li>'
                            : '<li data-p="' + esc(x.t) + '"><span class="tk tkp">人</span>' + esc(x.t) + '</li>';
    }).join('') || (q ? '<li class="hint">候補がありません</li>' : '');
  }
  document.addEventListener('submit', function (ev) { if (ev.target && ev.target.id === 'tedtf') ev.preventDefault(); });
  function edOpen(u) {
    var e = all.filter(function (x) { return x.u === u; })[0]; if (!e) return;
    ed = { e: e, w: shownW(e).slice(), p: shownP(e).slice(), x: (e.x || []).slice() };
    if (!$('ted')) { var d = document.createElement('div'); d.id = 'ted'; d.className = 'ted'; document.body.appendChild(d); d.addEventListener('click', edClick); }
    $('ted').hidden = false; edRender(); loadNames();
  }
  function edClose() { $('ted').hidden = true; ed = null; }
  function edClick(ev) {
    ev.stopPropagation();
    var t = ev.target.closest('[data-a],[data-rw],[data-rp],[data-rx],li[data-w],li[data-p],li[data-x]'); if (!t) return;
    if (t.dataset.a === 'close') return edClose();
    if (t.dataset.a === 'save') return edSave();
    if (t.dataset.rw) ed.w = ed.w.filter(function (w) { return w !== t.dataset.rw; });
    if (t.dataset.rp) ed.p = ed.p.filter(function (p) { return p !== t.dataset.rp; });
    if (t.dataset.rx) ed.x = ed.x.filter(function (x) { return x !== t.dataset.rx; });
    if (t.dataset.x && ed.x.indexOf(t.dataset.x) < 0) { ed.x.push(t.dataset.x); if (!TNX.some(function (y) { return y.t === t.dataset.x; })) TNX.unshift({ t: t.dataset.x, n: 0, k: kana(t.dataset.x) }); }
    if (t.dataset.w) { if (ed.w.indexOf(t.dataset.w) < 0) ed.w.push(t.dataset.w); works[t.dataset.w] = works[t.dataset.w] || [t.dataset.wt, t.dataset.wy]; }
    if (t.dataset.p && ed.p.indexOf(t.dataset.p) < 0) ed.p.push(t.dataset.p);
    edRender();
  }
  function b64dec(s) { var b = atob(s.replace(/\n/g, '')), a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return new TextDecoder().decode(a); }
  function b64enc(s) { var a = new TextEncoder().encode(s), b = ''; for (var i = 0; i < a.length; i++) b += String.fromCharCode(a[i]); return btoa(b); }
  function edSave() {
    if (!TOKEN) {   // 鍵がまだない（ブラウザが消した）とき：パネルの欄に入れてもらい、パスワードとして保存してもらう
      var tv = ($('tedtok') || {}).value; tv = (tv || '').trim();
      if (!tv) { $('tedm').textContent = '下の欄に鍵を入れてください'; $('tedtok').focus(); return; }
      TOKEN = tv; try { localStorage.setItem('gh-token', tv); } catch (x) {}
      var f = $('tedtf'); if (f && f.requestSubmit) f.requestSubmit();   // ブラウザに「パスワードを保存」を出させる
    }
    var e = ed.e, nw = ed.w.slice(), np = ed.p.slice(), nx = ed.x.slice();
    var api = 'https://api.github.com/repos/nzanke/anime-world/contents/content/tag_edits.json', H = { 'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json' };
    $('tedm').textContent = '保存しています…';
    // GitHub は書き込み直後の約1分、読むと古い版を返す。自分の保存で返ってきた版（LAST）を覚えて次の保存に使い、
    // 409（よそで書き換えられた）のときだけ読み直して、間を空けながら最大5回やり直す
    function read() {
      if (LAST) return Promise.resolve(LAST);
      return fetch(api + '?ref=main&t=' + Date.now(), { headers: H, cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error('読み込み ' + r.status); return r.json(); })
        .then(function (j) { return { sha: j.sha, cur: JSON.parse(b64dec(j.content) || '{}') }; });
    }
    function put(n) {
      var cur;
      return read().then(function (L) {
        cur = JSON.parse(JSON.stringify(L.cur)); cur[e.u] = { w: nw, p: np }; if (nx.length) cur[e.u].x = nx;
        var body = JSON.stringify(cur, null, 1) + '\n', who = { name: 'nzanke', email: 'nzanke@users.noreply.github.com' };
        return fetch(api, { method: 'PUT', headers: H, cache: 'no-store', body: JSON.stringify({ message: 'タグを編集：' + e.t.slice(0, 40), content: b64enc(body), sha: L.sha, branch: 'main', committer: who, author: who }) });
      }).then(function (r) {
        if ((r.status === 409 || r.status === 422) && n < 5) {
          LAST = null; $('tedm').textContent = '保存しています…（やり直し ' + (n + 1) + '回目）';
          return new Promise(function (ok) { setTimeout(ok, [3, 6, 12, 20, 30][n] * 1000); }).then(function () { return put(n + 1); });
        }
        if (!r.ok) return r;
        return r.json().then(function (j) { LAST = { sha: j.content.sha, cur: cur }; return { ok: true }; });
      });
    }
    put(0).then(function (r) {
      if (!r.ok) throw new Error('書き込み ' + r.status);
      // 画面にもすぐ反映（サイトの索引は数分で更新される）
      var gw = shownW(e).filter(function (w) { return nw.indexOf(w) < 0; }), gp = shownP(e).filter(function (p) { return np.indexOf(p) < 0; });
      e.w = nw.concat((e.w || []).filter(function (w) { return nw.indexOf(w) < 0 && gw.indexOf(w) < 0; })); e.wt = nw.length;
      e.p = np.concat((e.p || []).filter(function (p) { return np.indexOf(p) < 0 && gp.indexOf(p) < 0; })); e.pt = np; e.ed = 1; e.x = nx;
      keys(e); edClose(); search();
    }).catch(function (x) { $('tedm').textContent = 'できませんでした：' + x.message + (/401|403/.test(x.message) ? '（鍵を確かめてください）' : ''); });
  }
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && ed) edClose(); });
})();
