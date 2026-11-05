// 試し書き：評論と記事リンクを、公開と同じ見た目でその場に表示する（build.py の書式と同じ決まり）
(function(){
var $=function(id){return document.getElementById(id)};
var titles=null, byId={}, byTitle={};
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fmtDate(s){var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(s||'');if(m)return +m[1]+'年'+(+m[2])+'月'+(+m[3])+'日';m=/^(\d{4})-(\d{2})/.exec(s||'');return m?+m[1]+'年'+(+m[2])+'月':(s||'')}
function findWork(id,title){if(id&&byId[id])return id;if(!id&&title&&byTitle[title]&&byTitle[title].length==1)return byTitle[title][0];return null}
var warn=[];
function inline(s){
  s=esc(s);
  s=s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,'<a href="$2">$1</a>');
  s=s.replace(/\[\[([^\]]+)\]\]/g,function(_,k){
    var t=k.replace(/&amp;/g,'&');var w=byId[t]?t:(byTitle[t]&&byTitle[t].length==1?byTitle[t][0]:null);
    if(w)return '<a href="w/'+w+'.html">'+esc(byId[w][1])+'</a>';
    return '<a href="#" title="人の名前（公開時に人のページがあればリンク）">'+k+'</a>'});
  return s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
}
function body(text){
  var out=[],lst=[],q=[];
  function flush(){if(lst.length){out.push('<ul>'+lst.map(function(x){return '<li>'+x+'</li>'}).join('')+'</ul>');lst=[]}
    if(q.length){out.push('<blockquote>'+q.map(function(x){return '<p>'+x+'</p>'}).join('')+'</blockquote>');q=[]}}
  text.split('\n').forEach(function(line){
    var t=line.trim(),m;
    if(!t){flush();return}
    if(m=/^(#{2,4})\s+(.*)$/.exec(t)){flush();var lv=Math.min(6,4+m[1].length-2);out.push('<h'+lv+'>'+inline(m[2].replace(/\s*\{#[\w-]+\}$/,''))+'</h'+lv+'>');return}
    if(t[0]=='>'){if(lst.length)flush();q.push(inline(t.replace(/^>+/,'').trim()));return}
    if(/^[-・]\s/.test(t)){if(q.length)flush();lst.push(inline(t.slice(2).trim()));return}
    flush();out.push('<p>'+inline(t)+'</p>');
  });
  flush();return out.join('\n');
}
function review(src){
  src=src.replace(/\r\n/g,'\n');var meta={},b=src,m=/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(src);
  if(m){m[1].split('\n').forEach(function(l){var i=l.indexOf(':');if(i>0)meta[l.slice(0,i).trim()]=l.slice(i+1).trim()});b=m[2]}
  var w=findWork(meta['番組ID']||'',meta['番組']||'');
  if(!w&&(meta['番組ID']||meta['番組']))warn.push('評論：番組「'+(meta['番組ID']||meta['番組'])+'」が見つかりません');
  var title=meta['題名']||(w?byId[w][1]:'（題名）');
  return {w:w,html:'<article class="review"><h3>'+esc(title)+'</h3><p class="meta">'+fmtDate(meta['日付']||'')+(meta['初出']?'　'+esc(meta['初出']):'')+'</p><div class="text">'+body(b)+'</div></article>'};
}
function csvRows(text){var rows=[],row=[],f='',q=false;for(var i=0;i<text.length;i++){var c=text[i];
  if(q){if(c=='"'){if(text[i+1]=='"'){f+='"';i++}else q=false}else f+=c}
  else if(c=='"')q=true;else if(c==','){row.push(f);f=''}else if(c=='\n'){row.push(f);rows.push(row);row=[];f=''}else if(c!='\r')f+=c}
  if(f||row.length){row.push(f);rows.push(row)}return rows}
var COLS=['番組ID','番組名','種別','題名','筆者','媒体','日付','URL','抜粋・メモ'];
var ORDER=['評論','批評','インタビュー','対談','記事','コラム','感想','資料'];
function links(text){
  var rows=csvRows(text.trim()).filter(function(r){return r.join('').trim()&&r[0]!='番組ID'});
  var items=rows.map(function(r,i){var o={};COLS.forEach(function(k,j){o[k]=(r[j]||'').trim()});
    if(r.length>COLS.length)warn.push('リンク'+(i+1)+'行目：列が'+r.length+'個あります（9個のはず）。文の中の半角カンマは "…" で囲んでください');
    o.w=findWork(o['番組ID'],o['番組名']);if(!o.w)warn.push('リンク'+(i+1)+'行目：番組が見つかりません');return o});
  items.sort(function(a,b){var x=ORDER.indexOf(a['種別']),y=ORDER.indexOf(b['種別']);x=x<0?99:x;y=y<0?99:y;return x-y||(a['日付']<b['日付']?-1:1)});
  var out=[],cur=null;
  items.forEach(function(l){var k=l['種別']||'その他';if(k!==cur){if(cur!==null)out.push('</ul>');out.push('<h3>'+esc(k)+'</h3><ul class="links">');cur=k}
    var t=esc(l['題名']||l['URL']);if(l['URL'])t='<a href="'+esc(l['URL'])+'">'+t+'</a>';
    var by=[esc(l['筆者']),l['媒体']?'「'+esc(l['媒体'])+'」':'',fmtDate(l['日付'])].filter(Boolean).join('　');
    out.push('<li>'+t+'<span class="by">'+by+'</span>'+(l['抜粋・メモ']?'<blockquote>'+esc(l['抜粋・メモ'])+'</blockquote>':'')+'</li>')});
  if(cur!==null)out.push('</ul>');
  return {w:items.length?items[0].w:null,html:out.join('')};
}
function run(){
  if(!titles)return;warn=[];
  var r=$('rv').value.trim()?review($('rv').value):null, l=$('lk').value.trim()?links($('lk').value):null;
  var w=(r&&r.w)||(l&&l.w);
  $('out').innerHTML=(w?'<h1>'+esc(byId[w][1])+'</h1>':'<h1>（番組）</h1>')+
    '<h2>評論</h2>'+(r?r.html:'<p class="none">まだありません。</p>')+
    '<h2>評論・記事</h2>'+(l&&l.html?l.html:'<p class="none">まだありません。</p>');
  $('warn').innerHTML=warn.map(function(x){return '<li>'+esc(x)+'</li>'}).join('');
  try{localStorage.setItem('pv-rv',$('rv').value);localStorage.setItem('pv-lk',$('lk').value)}catch(e){}
}
try{var a=localStorage.getItem('pv-rv'),b=localStorage.getItem('pv-lk');if(a)$('rv').value=a;if(b)$('lk').value=b}catch(e){}
['rv','lk'].forEach(function(id){$(id).addEventListener('input',run)});
fetch('titles.json').then(function(r){return r.json()}).then(function(j){titles=j;j.forEach(function(x){byId[x[0]]=x;(byTitle[x[1]]=byTitle[x[1]]||[]).push(x[0])});run()});
})();
