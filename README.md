# Vireo Support Analysis — Task 1

Answers Priya Raman's ask ("CSAT and handle time per agent, flag the bottom
ten") and the question behind it (why CSAT slid since the festive season, and
where the Q3 training budget should go).

**Headline finding:** the CSAT slide is mostly a product problem, not a people
problem. Pulse 2 earbuds from the Oct–Dec 2025 production lots generate ~2× the
ticket rate of every other lot (₹21.2L direct cost at policy rates). After
adjusting for ticket mix, only **4 agents** — not 10 — are genuinely below
expectation. Full story: `memo/MEMO.md`, numbers: `output/findings.json`.

## Run it

Python 3.10+, standard library only. No API key needed for the default run.

```bash
python3 src/pipeline.py     # cleans data, computes everything -> output/
python3 src/dashboard.py    # -> output/dashboard.html (self-contained, open it)
python3 src/validate.py     # classifier accuracy report + hand-check sample
```

Inputs are read from `data/` (committed here for reproducibility of the
assessment; in a real engagement client data would not live in a public repo).

## What the tool does

1. **Cleans** the export: legacy (Freshdesk) resolution timestamps are UTC while
   everything else is IST (policy §9) — shifted +5:30; blank CSAT excluded from
   averages, never zero-filled (§8).
2. **Per-agent scorecard** (`output/agent_scorecard.csv`): raw CSAT, handle
   time, breach rate, repeat-contact rate, and **mix-adjusted CSAT** — each
   score compared with the average for the same category×channel cell, with a
   95% CI. Flags only agents whose deficit clears their CI. Tier 2 reported
   separately (policy §6 forbids comparing them with Tier 1 on these metrics).
3. **Lot analysis**: joins tickets to orders on `order_id`, computes tickets
   per order per manufacturing lot — this is what finds the defect wave.
4. **AI-assisted reclassification** of the 1,732 "Other" tickets from the
   customer's free text (`src/classify.py`). Default is a tuned rules
   classifier (free, deterministic); `classify_llm()` optionally sends the
   residual the rules can't place to Claude Haiku.
5. **Business case** at policy v3.2 rates: contact costs, SLA credits (₹350),
   transfers (₹305), replacements (unit cost + ₹340).

## How we know it works

- Classifier judged against the category agents could correct at closure:
  **77.8% agreement on 5,702 tickets** (it abstains on another 43% rather than
  guess). Per-category accuracy and top confusions: `python3 src/validate.py`.
- Hand-checked a random 50-ticket sample of 'Other' reclassifications
  (`output/handcheck_sample.csv`): ~82% of confident predictions correct.
  Known failure modes: cancellations (no class for them — the single biggest
  gap), and refund-worded hardware complaints.
- Timestamp fix verified: 2,121 impossible (negative) handle times before the
  +5:30 legacy correction, 0 after; anything still inconsistent is excluded
  and counted in `findings.json > data_quality`.
- Agent flags carry confidence intervals; nothing is flagged on noise.

## If you pick this up Monday (handover)

1. The defect-lot finding drives everything: `pipeline.py > lot_analysis()`.
   Bad lots are hard-coded as `BAD_LOT_PREFIXES` after discovery — if new data
   arrives, re-check the lot table in `findings.json` before trusting the flag.
2. The agent flag list is deliberately 4, not 10 — that is the mix adjustment
   + CI working as intended, not a bug. Tier 2 is excluded on policy grounds.
3. Legacy rows (`source_system=legacy_fd`) are only trustworthy after the
   +5:30 shift in `clean()`; never compute handle time from raw legacy fields.
   Joins are on `agent_id` only — two agents share the display name
   "Kavya Pandey" (Sameer's warning in the email thread).

The email thread matters: Neha's triage-rota objection is answered empirically
in `pipeline.py > rota_check()` (queues no angrier, deficit persists on calm
tickets, predates the wave) — read that before re-litigating the flag list.

## Known limitations

- Repeat-contact matching is by customer within 30 days of resolution, not by
  issue similarity — it overcounts customers with genuinely new issues.
- The rules classifier has no Cancellation / Address-change / GST-invoice
  classes; those stay in "Other" (abstained) by design.
- `orders.csv` joins cover only tickets that quoted an order_id; the
  customer+SKU fallback join from the README is not implemented (time-boxed).
- Duplicate legacy re-imports (policy §9) were checked for and not found in
  this extract; the check is in the analysis notes, not productionised.
