"""Stage daily debate changes atomically, independently of hourly publication."""
import json
import os
import re
import sqlite3
from datetime import date,timedelta
from pathlib import Path
from urllib.error import HTTPError
from sources import HardFailure, sources, verify_vote
from selector import select
from records import STATE, LOG, append_events, event, record, withdraw
import ledger

WORK = Path("debate-data/checkpoints")
FIRST_DAY = "2026-11-24"


def ballots(db_path):
    crosswalk=json.loads(Path(__file__).with_name("senate-ids.json").read_text())
    with sqlite3.connect(f"file:{db_path}?mode=ro",uri=True) as db:
        query="""select v.id,v.bill_id,v.chamber,v.date,b.title,e.payload
                 from votes v join entities e on e.id=v.id and e.kind='vote'
                 join bills b on b.id=v.bill_id where v.date>=? order by v.date,v.id"""
        for vid,bill,chamber,day,title,payload in db.execute(query,(FIRST_DAY,)):
            vote=json.loads(payload)
            if bill.split("-")[1] not in ("hr","s","hjres","sjres") or not re.match(r"^On (Passage\b|Motion to Suspend the Rules and Pass\b)",vote["question"],re.I):
                continue
            positions=vote["positions"]
            if chamber=="Senate" and vote.get("positionScheme")!="bioguide":
                positions={bio:positions[lid] for bio,lid in crosswalk.items() if lid in positions}
            dates=set()
            for d,body,origin in db.execute("select date,text,chamber from actions where bill_id=? and date<=? order by ordinal desc",(bill,day)):
                if origin and chamber.lower() not in origin.lower() and not re.search(r"\b"+chamber+r"\b",body,re.I):continue
                if d<day and re.search(r"(?:Passed (?:the )?"+chamber+r"|On passage.*(?:passed|failed))",body,re.I):break
                if re.search(r"\bdebate\b|considered by (?:the )?"+chamber,body,re.I):dates.add(d)
            yield dict(bill=bill,vote=vid,date=day,dates=sorted(dates or {day}),title=title,chamber=chamber,positions=positions)


def process(b):
    packet=sources(b)
    vote=verify_vote({**b,"positions":{}})
    try:
        verify_vote(b)
    except ValueError:
        result=record(b,vote,packet,[])
        return dict(result,emptyReason="Passage vote verification failed")
    deadline=date.fromisoformat(b["date"])+timedelta(days=14)
    if packet["missingDates"]:
        if date.today()<deadline:return None
        return dict(record(b,vote,packet,[]),emptyReason="Record unavailable after 14 days")
    audit=dict(selection=[],checks=[],responses=[])
    try:
        if ledger.run is None:ledger.begin()
        points=select(packet,audit)
        result=record(b,vote,packet,points)
    except HardFailure as exc:
        result=dict(record(b,vote,packet,[]),emptyReason=str(exc))
    return result


def main():
    state=json.loads(STATE.read_text())
    seeding=not state["seedComplete"]
    planned=json.loads(Path(__file__).with_name("seed-votes.json").read_text()) if seeding else ballots("../var/live/national.sqlite")
    events=[]
    try:
        for b in planned:
            if b["vote"] in state["records"]:continue
            checkpoint=WORK/(b["vote"].replace(":","-")+".json")
            if checkpoint.exists():
                rec=json.loads(checkpoint.read_text())
            else:
                rec=process(b)
                if rec is None:continue
                ledger.save(checkpoint,rec)
                ledger.commit("Checkpoint verified debate "+b["vote"],checkpoint)
            denied={p["id"] for p in rec["points"] if p["id"] in state["blocked"]}
            if denied:
                withdraw(state,rec,denied,events,"Previously withdrawn")
            state["records"][b["vote"]]=rec
            if not seeding:
                events.extend(event("publish",rec,p,"Daily publication") for p in rec["points"])
        if seeding:
            if len(state["records"])!=32:raise RuntimeError("Seed awaits complete debate records")
            state["seedComplete"]=True
            events=[event("publish",r,p,"Reviewed seed") for r in state["records"].values() for p in r["points"]]
        ledger.save(STATE,state)
        append_events(events)
    finally:
        ledger.finish()
    ledger.commit("Publish verified debate snapshot",STATE,LOG)
    if seeding and os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:print("seeded=true",file=f)


if __name__=="__main__":
    main()
