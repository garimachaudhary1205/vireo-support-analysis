"""Vireo support analysis pipeline.

Reads data/*.csv, applies the cleaning rules documented in README.md,
computes the agent scorecard and the business-case numbers, and writes:

  output/agent_scorecard.csv   one row per agent, raw + mix-adjusted CSAT
  output/findings.json         every number used by the dashboard and memo
  output/other_reclass.csv     'Other' tickets re-labelled from free text

Stdlib only. `python3 src/pipeline.py` from the repo root.
"""

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify import classify_rules

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "output"

# Policy v3.2 figures (section 3, 4, 5)
FR_TARGET_MIN = {"chat": 15, "voice": 120, "social": 240, "email": 480}
CONTACT_COST = {"chat": 210, "email": 260, "voice": 520, "social": 240}
BLENDED_COST = 290
SLA_CREDIT = 350
TRANSFER_COST = 305
REPLACEMENT_LOGISTICS = 340

BAD_LOT_PREFIXES = ("PL2-2510", "PL2-2511", "PL2-2512")
MONTHS_IN_DATA = 18


def parse(ts):
    return datetime.strptime(ts, "%Y-%m-%d %H:%M") if ts and ts.strip() else None


def load():
    tickets = list(csv.DictReader(open(DATA / "tickets.csv")))
    agents = {}
    for r in csv.DictReader(open(DATA / "agents.csv")):
        # roster is one row per assignment; keep latest row per agent for labels
        agents[r["agent_id"]] = r
    orders = {r["order_id"]: r for r in csv.DictReader(open(DATA / "orders.csv"))}
    products = {r["sku"]: r for r in csv.DictReader(open(DATA / "products.csv"))}
    return tickets, agents, orders, products


def clean(tickets):
    """Legacy (Freshdesk) resolution timestamps were reconstructed from a UTC
    event log while everything else is IST (policy section 9). Shift legacy
    resolved_at by +5:30. Anything still negative is excluded from handle time
    and counted as a data-quality casualty."""
    stats = Counter()
    for r in tickets:
        r["_created"] = parse(r["created_at"])
        r["_first_resp"] = parse(r["first_response_at"])
        r["_resolved"] = parse(r["resolved_at"])
        if r["source_system"] == "legacy_fd" and r["_resolved"]:
            r["_resolved"] += timedelta(hours=5, minutes=30)
            stats["legacy_tz_shifted"] += 1
        if r["_resolved"] and r["_resolved"] < r["_created"]:
            stats["still_negative_excluded"] += 1
            r["_resolved"] = None
        r["_csat"] = int(r["csat_score"]) if r["csat_score"].strip() else None
        r["_refund"] = float(r["refund_amount_inr"]) if r["refund_amount_inr"].strip() else 0.0
        r["_done"] = r["status"] in ("resolved", "closed")
    return stats


def monthly_series(tickets):
    csat, vol, cb_share = defaultdict(list), Counter(), defaultdict(Counter)
    for r in tickets:
        m = r["created_at"][:7]
        vol[m] += 1
        cb_share[m][r["category"]] += 1
        if r["_csat"] is not None:
            csat[m].append(r["_csat"])
    months = sorted(vol)
    return {
        "months": months,
        "csat": [round(sum(csat[m]) / len(csat[m]), 2) if csat[m] else None for m in months],
        "volume": [vol[m] for m in months],
        "charging_share_pct": [round(100 * cb_share[m]["Charging & Battery"] / vol[m], 1) for m in months],
    }


def lot_analysis(tickets, orders):
    lot_orders, lot_tickets = Counter(), Counter()
    for o in orders.values():
        if o["sku"] == "VA-EB-PL2":
            lot_orders[o["lot_code"]] += 1
    for r in tickets:
        if r["product_sku"] == "VA-EB-PL2" and r["order_id"] in orders:
            lot_tickets[orders[r["order_id"]]["lot_code"]] += 1
    rows = []
    for lot in sorted(lot_orders):
        n_o, n_t = lot_orders[lot], lot_tickets[lot]
        rows.append({"lot": lot, "orders": n_o, "tickets": n_t,
                     "tickets_per_order": round(n_t / n_o, 2) if n_o else 0,
                     "bad": lot.startswith(BAD_LOT_PREFIXES)})
    bad = [r for r in rows if r["bad"]]
    good = [r for r in rows if not r["bad"]]
    base_rate = sum(r["tickets"] for r in good) / max(1, sum(r["orders"] for r in good))
    bad_orders = sum(r["orders"] for r in bad)
    bad_tickets = sum(r["tickets"] for r in bad)
    excess = bad_tickets - base_rate * bad_orders
    return rows, {"baseline_tickets_per_order": round(base_rate, 2),
                  "bad_lot_orders": bad_orders, "bad_lot_tickets": bad_tickets,
                  "excess_tickets": round(excess)}


