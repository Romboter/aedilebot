import json,collections
exec(open("feat.py",encoding="utf-8").read().split("known=[r")[0])
known=[r for r in rows if r["bp_armour"]]; unk=[r for r in rows if not r["bp_armour"]]
by=collections.defaultdict(list)
for r in known: by[r["native"]].append(r)
# leave-one-out on known: predict armour from other known structures sharing native base class
ok=n=cov=0
for r in known:
    sib=[s["bp_armour"] for s in by[r["native"]] if s is not r]
    if not sib: continue
    cov+=1; pred=collections.Counter(sib).most_common(1)[0][0]; ok+= pred==r["bp_armour"]
print(f"LOO native-base rule on known: covered {cov}/{len(known)}, correct {ok}/{cov}")
# apply to the 45
hit=miss=nocov=0; rows45=[]
for r in unk:
    sib=[s["bp_armour"] for s in by.get(r["native"],[])]
    if not sib: nocov+=1; rows45.append((r["name"],r["native"],r["sheet"],None)); continue
    pred=collections.Counter(sib).most_common(1)[0][0]
    (hit:=hit+1) if pred==r["sheet"] else (miss:=miss+1)
    rows45.append((r["name"],r["native"],r["sheet"],pred))
print(f"45 native-class structures: no known sibling {nocov}, rule agrees with sheet {hit}, disagrees {miss}")
for x in rows45: print("  ",x)
