# Automatic debate review

The records review runs the automatic source parser, sentence selector, independent verification request and renderer. There is no editorial input or alternate selection path. The artifacts are review previews. The hourly records deployment and the app use separate workflows.

## Frozen November 24 holdout

Use the ten House final-passage ballots in holdout.json exactly once. The sampling rule takes the newest eligible House passage roll calls from the app’s archived 119th Congress votes, ordered by date and roll number, excluding bills used in either previous pilot. Each unique bill must have a verified passage vote and attributed Congressional Record paragraphs from members on both recorded sides. Eligibility uses speaker presence, without assessing argument quality. The sample is House-only.

Before any model call, verify each ballot against the Clerk’s XML. Only general debate and final-passage remarks are eligible. Strict structured responses nominate consecutive sentence IDs. Independent checks assess a concrete reason for the recorded vote, meaning beyond the title and whether the quotation stands alone. Each side displays up to three distinct speakers with an equal number on the other side. The source text, hash, character offsets, identifiers, responses, token counts and estimated cost are retained in the diagnostics. Display normalization strips the opening salutation and folds whitespace.

**Pass rule fixed before generation.** Zero wrong speakers, wrong sides or altered quotations. Across all ten bills at most one displayed quote may lack a reason, concern only an amendment, merely restate the title or require missing context. An empty state after genuine rejection is allowed. A missing output, API failure or failed source check is an incomplete evaluation. Report the number of bills with a pair and the total number of displayed quotes alongside the verdict. Score the first automatic outputs, with no manual selection, repairs or substitutions after generation.