def defect_wave_cost(tickets, orders, products):
    """Direct, policy-costed spend on tickets traceable to the three festive
    Pulse 2 lots: contact cost + refunds + replacement cost + SLA credits."""
    cost = {"contacts": 0.0, "refunds": 0.0, "replacements": 0.0, "sla_credits": 0.0, "tickets": 0}
    unit_cost = float(products["VA-EB-PL2"]["unit_cost_inr"])
    for r in tickets:
        o = orders.get(r["order_id"])
        if not (o and o["sku"] == "VA-EB-PL2" and o["lot_code"].startswith(BAD_LOT_PREFIXES)):
            continue
        cost["tickets"] += 1
        cost["contacts"] += CONTACT_COST[r["channel"]]
        cost["refunds"] += r["_refund"]
        if r["replacement_issued"] == "Y":
            cost["replacements"] += unit_cost + REPLACEMENT_LOGISTICS
        if r["_first_resp"] and r["_created"] and r["_done"]:
            if (r["_first_resp"] - r["_created"]).total_seconds() / 60 > FR_TARGET_MIN[r["channel"]]:
                cost["sla_credits"] += SLA_CREDIT
    cost["total"] = round(sum(v for k, v in cost.items() if k != "tickets"))
    return cost


def repeat_contacts(tickets):
    """Policy section 10: another contact from the same customer within 30
    days of resolution = repeat contact, costed at the channel contact cost."""
    by_cust = defaultdict(list)
    for r in tickets:
        by_cust[r["customer_id"]].append(r)
    n_repeat, resolved_n, repeat_cost = 0, 0, 0.0
    agent_repeat = Counter()
    agent_resolved = Counter()
    for r in tickets:
        if not (r["_resolved"] and r["_done"]):
            continue
        resolved_n += 1
        agent_resolved[r["agent_id"]] += 1
        for r2 in by_cust[r["customer_id"]]:
            if r2 is r or not r2["_created"]:
                continue
            if r["_resolved"] < r2["_created"] <= r["_resolved"] + timedelta(days=30):
                n_repeat += 1
                repeat_cost += CONTACT_COST[r2["channel"]]
                agent_repeat[r["agent_id"]] += 1
                break
    return {"repeat": n_repeat, "resolved": resolved_n,
            "rate_pct": round(100 * n_repeat / resolved_n, 1),
            "cost_18mo": round(repeat_cost)}, agent_repeat, agent_resolved


