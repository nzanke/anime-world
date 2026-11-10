// アニメ映画スタッフ表：選んだ年のファイル（credits/films/YYYY.json）だけを読み込む
(()=>{
const BASE=window.CREDITS_BASE||'credits/';
const gz=u=>fetch(u).then(r=>{if(!r.ok)throw new Error(r.status);return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()});   // 年のファイルは gzip で置いてある
const $=id=>document.getElementById(id);
const st={y:2024,y2:2024,role:'r:監督',mode:'作品ごと',q:''};
try{Object.assign(st,JSON.parse(localStorage.getItem('aw_film')||'{}'))}catch(e){}
const cache=new Map();
// 記事の役職表記が違っても、そろえた役職が同じものは1つにまとめる（「監督」と「監督・脚本」の監督）
const merge=cs=>{const m=new Map();for(const c of cs){const k=c[1]+'\u0000'+c[2];if(!m.has(k))m.set(k,[c[1],c[1],c[2],[]]);const L=m.get(k)[3];for(const p of c[3])if(!L.includes(p))L.push(p)}return[...m.values()]};
const load=y=>{if(!cache.has(y))cache.set(y,gz(BASE+'films/'+y+'.json.gz').catch(()=>({S:[],W:[]})).then(d=>d.W.map(w=>[w[0],w[1],w[2],merge(w[3].map(c=>[d.S[c[0]],d.S[c[1]],d.S[c[2]],c[3].map(i=>d.S[i])]))])).catch(()=>[]));return cache.get(y)};
const NQ=x=>(x||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');
const pn=x=>x.replace(/（[^（）]*）$/,'');   // 人ごとにまとめるときは、名前のあとのかっこ書きを外す
const okRole=c=>!st.role||(st.role.startsWith('k:')?c[2]===st.role.slice(2):c[1]===st.role.slice(2));
let Y=[],seq=0;
async function render(){
  $('y').value=st.y;$('y2').value=st.y2;$('role').value=st.role;if($('q').value!==st.q)$('q').value=st.q;
  [...$('mode').children].forEach(b=>b.setAttribute('aria-pressed',b.textContent===st.mode));
  try{localStorage.setItem('aw_film',JSON.stringify(st))}catch(e){}
  const my=++seq;$('count').textContent='読み込み中…';
  const ys=Y.filter(y=>y>=+st.y&&y<=+st.y2);
  const parts=await Promise.all(ys.map(load));if(my!==seq)return;
  const seen=new Set();
  const ws=parts.flat().filter(w=>{const k=w[0]+'|'+w[1];const y=+w[1].slice(0,4);if(seen.has(k)||y<+st.y||y>+st.y2)return false;seen.add(k);return true});
  const q=NQ(st.q),rn=st.role?st.role.slice(2):'すべての役職';
  const L=[`■ ${st.y===st.y2?st.y+'年':st.y+'〜'+st.y2+'年'}公開　${rn}　${st.mode}${q?'　キーワード「'+st.q+'」':''}`,''];let nf=0;
  if(st.mode==='作品ごと'){
    for(const w of ws){const cr=w[3].filter(okRole);
      const body=cr.map(c=>(st.role.startsWith('r:')?'':c[0]+'　')+c[3].join('、'));
      if(q&&!NQ(w[0]).includes(q)&&!body.some(x=>NQ(x).includes(q)))continue;
      if(!cr.length&&st.role)continue;nf++;
      L.push(`◆${w[0]}（${w[1]||'公開日不明'}）　${w[2]||'制作不明'}`);body.forEach(x=>L.push(x));if(!body.length)L.push('（記載なし）');L.push('')}
  }else{
    const m=new Map();
    for(const w of ws)for(const c of w[3]){if(!okRole(c))continue;for(const p of c[3]){const n=pn(p);if(!m.has(n))m.set(n,new Map());const e=m.get(n);if(!e.has(w))e.set(w,new Set());e.get(w).add(c[0])}}
    let rows=[...m].filter(([n,e])=>!q||NQ(n).includes(q)||[...e.keys()].some(w=>NQ(w[0]).includes(q)));
    rows.sort((a,b)=>b[1].size-a[1].size||a[0].localeCompare(b[0],'ja'));nf=rows.length;
    for(const[n,e]of rows)L.push(`${n}　${e.size}本　${[...e].map(([w,rs])=>w[0]+(st.role.startsWith('r:')?'':'（'+[...rs].join('・')+'）')).join('／')}`);
  }
  $('count').textContent=st.mode==='作品ごと'?`${nf}本`:`${nf}人`;
  $('out').textContent=nf?L.join('\n'):L[0]+'\n\nこの条件に合うものはありません。';
}
fetch(BASE+'films/index.json').then(r=>r.json()).then(ix=>{
  Y=ix.Y;for(const s of ['y','y2'])Y.slice().reverse().forEach(y=>$(s).add(new Option(y+'年',y)));
  if(!Y.includes(+st.y))st.y=Y.includes(2024)?2024:Y[Y.length-1];if(!Y.includes(+st.y2)||+st.y2<+st.y)st.y2=st.y;
  ['作品ごと','人ごと'].forEach(m=>{const b=document.createElement('button');b.type='button';b.textContent=m;b.onclick=()=>{st.mode=m;render()};$('mode').append(b)});
  const rs=$('role');rs.add(new Option('すべての役職',''));
  const g1=document.createElement('optgroup');g1.label='区分';ix.K.forEach(k=>g1.append(new Option('区分：'+k,'k:'+k)));rs.append(g1);
  const g2=document.createElement('optgroup');g2.label='役職（多い順）';ix.R.filter(r=>r[2]>=3).forEach(r=>g2.append(new Option(r[0]+'（'+r[2]+'）','r:'+r[0])));rs.append(g2);
  if(![...rs.options].some(o=>o.value===st.role))st.role='r:監督';
  $('y').onchange=e=>{st.y=+e.target.value;if(+st.y2<st.y)st.y2=st.y;render()};
  $('y2').onchange=e=>{st.y2=+e.target.value;if(st.y2<+st.y)st.y=st.y2;render()};
  rs.onchange=e=>{st.role=e.target.value;render()};
  let tm;$('q').oninput=e=>{clearTimeout(tm);tm=setTimeout(()=>{st.q=e.target.value.trim();render()},250)};
  render();
}).catch(()=>{$('count').textContent='データを読み込めませんでした。'});
window.CREDITS_COPY&&window.CREDITS_COPY();
})();
