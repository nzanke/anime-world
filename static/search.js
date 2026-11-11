// 記事検索：index.json（題名・サイト・日付・種類・番組・スタッフ）を読み、その場で絞り込む
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var PAGE = 200, all = [], works = {}, res = [], shown = 0;
  var MARK = { 'インタビュー': ['談', 'ty-i'], 'レビュー': ['評', 'ty-h'], '評論': ['評', 'ty-h'], '感想': ['感', 'ty-k'], '資料': ['資', 'ty-s'] };
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  var HUE = { 'インタビュー': 250, 'レビュー': 25, '評論': 25, '感想': 150, '資料': 70 };
  function hue(k) { if (k in HUE) return HUE[k]; var h = 0; for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 360; return h; }
  // インタビューのページはサイトで色分けする（明るさ・彩度はそろえ、色相だけ変える）
  var SHUE = { 'Febri': 250, 'アニメ！アニメ！': 15, 'アニメイトタイムズ': 330, 'コミックナタリー': 140, 'MANTANWEB': 50, 'アキバ総研': 70 };
  function shue(k) { if (k in SHUE) return SHUE[k]; var h = 0; for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 360; return h; }
  function row(e) {
    var tags = (e.w || []).slice(0, Math.min(6, e.wt == null ? 6 : e.wt)).map(function (w) { var x = works[w]; return x ? '<a class="tg tw" data-q="' + esc(x[0]) + '">' + esc(x[0]) + '</a>' : ''; }).join('') +
      (e.p || []).filter(function (p) { return norm(e.t).indexOf(norm(p)) >= 0; }).map(function (p) { return '<a class="tg tp" data-q="' + esc(p) + '">' + esc(p) + '</a>'; }).join('');
    return '<li><span class="date">' + (e.d ? esc(e.d.replace(/-/g, '.')) : '----.--.--') + '</span><span class="title">' +
      '<a href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
      (window.MODE !== 'column'
        ? '<span class="cat" style="--h:' + shue(e.s) + '">' + esc(e.s) + '</span>' + (e.a ? '<span class="writer">' + esc(e.a) + '</span>' : '')
        : '<span class="cat" style="--h:' + hue(e.k || '') + '">' + esc(e.k) + '</span><span class="writer">' + esc(e.s) + (e.a ? '／' + esc(e.a) : '') + '</span>') +
      (tags ? '<span class="tags">' + tags + '</span>' : '') + '</span></li>';
  }
  function render(more) {
    if (!more) { $('list').innerHTML = ''; shown = 0; }
    $('list').insertAdjacentHTML('beforeend', res.slice(shown, shown + PAGE).map(row).join(''));
    shown = Math.min(shown + PAGE, res.length);
    $('more').hidden = shown >= res.length;
  }
  function search() {
    var terms = norm($('q').value.replace(/\s+/g, ' ')).length ? $('q').value.split(/\s+/).map(norm).filter(Boolean) : [];
    var site = $('site').value, kind = $('kind') ? $('kind').value : '';
    var cast = !$('cast') || $('cast').checked;   // キャスト（声優）のインタビューを出すか
    try { if ($('cast')) localStorage.setItem('show-cast', cast ? '1' : '0'); } catch (x) {}
    res = all.filter(function (e) {
      return (cast || !e.c) && (!site || e.s === site) && (!kind || e.k === kind) && terms.every(function (t) { return e._t.indexOf(t) >= 0; });
    });
    if ($('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + ' 件 / 全 ' + all.length.toLocaleString() + ' 件';
    render(false);
    try { history.replaceState(null, '', $('q').value ? '?q=' + encodeURIComponent($('q').value) : location.pathname); } catch (x) {}
  }
  fetch(window.IDX).then(function (r) { return r.json(); }).then(function (j) {
    var iv = window.MODE !== 'column';
    all = j.items.filter(function (e) { return ((e.k || 'インタビュー') === 'インタビュー') === iv; }); works = j.works;
    all.forEach(function (e) {
      e._t = norm([e.t, e.s, e.a, (e.w || []).map(function (w) { return works[w] ? works[w][0] : ''; }).join(' '), (e.p || []).join(' ')].join(' '));
    });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  try { if ($('cast') && localStorage.getItem('show-cast') === '0') $('cast').checked = false; } catch (x) {}
  ['site', 'kind', 'old', 'cast'].forEach(function (id) { if ($(id)) $(id).addEventListener('change', search); });
  $('more').addEventListener('click', function () { render(true); });
  $('list').addEventListener('click', function (ev) {
    var a = ev.target.closest('.tg'); if (!a) return;
    ev.preventDefault(); $('q').value = a.getAttribute('data-q'); search(); window.scrollTo(0, 0);
  });
})();
