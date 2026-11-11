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

  // ---- 放送・公開前の一覧（1作品1行。媒体・続編はアイコン、局は略称と曜日・時刻だけ）
  var ICON = { '映画': ['映', 25, 'アニメ映画'], 'テレビ': ['TV', 250, 'テレビアニメ'], '未定': ['?', 70, '媒体の発表なし'] };
  var SUBI = { 'OVA': 'OVA', '配信': '配', 'CM': 'CM', '動画': '動' };
  var SHORT = { 'テレビ東京': 'テレ東', '日本テレビ': '日テレ', 'フジテレビ': 'フジ', 'テレビ朝日': 'テレ朝', 'TOKYO MX': 'MX', 'NHK総合': 'NHK', 'NHK Eテレ': 'Eテレ', 'ディズニープラス': 'ディズニー+', 'Prime Video': 'Prime', 'Amazonプライム・ビデオ': 'Prime', 'スーパーアニメイズム': 'アニメイズム' };
  var WD = '日月火水木金土';
  function icon(e) {
    var i = e.c === 'その他' ? [SUBI[e.x] || '他', 150, 'その他' + (e.x ? '（' + e.x + '）' : '')] : (ICON[e.c] || ICON['未定']);
    return '<span class="ic" style="--h:' + i[1] + '" title="' + esc(i[2]) + '">' + esc(i[0]) + '</span>';
  }
  function slot(w) {   // 「2027年1月9日(土)より毎週土曜23:30~」→「土 23:30」
    var d = (w.match(/毎週\s*([月火水木金土日])/) || [])[1] || '';
    var t = w.match(/(午前|午後|深夜)?(\d{1,2})(?::(\d{2})|時(?:(\d{1,2})分|(半))?)/), tm = '';
    if (t) { var h = +t[2]; if (t[1] === '午後' && h < 12) h += 12; if (t[1] === '深夜' && h < 6) h += 24; tm = h + ':' + (t[3] || (t[5] ? '30' : ('0' + (t[4] || '0')).slice(-2))); }
    return (d + (d && tm ? ' ' : '') + tm);
  }
  function tvline(e) {
    if (!e.tv) return '';
    var x = e.tv.filter(function (y) { return slot(y[1] || ''); })[0] || e.tv[0], s = slot(x[1] || '');   // 曜日・時刻の分かる局を先に
    return '<span class="st" title="' + esc(e.tv.map(function (y) { return y[0] + (y[1] ? ' ' + y[1] : ''); }).join('\n')) + '">' + esc(SHORT[x[0]] || x[0]) +
      (s ? ' <b>' + esc(s) + '</b>' : '') + (e.tv.length > 1 ? '<i>ほか</i>' : '') + '</span>';
  }
  function day(e) {
    var m = (e.pk || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return '<span class="dq">—</span>';
    if (m[3] === '99') return '<span class="dq">' + (/[春夏秋冬]$/.test(e.p || '') ? esc(e.p.slice(-1)) : '–') + '</span>';
    var w = new Date(+m[1], +m[2] - 1, +m[3]).getDay();
    return +m[3] + '<small>' + WD[w] + '</small>';
  }
  function group(e) {
    var m = (e.pk || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return '時期未発表';
    if (m[2] === '12' && m[3] === '99' && e.p === m[1] + '年') return m[1] + '年（月は未発表）';
    var se = (e.p || '').match(/^(\d{4})年(春|夏|秋|冬)$/);   // 季節だけの発表は月に入れず、季節の見出しにする
    if (se) return se[1] + '年' + se[2];
    return m[1] + '年' + (+m[2]) + '月';
  }
  function uprow(e) {
    return '<li class="ur"><span class="ud">' + day(e) + '</span>' + icon(e) +
      '<a class="un" href="' + esc(e.su || e.u) + '" target="_blank" rel="noopener">' + esc(e.n) + '</a>' +
      (e.q ? '<span class="sq" title="続編・新作">続</span>' : '') + tvline(e) + '</li>';
  }
  function row(e) {
    var tags = e.q ? '<span class="tg">続編・新作</span>' : '<span class="tg">新規</span>';
    var tv = e.tv ? '<span class="tvl">' + (e.c === '映画' ? '' : '放送・配信：') + e.tv.map(function (x) { return esc(x[0]) + (x[1] ? ' <span class="tvw">' + esc(x[1]) + '</span>' : ''); }).join('／') + '</span>' : '';
    if (UP) return uprow(e);
    // 制作決定ニュースの一覧も、記事検索と同じ見た目（月の見出し、日にちと印、題名は折り返して全部出す）
    var also = (e.o || []).map(function (o) { return '<a href="' + esc(o[1]) + '" target="_blank" rel="noopener">' + esc(o[0]) + '</a>'; }).join('・');
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(e.d || '');
    var dd = m ? +m[3] + '<small>' + WD[new Date(+m[1], +m[2] - 1, +m[3]).getDay()] + '</small>' : '<span class="dq">—</span>';
    var sub = (e.p ? '<span class="tg">' + esc(e.p) + '</span>' : '') + tv + (also ? '<span class="also">ほかの記事：' + also + '</span>' : '');
    return '<li class="ur sr"><span class="ud">' + dd + '</span>' + icon(e) +
      '<span class="sb"><a class="un" href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.t) + '</a>' +
      (e.k === 's' ? '<span class="sq" title="放送日・放送局・公開日のニュース">日程</span>' : (e.q ? '<span class="sq" title="続編・新作">続</span>' : '')) +
      (sub ? '<span class="tags">' + sub + '</span>' : '') + '</span>' +
      '<span class="st">' + esc(e.s) + '</span></li>';
  }
  var lastG = '';
  function ngroup(e) { var m = /^(\d{4})-(\d{2})/.exec(e.d || ''); return m ? m[1] + '年' + (+m[2]) + '月' : '日付なし'; }
  function render(more) {
    if (!more) { $('list').innerHTML = ''; shown = 0; }
    if (UP) {   // 月ごとの見出しを挟み、全部を出す
      var html = '', g0 = null;
      res.forEach(function (e) { var g = group(e); if (g !== g0) { html += '<li class="ug">' + esc(g) + '</li>'; g0 = g; } html += uprow(e); });
      $('list').innerHTML = html; shown = res.length; $('more').hidden = true; return;
    }
    if (!more) lastG = '';
    var h = '';
    res.slice(shown, shown + PAGE).forEach(function (e) { var g = ngroup(e); if (g !== lastG) { h += '<li class="ug">' + esc(g) + '</li>'; lastG = g; } h += row(e); });
    $('list').insertAdjacentHTML('beforeend', h);
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
