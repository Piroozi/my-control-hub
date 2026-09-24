#!/usr/bin/env python3
import os, json, urllib.request, urllib.error, time, datetime, ssl
from pathlib import Path

API="https://api.cloudflare.com/client/v4"
GQL=API+"/graphql"
TOKEN=os.environ.get("CLOUDFLARE_API_TOKEN","").strip()
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/systems.json").read_text(encoding="utf-8"))
IGNORE=set(CFG.get("ignoreZones",[]))
MANUAL=CFG.get("manualSystems",[])
TH=CFG.get("thresholds",{})
HEAD={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json","Accept":"application/json"}

def request_json(url, method="GET", payload=None, headers=None, timeout=30):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method,headers=headers or HEAD)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def list_zones():
    if not TOKEN:
        return []
    out=[]; page=1
    while True:
        obj=request_json(f"{API}/zones?per_page=50&page={page}")
        if not obj.get("success"):
            raise RuntimeError(obj.get("errors"))
        out += obj.get("result",[])
        total=obj.get("result_info",{}).get("total_pages",1)
        if page>=total: break
        page+=1
    return out

def health_url(url):
    try:
        t=time.perf_counter()
        req=urllib.request.Request(url,headers={"User-Agent":"MyControlHub/2.3"})
        with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as r:
            ms=round((time.perf_counter()-t)*1000)
            return r.getcode(),ms,r.geturl()
    except urllib.error.HTTPError as e:
        ms=round((time.perf_counter()-t)*1000)
        return e.code,ms,url
    except Exception:
        return 0,None,url

def health_domain(domain):
    last=None
    for url in [f"https://{domain}",f"https://www.{domain}"]:
        code,ms,final=health_url(url)
        if code and code < 500:
            return code,ms,final
        last=(code,ms,final)
    return last or (0,None,f"https://{domain}")

def gql(zone_id,start,end,error_only=False):
    extra=", edgeResponseStatus_geq: 500, edgeResponseStatus_lt: 600" if error_only else ""
    query=(
        'query Req($zoneTag: string, $start: Time, $end: Time) {'
        ' viewer { zones(filter: {zoneTag: $zoneTag}) {'
        ' series: httpRequestsAdaptiveGroups('
        ' limit: 1000, orderBy: [datetimeHour_ASC],'
        ' filter: {datetime_geq: $start, datetime_lt: $end, requestSource: "eyeball"' + extra + '}'
        ' ) { count sum { edgeResponseBytes } dimensions { datetimeHour } }'
        ' } } }'
    )
    obj=request_json(GQL,"POST",{"query":query,"variables":{"zoneTag":zone_id,"start":start,"end":end}})
    if obj.get("errors"):
        raise RuntimeError(obj["errors"])
    zones=obj.get("data",{}).get("viewer",{}).get("zones",[])
    return zones[0].get("series",[]) if zones else []

def collect_series(zone_id):
    end=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    start=end-datetime.timedelta(days=30)
    s=start.isoformat().replace("+00:00","Z")
    e=end.isoformat().replace("+00:00","Z")
    total=gql(zone_id,s,e,False)
    try:
        errs=gql(zone_id,s,e,True)
    except Exception:
        errs=[]
    by={}
    for x in total:
        ts=x.get("dimensions",{}).get("datetimeHour")
        if ts:
            by[ts]={
                "ts":ts,
                "requests":int(x.get("count") or 0),
                "errors":0,
                "bytes":int((x.get("sum") or {}).get("edgeResponseBytes") or 0)
            }
    for x in errs:
        ts=x.get("dimensions",{}).get("datetimeHour")
        if ts:
            by.setdefault(ts,{"ts":ts,"requests":0,"errors":0,"bytes":0})
            by[ts]["errors"]=int(x.get("count") or 0)
    return [by[k] for k in sorted(by)]

def summarize(domain,url,code,ms,final_url,series,now,analytics_available=True):
    cutoff=now-datetime.timedelta(hours=24)
    last24=[]
    for p in series:
        try:
            if datetime.datetime.fromisoformat(p["ts"].replace("Z","+00:00"))>=cutoff:
                last24.append(p)
        except Exception:
            pass
    req=sum(p["requests"] for p in last24)
    err=sum(p["errors"] for p in last24)
    rate=(err/req*100) if req else 0
    status="ok"
    if not code or code>=500 or rate>=float(TH.get("errorRateCritical",5)):
        status="critical"
    elif (ms and ms>=float(TH.get("responseMsWarning",2000))) or rate>=float(TH.get("errorRateWarning",2)):
        status="warning"
    return {
        "name":domain,
        "domain":domain,
        "url":url,
        "status":status,
        "httpStatus":code,
        "responseMs":ms,
        "finalUrl":final_url,
        "requests24h":req,
        "errors24h":err,
        "errorRate24h":round(rate,3),
        "series":series,
        "analyticsAvailable":analytics_available
    }

def main():
    now=datetime.datetime.now(datetime.timezone.utc)
    systems=[]; incidents=[]; seen=set()

    try:
        zones=[z for z in list_zones() if z.get("name") not in IGNORE and z.get("status")=="active"]
    except Exception:
        zones=[]
        incidents.append({"system":"Cloudflare","message":"فهرست Zoneها قابل دریافت نبود","time":now.isoformat()})

    for z in zones:
        domain=z["name"]; seen.add(domain)
        code,ms,final=health_domain(domain)
        try:
            series=collect_series(z["id"])
            analytics_available=True
        except Exception:
            series=[]; analytics_available=False
            incidents.append({"system":domain,"message":"Cloudflare Analytics قابل دریافت نبود","time":now.isoformat()})
        item=summarize(domain,f"https://{domain}",code,ms,final,series,now,analytics_available)
        if item["status"]!="ok":
            incidents.append({
                "system":domain,
                "message":f"وضعیت {item['status']} — HTTP {code or 'DOWN'}، خطای 5xx: {item['errorRate24h']:.2f}%",
                "time":now.isoformat()
            })
        systems.append(item)

    for m in MANUAL:
        domain=m.get("domain","").strip()
        if not domain or domain in seen:
            continue
        url=m.get("url") or f"https://{domain}"
        mode=m.get("monitoringMode","active")

        if mode=="setup":
            systems.append({
                "name":domain,
                "domain":domain,
                "url":url,
                "status":"setup",
                "httpStatus":None,
                "responseMs":None,
                "finalUrl":url,
                "requests24h":0,
                "errors24h":0,
                "errorRate24h":0,
                "series":[],
                "analyticsAvailable":False
            })
            continue

        code,ms,final=health_url(url)
        item=summarize(domain,url,code,ms,final,[],now,False)
        if item["status"]!="ok":
            incidents.append({
                "system":domain,
                "message":f"Health Check ناموفق — HTTP {code or 'DOWN'}",
                "time":now.isoformat()
            })
        systems.append(item)

    out={"generatedAt":now.isoformat(),"systems":systems,"incidents":incidents}
    (ROOT/"data/dashboard.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Generated dashboard for {len(systems)} systems")

if __name__=="__main__":
    main()
