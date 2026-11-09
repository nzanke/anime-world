// 記事リンクの追加：保存したHTMLから links.csv の1行を作る（任意で GitHub に直接追加）
(function(){
var $=function(id){return document.getElementById(id)};
var REPO='nzanke/anime-world', PATH='content/links.csv';
var titles=[], byId={};
function norm(s){return (s||'').normalize('NFKC').toLowerCase().replace(/[\s・!！?？:：\-－〜～☆★♪「」『』【】（）()、。,.]/g,'')}
fetch('titles.json').then(function(r){return r.json()}).then(function(j){titles=j;j.forEach(function(x){byId[x[0]]=x;x[5]=norm(x[1])});guess()});

function meta(doc,sel){var e=doc.querySelector(sel);return e?(e.getAttribute('content')||'').trim():''}
function pickDate(s){if(!s)return'';var m=/(\d{4})[-\/年.](\d{1,2})[-\/月.](\d{1,2})/.exec(s);return m?m[1]+'-'+('0'+m[2]).slice(-2)+'-'+('0'+m[3]).slice(-2):''}
function parse(raw){
  var doc=new DOMParser().parseFromString(raw,'text/html'), r={};
  var m=/saved from url=\(\d+\)(\S+)/.exec(raw);
  r.url=meta(doc,'meta[property="og:url"]')||((doc.querySelector('link[rel=canonical]')||{}).href||'')||(m?m[1].replace(/\s*-->.*$/,''):'')||((/dc:identifier="([^"]+)"/.exec(raw)||[])[1]||'');
  var site=meta(doc,'meta[property="og:site_name"]');
  var t=meta(doc,'meta[property="og:title"]')||((/dc:title="([^"]+)"/.exec(raw)||[])[1]||'')||(doc.title||'');
  if(site)t=t.replace(new RegExp('\\s*[:：|｜\\-－]\\s*'+site.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*$'),'');
  r.title=t.trim(); r.site=site;
  var ld={};doc.querySelectorAll('script[type="application/ld+json"]').forEach(function(s){try{var j=JSON.parse(s.textContent);(Array.isArray(j)?j:[j]).forEach(function(o){if(o.datePublished&&!ld.date)ld.date=o.datePublished;if(o.author&&!ld.author)ld.author=[].concat(o.author)[0].name||''})}catch(e){}});
  r.author=meta(doc,'meta[name="author"]')||meta(doc,'meta[property="article:author"]')||ld.author||((/dc:creator="([^"]+)"/.exec(raw)||[])[1]||'')||((/posted by\s*([^<|｜\s]+)/i.exec(raw)||[])[1]||'');
  if(/^https?:/.test(r.author))r.author='';
  var te=doc.querySelector('time[datetime]');
  r.date=pickDate(meta(doc,'meta[property="article:published_time"]'))||pickDate(ld.date)||pickDate((/dc:date="([^"]+)"/.exec(raw)||[])[1])||pickDate(te&&te.getAttribute('datetime'))||pickDate(((doc.body&&doc.body.textContent)||'').match(/\d{4}年\d{1,2}月\d{1,2}日/)||'');
  return r;
}
function readFile(f){
  var fr=new FileReader();fr.onload=function(){
    var buf=fr.result, head=new TextDecoder('ascii').decode(buf.slice(0,4000)).toLowerCase();
    var cs=(/charset=["']?([\w-]+)/.exec(head)||[])[1]||'utf-8';
    var raw;try{raw=new TextDecoder('utf-8',{fatal:true}).decode(buf)}catch(e){try{raw=new TextDecoder(cs).decode(buf)}catch(e2){raw=new TextDecoder('utf-8').decode(buf)}}
    var r=parse(raw);
    $('f-url').value=r.url;$('f-title').value=r.title;$('f-author').value=r.author;$('f-site').value=r.site;$('f-date').value=r.date;
    $('f-kind').value=kindOf(r.url);
    $('fname').textContent=f.name;guess();out()};
  fr.readAsArrayBuffer(f);
}
function kindOf(u){u=(u||'').toLowerCase();
  if(/note\.com|hatena|ameblo|seesaa|sblo\.jp|fc2\.com|livedoor\.(jp|blog)|blogspot|wordpress|cocolog|exblog|goo\.ne\.jp\/|jugem|teacup|yaplog|muragon|blog/.test(u))return 'ブログ';
  if(/natalie\.mu|animeanime|mantan-web|oricon|famitsu|4gamer|itmedia|gigazine|webnewtype|animatetimes|dengekionline|realsound|cinematoday|eiga\.com|febri|ddnavi|bunshun|gendai|toyokeizai|news\.|yahoo|livedoor\.com|excite|anime\.eiga|akiba-souken|animage|newtype/.test(u))return 'ネットメディア';
  if(/wiki/.test(u))return 'ウェブサイト';
  return 'その他'}
function guess(){
  if(!titles.length)return;var t=norm($('f-title').value+' '+$('q').value);if(!t)return;
  var c=titles.filter(function(x){return x[5].length>1&&t.indexOf(x[5])>=0}).sort(function(a,b){return b[5].length-a[5].length}).slice(0,8);
  setCands(c);
}
function search(){var k=norm($('q').value);if(!k){guess();return}
  setCands(titles.filter(function(x){return x[5].indexOf(k)>=0}).slice(0,30))}
function setCands(c){var s=$('f-work');s.innerHTML=c.length?c.map(function(x){return '<option value="'+x[0]+'">'+x[1].replace(/</g,'&lt;')+'（'+x[2]+'）</option>'}).join(''):'<option value="">（番組名で探してください）</option>';out()}
function q(v){v=(v||'').trim();return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
function line(){var w=$('f-work').value;
  return [w,w&&byId[w]?byId[w][1]:'',$('f-kind').value,$('f-title').value,$('f-author').value,$('f-site').value,$('f-date').value,$('f-url').value,$('f-scope').value?$('f-epno').value.replace(/^[#＃]\s*/,''):'',$('f-scope').value?$('f-epsub').value:'',$('f-type').value].map(q).join(',')}
function out(){$('line').value=line();$('chk').textContent=!$('f-work').value?'番組を選んでください':($('f-scope').value&&!$('f-epno').value?'話数を入れてください':'')}
var epFor=null,epList=[];
function loadEps(){var w=$('f-work').value,on=!!$('f-scope').value;$('ep-wrap').hidden=!on;
  if(!on||!w||epFor===w){out();return}epFor=w;$('f-ep').innerHTML='<option value="">読み込み中…</option>';
  fetch('eps/'+w+'.json').then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
    $('f-ep').innerHTML='<option value="">（選ぶと下の欄に入ります）</option>'+j.map(function(e,i){return '<option value="'+i+'">'+('#'+e[0]+(e[1]?'「'+e[1]+'」':'')).replace(/</g,'&lt;')+'</option>'}).join('');epList=j;out()})
  .catch(function(){$('f-ep').innerHTML='<option value="">（この番組には各話リストがありません）</option>';out()})}
$('f-scope').addEventListener('change',loadEps);$('f-work').addEventListener('change',loadEps);$('f-ep').addEventListener('change',function(){var e=epList[+this.value];if(this.value!==''&&e){$('f-epno').value=e[0];$('f-epsub').value=e[1]||''}out()});
['f-epno','f-epsub'].forEach(function(id){$(id).addEventListener('input',out)});
['f-url','f-title','f-author','f-site','f-date','f-kind','f-type','f-work'].forEach(function(id){$(id).addEventListener('input',out);$(id).addEventListener('change',out)});
$('q').addEventListener('input',search);
$('f-url').addEventListener('input',function(){$('f-kind').value=kindOf(this.value);out()});
var dz=$('drop');
dz.addEventListener('dragover',function(e){e.preventDefault();dz.classList.add('over')});
dz.addEventListener('dragleave',function(){dz.classList.remove('over')});
dz.addEventListener('drop',function(e){e.preventDefault();dz.classList.remove('over');if(e.dataTransfer.files[0])readFile(e.dataTransfer.files[0])});
$('file').addEventListener('change',function(){if(this.files[0])readFile(this.files[0])});
$('copy').addEventListener('click',function(){navigator.clipboard.writeText($('line').value).then(function(){$('msg').textContent='コピーしました。GitHubで links.csv のいちばん下に貼って保存してください。'},function(){$('line').select();$('msg').textContent='選択したので手動でコピーしてください'})});

// GitHub に直接追加（任意）
try{$('tok').value=localStorage.getItem('gh-token')||''}catch(e){}
$('tok').addEventListener('change',function(){try{localStorage.setItem('gh-token',this.value.trim())}catch(e){}});
function b64dec(s){var b=atob(s.replace(/\n/g,'')),a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return new TextDecoder().decode(a)}
function b64enc(s){var a=new TextEncoder().encode(s),b='';for(var i=0;i<a.length;i++)b+=String.fromCharCode(a[i]);return btoa(b)}
$('push').addEventListener('click',function(){
  var tok=$('tok').value.trim(),L=$('line').value;if(!tok){$('msg').textContent='トークンを入れてください';return}
  if(!$('f-work').value){$('msg').textContent='番組を選んでください';return}
  var api='https://api.github.com/repos/'+REPO+'/contents/'+PATH, H={'Authorization':'Bearer '+tok,'Accept':'application/vnd.github+json'};
  $('msg').textContent='追加しています…';
  fetch(api+'?ref=main',{headers:H}).then(function(r){if(!r.ok)throw new Error('読み込み '+r.status);return r.json()}).then(function(j){
    var cur=b64dec(j.content);if(cur.indexOf(L)>=0)throw new Error('同じ行がもうあります');
    var next=cur.replace(/\s*$/,'')+'\n'+L+'\n';
    return fetch(api,{method:'PUT',headers:H,body:JSON.stringify({message:'記事リンクを追加：'+$('f-title').value,content:b64enc(next),sha:j.sha,branch:'main'})})
  }).then(function(r){if(!r.ok)throw new Error('書き込み '+r.status);$('msg').textContent='追加しました。1〜2分でサイトに出ます。'})
  .catch(function(e){$('msg').textContent='できませんでした：'+e.message})});
})();
