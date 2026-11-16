"""Standalone HTML dashboard (fallback for the Tableau workbook): same 4 views, same extracts.

    python src/build_dashboard.py      -> docs/dashboard.html (one file, Plotly inlined, works offline)

Views: 1 Product pulse, 2 Funnel & cohorts, 3 Experiments, 4 Market view (PUBLIC DATA).
Filters (views 1-2): country and platform, applied in the browser on the embedded extracts.
"""
import json

import pandas as pd
from plotly.offline import get_plotlyjs

from common import BG, BLUE, BLUE_DARK, BLUE_LIGHT, BORDER, CARD, DISCLAIMER, DOCS, GREY, INK, INK2, MUTED, OUT, RED, utf8

TAB = OUT / "tableau"


def data():
    d = {}
    for name in ("pulse", "funnel", "retention", "experiments", "market_ratings", "market_prices", "review_themes", "trends"):
        df = pd.read_csv(TAB / f"{name}.csv")
        d[name] = json.loads(df.to_json(orient="split", index=False))
    return d


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>App H product dashboard</title><meta name="author" content="">
<style>
:root{--bg:__BG__;--card:__CARD__;--border:__BORDER__;--ink:__INK__;--ink2:__INK2__;--muted:__MUTED__;--blue:__BLUE__}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",system-ui,sans-serif}
header{padding:18px 24px 6px} h1{font-size:20px;margin:0 0 4px} .sub{color:var(--ink2);font-size:13px;margin:0}
nav{display:flex;gap:6px;padding:10px 24px;flex-wrap:wrap} nav button{border:1px solid var(--border);background:var(--card);padding:7px 12px;border-radius:6px;
cursor:pointer;font:inherit;font-size:13px;color:var(--ink2)} nav button.on{background:var(--blue);color:#fff;border-color:var(--blue)}
.filters{display:flex;gap:12px;align-items:center;padding:0 24px 8px;font-size:13px;color:var(--ink2);flex-wrap:wrap}
select{font:inherit;padding:4px 6px;border:1px solid var(--border);border-radius:5px;background:var(--card)}
.view{display:none;padding:4px 24px 18px} .view.on{display:block}
.grid{display:grid;gap:12px} .g2{grid-template-columns:1fr 1fr} .g4{grid-template-columns:repeat(4,1fr)} .g7{grid-template-columns:repeat(7,1fr)}
@media(max-width:900px){.g2,.g4,.g7{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;min-width:0}
.card h3{font-size:13px;margin:0 0 4px;font-weight:600} .tag{font-size:10px;font-weight:700;letter-spacing:.06em;color:var(--ink2)}
.kv{font-size:24px;font-weight:700;margin:2px 0} .kt{font-size:11px;color:var(--ink2)}
.plot{width:100%;height:300px} .note{font-size:11.5px;color:var(--ink2);line-height:1.4;margin:6px 0 0}
table{border-collapse:collapse;width:100%;font-size:12px} th{text-align:left;color:var(--ink2);border-bottom:1px solid var(--ink2);padding:4px}
td{border-bottom:1px solid var(--border);padding:4px} td.n{text-align:right;white-space:nowrap} .bad{color:__RED__;font-weight:600} .good{color:var(--blue);font-weight:600}
footer{color:var(--muted);font-size:11px;padding:8px 24px 18px}
</style><script>__PLOTLY__</script></head><body>
<header><h1>App H: product, funnel, experiments and market</h1>
<p class="sub">Views 1-3: SIMULATED dating-app event log (fictional "App H", 1 May - 31 Oct 2026, seed 42). View 4: PUBLIC DATA (App Store, Google Trends), collected 15 Nov 2026.
Dashboard prototyped in HTML; the Tableau build guide and workbook are in the repository.</p></header>
<nav id="nav"></nav>
<div class="filters" id="filters">Country <select id="fc"><option>All</option><option>US</option><option>GB</option><option>CA</option><option>AU</option></select>
Platform <select id="fp"><option>All</option><option>ios</option><option>android</option></select></div>
<section class="view" id="v0"><div class="tag">SIMULATED</div><div class="grid g7" id="kpis"></div>
<div class="grid g2" style="margin-top:12px"><div class="card"><h3>Sign-ups and daily active users (weekly average)</h3><div class="plot" id="p_users"></div></div>
<div class="card"><h3>Matches and new conversations per week</h3><div class="plot" id="p_matches"></div></div>
<div class="card"><h3>New payers per week</h3><div class="plot" id="p_payers"></div></div>
<div class="card"><h3>Revenue per week (USD, refunds netted)</h3><div class="plot" id="p_rev"></div></div></div></section>
<section class="view" id="v1"><div class="tag">SIMULATED</div><div class="grid g2">
<div class="card"><h3>Funnel: share of sign-ups reaching each stage, by platform</h3><div class="plot" id="p_funnel" style="height:380px"></div>
<p class="note">The Android drop sits at the photo-upload step (stage 4 to 5): the first growth opportunity.</p></div>
<div class="card"><h3>Retention curve by monthly sign-up cohort (share active on day N)</h3><div class="plot" id="p_ret" style="height:380px"></div>
<p class="note">Only days fully observed for every user of a cohort are drawn.</p></div>
<div class="card"><h3>Activation and payer share by acquisition channel</h3><div class="plot" id="p_channel"></div></div>
<div class="card"><h3>Day-7 retention by channel</h3><div class="plot" id="p_ch_ret"></div></div></div></section>
<section class="view" id="v2"><div class="tag">SIMULATED</div><div class="grid g2">
<div class="card"><h3>Experiment read-outs: relative effect and 95% confidence interval</h3><div class="plot" id="p_forest" style="height:560px"></div></div>
<div class="card"><h3>Read-outs, SRM checks and decisions</h3><div id="t_exp" style="max-height:560px;overflow:auto"></div></div></div></section>
<section class="view" id="v3"><div class="tag">PUBLIC DATA</div><div class="grid g2">
<div class="card"><h3>US App Store: number of ratings and average rating</h3><div class="plot" id="p_ratings" style="height:340px"></div></div>
<div class="card"><h3>Weekly or flagship subscription price by storefront, in USD (ECB rates, 13 Nov 2026)</h3><div class="plot" id="p_prices" style="height:340px"></div>
<p class="note">GB, DE and FR prices include VAT; US, CA and AU store prices exclude sales tax.</p></div>
<div class="card"><h3>Themes in written reviews, last 12 months (share of reviews)</h3><div class="plot" id="p_themes" style="height:340px"></div>
<p class="note">Keyword rules, precision 83% / recall 92% on 45 hand-labelled reviews. Written reviews skew negative: themes, not satisfaction.</p></div>
<div class="card"><h3>Google Trends, US, weekly (0-100 within one request)</h3><div class="plot" id="p_trends" style="height:340px"></div>
<p class="note">"Hily" and "Taimi" are also first names: read as an upper bound.</p></div></div></section>
<footer>__DISCLAIMER__ · Simulated figures are not appflame, Hily or Taimi data.</footer>
<script>
const D=__DATA__;
const C={blue:"__BLUE__",light:"__BLUE_LIGHT__",dark:"__BLUE_DARK__",grey:"__GREY__",red:"__RED__",ink2:"__INK2__",border:"__BORDER__"};
const L=(o)=>Object.assign({margin:{l:48,r:12,t:8,b:36},paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)",
  font:{family:"Segoe UI, sans-serif",size:11,color:C.ink2},xaxis:{gridcolor:C.border},yaxis:{gridcolor:C.border,zeroline:false},
  legend:{orientation:"h",y:1.12},showlegend:true},o||{});
const CFG={displayModeBar:false,responsive:true};
function rows(t){const c=D[t].columns;return D[t].data.map(r=>Object.fromEntries(c.map((k,i)=>[k,r[i]])))}
const T={};for(const k in D)T[k]=rows(k);
const views=["Product pulse","Funnel & cohorts","Experiments","Market view"];
const nav=document.getElementById("nav");
views.forEach((v,i)=>{const b=document.createElement("button");b.textContent=(i+1)+" · "+v;b.onclick=()=>show(i);nav.appendChild(b)});
function show(i){document.querySelectorAll(".view").forEach((e,j)=>e.classList.toggle("on",i===j));
  nav.querySelectorAll("button").forEach((e,j)=>e.classList.toggle("on",i===j));
  document.getElementById("filters").style.display=i<2?"flex":"none";draw(i);window.dispatchEvent(new Event("resize"))}
const f=()=>({c:document.getElementById("fc").value,p:document.getElementById("fp").value});
const keep=(r)=>{const x=f();return (x.c==="All"||r.country===x.c)&&(x.p==="All"||r.platform===x.p)};
function week(d){const t=new Date(d+"T00:00:00Z");const w=new Date(t);w.setUTCDate(t.getUTCDate()-((t.getUTCDay()+6)%7));return w.toISOString().slice(0,10)}
function sumBy(arr,key,cols){const m={};arr.forEach(r=>{const k=key(r);m[k]=m[k]||Object.fromEntries(cols.map(c=>[c,0]));cols.forEach(c=>m[k][c]+=r[c])});return m}
const fmt=(v,d=0)=>v.toLocaleString("en-US",{maximumFractionDigits:d,minimumFractionDigits:d});
function pulse(){
  const r=T.pulse.filter(keep);const tot=sumBy(r,()=>1,["signups","activated","dau","matches","new_conversations","new_payers","revenue_usd"])[1];
  const ret=T.retention.filter(keep);const sz={},a7={},a1={},a30={};
  ret.forEach(x=>{const k=[x.cohort_month,x.country,x.platform,x.channel].join();if(x.cohort_month<="2026-09-01"){sz[k]=x.cohort_size;
    if(x.day_since_signup===1)a1[k]=x.active_users;if(x.day_since_signup===7)a7[k]=x.active_users;}
    if(x.cohort_month<="2026-08-01"&&x.day_since_signup===30)a30[k]=x.active_users});
  const S=o=>Object.values(o).reduce((a,b)=>a+b,0);
  const sz30=S(Object.fromEntries(Object.entries(sz).filter(([k])=>k<="2026-08-01~")));
  const k=[["Sign-ups",fmt(tot.signups),"6 months"],["Activation",(100*tot.activated/tot.signups).toFixed(1)+"%","like sent on day 0"],
    ["Day-1 retention",(100*S(a1)/S(sz)).toFixed(1)+"%","cohorts May-Sep"],["Day-7 retention",(100*S(a7)/S(sz)).toFixed(1)+"%","cohorts May-Sep"],
    ["Matches",fmt(tot.matches),"mutual likes"],["New payers",fmt(tot.new_payers),(100*tot.new_payers/tot.signups).toFixed(1)+"% of sign-ups"],
    ["Revenue","$"+fmt(tot.revenue_usd/1000,0)+"K","subscriptions, net"]];
  document.getElementById("kpis").innerHTML=k.map(x=>`<div class="card"><div class="tag">${x[0].toUpperCase()}</div><div class="kv">${x[1]}</div><div class="kt">${x[2]}</div></div>`).join("");
  const w=sumBy(r,x=>week(x.date),["signups","dau","matches","new_conversations","new_payers","revenue_usd"]);
  const ks=Object.keys(w).sort().slice(0,-1);
  Plotly.react("p_users",[{x:ks,y:ks.map(k=>w[k].signups/7),name:"sign-ups / day",line:{color:C.light}},{x:ks,y:ks.map(k=>w[k].dau/7),name:"DAU",line:{color:C.blue}}],L(),CFG);
  Plotly.react("p_matches",[{x:ks,y:ks.map(k=>w[k].matches),name:"matches",type:"bar",marker:{color:C.light}},{x:ks,y:ks.map(k=>w[k].new_conversations),name:"new conversations",line:{color:C.dark}}],L(),CFG);
  Plotly.react("p_payers",[{x:ks,y:ks.map(k=>w[k].new_payers),type:"bar",marker:{color:C.blue},name:"new payers"}],L({showlegend:false}),CFG);
  Plotly.react("p_rev",[{x:ks,y:ks.map(k=>w[k].revenue_usd),type:"bar",marker:{color:C.dark},name:"revenue"}],L({showlegend:false,yaxis:{tickprefix:"$",gridcolor:C.border}}),CFG);
}
function funnel(){
  const r=T.funnel.filter(keep);const tr=[];
  for(const p of ["ios","android"]){if(f().p!=="All"&&f().p!==p)continue;
    const g=r.filter(x=>x.platform===p);const s=sumBy(g,x=>x.stage_order+"|"+x.stage,["users"]);const ks=Object.keys(s).sort((a,b)=>parseInt(a)-parseInt(b));
    const base=s[ks[0]].users;tr.push({y:ks.map(k=>k.split("|")[1].replace(/^\\d+_/,"").replace(/_/g," ")),x:ks.map(k=>s[k].users/base),type:"bar",orientation:"h",name:p,
      marker:{color:p==="ios"?C.light:C.blue},text:ks.map(k=>(100*s[k].users/base).toFixed(0)+"%"),textposition:"outside"})}
  Plotly.react("p_funnel",tr,L({margin:{l:130,r:30,t:8,b:30},yaxis:{autorange:"reversed"},xaxis:{tickformat:".0%",range:[0,1.12],gridcolor:C.border},barmode:"group"}),CFG);
  const ret=T.retention.filter(x=>keep(x)&&x.fully_observed);const tr2=[];const months=[...new Set(ret.map(x=>x.cohort_month))].sort();
  const pal=["#CDE2FB","#86B6EF","#5598E7","#2A78D6","#104281","#0B2A55"];
  months.forEach((m,i)=>{const g=ret.filter(x=>x.cohort_month===m);const a=sumBy(g,x=>x.day_since_signup,["active_users"]);
    const sz=sumBy(g.filter(x=>x.day_since_signup===0),()=>1,["cohort_size"])[1];if(!sz)return;
    const ds=Object.keys(a).map(Number).sort((x,y)=>x-y).filter(d=>d>0&&d<=60);
    tr2.push({x:ds,y:ds.map(d=>a[d].active_users/sz.cohort_size),name:m.slice(0,7),line:{color:pal[i]}})});
  Plotly.react("p_ret",tr2,L({yaxis:{tickformat:".0%",gridcolor:C.border},xaxis:{title:"days since sign-up",gridcolor:C.border}}),CFG);
  const ch={};r.forEach(x=>{ch[x.channel]=ch[x.channel]||{};ch[x.channel][x.stage_order]=(ch[x.channel][x.stage_order]||0)+x.users});
  const cs=Object.keys(ch).sort((a,b)=>ch[b][11]/ch[b][1]-ch[a][11]/ch[a][1]);
  Plotly.react("p_channel",[{x:cs,y:cs.map(c=>ch[c][8]/ch[c][1]),name:"activation",type:"bar",marker:{color:C.light},offsetgroup:1},
    {x:cs,y:cs.map(c=>ch[c][11]/ch[c][1]),name:"paid (any time)",type:"bar",marker:{color:C.blue},yaxis:"y2",offsetgroup:2}],
    L({barmode:"group",yaxis:{tickformat:".0%",gridcolor:C.border,title:"activation"},yaxis2:{tickformat:".0%",overlaying:"y",side:"right",title:"paid"}}),CFG);
  const rr=T.retention.filter(x=>keep(x)&&x.cohort_month<="2026-09-01");const c7={};
  rr.forEach(x=>{c7[x.channel]=c7[x.channel]||{a:0,s:0};if(x.day_since_signup===7)c7[x.channel].a+=x.active_users;if(x.day_since_signup===0)c7[x.channel].s+=x.cohort_size});
  const c2=Object.keys(c7).sort((a,b)=>c7[b].a/c7[b].s-c7[a].a/c7[a].s);
  Plotly.react("p_ch_ret",[{x:c2,y:c2.map(c=>c7[c].a/c7[c].s),type:"bar",marker:{color:c2.map(c=>c==="tiktok"?C.red:C.blue)},name:"day-7"}],L({showlegend:false,yaxis:{tickformat:".0%",gridcolor:C.border}}),CFG);
}
function experiments(){
  const e=T.experiments.slice().reverse();const lab=e.map(x=>x.experiment+" · "+x.read);
  const col=e.map(x=>/biased|SRM|misleading|Day 1/.test(x.read)?C.red:(x.ci_low>0||x.ci_high<0?C.blue:C.grey));
  Plotly.react("p_forest",[{x:e.map(x=>x.estimate),y:lab,mode:"markers",marker:{color:col,size:8},
    error_x:{type:"data",symmetric:false,array:e.map(x=>x.ci_high-x.estimate),arrayminus:e.map(x=>x.estimate-x.ci_low),color:C.ink2,thickness:1},
    hovertemplate:"%{y}<br>%{x:.1%}<extra></extra>"}],
    L({showlegend:false,margin:{l:270,r:12,t:8,b:30},xaxis:{tickformat:".0%",zeroline:true,zerolinecolor:C.ink2,gridcolor:C.border}}),CFG);
  const h="<table><tr><th>Experiment</th><th>Read</th><th class=n>Effect [95% CI]</th><th class=n>p</th><th class=n>SRM p</th><th>Decision</th></tr>"+
    T.experiments.map(x=>`<tr><td>${x.experiment}</td><td>${x.read}</td><td class=n>${(100*x.estimate).toFixed(1)}% [${(100*x.ci_low).toFixed(1)}, ${(100*x.ci_high).toFixed(1)}]</td>
    <td class=n>${x.p_value==null?"":x.p_value<0.001?"<0.001":x.p_value.toFixed(3)}</td><td class=n ${x.srm_p!=null&&x.srm_p<0.001?'class="bad"':""}>${x.srm_p==null?"":x.srm_p<0.001?'<span class="bad">&lt;0.001</span>':x.srm_p.toFixed(2)}</td><td>${x.decision}</td></tr>`).join("")+"</table>";
  document.getElementById("t_exp").innerHTML=h;
}
function market(){
  const r=T.market_ratings.filter(x=>x.country==="us").sort((a,b)=>a.rating_count-b.rating_count);
  Plotly.react("p_ratings",[{y:r.map(x=>x.app),x:r.map(x=>x.rating_count),type:"bar",orientation:"h",marker:{color:r.map(x=>x.focus?C.blue:C.grey)},
    text:r.map(x=>x.avg_rating.toFixed(2)+"★"),textposition:"outside",cliponaxis:false}],L({showlegend:false,margin:{l:110,r:50,t:8,b:30},xaxis:{range:[0,Math.max(...r.map(x=>x.rating_count))*1.15],gridcolor:C.border}}),CFG);
  const p=T.market_prices;const apps=[...new Set(p.map(x=>x.app))];
  Plotly.react("p_prices",apps.map((a,i)=>({x:p.filter(x=>x.app===a).map(x=>x.country),y:p.filter(x=>x.app===a).map(x=>x.price_usd),type:"bar",
    name:a+" · "+p.find(x=>x.app===a).item,marker:{color:i?C.dark:C.blue}})),L({barmode:"group",yaxis:{tickprefix:"$",gridcolor:C.border}}),CFG);
  const t=T.review_themes;const th=[...new Set(t.map(x=>x.theme))];const order=["Hily","Taimi","Tinder","Bumble","Hinge"];const pc=[C.blue,C.dark,"#C9C7C0","#B0AEA6","#97958D"];
  Plotly.react("p_themes",order.map((a,i)=>({y:th,x:th.map(h=>(t.find(x=>x.app===a&&x.theme===h)||{}).share),type:"bar",orientation:"h",name:a,marker:{color:pc[i]}})),
    L({barmode:"group",margin:{l:170,r:12,t:8,b:30},xaxis:{tickformat:".0%",gridcolor:C.border},yaxis:{autorange:"reversed"}}),CFG);
  const g=T.trends;const terms=[...new Set(g.map(x=>x.term))];const tc={Hily:C.blue,Taimi:C.dark,Grindr:"#C9C7C0","HER app":"#97958D"};
  Plotly.react("p_trends",terms.map(k=>({x:g.filter(x=>x.term===k).map(x=>x.date),y:g.filter(x=>x.term===k).map(x=>x.interest),name:k,line:{color:tc[k]||C.grey,width:k.length<6?2:1}})),L(),CFG);
}
const drawn={};
function draw(i){if(i===0)pulse();if(i===1)funnel();if(i===2&&!drawn[2]){experiments();drawn[2]=1}if(i===3&&!drawn[3]){market();drawn[3]=1}}
["fc","fp"].forEach(id=>document.getElementById(id).onchange=()=>{const i=[...document.querySelectorAll(".view")].findIndex(e=>e.classList.contains("on"));draw(i)});
const start=parseInt((location.hash||"#0").slice(1))||0;show(start);
</script></body></html>"""


def main():
    utf8()
    page = HTML
    for k, v in {"__BG__": BG, "__CARD__": CARD, "__BORDER__": BORDER, "__INK__": INK, "__INK2__": INK2, "__MUTED__": MUTED, "__BLUE__": BLUE,
                 "__BLUE_LIGHT__": BLUE_LIGHT, "__BLUE_DARK__": BLUE_DARK, "__GREY__": GREY, "__RED__": RED, "__DISCLAIMER__": DISCLAIMER}.items():
        page = page.replace(k, v)
    page = page.replace("__DATA__", json.dumps(data(), separators=(",", ":")))
    page = page.replace("__PLOTLY__", get_plotlyjs())
    DOCS.mkdir(exist_ok=True)
    (DOCS / "dashboard.html").write_text(page, encoding="utf-8")
    print(f"docs/dashboard.html ({len(page) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
