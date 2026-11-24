"""Resolve the pilot ballots to dated GovInfo source paragraphs and named speakers."""

import collections
import hashlib
import json
import re
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

CACHE = Path(".source-cache")
CACHE.mkdir(exist_ok=True)


class HardFailure(ValueError):
    """An official evidence invariant failed."""


def read(url):
    path = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not path.exists():
        with urlopen(url, timeout=45) as response:
            body = response.read()
            if not body:
                raise ValueError(f"Empty official source at {url}")
            with NamedTemporaryFile(dir=CACHE, delete=False) as temp:
                temp.write(body)
            Path(temp.name).replace(path)
    return path.read_bytes()


def norm(text):
    return " ".join(text.split())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_vote(ballot):
    chamber, congress, session, roll = ballot["vote"].split(":")
    if chamber == "house":
        url = f"https://clerk.house.gov/evs/{ballot['date'][:4]}/roll{int(roll):03}.xml"
    else:
        url = f"https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{int(roll):05}.xml"
    raw = read(url)
    root = ET.fromstring(raw)
    if chamber == "house":
        votes = {
            r.find("legislator").get("name-id"): r.findtext("vote")
            for r in root.findall(".//recorded-vote")
        }
    else:
        ids = json.loads(Path(__file__).with_name("senate-ids.json").read_text())
        lis = {
            r.findtext("lis_member_id"): r.findtext("vote_cast")
            for r in root.findall(".//members/member")
        }
        votes = {bio: lis.get(member) for bio, member in ids.items()}
    ref = (
        root.findtext(".//legis-num")
        if chamber == "house"
        else root.findtext(".//document_type", "")
        + root.findtext(".//document_number", "")
    )
    question = root.findtext(".//vote-question") or root.findtext(
        ".//vote_question_text", ""
    )
    bill = "".join(ballot["bill"].split("-")[1:])
    if re.sub(r"[^a-z0-9]", "", (ref or "").lower()) != bill or not re.match(
        r"^On (Passage\b|Motion to Suspend the Rules and Pass\b)", question, re.I
    ):
        raise ValueError(f"Unverified bill or final passage question in {url}")
    for bio, side in ballot["positions"].items():
        if votes.get(bio) != side:
            raise ValueError(
                f"Official vote and archived position disagree for {bio} in {url}"
            )
    if chamber == "house":
        members = {r.get("name-id"): [r.get("party"), r.get("state")] for r in root.findall(".//recorded-vote/legislator")}
    else:
        by_lis = {r.findtext("lis_member_id"): [r.findtext("party"), r.findtext("state")] for r in root.findall(".//members/member")}
        members = {bio: by_lis[lid] for bio, lid in ids.items() if lid in by_lis}
    tally = collections.Counter(votes.values() if chamber == "house" else lis.values())
    result = root.findtext(".//vote-result") or root.findtext("vote_result")
    return {"url": url, "sha256": digest(raw), "members": members,
            "result": result, "yea": tally["Yea"] + tally["Aye"], "nay": tally["Nay"] + tally["No"]}


# A member marker can contain mixed case, a state qualifier, or a wrapped name.
MEMBER = re.compile(r"^((?:Mr|Mrs|Ms|Miss|Dr)\.\s+[A-Za-zÀ-ž][\w’'–-]*(?:\s+[A-Za-zÀ-ž][\w’'–-]*)*)[.]\s*", re.I)
SALUTATION = re.compile(r"^(?:(?:Mr|Madam)\.?\s+(?:Speaker|Chairman|Chairwoman|Chair|President)|(?:my |dear )?colleagues)(?:,\s*(?:(?:my |dear )?colleagues,\s*)?)", re.I)


def starts_marker(body):
    if SALUTATION.match(body):
        return False
    return bool(re.match(r"^(?:(?:Mr|Mrs|Ms|Miss|Dr)\.\s|The (?:SPEAKER|PRESIDING|ACTING|Chair|Clerk|President)|Acting |Speaker |Clerk |\()", body, re.I))


# Track procedural events in the full granule, including centered headings that
# the speaker parser skips. A pending amendment stays excluded through its vote.
AMENDMENT_EVENTS = re.compile(
    r"(?P<start>^[ \t]*(?:amendments? (?:no\.\s*\d+|number\s+\d+|offered by|en bloc)|"
    r"(?:the (?:acting )?(?:chair|speaker pro tempore)|the presiding officer)\.\s+"
    r"(?:it is now in order to consider (?:an |the )?amendment|the (?:clerk will report|question is on) (?:the |an )?amendment)|"
    r"[^\n]{0,75}\.\s+(?:I (?:offer|call up|have) an amendment|I send an amendment to the desk)))"
    r"|(?P<end>^[ \t]*(?:so,? )?the amendment(?:, as amended,)? was (?:not )?(?:agreed to|withdrawn|rejected))"
    r"|(?P<general>^[ \t]*(?:general debate[ \t]*$|(?:the (?:acting )?(?:chair|speaker pro tempore)|the presiding officer)\.\s+"
    r"(?:the question is on (?:the )?passage|the (?:House|Committee|Senate) will (?:now )?resume general debate)))",
    re.I | re.M,
)


