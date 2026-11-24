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
