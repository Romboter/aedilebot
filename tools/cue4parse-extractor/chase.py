import json,glob,os,re,collections
S="D:/SteamLibrary/steamapps/common/Foxhole/Modding/Tools/UnrealExporter-1.1.2/output/fresh/War/Content/"
byname={}
for p in glob.glob(S+"Blueprints/**/*.json",recursive=True): byname.setdefault(os.path.basename(p)[:-5],p)
T=json.load(open("C:/sc/bots/aedilebot/data/Targets.json",encoding="utf-8"))
def super_of(path):
    for e in json.load(open(path,encoding="utf-8-sig")):
        if e.get("Type")=="BlueprintGeneratedClass":
            s=e.get("SuperStruct") or {}
            return s.get("ObjectName",""),s.get("ObjectPath","")
    return "",""
def armour(path):
    return set(re.findall(r'EArmourType::(\w+)',open(path,encoding="utf-8-sig").read()))
def resolve(path,depth=0):
    chain=[]
    while depth<8:
        a=armour(path)
        sn,sp=super_of(path)
        chain.append(os.path.basename(path)[:-5])
        if a: return a,chain,"blueprint"
        m=re.search(r"'([^']+)'",sn); name=m.group(1) if m else ""
        if sp.startswith("/Script"): return set(),chain+["native:"+name],"native"
        nxt=byname.get(os.path.basename(sp.split(".")[0]) )
        if not nxt: return set(),chain+["?"+sn],"unresolved"
        path=nxt; depth+=1
    return set(),chain,"deep"
out=collections.Counter(); native=collections.defaultdict(list); mism=[]
for n,t in T.items():
    if t.get("ObjectType") not in("Structures","Multitier_structures"): continue
    dev=t.get("Dev Name",""); f=byname.get("BP"+dev) or byname.get(dev)
    if not f or armour(f): continue
    a,chain,how=resolve(f)
    out[how]+=1
    if how=="blueprint":
        ok=t.get("Mitigation Type") in a
        out["  parent-BP matches sheet" if ok else "  parent-BP DIFFERS from sheet"]+=1
        if not ok: mism.append((n,t.get("Mitigation Type"),sorted(a),chain))
    elif how=="native": native[chain[-1]].append((n,t.get("Mitigation Type")))
print(dict(out))
print("DIFFERS:",mism[:6])
print("native base classes -> sheet types:")
for c,v in sorted(native.items(),key=lambda x:-len(x[1])): print(" ",c,len(v),collections.Counter(m for _,m in v).most_common(3),[x[0] for x in v][:3])
