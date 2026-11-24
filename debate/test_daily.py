import json
import sqlite3
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
import daily


class DiscoveryTest(unittest.TestCase):
    def test_late_bill_link_and_senate_crosswalk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"national.sqlite"
            db=sqlite3.connect(path)
            db.executescript("""
                create table bills(id,title);
                create table votes(id,bill_id,chamber,date);
                create table entities(id,kind,payload,source_sha);
                create table sources(sha,url);
                create table actions(bill_id,date,text,chamber,ordinal);
            """)
            ids=json.loads(Path(daily.__file__).with_name("senate-ids.json").read_text())
            bio,lid=next(iter(ids.items()))
            for n,chamber in enumerate(("House","Senate"),1):
                bill=f"119-hr-{n}"
                vid=f"{chamber.lower()}:119:2:{n}"
                db.execute("insert into bills values(?,?)",(bill,"Test bill"))
                db.execute("insert into votes values(?,NULL,?,'2026-11-24')",(vid,chamber))
                positions={bio if n==1 else lid:"Yea"}
                payload=dict(unimportedBillId=bill,question="On Passage",result="Passed",tally={"Yea":1},
                             positions=positions,positionScheme="bioguide" if n==1 else "lis")
                db.execute("insert into entities values(?,'vote',?,?)",(vid,json.dumps(payload),vid))
                db.execute("insert into sources values(?,?)",(vid,"https://example.org/vote"))
                db.execute("insert into actions values(?,'2026-11-23','Debate on the bill',?,0)",(bill,chamber))
            db.commit()
            rows=list(daily.ballots(path))
            db.close()
            self.assertEqual(len(rows),2)
            for row in rows:
                self.assertEqual(row["positions"],{bio:"Yea"})
                self.assertEqual(row["dates"],["2026-11-23"])

    def test_pending_record_expires_without_ai(self):
        day=date.today()
        b=dict(bill="119-hr-1",vote="house:119:2:1",date=str(day),dates=[str(day)])
        packet=dict(sources={},paragraphs=[],missingDates=[str(day)])
        vote=dict(url="https://example.org/vote",sha256="abc",result="Passed",yea=230,nay=200)
        with patch.object(daily,"sources",return_value=packet),patch.object(daily,"verify_vote",return_value=vote):
            self.assertTrue(daily.process(b)["retryPending"])
            b["date"]=str(day-timedelta(days=14))
            result=daily.process(b)
            self.assertFalse(result["points"])
            self.assertEqual(result["passage"]["yea"],230)
            self.assertTrue(result["floorDebate"])
