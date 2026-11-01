import json,collections,re,glob,os
exec(open("feat.py",encoding="utf-8").read().split("known=[r")[0])   # reuse rows (with props)
SD=json.load(open("D:/work/extractor_spike/stats_out/War/Content/Blueprints/Data/BPStructureDynamicData.json",encoding="utf-8-sig"))[0]["Rows"]
known=[r for r in rows if r["bp_armour"]]
def feats(r):
    f={"native":r["native"],"profile":r["profile"]}
    sd=SD.get(r["dev"],{})
    for k in("MaxHealth","StructuralIntegrity","DecayStartHours","RepairCost","RamDamageReceivedFlags","StoredItemCapacity"): f["sd."+k]=sd.get(k)
    for k,v in r["props"].items():
        if isinstance(v,(str,int,float,bool)) and not isinstance(v,dict): f["bp."+k]=v
    return f
F=[(feats(r),r["bp_armour"]) for r in known]
allk=set(k for f,_ in F for k in f)
res=[]
for k in allk:
    g=collections.defaultdict(collections.Counter)
    for f,y in F: g[str(f.get(k))][y]+=1
    n=len(F); acc=sum(max(c.values()) for c in g.values())/n
    res.append((acc,len(g),k))
res.sort(reverse=True)
base=collections.Counter(y for _,y in F).most_common(1)[0][1]/len(F)
print("majority-class baseline: %.2f"%base)
for acc,ng,k in res[:10]: print(f"  {k:40} acc={acc:.2f} groups={ng}")