def attributed(text, speakers, managers, ballot, url):
    active = None
    previous_end = 0
    events = iter(AMENDMENT_EVENTS.finditer(text))
    event = next(events, None)
    turn_amendment = False
    scope = "general"
    for para in re.finditer(
        r"(?m)^  (?! )\S[^\n]*(?:\n(?!\s*\n|  |\[\[|<)[^\n]+)*", text
    ):
        # Page furniture, unparsed formatting and speaker changes end attribution.
        if text[previous_end : para.start()].strip():
            active = None
        previous_end = para.end()
        while event and event.start() < para.end():
            scope = "amendment" if event.lastgroup == "start" else "general"
            active = None
            event = next(events, None)
        body = para.group().strip()
        marker = None if SALUTATION.match(body) else MEMBER.match(body)
        if marker:
            turn_amendment = False
            matches = set(speakers.get(norm(marker[1]).upper(), []))
            active = (
                (norm(marker[1]).upper(), *next(iter(matches)))
                if len(matches) == 1
                else None
            )
            body = body[marker.end() :]
        if starts_marker(body):
            active = None
        if (
            not active
            or not body.endswith((".", "!", "?"))
            or "<" in body
            or len(body) > 2500
        ):
            continue
        if re.search(r"\b(?:my amendment|this amendment|amendment (?:No\.|number)\s*\d+)\b", norm(body), re.I):
            turn_amendment = True
        label, bio, name = active
        side = ballot["positions"].get(bio)
        if side not in ("Yea", "Nay", "Aye", "No"):
            continue
        start = para.start() + para.group().index(body)
        yield dict(
                debateScope="amendment" if turn_amendment else scope,
                bio=bio,
                speaker=name,
                side="Yea" if side in ("Yea", "Aye") else "Nay",
                manager=label in managers,
                url=url,
                start=start,
                quote=body,
            )


def sources(ballot):
    result, docs = [], {}
    covered_dates = set()
    speaking = set()
    unidentified = False
    congress, kind, number = ballot["bill"].split("-")
    for day in ballot["dates"]:
        package = "CREC-" + day
        try:
            root = ET.fromstring(
                read(f"https://www.govinfo.gov/metadata/pkg/{package}/mods.xml")
            )
        except HTTPError as e:
            if e.code == 404:
                continue
            raise
        for item in root.findall("{*}relatedItem"):
            ext = item.find("{*}extension")
            if (
                ext is None
                or ext.findtext("{*}granuleClass") != ballot["chamber"].upper()
            ):
                continue
            refs = {
                (r.get("congress"), r.get("type"), r.get("number"))
                for r in ext.findall("{*}bill")
                if r.get("context") in {"HEADERLINE", "FIRSTPARAGRAPH"}
            }
            headlines = {
                (r.get("congress"), r.get("type"), r.get("number"))
                for r in ext.findall("{*}bill[@context='HEADERLINE']")
            }
            refs = headlines or refs
            if refs != {(congress, kind.upper(), number)}:
                continue
            granule = ext.findtext("{*}accessId")
            url = f"https://www.govinfo.gov/content/pkg/{package}/html/{granule}.htm"
            raw = read(url)
            docs[url] = digest(raw)
            covered_dates.add(day)
            text = raw.decode()
            speakers = collections.defaultdict(list)
            for member in ext.findall("{*}congMember[@role='SPEAKING']"):
                label = member.findtext("{*}name[@type='parsed']")
                bio = member.get("bioGuideId")
                if bio:
                    speaking.add(bio)
                else:
                    unidentified = True
                if label and bio:
                    speakers[label.upper()].append(
                        (bio, member.findtext("{*}name[@type='authority-fnf']"))
                    )
            managers = set()
            floor = norm(text)
            # Restrict the designation to the opening order of debate.
            opening = re.split(r"(?i)an amendment (?:offered|printed)|amendment no\. \d+ offered", floor, maxsplit=1)[0]
            designation = re.search(r"(?i)(?:gentleman|gentlewoman) from ([A-Za-z ]+?) \(((?:Mr|Ms|Mrs)\. [^()]+)\),? and (?:the )?(?:gentleman|gentlewoman) from ([A-Za-z ]+?) \(((?:Mr|Ms|Mrs)\. [^()]+)\) (?:each )?will control (\d+) minutes", opening)
            if designation and int(designation[5]) >= 20:
                for state, name in [(designation[1], designation[2]), (designation[3], designation[4])]:
                    qualified = (name + " of " + state).upper()
                    if qualified in speakers:
                        managers.add(qualified)
                    elif len(speakers.get(name.upper(), [])) == 1:
                        managers.add(name.upper())
            # Preserve paragraph breaks while allowing a span across adjacent paragraphs in one turn.
            previous = None
            for row in attributed(text, speakers, managers, ballot, url):
                if previous and (row["bio"], row["debateScope"]) == (previous["bio"], previous["debateScope"]):
                    end = previous["start"] + len(previous["quote"])
                    if text[end:row["start"]].isspace():
                        previous["quote"] = text[previous["start"]:row["start"] + len(row["quote"])]
                        continue
                result.append(row)
                previous = row
    return dict(
        bill=ballot["bill"],
        vote=ballot["vote"],
        title=ballot["title"],
        sources=docs,
        paragraphs=result, missingDates=sorted(set(ballot["dates"])-covered_dates),
        speakerVotes={bio: ballot["positions"].get(bio) for bio in sorted(speaking)}, unidentified=unidentified,
    )