def agent_scorecard(tickets, agents, agent_repeat, agent_resolved):
    cell_scores = defaultdict(list)       # (category, channel) -> scores
    per_agent = defaultdict(lambda: {"csat": [], "resid_keys": [], "ht": [],
                                     "n": 0, "transfers": 0, "breaches": 0, "fr_n": 0})
    for r in tickets:
        a = per_agent[r["agent_id"]]
        a["n"] += 1
        a["transfers"] += int(r["transfers"] or 0)
        if r["_csat"] is not None:
            cell = (r["category"], r["channel"])
            cell_scores[cell].append(r["_csat"])
            a["csat"].append(r["_csat"])
            a["resid_keys"].append((r["_csat"], cell))
        if r["_first_resp"] and r["_resolved"]:
            ht = (r["_resolved"] - r["_first_resp"]).total_seconds() / 3600
            if 0 <= ht:
                a["ht"].append(ht)
        if r["_first_resp"] and r["_created"] and r["_done"]:
            a["fr_n"] += 1
            if (r["_first_resp"] - r["_created"]).total_seconds() / 60 > FR_TARGET_MIN[r["channel"]]:
                a["breaches"] += 1

    cell_mean = {k: sum(v) / len(v) for k, v in cell_scores.items()}
    rows = []
    for aid, d in per_agent.items():
        meta = agents.get(aid, {})
        resids = [s - cell_mean[c] for s, c in d["resid_keys"]]
        n_s = len(d["csat"])
        raw = sum(d["csat"]) / n_s if n_s else None
        adj = sum(resids) / n_s if n_s else None
        se = (statistics.pstdev(resids) / (n_s ** 0.5)) if n_s > 1 else None
        rows.append({
            "agent_id": aid, "name": meta.get("name", "?"), "team": meta.get("team", "?"),
            "tier": meta.get("tier", "?"), "site": meta.get("site", "?"), "shift": meta.get("shift", "?"),
            "tickets": d["n"], "surveyed": n_s,
            "csat_raw": round(raw, 2) if raw else None,
            "csat_adj_residual": round(adj, 2) if adj is not None else None,
            "adj_ci95": round(1.96 * se, 2) if se else None,
            "median_handle_hrs": round(statistics.median(d["ht"]), 1) if d["ht"] else None,
            "breach_rate_pct": round(100 * d["breaches"] / d["fr_n"], 1) if d["fr_n"] else None,
            "repeat_rate_pct": round(100 * agent_repeat[aid] / agent_resolved[aid], 1) if agent_resolved[aid] else None,
            "transfers": d["transfers"],
        })
    # Flag: bottom Tier 1 agents by adjusted residual, min 20 surveys, and the
    # deficit must clear its own 95% CI (don't flag noise).
    t1 = [r for r in rows if r["tier"] == "1" and r["surveyed"] >= 20 and r["csat_adj_residual"] is not None]
    t1.sort(key=lambda r: r["csat_adj_residual"])
    flagged = [r["agent_id"] for r in t1
               if r["csat_adj_residual"] + (r["adj_ci95"] or 0) < 0][:10]
    for r in rows:
        r["flag_retrain"] = "Y" if r["agent_id"] in flagged else ""
    rows.sort(key=lambda r: (r["tier"], r["csat_adj_residual"] if r["csat_adj_residual"] is not None else 99))
    return rows, flagged


def reclassify_other(tickets):
    out, moved = [], Counter()
    for r in tickets:
        if r["category"] != "Other":
            continue
        new_cat, confident = classify_rules(r["customer_message"])
        out.append({"ticket_id": r["ticket_id"], "assigned_team": r["assigned_team"],
                    "transfers": r["transfers"], "new_category": new_cat,
                    "confident": "Y" if confident else "N",
                    "customer_message": r["customer_message"][:200].replace("\n", " ")})
        if confident and new_cat != "Other":
            moved[new_cat] += 1
    return out, moved


def main():
    OUT.mkdir(exist_ok=True)
    tickets, agents, orders, products = load()
    dq = clean(tickets)

    series = monthly_series(tickets)
    lots, lot_summary = lot_analysis(tickets, orders)
    wave = defect_wave_cost(tickets, orders, products)
    rep, agent_rep, agent_res = repeat_contacts(tickets)
    scorecard, flagged = agent_scorecard(tickets, agents, agent_rep, agent_res)
    other_rows, moved = reclassify_other(tickets)

    # SLA + transfer money, double-dip check
    total_breaches = sum(1 for r in tickets if r["_first_resp"] and r["_created"] and r["_done"]
                         and (r["_first_resp"] - r["_created"]).total_seconds() / 60 > FR_TARGET_MIN[r["channel"]])
    total_transfers = sum(int(r["transfers"] or 0) for r in tickets)
    double_dip = [r["ticket_id"] for r in tickets if r["replacement_issued"] == "Y" and r["_refund"] > 0]

    findings = {
        "data_quality": dict(dq),
        "monthly": series,
        "lots": lots, "lot_summary": lot_summary,
        "defect_wave_cost_inr": wave,
        "repeat_contacts": rep,
        "sla": {"breaches": total_breaches, "credits_inr": total_breaches * SLA_CREDIT},
        "transfers": {"count": total_transfers, "cost_inr": total_transfers * TRANSFER_COST},
        "double_dip_tickets": double_dip,
        "other_reclassified": dict(moved),
        "other_total": len(other_rows),
        "flagged_for_retraining": flagged,
    }
    with open(OUT / "findings.json", "w") as f:
        json.dump(findings, f, indent=2)
    with open(OUT / "agent_scorecard.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(scorecard[0].keys()))
        w.writeheader()
        w.writerows(scorecard)
    with open(OUT / "other_reclass.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(other_rows[0].keys()))
        w.writeheader()
        w.writerows(other_rows)

    print(json.dumps({k: v for k, v in findings.items() if k not in ("monthly", "lots")}, indent=2))
    print(f"\nWrote {OUT/'agent_scorecard.csv'}, findings.json, other_reclass.csv")


if __name__ == "__main__":
    main()
