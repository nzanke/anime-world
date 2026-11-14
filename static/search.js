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
  // コラム欄は種類で分けない：媒体名の頭2文字・1色（媒体名がなければ「記」）
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
  function row(e) {
    var tags = (e.w || []).slice(0, Math.min(6, e.wt == null ? 6 : e.wt)).map(function (w) { var x = works[w]; return x ? '<a class="tg tw" data-q="' + esc(x[0]) + '">' + esc(x[0]) + '</a>' : ''; }).join('') +
      (e.p || []).filter(function (p) { return norm(e.t).indexOf(norm(p)) >= 0; }).map(function (p) { return '<a class="tg tp" data-q="' + esc(p) + '">' + esc(p) + '</a>'; }).join('');
    var ic = eicon(e);
    var meta = IV ? (e.a || '') : e.s + (e.a ? '／' + e.a : '');
    return '<li class="ur sr"><span class="ud">' + day(e) + '</span>' +
      '<span class="ic" style="--h:' + ic[1] + '" title="' + esc(IV ? e.s : e.k) + '">' + esc(ic[0]) + '</span>' +
      '<span class="sb"><a class="un" href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
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
  var pick = {};
  try { (JSON.parse(localStorage.getItem('media-pick') || '[]')).forEach(function (x) { pick[x] = 1; }); } catch (x) {}
  function picked() { return Object.keys(pick); }
  function mlabel() {
    var p = picked();
    $('mbtn').textContent = '媒体：' + (!p.length ? 'すべて' : p.length === 1 ? p[0] : p.length + 'つ') + ' ▾';
    $('mbtn').classList.toggle('on', p.length > 0);
  }
  function mpanel(base) {
    var n = {}; base.forEach(function (e) { n[site(e)] = (n[site(e)] || 0) + 1; });
    var html = '<div class="mtop"><button type="button" data-a="all">すべて選ぶ</button><button type="button" data-a="none">選ぶのをやめる（すべて）</button><button type="button" data-a="close" class="mx" aria-label="閉じる">×</button></div>';
    (window.GENRES || []).forEach(function (g) {
      var ss = Object.keys(SG).concat(Object.keys(n)).filter(function (x, i, a) { return a.indexOf(x) === i && (SG[x] || ['カルチャー・その他'])[0] === g[0] && n[x]; })
        .sort(function (a, b) { return n[b] - n[a]; });
      if (!ss.length) return;
      html += '<div class="mrow"><button type="button" class="mg" data-g="' + esc(g[0]) + '" style="--h:' + g[1] + '" title="このジャンルをまとめて選ぶ・外す">' + esc(g[0]) + '</button><div class="mchips">' +
        ss.map(function (x) {
          return '<button type="button" class="mc' + (pick[x] ? ' on' : '') + '" data-s="' + esc(x) + '" style="--h:' + g[1] + '">' + esc(x) + '<span class="n">' + n[x].toLocaleString() + '</span></button>';
        }).join('') + '</div></div>';
    });
    $('mpop').innerHTML = html;
  }
  function msave() { try { localStorage.setItem('media-pick', JSON.stringify(picked())); } catch (x) {} }
  function search() {
    var terms = $('q').value.split(/\s+/).map(norm).filter(Boolean);
    var cast = !$('cast') || $('cast').checked;   // キャスト（声優）のインタビューを出すか
    try { if ($('cast')) localStorage.setItem('show-cast', cast ? '1' : '0'); } catch (x) {}
    var scope = (document.querySelector('input[name=scope]:checked') || {}).value || 'tag';
    try { localStorage.setItem('search-scope', scope); } catch (x) {}
    var F = scope === 'title' ? '_ti' : scope === 'all' ? '_t' : '_tg';
    var base = all.filter(function (e) { return (cast || !e.c) && terms.every(function (t) { return e[F].indexOf(t) >= 0; }); });
    var p = IV ? picked() : [];
    if (IV) { mlabel(); if (!$('mpop').hidden) mpanel(base); lastBase = base; }
    var base2 = base.filter(function (e) { return !p.length || pick[site(e)]; });
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
      var tw = (e.w || []).slice(0, e.wt == null ? 10 : e.wt).map(function (w) { return works[w] ? works[w][0] : ''; });
      var tp = (e.p || []).filter(function (p) { return norm(e.t).indexOf(norm(p)) >= 0; });
      e._ti = norm(e.t);
      e._tg = norm([e.t, e.s, e.a, tw.join(' '), tp.join(' ')].join(' '));
      e._t = norm([e.t, e.s, e.a, (e.w || []).map(function (w) { return works[w] ? works[w][0] : ''; }).join(' '), (e.p || []).join(' ')].join(' '));
    });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
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
    var a = ev.target.closest('.tg'); if (!a) return;
    ev.preventDefault(); $('q').value = a.getAttribute('data-q'); search(); window.scrollTo(0, 0);
  });
})();
