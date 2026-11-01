import json,glob,os,re,collections
exec(open("feat.py",encoding="utf-8").read().split("known=[r")[0])
SD=json.load(open("D:/work/extractor_spike/stats_out/War/Content/Blueprints/Data/BPStructureDynamicData.json",encoding="utf-8-sig"))[0]["Rows"]
targets={"Bridge":4200,"A0E-9 Rocket Platform Husk":5400,"Dry Dock":4650,"Dry Dock Husk":6375,"Offshore Platform":1850,"Infantry Support Gun Pillbox (ISG Pillbox)":950,"Metalworks Factory Husk":6000,"Heavy Assembly Station Husk":4050,"RailTrackSplineFoundation":750,"SmallRailTrackSplineFoundation":750}
# index: MaxHealth in SD rows and in BP default props (via chain)
bp_hp=collections.defaultdict(list)
for dev,p in list(byname.items()):
    if "/Structures/" not in p.replace("\\","/"): continue
    try: props,native,names=chain(p)
    except Exception: continue
    for k in("MaxHealth","Health"):
        if isinstance(props.get(k),(int,float)): bp_hp[int(props[k])].append(dev)
for n,t in T.items():
    for tn,hp in targets.items():
        if n.startswith(tn[:30]):
            sd=[k for k,v in SD.items() if v.get("MaxHealth")==hp]
            print(f"{n[:44]:44} sheet={t['Health']:>5} dev={t['Dev Name']:<24} SD rows w/ MaxHealth={hp}: {sd[:6]}  BP defaults w/ it: {sorted(set(bp_hp.get(hp,[])))[:5]}")
            break
