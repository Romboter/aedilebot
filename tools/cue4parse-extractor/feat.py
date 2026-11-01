import json,glob,os,re,collections
S="D:/SteamLibrary/steamapps/common/Foxhole/Modding/Tools/UnrealExporter-1.1.2/output/fresh/War/Content/Blueprints/"
byname={}
for p in glob.glob(S+"**/*.json",recursive=True): byname.setdefault(os.path.basename(p)[:-5],p)
T=json.load(open("C:/sc/bots/aedilebot/data/Targets.json",encoding="utf-8"))
def load(path):
    d=json.load(open(path,encoding="utf-8-sig")); cls=None; props={}
    for e in d:
        if e.get("Type")=="BlueprintGeneratedClass": cls=e
        if e.get("Name","").startswith("Default__"): props.update(e.get("Properties",{}))
    return cls,props
def chain(path):
    """merged default props along BP parents; returns props(child wins), native base, bp chain"""
    props={}; names=[]; native=None
    while path:
        cls,p=load(path); names.append(os.path.basename(path)[:-5])
        for k,v in p.items(): props.setdefault(k,v)
        s=(cls or {}).get("SuperStruct") or {}; sp=s.get("ObjectPath",""); sn=re.search(r"'([^']+)'",s.get("ObjectName","")); sn=sn.group(1) if sn else ""
        if sp.startswith("/Script"): native=sn; break
        path=byname.get(os.path.basename(sp.split(".")[0]))
    return props,native,names
rows=[]
for n,t in T.items():
    if t.get("ObjectType") not in("Structures","Multitier_structures"): continue
    dev=t.get("Dev Name",""); f=byname.get("BP"+dev) or byname.get(dev)
    if not f: continue
    props,native,names=chain(f)
    at=props.get("ArmourType","").replace("EArmourType::","")
    pt=str(props.get("ProfileType","")).replace("EStructureProfileType::","")
    rows.append(dict(name=n,dev=dev,sheet=t.get("Mitigation Type"),bp_armour=at,profile=pt,native=native,hp=float(t["Health"]) if t.get("Health") else None,props=props))
json.dump([{k:v for k,v in r.items() if k!="props"} for r in rows],open("feat.json","w"))
known=[r for r in rows if r["bp_armour"]]; unk=[r for r in rows if not r["bp_armour"]]
print("known",len(known),"unknown",len(unk))
# does ProfileType predict armour among known?
g=collections.defaultdict(collections.Counter)
for r in known: g[r["profile"]][r["bp_armour"]]+=1
print("ProfileType -> armour (known):")
for k,c in sorted(g.items(),key=lambda x:-sum(x[1].values())): print(f"  {k or '(none)':22}",dict(c))
