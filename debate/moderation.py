"""Poll every newly created owner command; persist its result before replying."""
import json
import re
import subprocess
from records import STATE,LOG,withdraw,append_events
from ledger import save,commit

REPO="dustinbowers51/pocket-politics-records"
ISSUE=7
OWNER=318668238
PATH=f"repos/{REPO}/issues/{ISSUE}/comments"


def surname(name):
    words=re.sub(r"[,\.]","",name).casefold().split()
    while len(words)>1 and words[-1] in {"jr","sr","ii","iii","iv"}:words.pop()
    return words[-1]


def command(state,body,events):
    match=re.fullmatch(r"drop\s+(H\.?\s*R\.?|S\.?|H\.?\s*J\.?\s*Res\.?|S\.?\s*J\.?\s*Res\.?)\s*(\d+)\s+(.+)",body,re.I)
    if not match:return "Nothing changed. Use `drop H.R. 7567 Lucas` or `drop S. 123 Smith`."
    kind=re.sub(r"[^a-z]","",match[1].lower());name=match[3].strip().casefold()
    hits=[(r,p) for r in state["records"].values() if r["bill"].endswith(f"-{kind}-{int(match[2])}")
          for p in r["points"] if name in (p["speaker"].casefold(),surname(p["speaker"]))]
    if not hits:return "Nothing changed. No active quote matched that bill and speaker."
    if len(hits)!=1:return "Nothing changed. Multiple quotes matched. Use the speaker’s full name or the exact quote ID with `drop-id ID`."
    r,p=hits[0]
    return remove(state,r,p,events)


def remove(state,r,p,events):
    before=len(events)
    withdraw(state,r,{p["id"]},events,"Owner removal")
    return "Removed "+", ".join(e["speaker"]+" ("+e["reason"]+")" for e in events[before:])+f" from {r['bill']}. The next records publication will reflect the change."


def main():
    pages=json.loads(subprocess.check_output(["gh","api","--paginate","--slurp",PATH+"?per_page=100"]))
    comments=[c for page in pages for c in page]
    state=json.loads(STATE.read_text())
    for c in comments:
        body=c["body"].strip()
        if c["user"]["id"]!=OWNER or not re.match(r"^drop(?:-id)?\b",body,re.I):continue
        key=str(c["id"]);marker=f"<!-- debate-command-{key} -->"
        if key not in state["commands"]:
            events=[]
            if body.lower().startswith("drop-id "):
                ident=body[8:].strip()
                hits=[(r,p) for r in state["records"].values() for p in r["points"] if p["id"]==ident]
                reply=remove(state,*hits[0],events) if len(hits)==1 else "Nothing changed. No unique active quote matched that ID."
            else:reply=command(state,body,events)
            state["commands"][key]=reply
            save(STATE,state);append_events(events)
            commit("Apply owner debate command "+key,STATE,LOG)
        if not any(x["user"]["login"]=="github-actions[bot]" and marker in x["body"] for x in comments):
            subprocess.run(["gh","api",PATH,"--method","POST","-f","body="+state["commands"][key]+"\n\n"+marker],check=True,stdout=subprocess.DEVNULL)

if __name__=="__main__":main()
