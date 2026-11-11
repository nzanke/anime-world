// 制作決定ニュース（news.html。放送日・放送局・公開日の続報 k=s も）と放送・公開前のアニメ（upcoming.html）：news.json を読み、その場で絞り込む
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var UP = window.MODE === 'upcoming';
  var PAGE = 200, all = [], res = [], shown = 0, cat = '';
  var CAT = { '映画': ['アニメ映画', 25], 'テレビ': ['テレビアニメ', 250], 'その他': ['その他', 150], '未定': ['媒体の発表なし', 70] };
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function norm(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：~〜～\-－「」『』【】]/g, ''); }
  function dot(d) { return d ? esc(d.replace(/-/g, '.')) : '----.--.--'; }
  function badge(e) {
    var c = CAT[e.c] || CAT['未定'];
    return '<span class="cat" style="--h:' + c[1] + '">' + esc(c[0]) + (e.x ? '・' + esc(e.x) : '') + '</span>';
  }
  function row(e) {
    var tags = e.q ? '<span class="tg">続編・新作</span>' : '<span class="tg">新規</span>';
    var tv = e.tv ? '<span class="tvl">' + (e.c === '映画' ? '' : '放送・配信：') + e.tv.map(function (x) { return esc(x[0]) + (x[1] ? ' <span class="tvw">' + esc(x[1]) + '</span>' : ''); }).join('／') + '</span>' : '';
    if (UP) {
      var sched = e.su ? '<span class="also"><a href="' + esc(e.su) + '" target="_blank" rel="noopener">日程の記事（' + esc(e.ss) + '）</a></span>' : '';
      return '<li><span class="date when">' + (e.p ? esc(e.p) : '<span class="none">時期未発表</span>') + '</span><span class="title">' +
        '<a href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.n) + '</a>' + badge(e) +
        '<span class="writer">' + dot(e.d) + '／' + esc(e.s) + '</span><span class="tags">' + tags + tv + sched + '</span></span></li>';
    }
    if (e.k === 's') tags = '<span class="tg tk">日程</span>';
    var also = (e.o || []).map(function (o) { return '<a href="' + esc(o[1]) + '" target="_blank" rel="noopener">' + esc(o[0]) + '</a>'; }).join('・');
    return '<li><span class="date">' + dot(e.d) + '</span><span class="title">' +
      '<a href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' + badge(e) + '<span class="writer">' + esc(e.s) + '</span>' +
      '<span class="tags">' + tags + (e.p ? '<span class="tg">' + esc(e.p) + '</span>' : '') + tv + (also ? '<span class="also">ほかの記事：' + also + '</span>' : '') + '</span></span></li>';
  }
  function render(more) {
    if (!more) { $('list').innerHTML = ''; shown = 0; }
    $('list').insertAdjacentHTML('beforeend', res.slice(shown, shown + PAGE).map(row).join(''));
    shown = Math.min(shown + PAGE, res.length);
    $('more').hidden = shown >= res.length;
  }
  function search() {
    var terms = $('q').value.split(/\s+/).map(norm).filter(Boolean);
    var site = $('site') ? $('site').value : '', newonly = $('newonly').checked, sch = !$('sched') || $('sched').checked;
    var base = all.filter(function (e) {
      return (sch || e.k !== 's') && (!site || e.s === site || (e.o || []).some(function (o) { return o[0] === site; })) && (!newonly || !e.q) &&
        terms.every(function (t) { return e._t.indexOf(t) >= 0; });
    });
    var n = {}; base.forEach(function (e) { n[e.c] = (n[e.c] || 0) + 1; });
    [].forEach.call(document.querySelectorAll('#seg button'), function (b) {
      var c = b.getAttribute('data-c'); b.querySelector('.n').textContent = ' ' + (c ? (n[c] || 0) : base.length);
    });
    res = base.filter(function (e) { return !cat || e.c === cat; });
    if ($('old') && $('old').checked) res = res.slice().reverse();
    $('count').textContent = res.length.toLocaleString() + (UP ? ' 作品' : ' 件') + ' / 全 ' + all.length.toLocaleString() + (UP ? ' 作品' : ' 件');
    render(false);
    try { history.replaceState(null, '', $('q').value ? '?q=' + encodeURIComponent($('q').value) : location.pathname); } catch (x) {}
  }
  fetch(window.NEWS).then(function (r) { return r.json(); }).then(function (j) {
    all = (UP ? j.upcoming : j.items) || [];
    all.forEach(function (e) { e._t = norm([e.t, e.n, e.s, e.p, (e.tv || []).map(function (x) { return x[0]; }).join(' ')].join(' ')); });
    var q = new URLSearchParams(location.search).get('q'); if (q) $('q').value = q;
    search();
  });
  var timer;
  $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(search, 150); });
  ['site', 'newonly', 'old', 'sched'].forEach(function (id) { if ($(id)) $(id).addEventListener('change', search); });
  $('seg').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    cat = b.getAttribute('data-c');
    [].forEach.call(document.querySelectorAll('#seg button'), function (x) { x.classList.toggle('on', x === b); });
    search();
  });
  $('more').addEventListener('click', function () { render(true); });
})();
