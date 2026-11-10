// 各話クレジット：選んだ年のファイル（credits/episodes/YYYY.json）だけを読み込む
(()=>{
const BASE=window.CREDITS_BASE||'credits/';
const gz=u=>fetch(u).then(r=>{if(!r.ok)throw new Error(r.status);return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()});   // 年のファイルは gzip で置いてある
let D={W:[]},M=[],MS={},DL={},S=[],RL=[],FIRST=[],RG={},LOADED=null;
const cache=new Map();
const load=y=>{if(!cache.has(y))cache.set(y,gz(BASE+'episodes/'+y+'.json.gz'));return cache.get(y)};
const SEASONS=[['冬','12-01','02-31',-1],['春','03-01','05-31',0],['夏','06-01','08-31',0],['秋','09-01','11-30',0],['通年','01-01','12-31',0]];
const MODES=['回ごと','人ごと','季節の合計'];
const $=id=>document.getElementById(id);
const st={year:2024,season:'春',role:'絵コンテ',mode:'人ごと',by:'開始日'};
try{Object.assign(st,JSON.parse(localStorage.getItem('aw_ep')||'{}'))}catch(e){}
const seg=(id,list,key)=>list.forEach(s=>{const b=document.createElement('button');b.type='button';b.textContent=s;b.onclick=()=>{st[key]=s;render()};$(id).append(b)});
seg('season',SEASONS.map(s=>s[0]),'season');seg('by',['開始日','放送日'],'by');seg('mode',MODES,'mode');

const SAK=new Set(['作画監督','総作画監督','専門作画監督']);
const ds=n=>n?String(n).replace(/(\d{4})(\d\d)(\d\d)/,'$1-$2-$3'):'';const wsd=w=>+(w[1]||'0').replace(/-/g,'');
const P=x=>typeof x==='number'?[x,1]:x;
// 年のファイルを読み込んで、初登場（役職ごと：その人が担当したいちばん早く始まった作品の開始日）と、スタジオの常連かを用意する
function use(d){D=d;S=d.S;M=d.m;MS=d.ms;DL=d.dl;FIRST=d.fx.map(o=>new Map(Object.entries(o)));RG={};for(const k in d.rg){const m=RG[k]={};d.rg[k].forEach((L,i)=>L.forEach(x=>m[S[x]]=i?'2作目':'初参加'))}}
const DEBUT_ROLES=new Set(['絵コンテ','演出']);
const yearOf=(r,p)=>(DEBUT_ROLES.has(r)&&DL[p])||Math.floor((FIRST[RL.indexOf(r)].get(p)||0)/10000)||'';
function range(){const s=SEASONS.find(x=>x[0]===st.season);const y=+st.year;const n=(yy,m)=>+(yy+m.replace('-',''));return[n(y+s[3],s[1]),n(y,s[2])]}
const md=d=>{if(!d)return'';const m=d.split('-');return(+m[1])+'/'+(+m[2])};
const fmt=v=>(Math.round(v*100)/100).toString();
function nm(x){x=P(x);const k=x[2]!=null?S[x[2]]:'';return S[x[0]]+(k&&!/^作画監督$|^総作画監督$/.test(k)?'（'+k.replace(/作画監督$|総作画監督$/,'')+'）':'')}
function soleIn(e,r){const i=RL.indexOf(r);const c=e[3].find(x=>x[0]===i);if(!c||c[1].length!==1)return null;const x=P(c[1][0]);return x[1]===1&&!(x[2]!=null&&S[x[2]]==='演出から')?S[x[0]]:null}
function tally(eps,roles,main,reg){
  const T={};
  for(const e of eps){
    const ce=soleIn(e,'絵コンテ'),en=soleIn(e,'演出');const both=ce&&ce===en?ce:null;
    for(const[ri,ns]of e[3]){const r=RL[ri];if(!roles.has(r))continue;
      const best={};for(let x of ns){x=P(x);const p=S[x[0]];const v=SAK.has(r)?1/x[1]:(x[1]>1?0.5:1);best[p]=Math.max(best[p]||0,v)}
      for(const p in best){const k=r+'\u0000'+p;const t=T[k]=T[k]||{r,p,v:0,j:0,s:0,ce:0};t.v+=best[p];if(!SAK.has(r)&&best[p]<1)t.j++;else t.s++;if(both===p&&DEBUT_ROLES.has(r))t.ce++}}}
  const out=Object.values(T);out.forEach(t=>{t.y=yearOf(t.r,t.p);t.notes=[...((main&&main[t.p])||[]),...(t.ce?['コンテ演出回']:[])];t.reg=reg&&!reg[t.p]?'常連':''});
  return out.sort((a,b)=>RL.indexOf(a.r)-RL.indexOf(b.r)||b.v-a.v||(a.y||9999)-(b.y||9999)||a.p.localeCompare(b.p,'ja'));
}
function line(t,a,b){const f=FIRST[RL.indexOf(t.r)].get(t.p);const star=f>=a&&f<=b?'★':'';
  return `${star}${t.y||'----'}　${t.j&&!t.s?'（共）':''}${t.p}　${fmt(t.v)}話${t.notes.length||t.reg?'（'+[t.notes.join('、'),t.reg].filter(Boolean).join('／')+'）':''}`}
let seq=0;
async function render(){
  if(LOADED!==+st.year){const my=++seq;$('count').textContent='読み込み中…';let d;try{d=await load(+st.year)}catch(e){$('count').textContent='データを読み込めませんでした。';return}if(my!==seq)return;use(d);LOADED=+st.year}
  $('year').value=st.year;$('role').value=st.role;
  for(const[id,k]of[['season','season'],['mode','mode'],['by','by']])[...$(id).children].forEach(b=>b.setAttribute('aria-pressed',b.textContent===st[k]));
  try{localStorage.setItem('aw_ep',JSON.stringify(st))}catch(e){}
  const[a,b]=range();const all=st.role==='*';const roles=new Set(all?RL:[st.role]);
  const ri=new Set([...roles].map(r=>RL.indexOf(r)));
  const L=[`■ ${st.year}年${st.season==='通年'?'':st.season}　${all?'7役職':st.role}　${st.mode}`,''];
  let nw=0,ne=0;const agg=[];const ws=[];
  for(const w of D.W){
    {const d=wsd(w);if(st.by==='開始日'&&!(d>=a&&d<=b))continue}
    const eps=w[3].filter(e=>{if(st.by==='開始日')return true;const d=e[2]||wsd(w);return d>=a&&d<=b}).filter(e=>e[3].some(x=>ri.has(x[0])));
    if(eps.length)ws.push([w,eps]);
  }
  ws.sort((x,y)=>(st.by==='開始日'?wsd(x[0])-wsd(y[0]):((x[1][0][2]||wsd(x[0]))-(y[1][0][2]||wsd(y[0]))))||x[0][0].localeCompare(y[0][0],'ja'));
  for(const[w,eps]of ws){
    nw++;ne+=eps.length;
    if(st.mode==='季節の合計'){agg.push(...eps);continue}
    if(st.mode==='回ごと'){
      L.push(`${w[0]}（${md(w[1])}〜${w[2]?'・'+w[2]:''}）`);
      let lastK=null;
      for(const e of eps){
        const kg=S[e[0]];if(kg&&kg!=='各話リスト'&&kg!==lastK){L.push('　〔'+kg+'〕');lastK=kg}
        const ep=e[1]?(/^\d+$/.test(e[1])?'#'+e[1]:e[1]):'';
        const body=e[3].filter(x=>ri.has(x[0])).sort((p,q)=>p[0]-q[0]).map(([r,ns])=>(all?RL[r]+'：':'')+ns.map(nm).join('、')).join('　／　');
        L.push(`　${ep}　${md(ds(e[2]))}　${body}`);
      }
    }else{
      L.push(`◆${w[0]}　${w[2]||''}`.trimEnd());
      let cur=null;
      for(const t of tally(eps,roles,MS[w[0]+'|'+w[1]],RG[w[0]+'|'+w[1]])){if(all&&t.r!==cur){L.push('〔'+t.r+'〕');cur=t.r}L.push(line(t,a,b))}
    }
    L.push('');
  }
  if(st.mode==='季節の合計'){let cur=null;for(const t of tally(agg,roles,null)){if(all&&t.r!==cur){L.push('〔'+t.r+'〕');cur=t.r}L.push(line(t,a,b))}}
  if(!ws.length)L.push('この期間のデータはありません。');
  if(st.by==='開始日'){
    const MAIN=['作画監督','総作画監督','脚本','絵コンテ','演出'];
    const ms=M.filter(m=>{const d=+m[1].replace(/-/g,'');return d>=a&&d<=b}).map(m=>[m,(all?MAIN:[st.role]).filter(r=>m[2][r])]).filter(x=>x[1].length);
    if(ms.length){L.push('','―― 各話データが取れなかった作品（'+ms.length+'）');
      for(const[m,rs]of ms)L.push(`　${m[0]}（${md(m[1])}〜）　`+(all?rs.map(r=>r+'：'+m[2][r]).join('／'):m[2][rs[0]]))}
  }
  $('out').textContent=L.join('\n');
  $('count').innerHTML=`${nw}作品<small>${ne}回</small>`;
}
$('year').onchange=e=>{st.year=+e.target.value;render()};
$('role').onchange=e=>{st.role=e.target.value;render()};
window.CREDITS_COPY_DONE=1;$('copy').onclick=()=>{const t=$('out').textContent;const done=()=>{$('copy').textContent='コピーしました';setTimeout(()=>$('copy').textContent='テキストをコピー',1500)};
  const sel=()=>{const r=document.createRange();r.selectNodeContents($('out'));const s=getSelection();s.removeAllRanges();s.addRange(r);$('copy').textContent='選択しました（Ctrl+C）'};
  try{navigator.clipboard.writeText(t).then(done,sel)}catch(e){sel()}};
fetch(BASE+'episodes/index.json').then(r=>r.json()).then(ix=>{
  RL=ix.R;const Y=ix.Y;for(let y=Y[Y.length-1];y>=Y[0];y--)$('year').add(new Option(y+'年',y));
  if(!Y.includes(+st.year))st.year=2024;
  $('role').add(new Option('7役職すべて','*'));RL.forEach(r=>$('role').add(new Option(r,r)));
  render();
}).catch(()=>{$('count').textContent='データを読み込めませんでした。'});
})();
