# Submission — Task 1 (Vireo Audio, Set B)

> Fill the bracketed placeholders (links, hours) before submitting.

## What did you build, and what business outcome does it move?

A pipeline + dashboard that (a) scores all 44 agents on CSAT and handle time
**adjusted for the ticket mix they actually drew**, and (b) traces the CSAT
slide to its cause: Pulse 2 earbuds from the Oct–Dec 2025 festive production
lots, which generate ~2× the ticket rate of every other lot.

The numbers: that defect wave cost **₹21.2 lakh at Vireo's own policy rates**
(₹11.5L replacements, ₹4.5L refunds, ₹4.7L handling, ₹0.5L SLA credits) —
about **₹10.6L per quarter while it ran** — and dragged CSAT from ~3.5 to 2.95.
The movable outcome: a weekly tickets-per-order-per-lot monitor (now on the
dashboard) catches the next bad lot in weeks instead of four months, worth most
of that ₹21L per incident. Secondary: pointing the Q3 training budget at the
**4 agents** who are genuinely below expectation (not a naive bottom ten, six
of whom would have been Tier-2 agents the policy says can't be measured this
way), and at first-contact resolution — 27.3% of resolved tickets come back
within 30 days, ₹8.4L of re-handling over the 18 months.

## What does one run cost? A month at ~650 tickets/week?

The default run makes **no paid calls**: stdlib Python + a rules classifier.
₹0 per run, ₹0 per month.

The optional LLM pass (Claude Haiku 4.5, $1/M input, $5/M output tokens) covers
only tickets the rules can't place. Backfill: 1,732 'Other' tickets × ~130
input tokens ≈ 225k in + ~17k out → $0.23 + $0.09 ≈ **$0.32 (~₹28) once**.
Ongoing: 650/wk × 4.33 = 2,815 tickets/mo, ~15% land in 'Other' = 422 tickets
→ ~55k in + ~4k out → **~$0.08 (~₹7) per month**. (Note: the pack itself runs
~150 tickets/week, not 650; we scaled the arithmetic to the stated volume.)

## How do you know it works?

Three checks, error rates included:

1. **Classifier vs agent-corrected tags**: on the 10,018 tickets with a real
   category, the rules classifier judged 5,702 and agreed **77.8%**; it
   abstains (stays 'Other') on the rest rather than guess. Worst categories:
   Returns↔Delivery confusion (genuinely ambiguous — "box crushed, want
   refund"). Full per-category table: `python3 src/validate.py`.
2. **Hand check**: 50 random 'Other' reclassifications read by a human
   (`output/handcheck_sample.csv`): ~82% of confident predictions correct.
   The kind it gets wrong: cancellation requests (no class exists for them)
   and hardware complaints phrased around refunds.
3. **Cleaning verified by invariant**: 2,121 negative handle times before the
   legacy UTC→IST fix, 0 after. Agent flags require the deficit to clear a 95%
   CI, so no one is flagged on noise.

## Did you change, narrow, or push back on the client's ask?

Yes, twice. Priya asked for "the bottom ten to retrain." (1) Her own policy
(§6) forbids comparing Tier-2 agents on these metrics — a naive bottom ten is
six Tier-2 agents who caught the warranty wave. (2) After mix-adjustment with
confidence intervals, only **4** Tier-1 agents are credibly below expectation;
flagging six more would spend training budget on noise. We also used
orders.csv, which she said to ignore — the lot codes in it are the entire
explanation for her CSAT slide.

## What is wrong with what you are handing us?

- Repeat-contact matching is customer+30-days, not issue-similarity: it counts
  a genuinely new problem as a repeat. The 27.3% is an upper bound.
- The classifier has no Cancellation / Address-change / GST-invoice classes —
  the biggest clusters inside 'Other' — so ~40% of 'Other' stays unplaced.
- `BAD_LOT_PREFIXES` is hard-coded after discovery rather than detected by a
  threshold rule; new data requires re-checking the lot table.
- Tickets without an order_id (the README's customer+SKU fallback join) are
  excluded from lot analysis, so the ₹21.2L understates the wave.
- Handle time uses first-response→resolution per policy §10; for voice
  callbacks this is dominated by queue time, not talk time, and we did not
  separate the two.
- The dashboard is a static regenerated file, not live.

## What did you deliberately leave out, and why that rather than something else?

- **customers.csv** (city/state/care_plus cuts) and **shift/site breakdowns** —
  interesting, but they don't change either decision on the table (train whom;
  act on which lots). Everything kept had to move one of those two decisions.
- **An LLM pass over all 11,750 messages** (sentiment, agent-note quality):
  the two free-text fields' marginal value beyond classification didn't
  justify the validation burden inside 5 hours.
- **Live dashboard / web app**: a static HTML file answers Priya's question;
  hosting adds failure modes to a vendor evaluation, not information.
- **Duplicate re-import reconciliation** (policy §9 warns of it): we tested
  for cross-system duplicates on three keys, found none in this extract, and
  stopped there rather than productionising a check for a problem the data
  doesn't show.

## Anything you built or found that nobody asked for?

- The lot-code defect finding itself — Priya said to ignore orders.csv.
- **6 tickets where a customer got both a refund and a replacement** (policy
  §5 says this must be escalated same-day): TK-240833, TK-244004, TK-245019,
  TK-247304, TK-250859, TK-253280 — ~₹15–20k of leakage, listed in
  `findings.json`.
- SLA breach credits totalled ₹3.5L over the period; breaches are charged to
  the *resolving* agent even when the delay happened before a transfer —
  worth fixing before anyone is managed on that number.
- The intake bot's 'Other' rate (15%) is itself a finding: half of those are
  machine-classifiable from the first message alone.

## What did you use AI for?

[Edit to match your actual workflow before submitting.]
Claude Code (Fable 5) was used end-to-end: data profiling, the cleaning rules,
the pipeline/dashboard code, the validation harness, and drafting the memo —
all reviewed and directed by me. The rules classifier was AI-drafted, then
corrected after validation caught substring bugs ("re**pair**" matching the
*pair* rule, "dis**charged twice**" matching "charged twice") — the error rate
analysis is what made it shippable. Thrown away: an early plan to LLM-classify
all 11,750 messages (cost/validation not justified — see above), and a
first-pass naive bottom-ten ranking that the policy PDF invalidated.
Runtime AI: none by default; optional Claude Haiku 4.5 for residual
classification (arithmetic above).

Screen recording: [LINK]

## Google Drive link

[LINK — folder should contain: memo PDF, dashboard.html, screen recording]

## Someone picks this up on Monday — the three things they need to know

1. The whole story hangs on tickets-per-order by manufacturing lot
   (`pipeline.py > lot_analysis()`); the three bad lots are hard-coded after
   discovery — re-verify against `findings.json > lots` on new data.
2. Legacy (`legacy_fd`) resolution timestamps are UTC; only use them after the
   +5:30 shift in `clean()`, or every legacy handle time is wrong by 5.5 hours.
3. The flag list is 4 agents, not 10, on purpose: mix-adjustment + 95% CI,
   Tier 2 excluded per policy §6. Don't "fix" it back to ten.

## Honest hours spent

[YOUR NUMBER]

## GitHub repo

[LINK]
