"""One-time accuracy-only migration of the approved, frozen Round 6 inventory."""
import json
import os
from pathlib import Path
from daily import process
from records import STATE, LOG, record, event, append_events, display
from sources import sources,verify_vote
import ledger


def main():
    state=json.loads(STATE.read_text())
    if state.get("accuracyOnly"):return
    plan=json.loads(Path(__file__).with_name("round6-input.json").read_text())
    restore=set(plan["restore"])
    history=[json.loads(line) for line in LOG.read_text().splitlines()]
    events=[]
    try:
        for b in plan["ballots"]:
            old=state["records"][b["vote"]]
            vote=verify_vote(b)
            points=list(old["points"])
            for item in history:
                ident=item["quoteId"]
                if item["vote"]==b["vote"] and item["action"]=="drop" and ident in restore and ident in state["blocked"]:
                    pt=dict(item["point"],display=display(item["point"]["quote"]))
                    points.append(pt)
                    del state["blocked"][ident]
                    events.append(event("restore",old,pt,"Round 6 accuracy-only decision"))
            packet=sources(b)
            rec=record(b,vote,packet,points)
            if not points and rec["emptyReason"]=="noClearPair":
                path=Path("debate-data/accuracy-checkpoints")/(b["vote"].replace(":","-")+".json")
                if not path.exists():
                    rec=process(b)
                    ledger.save(path,rec)
                    ledger.commit("Checkpoint accuracy-only debate "+b["vote"],path)
                else:
                    rec=record(b,vote,packet,json.loads(path.read_text())["points"])
                events.extend(event("publish",rec,p,"Accuracy-only rerun") for p in rec["points"])
            state["records"][b["vote"]]=rec
        state["accuracyOnly"]=True
        ledger.save(STATE,state)
        append_events(events)
    finally:
        ledger.finish()
    ledger.commit("Restore reviewed quotes and publish accuracy-only debate",STATE,LOG)
    with open(os.environ["GITHUB_OUTPUT"],"a") as f:print("seeded=true",file=f)

if __name__=="__main__":main()
