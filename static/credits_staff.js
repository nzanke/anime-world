// シーズン別スタッフ表：選んだ年のファイル（credits/staff/YYYY.json）だけを読み込む
(()=>{
const BASE=window.CREDITS_BASE||'credits/';
const $=id=>document.getElementById(id);
const SEASONS=[['冬','12-01','02-31',-1],['春','03-01','05-31',0],['夏','06-01','08-31',0],['秋','09-01','11-30',0],['通年','01-01','12-31',0]];
const st={year:2024,year2:2024,season:'春',role:'#CG',raw:false,q:''};
try{Object.assign(st,JSON.parse(localStorage.getItem('aw_staff')||'{}'))}catch(e){}
const cache=new Map();
const load=y=>{if(!cache.has(y))cache.set(y,fetch(BASE+'staff/'+y+'.json').then(r=>r.ok?r.json():{S:[],W:[]}).then(d=>d.W.map(w=>[w[0],w[1],w[2],w[3].map(c=>[d.S[c[0]],d.S[c[1]],d.S[c[2]],c[3].map(i=>d.S[i])])])).catch(()=>[]));return cache.get(y)};
const NQ=x=>(x||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');
const md=d=>{if(!d)return'';const m=d.split('-');return(+m[1])+'/'+(+m[2]||'')};
let IX,KUB;
function range(){const s=SEASONS.find(x=>x[0]===st.season);const y=+st.year,y2=+st.year2;
  if(y2>y)return[y+'-01-01',y2+'-12-31'];return[(y+s[3])+'-'+s[1],y+'-'+s[2]]}
let seq=0;
async function render(){
  $('year').value=st.year;$('year2').value=st.year2;$('role').value=st.role;$('raw').checked=st.raw;if($('q').value!==st.q)$('q').value=st.q;
  const multi=+st.year2>+st.year;$('season').classList.toggle('off',multi);
  [...$('season').children].forEach(b=>b.setAttribute('aria-pressed',b.textContent===st.season));
  try{localStorage.setItem('aw_staff',JSON.stringify(st))}catch(e){}
  const my=++seq;$('count').textContent='読み込み中…';
  const ys=[];for(let y=+st.year;y<=+st.year2;y++)ys.push(y);
  const parts=await Promise.all(ys.map(load));if(my!==seq)return;
  const[a,b]=range();const seen=new Set();
  const ws=parts.flat().filter(w=>{const k=w[0]+'|'+w[1];if(seen.has(k)||!(w[1]>=a&&w[1]<=b+'~'))return false;seen.add(k);return true})
    .sort((x,y)=>x[1]<y[1]?-1:x[1]>y[1]?1:x[0].localeCompare(y[0],'ja'));
  const all=st.role==='*',grp=st.role[0]==='#'?st.role.slice(1):null,q=NQ(st.q);
  const hitRole=c=>all||(grp?c[2]===grp:c[1]===st.role);
  const label=all?'すべての役職':grp?grp+'（区分）':st.role;
  const per=multi?`${st.year}〜${st.year2}年`:`${st.year}年${st.season==='通年'?'':st.season}`;
  const L=[`■ ${per}　${label}${q?'　キーワード「'+st.q+'」':''}`,''];let n=0;const none=[];
  for(const w of ws){
    const tq=q&&NQ(w[0]).includes(q);
    const cs=w[3].filter(c=>hitRole(c)&&(!q||tq||c[3].some(x=>NQ(x).includes(q))||NQ(c[0]).includes(q)));
    if(!cs.length){if(!q)none.push(w[0]);continue}
    n++;L.push(`${w[0]}（${multi?w[1].slice(0,4)+'/':''}${md(w[1])}〜${w[2]?'・'+w[2]:''}）`);
    if(all||grp)cs.forEach(c=>L.push('　'+c[0]+'：'+c[3].join('、')));
    else L.push('　'+cs.map(c=>c[3].join('、')+(st.raw&&c[0]!==st.role?'（'+c[0]+'）':'')).join('／'));
    L.push('');
  }
  if(none.length)L.push('―― スタッフ欄にこの役職がない作品（'+none.length+'）','　'+none.join('、'));
  if(!ws.length)L.push('この期間に始まった作品はありません。');else if(q&&!n)L.push('この期間・役職で、キーワードに合うクレジットはありません。');
  $('out').textContent=L.join('\n');
  $('count').textContent=`${n}作品（この期間に始まった作品 ${ws.length}）`;
}
fetch(BASE+'staff/index.json').then(r=>r.json()).then(ix=>{
  IX=ix;KUB=Object.fromEntries(ix.R.map(r=>[r[0],r[1]]));
  const Y=ix.Y;for(let y=Y[Y.length-1];y>=Y[0];y--){$('year').add(new Option(y+'年',y));$('year2').add(new Option(y+'年',y))}
  if(!Y.includes(+st.year))st.year=2024;if(!Y.includes(+st.year2)||st.year2<st.year)st.year2=st.year;
  SEASONS.forEach(s=>{const b=document.createElement('button');b.type='button';b.textContent=s[0];b.onclick=()=>{st.season=s[0];st.year2=st.year;render()};$('season').append(b)});
  const rs=$('role');rs.add(new Option('すべての役職','*'));
  ix.K.forEach(k=>{const rl=ix.R.filter(r=>r[1]===k&&r[2]>=3);if(!rl.length)return;const g=document.createElement('optgroup');g.label=k;g.append(new Option('〔'+k+'をすべて〕','#'+k));rl.forEach(r=>g.append(new Option(r[0],r[0])));rs.append(g)});
  if(![...rs.options].some(o=>o.value===st.role))st.role='#CG';
  $('year').onchange=e=>{st.year=+e.target.value;if(st.year2<st.year)st.year2=st.year;render()};
  $('year2').onchange=e=>{st.year2=+e.target.value;if(st.year2<st.year)st.year=st.year2;render()};
  rs.onchange=e=>{st.role=e.target.value;render()};$('raw').onchange=e=>{st.raw=e.target.checked;render()};
  let tm;$('q').oninput=e=>{clearTimeout(tm);tm=setTimeout(()=>{st.q=e.target.value.trim();render()},250)};
  render();
}).catch(()=>{$('count').textContent='データを読み込めませんでした。'});
window.CREDITS_COPY&&window.CREDITS_COPY();
})();
