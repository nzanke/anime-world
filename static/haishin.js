// アニメ配信カレンダー：選んだサービスの中で、各話をいちばん早く見られる日時を並べる
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var LS = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  var SITE = 'https://nzanke.github.io/anime-world/';
  var ICS_URL = SITE + 'haishin/my.ics';
  var EDIT_URL = 'https://github.com/nzanke/anime-world/edit/main/content/haishin_my.json';
  var DEF_SVC = ['danime', 'unext', 'dmm', 'netflix', 'prime', 'tv:NHK総合', 'tv:NHK Eテレ', 'tv:日本テレビ', 'tv:TBS', 'tv:フジテレビ', 'tv:テレビ朝日', 'tv:テレビ東京', 'tv:TOKYO MX'];
  var WD = '日月火水木金土';
  var D, NAMES = {}, MY = null, svc, sel, view = LS.get('hs_view', 'week'), q = '';

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function P(t) { // 'YYYY-MM-DDTHH:MM'（日本時間）を分解
    var y = +t.slice(0, 4), m = +t.slice(5, 7), d = +t.slice(8, 10);
    return { y: y, m: m, d: d, hm: (+t.slice(11, 13)) + ':' + t.slice(14, 16), wd: WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()], day: t.slice(0, 10) };
  }
  function nowJST() { var n = new Date(Date.now() + 9 * 3600e3); return n.toISOString().slice(0, 16); }
  function addDays(t, k) { var x = new Date(Date.parse(t.slice(0, 10) + 'T00:00:00Z') + k * 864e5); return x.toISOString().slice(0, 10); }
  function sname(s) { return (NAMES[s] || s); }
  function isTV(s) { return s.indexOf('tv:') === 0; }

  // 作品ごとに、選んだサービスで話ごとのいちばん早い配信を出す
  function episodes(w, S) {
    var by = {};
    w.e.forEach(function (e) { if (S[e[0]]) (by[e[2]] = by[e[2]] || []).push(e); });
    var out = [];
    Object.keys(by).forEach(function (n) {
      var l = by[n].sort(function (a, b) { return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0; });
      // 同じ時刻のサービスはまとめて出す
      var first = l[0], same = l.filter(function (e) { return e[1] === first[1]; }).map(function (e) { return e[0]; });
      out.push({ t: first[1], n: +n, sure: first[3], svcs: same, others: l.filter(function (e) { return e[1] !== first[1]; }) });
    });
    return out.sort(function (a, b) { return a.t < b.t ? -1 : 1; });
  }
  function svcSet() { var S = {}; svc.forEach(function (s) { S[s] = 1; }); return S; }
  function epLabel(x) { return x.sure && x.n < 1000 ? '第' + x.n + '話' : ''; }
  function svcLabel(l) {
    var v = l.filter(function (s) { return !isTV(s); }), t = l.filter(isTV);
    var a = v.map(sname).concat(t.map(sname));
    return a.length > 3 ? a.slice(0, 3).join('・') + 'ほか' : a.join('・');
  }
  function save() { LS.set('hs_svc', svc); LS.set('hs_sel', sel); }

  // ------------------------------------------------------------ サービスの選択
  function renderSvc() {
    var cnt = {};
    D.works.forEach(function (w) { var seen = {}; w.e.forEach(function (e) { if (!seen[e[0]]) { seen[e[0]] = 1; cnt[e[0]] = (cnt[e[0]] || 0) + 1; } }); });
    var on = svcSet();
    function chip(s) {
      return '<label class="hs-chip' + (on[s[0]] ? ' on' : '') + '"><input type="checkbox" value="' + esc(s[0]) + '"' + (on[s[0]] ? ' checked' : '') + '>' + esc(s[1]) + '<small>' + (cnt[s[0]] || 0) + '</small></label>';
    }
    var vod = D.services.filter(function (s) { return !isTV(s[0]) && cnt[s[0]]; }), tv = D.services.filter(function (s) { return isTV(s[0]) && cnt[s[0]]; });
    $('#hs-svc').innerHTML = '<div class="hs-row"><span class="hs-k">配信</span>' + vod.map(chip).join('') + '</div><div class="hs-row"><span class="hs-k">テレビ</span>' + tv.map(chip).join('') +
      '<button type="button" class="hs-mini" id="hs-tvall">テレビを全部' + (tv.every(function (s) { return on[s[0]]; }) ? '外す' : '選ぶ') + '</button></div>';
    Array.prototype.forEach.call(document.querySelectorAll('#hs-svc input'), function (i) {
      i.onchange = function () { svc = Array.prototype.filter.call(document.querySelectorAll('#hs-svc input'), function (x) { return x.checked; }).map(function (x) { return x.value; }); save(); render(); };
    });
    $('#hs-tvall').onclick = function () {
      var all = tv.every(function (s) { return on[s[0]]; });
      svc = svc.filter(function (s) { return !isTV(s); }).concat(all ? [] : tv.map(function (s) { return s[0]; })); save(); render();
    };
  }

  // ------------------------------------------------------------ これから7日間
  function renderWeek() {
    var S = svcSet(), now = nowJST(), start = now.slice(0, 10), end = addDays(start, 7);
    var picked = sel.length ? D.works.filter(function (w) { return sel.indexOf(w.id) >= 0; }) : D.works;
    var rows = [];
    picked.forEach(function (w) {
      episodes(w, S).forEach(function (x) { if (x.t.slice(0, 10) >= start && x.t.slice(0, 10) < end) rows.push({ w: w, x: x }); });
    });
    rows.sort(function (a, b) { return a.x.t < b.x.t ? -1 : a.x.t > b.x.t ? 1 : (a.w.t < b.w.t ? -1 : 1); });
    var h = sel.length ? '' : '<p class="hs-note">作品をまだ選んでいないので、選んだサービスで配信される作品を全部出しています。「作品を選ぶ」で見る作品に印を付けると、自分用の表になります。</p>';
    if (!rows.length) h += '<p class="hs-note">この7日間に配信される作品はありません。</p>';
    var cur = '';
    rows.forEach(function (r) {
      var p = P(r.x.t), past = r.x.t < now;
      if (p.day !== cur) { if (cur) h += '</ul>'; cur = p.day; h += '<h3 class="hs-day' + (p.wd === '土' ? ' sat' : p.wd === '日' ? ' sun' : '') + '">' + p.m + '月' + p.d + '日（' + p.wd + '）' + (p.day === start ? '<span>今日</span>' : '') + '</h3><ul class="hs-list">'; }
      var oth = r.x.others.length ? '<span class="hs-oth">ほか：' + r.x.others.slice(0, 4).map(function (e) { var q2 = P(e[1]); return esc(sname(e[0])) + ' ' + (q2.day === p.day ? '' : q2.wd + ' ') + q2.hm; }).join('、') + (r.x.others.length > 4 ? ' など' : '') + '</span>' : '';
      h += '<li' + (past ? ' class="past"' : '') + '><span class="hs-t">' + p.hm + '</span><span class="hs-b"><b>' + esc(r.w.t) + '</b> ' + epLabel(r.x) +
        '<span class="hs-s' + (r.x.svcs.every(isTV) ? ' tv' : '') + '">' + esc(svcLabel(r.x.svcs)) + '</span>' + oth + '</span></li>';
    });
    if (cur) h += '</ul>';
    $('#hs-main').innerHTML = h;
    $('#count').textContent = (sel.length ? '選んだ' + sel.length + '作品' : '選んだサービスの全作品') + '　これから7日間に' + rows.length + '回';
  }

  // ------------------------------------------------------------ 作品を選ぶ
  function slot(w, S) {
    var now = nowJST(), ep = episodes(w, S).filter(function (x) { return x.t >= now.slice(0, 10); })[0];
    if (!ep) return null;
    var p = P(ep.t);
    return { txt: p.wd + ' ' + p.hm + '　' + svcLabel(ep.svcs) + (epLabel(ep) ? '（次は' + epLabel(ep) + '）' : ''), t: ep.t };
  }
  function renderWorks() {
    var S = svcSet(), on = {};
    sel.forEach(function (i) { on[i] = 1; });
    var qq = q.trim().toLowerCase();
    var list = D.works.filter(function (w) { return !qq || w.t.toLowerCase().indexOf(qq) >= 0; }).map(function (w) { return { w: w, s: slot(w, S) }; });
    function wk(s) { if (!s) return 1e9; var p = P(s.t); return ('月火水木金土日'.indexOf(p.wd)) * 1440 + (+s.t.slice(11, 13)) * 60 + (+s.t.slice(14, 16)); }
    list.sort(function (a, b) { return (!!b.s - !!a.s) || wk(a.s) - wk(b.s) || (a.w.t < b.w.t ? -1 : 1); });
    var h = '<div class="hs-bar"><input type="search" id="hs-q" placeholder="作品名で絞り込む" value="' + esc(q) + '"><button type="button" class="hs-mini" id="hs-all">表示中を全部選ぶ</button><button type="button" class="hs-mini" id="hs-none">選択を全部外す</button></div><ul class="hs-works">';
    list.forEach(function (r) {
      var w = r.w, all = {};
      w.e.forEach(function (e) { all[e[0]] = 1; });
      h += '<li class="' + (r.s ? '' : 'na') + (on[w.id] ? ' on' : '') + '"><label><input type="checkbox" value="' + w.id + '"' + (on[w.id] ? ' checked' : '') + '><span><b>' + esc(w.t) + '</b>' +
        '<span class="hs-slot">' + (r.s ? esc(r.s.txt) : '選んだサービスでは配信なし') + '</span>' +
        '<span class="hs-where">' + Object.keys(all).map(function (s) { return '<i' + (S[s] ? ' class="on"' : '') + '>' + esc(sname(s)) + '</i>'; }).join('') + '</span></span></label></li>';
    });
    h += '</ul>';
    $('#hs-main').innerHTML = h;
    $('#count').textContent = '今期の作品 ' + D.works.length + '　選んだ作品 ' + sel.length;
    var qi = $('#hs-q');
    qi.oninput = function () { q = qi.value; var pos = qi.selectionStart; renderWorks(); var n = $('#hs-q'); n.focus(); n.setSelectionRange(pos, pos); };
    Array.prototype.forEach.call(document.querySelectorAll('.hs-works input'), function (i) {
      i.onchange = function () { if (i.checked) { if (sel.indexOf(i.value) < 0) sel.push(i.value); } else sel = sel.filter(function (x) { return x !== i.value; }); save(); i.closest('li').classList.toggle('on', i.checked); $('#count').textContent = '今期の作品 ' + D.works.length + '　選んだ作品 ' + sel.length; renderTabs(); };
    });
    $('#hs-all').onclick = function () { list.forEach(function (r) { if (r.s && sel.indexOf(r.w.id) < 0) sel.push(r.w.id); }); save(); render(); };
    $('#hs-none').onclick = function () { if (confirmNone()) { sel = []; save(); render(); } };
  }
  function confirmNone() { var b = $('#hs-none'); if (b.dataset.ok) return true; b.dataset.ok = 1; b.textContent = 'もう一度押すと全部外します'; return false; }

  // ------------------------------------------------------------ カレンダーに入れる
  function icsText(S, works) {
    var esc2 = function (s) { return s.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n'); };
    var now = nowJST(), from = addDays(now, -7);
    var stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
    var L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//nzanke//anime-haishin//JA', 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:アニメ配信カレンダー', 'X-WR-TIMEZONE:Asia/Tokyo'];
    function utc(t, add) { var d = new Date(Date.parse(t + ':00+09:00') + (add || 0) * 60e3); return d.toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z'; }
    works.forEach(function (w) {
      episodes(w, S).forEach(function (x) {
        if (x.t < from) return;
        var desc = svcLabel(x.svcs) + 'がいちばん早い' + (x.others.length ? '\nほか：' + x.others.slice(0, 6).map(function (e) { return sname(e[0]) + ' ' + e[1].slice(5).replace('T', ' '); }).join('、') : '') + '\n' + SITE + 'haishin.html';
        L.push('BEGIN:VEVENT', 'UID:' + w.id + '-' + x.n + '@nzanke.github.io', 'DTSTAMP:' + stamp, 'DTSTART:' + utc(x.t), 'DTEND:' + utc(x.t, 30),
          'SUMMARY:' + esc2(w.t + (epLabel(x) ? ' ' + epLabel(x) : '') + '（' + svcLabel(x.svcs) + '）'), 'DESCRIPTION:' + esc2(desc), 'END:VEVENT');
      });
    });
    L.push('END:VCALENDAR');
    return L.join('\r\n') + '\r\n';
  }
  function myJSON() {
    var t = {}; D.works.forEach(function (w) { t[w.id] = w.t; });
    return JSON.stringify({ services: svc, works: sel, '作品名（確認用）': sel.map(function (i) { return t[i] || i; }) }, null, 1) + '\n';
  }
  function same() {
    if (!MY) return null;
    var a = (MY.works === 'all' ? ['all'] : (MY.works || []).slice()).sort().join(), b = sel.slice().sort().join();
    var c = (MY.services || []).slice().sort().join(), d = svc.slice().sort().join();
    return a === b && c === d;
  }
  function renderCal() {
    var st = same();
    var h = '<h2>Googleカレンダーで購読する（毎日自動で更新）</h2>' +
      '<p class="hs-note">購読用のURLを一度カレンダーに登録しておけば、配信予定が毎日自動で更新されます。中身は、下の「購読の設定」に保存したサービスと作品で決まります。</p>' +
      '<p class="hs-url"><code>' + ICS_URL + '</code> <button type="button" class="hs-mini" id="hs-cp">URLをコピー</button></p>' +
      '<ol class="hs-steps"><li>Googleカレンダーの<a href="https://calendar.google.com/calendar/u/0/r/settings/addbyurl" target="_blank" rel="noopener">「URLで追加」</a>を開き、上のURLを貼って「カレンダーを追加」。（iPhoneは<a href="webcal://' + ICS_URL.replace(/^https:\/\//, '') + '">ここを押す</a>と購読できます）</li>' +
      '<li>サービスや作品の選択を変えたら、下の「購読の設定に保存」を押す（設定の文がコピーされ、GitHubの編集画面が開くので、中身を全部貼り替えて「Commit changes」）。数分でURLの中身が変わります。</li></ol>' +
      '<h3>購読の設定</h3><p class="hs-note">' + (st === null ? '購読の設定はまだ保存されていません。' : st ? '購読の設定は、いまの選択と同じです（サービス' + svc.length + '・作品' + sel.length + '）。' : '<b>いまの選択は、購読の設定とちがいます。</b>（保存済み：サービス' + (MY.services || []).length + '・作品' + (MY.works === 'all' ? '全部' : (MY.works || []).length) + '　いま：サービス' + svc.length + '・作品' + sel.length + '）') + '</p>' +
      '<p><button type="button" class="btn hs-btn" id="hs-save">購読の設定に保存</button>' + (MY && st === false ? ' <button type="button" class="hs-mini" id="hs-load">保存済みの設定に戻す</button>' : '') + '</p>' +
      '<h2>いまの選択をファイルで取り込む</h2><p class="hs-note">これから5週間分の予定を .ics ファイルにします（取り込んだあとは自動では更新されません）。</p>' +
      '<p><button type="button" class="btn hs-btn" id="hs-dl">.ics をダウンロード</button></p>';
    $('#hs-main').innerHTML = h;
    $('#count').textContent = '選んだサービス ' + svc.length + '　選んだ作品 ' + sel.length;
    function copy(t, b, label) {
      var done = function () { b.textContent = 'コピーしました'; setTimeout(function () { b.textContent = label; }, 1800); };
      try { navigator.clipboard.writeText(t).then(done, function () { prompt('コピーしてください', t); }); } catch (e) { prompt('コピーしてください', t); }
    }
    $('#hs-cp').onclick = function () { copy(ICS_URL, this, 'URLをコピー'); };
    $('#hs-save').onclick = function () {
      if (!sel.length) { alert('先に「作品を選ぶ」で作品を選んでください。'); return; }
      copy(myJSON(), this, '購読の設定に保存'); window.open(EDIT_URL, '_blank', 'noopener');
    };
    if ($('#hs-load')) $('#hs-load').onclick = function () { svc = (MY.services || svc).slice(); sel = MY.works === 'all' ? [] : (MY.works || []).slice(); save(); render(); };
    $('#hs-dl').onclick = function () {
      var S = svcSet(), ws = sel.length ? D.works.filter(function (w) { return sel.indexOf(w.id) >= 0; }) : D.works;
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([icsText(S, ws)], { type: 'text/calendar' }));
      a.download = 'anime-haishin.ics'; document.body.appendChild(a); a.click(); a.remove();
    };
  }

  // ------------------------------------------------------------ 全体
  function renderTabs() {
    var T = [['week', 'これから7日間'], ['works', '作品を選ぶ（' + sel.length + '）'], ['cal', 'カレンダーに入れる']];
    $('#hs-tabs').innerHTML = T.map(function (t) { return '<a href="#' + t[0] + '"' + (view === t[0] ? ' class="on"' : '') + ' data-v="' + t[0] + '">' + t[1] + '</a>'; }).join('');
    Array.prototype.forEach.call(document.querySelectorAll('#hs-tabs a'), function (a) { a.onclick = function (e) { e.preventDefault(); view = a.dataset.v; LS.set('hs_view', view); render(); }; });
  }
  function render() {
    renderSvc(); renderTabs();
    if (view === 'works') renderWorks(); else if (view === 'cal') renderCal(); else renderWeek();
  }
  var V = (document.currentScript && document.currentScript.dataset.v) || '';
  Promise.all([
    fetch('haishin/schedule.json?v=' + V).then(function (r) { return r.json(); }),
    fetch('haishin/my.json?v=' + V).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (a) {
    D = a[0]; MY = a[1];
    D.services.forEach(function (s) { NAMES[s[0]] = s[1]; });
    svc = LS.get('hs_svc', null) || (MY && MY.services) || DEF_SVC.slice();
    sel = LS.get('hs_sel', null) || (MY && MY.works !== 'all' && MY.works) || [];
    var ids = {}; D.works.forEach(function (w) { ids[w.id] = 1; });
    sel = sel.filter(function (i) { return ids[i]; });
    if (location.hash && ['#week', '#works', '#cal'].indexOf(location.hash) >= 0) view = location.hash.slice(1);
    $('#hs-gen').textContent = D.generated.replace('T', ' ') + ' 取得';
    render();
  }).catch(function (e) { $('#hs-main').innerHTML = '<p class="hs-note">データを読み込めませんでした（' + esc(e) + '）</p>'; });
})();
