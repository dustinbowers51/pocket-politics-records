"""Verified debate snapshots and permanent withdrawal history."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from sources import HardFailure, digest, norm, SALUTATION, read

STATE = Path("debate-data/state.json")
LOG = Path("debate-data/history.jsonl")
LABEL = "From the official debate. Exact quotes, selected by AI."


def identity(bill,point):
    return digest(json.dumps([bill,point["bio"],norm(point["quote"])],ensure_ascii=False).encode())


def display(quote):
    stripped=SALUTATION.sub("",norm(quote),count=1)
    text = re.sub(r"^in closing,\s*", "", stripped, count=1, flags=re.I)
    return text[:1].upper()+text[1:]


def record(ballot, vote, packet, points):
    rows=packet["paragraphs"]
    result=[]
    for pt in points:
        raw=read(pt["url"])
        if digest(raw)!=packet["sources"][pt["url"]] or raw.decode()[pt["start"]:pt["end"]]!=pt["quote"]:
            raise HardFailure("Source hash or offsets failed")
        turn=next((r for r in rows if r["url"]==pt["url"] and r["start"]<=pt["start"]
                   and pt["end"]<=r["start"]+len(r["quote"])),None)
        side=ballot["positions"].get(pt["bio"])
        if not turn or turn["debateScope"]!="general" or turn["bio"]!=pt["bio"] or turn["speaker"]!=pt["speaker"] or side not in ("Aye","Yea","Nay","No") or ("Yea" if side in ("Aye","Yea") else "Nay")!=pt["side"]:
            raise HardFailure("Speaker turn or vote mismatch")
        from selector import sentences, PROCEDURE
        spans=list(sentences(turn))
        starts=[i for i,(a,b) in enumerate(spans) if turn["start"]+a==pt["start"]]
        ends=[i for i,(a,b) in enumerate(spans) if turn["start"]+b==pt["end"]]
        if not starts or not ends or not 1<=ends[0]-starts[0]+1<=3 or len(pt["quote"].split())>60 or PROCEDURE.search(norm(pt["quote"])):
            raise HardFailure("Ineligible exact span")
        party,state=vote["members"][pt["bio"]]
        result.append({**{k:pt[k] for k in ("bio","speaker","side","manager","url","passageUrl","start","end","quote")},
                       "id":identity(ballot["bill"],pt),"sha256":packet["sources"][pt["url"]],
                       "party":party,"state":state,"display":display(pt["quote"])})
    if sum(p["side"]=="Yea" for p in result)*2!=len(result) or len({p["bio"] for p in result})!=len(result):
        raise HardFailure("Unbalanced sides or duplicate speaker")
    urls=list(dict.fromkeys([r["url"] for r in rows]+list(packet["sources"])))
    rec = dict(bill=ballot["bill"],vote=ballot["vote"],date=ballot["date"],points=result,
                floorDebate=urls or ["https://www.govinfo.gov/app/details/CREC-"+ballot["dates"][-1]],
                sources=packet["sources"],passage={k:vote[k] for k in ("url","sha256","result","yea","nay")})
    sides=set(packet.get("speakerVotes",{}).values())
    spoke={side for side,labels in (("Yea",{"Yea","Aye"}),("Nay",{"Nay","No"})) if sides & labels}
    if len(spoke)==1 and None not in sides and not packet.get("unidentified"):
        rec["speakingSide"]=spoke.pop()
    classify(rec, bool(packet.get("missingDates")))
    return rec


def classify(rec, pending=False):
    if rec["points"]:
        rec.pop("emptyReason",None)
    else:
        rec["emptyReason"]="recordPending" if pending else "oneSided" if rec.get("speakingSide") else "noClearPair"



def event(action,rec,pt,reason):
    return dict(at=datetime.now(timezone.utc).isoformat(),action=action,bill=rec["bill"],vote=rec["vote"],quoteId=pt["id"],speaker=pt["speaker"],reason=reason,point=pt)


def withdraw(state,rec,ids,events,reason):
    def remove(point,why):
        rec["points"].remove(point)
        state["blocked"][point["id"]]=why
        events.append(event("drop",rec,point,why))
    for point in list(rec["points"]):
        if point["id"] in ids:
            remove(point,reason)
    sides=[[p for p in rec["points"] if p["side"]==s] for s in ("Yea","Nay")]
    count=min(map(len,sides))
    for group in sides:
        for pt in group[count:]:
            remove(pt,"Equal-side trim")
    classify(rec)


def append_events(events):
    with LOG.open("a") as stream:
        for item in events:
            stream.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
