// スタッフランキング：役職のボタンで切り替える（ranking.json を読む）
(function () {
  var data, g = '全役職';
  function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function draw() {
    document.querySelectorAll('#rank details').forEach(function (el) {
      var rows = (data.rank[g] || {})[el.getAttribute('data-d')] || [];
      el.hidden = !rows.length;
      el.querySelector('.n').textContent = '上位' + rows.length + '人';
      el.querySelector('ul').innerHTML = rows.map(function (r, i) {
        return '<li><span class="date">' + (i + 1) + '</span><span class="title"><a href="index.html?q=' + encodeURIComponent(r[0]) + '">' + esc(r[0]) + '</a>' +
          '<span class="writer">' + esc(r[2]) + '</span></span><span class="num">' + r[1] + '番組</span><span class="art">' + (r[3] ? '記事' + r[3] : '') + '</span></li>';
      }).join('');
    });
    document.querySelectorAll('#seg button').forEach(function (b) {
      var on = b.getAttribute('data-g') === g; b.classList.toggle('on', on);
    });
  }
  document.getElementById('seg').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b || !data) return;
    g = b.getAttribute('data-g'); draw();
    try { history.replaceState(null, '', '?role=' + encodeURIComponent(g)); } catch (x) {}
  });
  fetch(window.RANK).then(function (r) { return r.json(); }).then(function (j) {
    data = j; var q = new URLSearchParams(location.search).get('role'); if (q && j.rank[q]) g = q; draw();
  });
})();
