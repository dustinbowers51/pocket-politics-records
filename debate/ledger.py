"""Reserve the monthly balance durably before a run and settle measured API usage."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PATH = Path("debate-data/budget.json")
LIMIT = 5_000_000_000  # nanodollars
run = None


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n")


def commit(message, *paths):
    subprocess.run(["git","add","--",*map(str,paths)],check=True)
    if subprocess.run(["git","diff","--cached","--quiet"]).returncode:
        subprocess.run(["git","commit","-m",message],check=True)
        subprocess.run(["git","push","origin","HEAD:published-debate"],check=True)


def month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def begin():
    global run
    book = json.loads(PATH.read_text()) if PATH.exists() else {}
    key = month()
    balance = LIMIT - sum(x["charge"] for x in book.get(key,[]))
    if balance <= 0:
        raise RuntimeError("Monthly debate budget exhausted")
    entry = dict(run=os.environ["GITHUB_RUN_ID"],charge=balance,status="reserved")
    book.setdefault(key,[]).append(entry)
    save(PATH,book)
    commit("Reserve monthly debate API allowance",PATH)
    run = dict(book=book,entry=entry,balance=balance,spent=0,month=key)


def reserve(data):
    # UTF-8 request bytes upper-bound input token count, with room for API framing.
    maximum = (len(data)+4096)*750 + 10000*4500
    if run is None or month()!=run["month"] or run["spent"]+maximum>run["balance"]:
        raise RuntimeError("Monthly debate budget cannot cover another request")
    run["spent"] += maximum
    return maximum


def settle(maximum, usage):
    cached=usage.get("input_tokens_details",{}).get("cached_tokens",0)
    actual=(usage["input_tokens"]-cached)*750+cached*75+usage["output_tokens"]*4500
    if actual>maximum:
        raise RuntimeError("API accounting exceeded reservation")
    run["spent"] += actual-maximum


def finish():
    if run:
        run["entry"].update(charge=run["spent"],status="settled")
        save(PATH,run["book"])
        commit("Settle measured debate API usage",PATH)
