#!/usr/bin/env python3
import os, json, urllib.request, urllib.error, time, datetime, ssl
from pathlib import Path

API="https://api.cloudflare.com/client/v4"
GQL=API+"/graphql"
TOKEN=os.environ.get("CLOUDFLARE_API_TOKEN","").strip()
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/systems.json").read_text(encoding="utf-8"))
ALIASES=CFG.get("aliases",{})
IGNORE=set(CFG.get("ignoreZones",[]))
TH=CFG.get("thresholds",{})
HEAD={"Authorization":f"Bearer {TOKEN}","Content-Type":"application/json","Accept":"application/json"}

def request_json(url, method="GET", payload=None, headers=None, timeout=30):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method,headers=headers or HEAD)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode())

def list_zones():
    out=[]; page=1
    while True:
        obj=request_json(f"{API}/zones?per_page=50&page={page}")
        if not obj.get("success"): raise RuntimeError(obj.get("errors"))
        out += obj.get("result",[])
        total=obj.get("result_info",{}).get("total_pages",1)
        if page>=total: break
        page+=1
    return out

def health(domain):
    urls=[f"https://{domain}", f"https://www.{domain}"]
    last=None
    for url in urls:
        try:
            t=time.perf_counter()
            req=urllib.request.Request(url,headers={"User-Agent":"MyControlHub/2.0"})
            with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as r:
                ms=round((time.perf_counter()-t)*1000)
                return r.getcode(), ms, r.geturl()
        except urllib.error.HTTPError as e:
            ms=round((time.perf_counter()-t)*1000)
            if e.code < 500: return e.code,ms,url
            last=(e.code,ms,url)
        except Exception:
            last=(0,None,url)
    return last or (0,None,urls[0])

def gql(zone_id, start, end, error_only=False):
    extra=", edgeResponseStatus_geq: 500, edgeResponseStatus_lt: 600" if error_only else ""
    query = (
        'query Req($zoneTag: string, $start: Time, $end: Time) {'
        ' viewer { zones(filter: {zoneTag: $zoneTag}) {'
        ' series: httpRequestsAdaptiveGroups('
        ' limit: 1000, orderBy: [datetimeHour_ASC],'
        ' filter: {datetime_geq: $start, datetime_lt: $end, requestSource: "eyeball"' + extra + '}'
        ' ) { count sum { edgeResponseBytes } dimensions { datetimeHour } }'
        ' } } }'
    )
    obj=request_json(GQL,"POST",{"query":query,"variables":{"zoneTag":zone_id,"start":start,"end":end}})
    if obj.get("errors"): raise RuntimeError(obj["errors"])
    zones=obj.get("data",{}).get("viewer",{}).get("zones",[])
    return zones[0].get("series",[]) if zones else []

def collect_series(zone_id):
    end=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    start=end-datetime.timedelta(days=30)
    s=start.isoformat().replace("+00:00","Z"); e=end.isoformat().replace("+00:00","Z")
    total=gql(zone_id,s,e,False)
    try: errs=gql(zone_id,s,e,True)
    except Exception: errs=[]
    by={}
    for x in total:
        ts=x.get("dimensions",{}).get("datetimeHour")
        if ts: by[ts]={"ts":ts,"requests":int(x.get("count") or 0),"errors":0,"bytes":int((x.get("sum") or {}).get("edgeResponseBytes") or 0)}
    for x in errs:
        ts=x.get("dimensions",{}).get("datetimeHour")
        if ts:
            by.setdefault(ts,{"ts":ts,"requests":0,"errors":0,"bytes":0})
            by[ts]["errors"]=int(x.get("count") or 0)
    return [by[k] for k in sorted(by)]

def main():
    if not TOKEN: raise SystemExit("CLOUDFLARE_API_TOKEN is missing")
    zones=[z for z in list_zones() if z.get("name") not in IGNORE and z.get("status")=="active"]
    systems=[]; incidents=[]
    now=datetime.datetime.now(datetime.timezone.utc)
    cutoff=now-datetime.timedelta(hours=24)
    for z in zones:
        domain=z["name"]
        code,ms,final_url=health(domain)
        try:
            series=collect_series(z["id"])
        except Exception:
            series=[]
            incidents.append({"system":ALIASES.get(domain,domain),"message":"Cloudflare Analytics قابل دریافت نبود","time":now.isoformat()})
        last24=[]
        for p in series:
            try:
                if datetime.datetime.fromisoformat(p["ts"].replace("Z","+00:00"))>=cutoff: last24.append(p)
            except Exception:
                pass
        req=sum(p["requests"] for p in last24); err=sum(p["errors"] for p in last24)
        rate=(err/req*100) if req else 0
        status="ok"
        if not code or code>=500 or rate>=float(TH.get("errorRateCritical",5)): status="critical"
        elif (ms and ms>=float(TH.get("responseMsWarning",2000))) or rate>=float(TH.get("errorRateWarning",2)): status="warning"
        name=ALIASES.get(domain,domain)
        if status!="ok":
            incidents.append({"system":name,"message":f"وضعیت {status} — HTTP {code or 'DOWN'}، خطای 5xx: {rate:.2f}%","time":now.isoformat()})
        systems.append({"name":name,"domain":domain,"status":status,"httpStatus":code,"responseMs":ms,"finalUrl":final_url,
                        "requests24h":req,"errors24h":err,"errorRate24h":round(rate,3),"series":series})
    out={"generatedAt":now.isoformat(),"systems":systems,"incidents":incidents}
    (ROOT/"data/dashboard.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Generated dashboard for {len(systems)} active zones")

if __name__=="__main__":
    main()
