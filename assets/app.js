const state={data:null,range:"24h",selected:null};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const fa=n=>new Intl.NumberFormat("fa-IR",{maximumFractionDigits:1}).format(n??0);
const faDate=s=>{try{return new Intl.DateTimeFormat("fa-IR-u-ca-persian",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Tehran"}).format(new Date(s))}catch{return s||"—"}};
function statusLabel(s){return s==="ok"?"سالم":s==="warning"?"نیاز به توجه":s==="setup"?"در حال راه‌اندازی":"بحرانی"}
function badge(s){return `<span class="badge ${s==="ok"?"ok":s==="warning"?"warn":s==="setup"?"setup":"critical"}">${statusLabel(s)}</span>`}
function draw(canvas,points,key,color="#1769ff"){
  const dpr=devicePixelRatio||1,r=canvas.getBoundingClientRect();canvas.width=r.width*dpr;canvas.height=r.height*dpr;
  const c=canvas.getContext("2d");c.scale(dpr,dpr);c.clearRect(0,0,r.width,r.height);
  if(!points.length)return;
  const vals=points.map(p=>+p[key]||0),max=Math.max(...vals,1);c.strokeStyle=color;c.lineWidth=2;c.beginPath();
  points.forEach((p,i)=>{const x=(i/(Math.max(points.length-1,1)))*(r.width-12)+6,y=r.height-10-(vals[i]/max)*(r.height-25);i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke()
}
function rangePoints(s){const p=s.series||[],now=Date.now(),hours=state.range==="24h"?24:state.range==="7d"?168:720;return p.filter(x=>new Date(x.ts).getTime()>=now-hours*3600000)}
function renderSummary(){
  const systems=state.data.systems||[],
  ok=systems.filter(x=>x.status==="ok").length,
  w=systems.filter(x=>x.status==="warning").length,
  c=systems.filter(x=>x.status==="critical").length;
  $("#summary").innerHTML=[["سامانه‌ها",systems.length],["سالم",ok],["نیاز به توجه",w],["بحرانی",c]].map(([a,b])=>`<div class="summary-card"><small>${a}</small><strong>${fa(b)}</strong></div>`).join("")
}
function renderSystems(){
  const systems=state.data.systems||[];
  $("#systemsGrid").innerHTML=systems.map((s,i)=>`<article class="system-card" data-i="${i}">
    <div class="sys-head"><div><h3 dir="ltr">${s.domain}</h3></div>${badge(s.status)}</div>
    <canvas class="spark" data-spark="${i}"></canvas>
    <div class="metrics-row">
      <div class="mini"><small>درخواست ۲۴ساعت</small><b>${s.status==="setup"?"—":(s.analyticsAvailable?fa(s.requests24h):"—")}</b></div>
      <div class="mini"><small>5xx</small><b>${s.status==="setup"?"—":(s.analyticsAvailable?fa(s.errors24h):"—")}</b></div>
      <div class="mini"><small>HTTP</small><b>${s.status==="setup"?"—":(s.httpStatus||"—")}</b></div>
      <div class="mini"><small>پاسخ</small><b>${s.status==="setup"?"—":(s.responseMs?fa(s.responseMs)+" ms":"—")}</b></div>
    </div>
  </article>`).join("");
  $$(".system-card").forEach(el=>el.onclick=()=>openDetail(+el.dataset.i));
  setTimeout(()=>$$("[data-spark]").forEach(c=>draw(c,(systems[+c.dataset.spark].series||[]).slice(-24),"requests","#1769ff")),10)
}
function openDetail(i){
  state.selected=i;const s=state.data.systems[i];
  $("#detail").classList.remove("hidden");$("#incidentsPanel").classList.add("hidden");$("#repairPanel").classList.add("hidden");
  $("#detailName").textContent=s.domain;$("#detailName").setAttribute("dir","ltr");$("#detailDomain").textContent="";
  $("#detailKpis").innerHTML=[
    ["وضعیت",statusLabel(s.status)],
    ["درخواست ۲۴ساعت",s.status==="setup"?"—":(s.analyticsAvailable?fa(s.requests24h):"—")],
    ["خطای 5xx",s.status==="setup"?"—":(s.analyticsAvailable?fa(s.errors24h):"—")],
    ["Response",s.status==="setup"?"—":(s.responseMs?fa(s.responseMs)+" ms":"—")]
  ].map(x=>`<div class="kpi"><small>${x[0]}</small><b>${x[1]}</b></div>`).join("");
  $("#latencyBox").textContent=s.status==="setup"?"—":(s.responseMs?fa(s.responseMs)+" ms":"—");
  setTimeout(()=>{const p=rangePoints(s);draw($("#requestsChart"),p,"requests","#1769ff");draw($("#errorsChart"),p,"errors","#e84545")},20)
}
function renderIncidents(){
  const list=state.data.incidents||[];
  $("#incidentList").innerHTML=list.length?list.map(x=>`<div class="incident"><b>${x.system}</b> — ${x.message}<br><small>${faDate(x.time)}</small></div>`).join(""):"<p>رخداد فعالی ثبت نشده است.</p>"
}
function nav(view){
  $$(".nav").forEach(n=>n.classList.toggle("active",n.dataset.view===view));
  $("#systemsGrid").classList.toggle("hidden",view==="incidents"||view==="repair");
  $("#summary").classList.toggle("hidden",view==="incidents"||view==="repair");
  $("#detail").classList.add("hidden");
  $("#incidentsPanel").classList.toggle("hidden",view!=="incidents");
  $("#repairPanel").classList.toggle("hidden",view!=="repair");
  if(view==="incidents")renderIncidents()
}
$$(".nav").forEach(n=>n.onclick=()=>nav(n.dataset.view));
$$(".range button").forEach(b=>b.onclick=()=>{$$(".range button").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.range=b.dataset.range;if(state.selected!==null)openDetail(state.selected)});
$("#closeDetail").onclick=()=>$("#detail").classList.add("hidden");
$("#downloadDiag").onclick=()=>{
  const s=state.data.systems[state.selected];
  const payload={generatedAt:new Date().toISOString(),system:s.domain,domain:s.domain,status:s.status,httpStatus:s.httpStatus,responseMs:s.responseMs,requests24h:s.requests24h,errors24h:s.errors24h,series:s.series,incidents:(state.data.incidents||[]).filter(x=>x.system===s.domain)};
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));a.download=`diagnostic-${s.domain}-${Date.now()}.json`;a.click();URL.revokeObjectURL(a.href)
};
fetch("data/dashboard.json?ts="+Date.now()).then(r=>r.json()).then(d=>{state.data=d;$("#updatedAt").textContent=faDate(d.generatedAt);renderSummary();renderSystems();renderIncidents()}).catch(()=>document.body.insertAdjacentHTML("beforeend",`<div style="position:fixed;left:20px;bottom:20px;background:#fee;color:#900;padding:12px;border-radius:10px">داده مانیتورینگ هنوز تولید نشده است.</div>`));
