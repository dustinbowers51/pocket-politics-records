# Automatic debate span review

## Frozen test protocol

Score the first automatic outputs from the ten previously unused House-origin bills with House final-passage votes in span-holdout.json. Take the newest eligible bills by archived passage date and roll number. Exclude every prior sample and require remarks by members on both sides of a passage vote verified against the House Clerk. Do not choose bills by argument quality. Use the same automatic selection path for every bill, with no editorial nominations or replacements.

Each eligible span contains one to three consecutive complete sentences from one member’s general debate or final-passage remarks, with a maximum of 60 source words. Preserve the original text and offsets. Strip opening salutations and fold whitespace for display. Enumerate span IDs before the model selects them. Only a side with zero accepted quotes gets one additional nomination round from remaining spans. An empty card after that is a valid output.

Count a quote as weak if it fails to say what the bill does or would do, or its effect, and why that is good or bad. Deadlines or timing alone, objections solely to process, and background without a bill connection are weak. A bill-referring pronoun is acceptable. Material references to missing context are not.

**Pass requires all three conditions.** Zero wrong speakers, wrong passage votes, or altered quotes. At most one weak quote across the ten bills, using the higher of the initial and independent reviewer counts. At least six bills must display a pair. A missing output or operational error makes the run incomplete. Preserve the first results even if the test fails. Report screenshots, diagnostics and estimated spend.

The prior ten-bill holdout scored three weak quotes on independent review, including Frost on H.R. 1181. The previous screenshots and evidence remain in git history.
