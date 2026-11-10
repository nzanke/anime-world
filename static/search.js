// 記事検索：index.json（題名・サイト・日付・種類・番組・スタッフ）を読み、その場で絞り込む
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var PAGE = 200, all = [], works = {}, res = [], shown = 0;
  var MARK = { 'インタビュー': ['談', 'ty-i'], 'レビュー': ['評', 'ty-h'], '評論': ['評', 'ty-h'], '感想': ['感', 'ty-k'], '資料': ['資', 'ty-s'] };
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  var HUE = { 'インタビュー': 250, 'レビュー': 25, '評論': 25, '感想': 150, '資料': 70 };
  function hue(k) { if (k in HUE) return HUE[k]; var h = 0; for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 360; return h; }
  function row(e) {
    var tags = (e.w || []).slice(0, 6).map(function (w) { var x = works[w]; return x ? '<a class="tg tw" data-q="' + esc(x[0]) + '">' + esc(x[0]) + '</a>' : ''; }).join('') +
      (e.p || []).slice(0, 8).map(function (p) { return '<a class="tg tp" data-q="' + esc(p) + '">' + esc(p) + '</a>'; }).join('');
    return '<li><span class="date">' + (e.d ? esc(e.d.replace(/-/g, '.')) : '----.--.--') + '</span><span class="title">' +
      '<a href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
      '<span class="cat" style="--h:' + hue(e.k || '') + '">' + esc(e.k) + '</span>' +
      '<span class="writer">' + esc(e.s) + (e.a ? '／' + esc(e.a) : '') + '</span>' +
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
    var site = $('site').value, kind = $('kind').value;
    res = all.filter(function (e) {
      return (!site || e.s === site) && (!kind || e.k === kind) && terms.every(function (t) { return e._t.indexOf(t) >= 0; });
    });
    if ($('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + ' 件 / 全 ' + all.length.toLocaleString() + ' 件';
    render(false);
    try { history.replaceState(null, '', $('q').value ? '?q=' + encodeURIComponent($('q').value) : location.pathname); } catch (x) {}
  }
  fetch(window.IDX).then(function (r) { return r.json(); }).then(function (j) {
    all = j.items; works = j.works;
    all.forEach(function (e) {
      e._t = norm([e.t, e.s, e.a, (e.w || []).slice(0, 6).map(function (w) { return works[w] ? works[w][0] : ''; }).join(' '), (e.p || []).join(' ')].join(' '));
    });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  ['site', 'kind', 'old'].forEach(function (id) { $(id).addEventListener('change', search); });
  $('more').addEventListener('click', function () { render(true); });
  $('list').addEventListener('click', function (ev) {
    var a = ev.target.closest('.tg'); if (!a) return;
    ev.preventDefault(); $('q').value = a.getAttribute('data-q'); search(); window.scrollTo(0, 0);
  });
})();
