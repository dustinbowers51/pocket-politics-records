import unittest

from sources import attributed

# https://www.govinfo.gov/content/pkg/CREC-2026-07-21/html/CREC-2026-07-21-pt1-PgH4736.htm
EXCHANGE = "  Mr. ROGERS of Alabama. Mr. Chairman, I yield 2 minutes to the \ngentleman from Tennessee (Mr. DesJarlais), the chairman of Strategic \nForces Subcommittee.\n  Mr. DesJARLAIS. Mr. Chairman, I rise today in favor of the Fiscal \nYear 2027 National Defense Authorization Act.\n  As the chairman of the Strategic Forces Subcommittee, I was proud to \nwork in a bipartisan fashion along with my friend Ranking Member Seth \nMoulton on some of the most consequential issues to our national \nsecurity.\n  This legislation authorizes full funding to keep modernizing the \nNation's nuclear forces as well as the Department of Energy's \nscientific and production capabilities upon which our deterrent \ndepends."

MEMBERS = {"MR. ROGERS OF ALABAMA": [("R000575", "Mike Rogers")],
           "MR. DESJARLAIS": [("D000616", "Scott DesJarlais")]}
BALLOT = {"positions": {"R000575": "Yea", "D000616": "Yea"}}


class SpeakerTest(unittest.TestCase):
    def test_handoff_and_continuations(self):
        rows = list(attributed(EXCHANGE, MEMBERS, set(), BALLOT, "record"))
        self.assertEqual([r["bio"] for r in rows], ["R000575"] + ["D000616"] * 3)
        for row in rows:
            self.assertTrue(EXCHANGE.startswith(row["quote"], row["start"]))

    def test_unknown_and_ambiguous_end_turn(self):
        for matches in ([], list(MEMBERS.values())[0] + list(MEMBERS.values())[1]):
            members = dict(MEMBERS, **{"MR. DESJARLAIS": matches})
            rows = list(attributed(EXCHANGE, members, set(), BALLOT, "record"))
            self.assertEqual([r["bio"] for r in rows], ["R000575"])


class SentenceTest(unittest.TestCase):
    def test_closing_procedure_and_original_offsets(self):
        from preview import candidate_rows, resolve
        from sources import digest
        from unittest.mock import patch
        text = "Mr. Speaker, this bill funds clinics. Rural patients will regain access. I yield back the balance of my time."
        row = dict(quote=text, speaker="Member", side="Yea", bio="B", manager=True, url="record", start=0)
        packet = dict(paragraphs=[row], sources={"record":digest(text.encode())}, passageRecord={"members":{"B":[]}})
        item, = candidate_rows(packet, "Yea")
        self.assertEqual(set(item[3]), {0,1})
        with patch("preview.read", return_value=text.encode()):
            point = resolve(packet, item, 0, 1)
            self.assertEqual(point["display"], "this bill funds clinics. Rural patients will regain access.")
            self.assertEqual(point["quote"], text[point["start"]:point["end"]])
            with self.assertRaises(ValueError):
                resolve(packet, item, 0, 2)

class HoldoutGuards(unittest.TestCase):
    def test_amendment_stays_excluded_through_vote(self):
        from preview import candidate_rows
        text = ("  Mr. DesJARLAIS. The bill provides funding for rural clinics.\n"
                "                 Amendment No. 1 Offered by Mr. Rogers\n"
                "  Mr. ROGERS of Alabama. This change would close all the rural clinics.\n"
                "  A second sentence with no amendment keywords must still be excluded.\n"
                "  The amendment was not agreed to.\n"
                "  Mr. DesJARLAIS. The final bill keeps the rural clinics open.")
        rows = list(attributed(text, MEMBERS, set(), BALLOT, "record"))
        self.assertEqual([r["debateScope"] for r in rows], ["general","amendment","amendment","general"])
        self.assertEqual([item[0] for item in candidate_rows({"paragraphs":rows}, "Yea")], [0,3])

    def test_title_context_and_salutation(self):
        from sources import SALUTATION
        from preview import BACK_REFERENCE, title_only
        self.assertEqual(SALUTATION.sub("", "Mr. President, colleagues, every day counts."), "every day counts.")
        for opening in ("Anything less than that leaves a loophole.", "This bill makes all of those protections real.",
                        "The Act seeks to shrink that gap by restoring authority."):
            self.assertTrue(BACK_REFERENCE.search(opening))
        self.assertTrue(title_only("I rise today in support of the Stop Insider Trading Act.", "Stop Insider Trading Act"))
        self.assertFalse(title_only("Members could still trade using confidential committee information.", "Stop Insider Trading Act"))

class SpanCatalogTest(unittest.TestCase):
    def test_all_valid_lengths_and_bill_pronoun(self):
        from preview import candidate_spans
        text = "It pays hospitals for care. Rural clinics could stay open. Those protections matter. Families could get care locally."
        row = dict(quote=text, side="Yea", manager=False, bio="M", debateScope="general")
        spans = candidate_spans(dict(title="Hospital Payment Act",paragraphs=[row]), "Yea")
        self.assertEqual([(a,b) for _,a,b in spans], [(0,0),(0,1),(0,2),(1,1),(1,2),(1,3),(3,3)])

    def test_retry_only_for_empty_side_and_remove_previous_span(self):
        from preview import select
        from sources import digest
        from unittest.mock import patch
        text = "It funds rural clinics. Patients can get care locally."
        rows = [dict(quote=text, speaker=s, side=s, bio=s, manager=True, url="record", start=0)
                for s in ("Yea","Nay")]
        packet = dict(title="Health Act", paragraphs=rows, sources={"record":digest(text.encode())},
                      passageRecord={"members":{"Yea":[],"Nay":[]}})
        seen=[]
        def ask(prompt, payload, audit, stage, side):
            if stage=="selection":
                seen.append((side,payload["last_id"]))
                return {"span_ids":[0]}
            quote=payload["quotes"][0]
            return {"checks":[dict(id=0,substantive=side=="Yea" or seen.count(("Nay",1))==1,
                                   stands_alone=True,effect_evidence=quote,value_evidence=quote,reason="test")]}
        with patch("preview.ask",side_effect=ask), patch("preview.read",return_value=text.encode()):
            result=select(packet,dict(selection=[],checks=[]))
        self.assertEqual(seen,[("Yea",2),("Nay",2),("Nay",1)])
        self.assertEqual(len(result),2)
