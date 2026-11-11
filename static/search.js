// 記事検索：index.json（題名・サイト・日付・種類・番組・スタッフ）を読み、その場で絞り込む。
// 見た目は「放送・公開前のアニメ」と同じ（月ごとの見出し、日にちと印、題名は折り返して全部出す）
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var PAGE = 200, all = [], works = {}, res = [], shown = 0, sel = '', lastGroup = '';
  var IV = window.MODE !== 'column', ICONS = window.ICONS || {};
  var WD = '日月火水木金土';
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  function hash(k) { var h = 0; for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 360; return h; }
  function icon(name) { var x = ICONS[name] || [name.slice(0, 1), hash(name)]; return x; }
  var key = function (e) { return IV ? e.s : (e.k === '評論' ? 'レビュー' : e.k); };   // 絞り込みと印の単位
  function day(e) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(e.d || '');
    if (!m) return '<span class="dq">—</span>';
    return +m[3] + '<small>' + WD[new Date(+m[1], +m[2] - 1, +m[3]).getDay()] + '</small>';
  }
  function group(e) { var m = /^(\d{4})-(\d{2})/.exec(e.d || ''); return m ? m[1] + '年' + (+m[2]) + '月' : '日付なし'; }
  function row(e) {
    var tags = (e.w || []).slice(0, Math.min(6, e.wt == null ? 6 : e.wt)).map(function (w) { var x = works[w]; return x ? '<a class="tg tw" data-q="' + esc(x[0]) + '">' + esc(x[0]) + '</a>' : ''; }).join('') +
      (e.p || []).filter(function (p) { return norm(e.t).indexOf(norm(p)) >= 0; }).map(function (p) { return '<a class="tg tp" data-q="' + esc(p) + '">' + esc(p) + '</a>'; }).join('');
    var ic = icon(key(e));
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
    var names = Object.keys(n).sort(function (a, b) { return n[b] - n[a]; });
    $('seg').innerHTML = '<button type="button" data-c="" style="--h:250"' + (sel ? '' : ' class="on"') + '>すべて<span class="n"> ' + base.length.toLocaleString() + '</span></button>' +
      names.map(function (k) { return '<button type="button" data-c="' + esc(k) + '" style="--h:' + icon(k)[1] + '"' + (sel === k ? ' class="on"' : '') + '>' + esc(k) + '<span class="n"> ' + n[k].toLocaleString() + '</span></button>'; }).join('');
  }
  function search() {
    var terms = $('q').value.split(/\s+/).map(norm).filter(Boolean);
    var cast = !$('cast') || $('cast').checked;   // キャスト（声優）のインタビューを出すか
    try { if ($('cast')) localStorage.setItem('show-cast', cast ? '1' : '0'); } catch (x) {}
    var base = all.filter(function (e) { return (cast || !e.c) && terms.every(function (t) { return e._t.indexOf(t) >= 0; }); });
    pills(base);
    res = base.filter(function (e) { return !sel || key(e) === sel; });
    if ($('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + ' 件 / 全 ' + all.length.toLocaleString() + ' 件';
    render(false);
    try { history.replaceState(null, '', $('q').value ? '?q=' + encodeURIComponent($('q').value) : location.pathname); } catch (x) {}
  }
  fetch(window.IDX).then(function (r) { return r.json(); }).then(function (j) {
    all = j.items.filter(function (e) { return ((e.k || 'インタビュー') === 'インタビュー') === IV; }); works = j.works;
    all.forEach(function (e) {
      e._t = norm([e.t, e.s, e.a, (e.w || []).map(function (w) { return works[w] ? works[w][0] : ''; }).join(' '), (e.p || []).join(' ')].join(' '));
    });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  try { if ($('cast') && localStorage.getItem('show-cast') === '0') $('cast').checked = false; } catch (x) {}
  ['old', 'cast'].forEach(function (id) { if ($(id)) $(id).addEventListener('change', search); });
  $('seg').addEventListener('click', function (ev) { var b = ev.target.closest('button'); if (!b) return; sel = b.getAttribute('data-c'); search(); });
  $('more').addEventListener('click', function () { render(true); });
  $('list').addEventListener('click', function (ev) {
    var a = ev.target.closest('.tg'); if (!a) return;
    ev.preventDefault(); $('q').value = a.getAttribute('data-q'); search(); window.scrollTo(0, 0);
  });
})();
