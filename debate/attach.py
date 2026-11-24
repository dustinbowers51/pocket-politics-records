"""Place debate inside the schema-1 metadata object and rehash the complete manifest."""
import hashlib
import json
import os
import sys
from pathlib import Path

def encode(value):
    return json.dumps(value,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def attach(root, state, enabled):
    mf=root/"manifest.json"
    manifest=json.loads(mf.read_text())
    assert sha(encode(manifest["files"]))==manifest["version"]
    meta,=[f for f in manifest["files"] if f["group"]=="metadata"]
    raw=(root/"objects"/(meta["hash"]+".json")).read_bytes()
    assert sha(raw)==meta["hash"] and len(raw)==meta["bytes"]
    data=json.loads(raw)
    active=enabled and state["seedComplete"]
    data["debate"]={"schema":1,"enabled":active,"label":"From the official debate. Exact quotes, selected by AI.",
                    "records":state["records"] if active else {}}
    raw=encode(data)
    meta.update(hash=sha(raw),bytes=len(raw))
    path=root/"objects"/(meta["hash"]+".json")
    path.write_bytes(raw)
    assert sha(path.read_bytes())==meta["hash"]
    manifest["version"]=sha(encode(manifest["files"]))
    mf.write_bytes(encode(manifest))

if __name__=="__main__":
    state=json.loads((Path(__file__).resolve().parents[1]/"debate-data/state.json").read_text())
    attach(Path(sys.argv[1]),state,os.getenv("DEBATE_QUOTES_ENABLED","").lower() in ("","true"))
