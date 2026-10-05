"""Generate output/dashboard.html from findings.json + agent_scorecard.csv.

Single self-contained file: inline SVG, no CDN, light/dark via
prefers-color-scheme. `python3 src/dashboard.py` after pipeline.py.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# dataviz reference palette (validated)
CSS = """
:root { --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --grid:#e8e7e3;
  --s1:#2a78d6; --s1l:#86b6ef; --crit:#d03b3b; --good:#0ca30c; --card:#f4f3f0; }
@media (prefers-color-scheme: dark) {
  :root { --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --grid:#383835;
    --s1:#3987e5; --s1l:#1c5cab; --crit:#d03b3b; --good:#0ca30c; --card:#242423; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink);
  font:14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; padding:24px; }
h1 { font-size:20px; margin:0 0 2px; } h2 { font-size:15px; margin:28px 0 8px; }
.sub { color:var(--ink2); margin-bottom:20px; }
.tiles { display:flex; gap:12px; flex-wrap:wrap; }
.tile { background:var(--card); border-radius:10px; padding:14px 18px; min-width:170px; }
.tile .v { font-size:26px; font-weight:650; } .tile .l { color:var(--ink2); font-size:12px; }
.tile .d { font-size:12px; margin-top:2px; }
.crit { color:var(--crit); } .good { color:var(--good); }
.wrap { overflow-x:auto; }
svg text { fill:var(--ink2); font-size:11px; }
svg .lbl { fill:var(--ink); font-weight:600; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; }
th { color:var(--ink2); font-weight:600; font-size:12px; }
tr.flag td { background:color-mix(in srgb, var(--crit) 12%, transparent); }
.note { color:var(--ink2); font-size:12px; max-width:720px; }
.legend { font-size:12px; color:var(--ink2); margin:4px 0; }
.sw { display:inline-block; width:10px; height:10px; border-radius:2px; margin:0 4px 0 12px; vertical-align:-1px; }
"""


def svg_line(months, values, w=860, h=200, lo=2.5, hi=4.2):
    pad_l, pad_b, pad_t = 40, 26, 10
    iw, ih = w - pad_l - 12, h - pad_b - pad_t
    pts = []
    for i, v in enumerate(values):
        x = pad_l + i * iw / (len(values) - 1)
        y = pad_t + (hi - v) / (hi - lo) * ih
        pts.append((round(x, 1), round(y, 1), v, months[i]))
    path = "M" + " L".join(f"{x},{y}" for x, y, *_ in pts)
    grid = "".join(
        f'<line x1="{pad_l}" y1="{pad_t + (hi - g) / (hi - lo) * ih:.1f}" x2="{w-12}" '
        f'y2="{pad_t + (hi - g) / (hi - lo) * ih:.1f}" stroke="var(--grid)"/>'
        f'<text x="6" y="{pad_t + (hi - g) / (hi - lo) * ih + 4:.1f}">{g:.1f}</text>'
        for g in (2.5, 3.0, 3.5, 4.0))
    ticks = "".join(f'<text x="{pts[i][0]:.1f}" y="{h-8}" text-anchor="middle">{months[i][2:]}</text>'
                    for i in range(0, len(months), 3))
    lowest = min(pts, key=lambda p: p[2])
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="transparent"><title>{m}: {v}</title></circle>'
                   for x, y, v, m in pts)
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly CSAT">'
            f'{grid}<path d="{path}" fill="none" stroke="var(--s1)" stroke-width="2"/>'
            f'<circle cx="{lowest[0]}" cy="{lowest[1]}" r="4" fill="var(--crit)"/>'
            f'<text class="lbl" x="{lowest[0]}" y="{lowest[1]-10}" text-anchor="middle">'
            f'{lowest[3]}: {lowest[2]}</text>{dots}{ticks}</svg>')


def svg_bars(months, vols, shares, w=860, h=220):
    pad_l, pad_b, pad_t = 40, 26, 14
    iw, ih = w - pad_l - 12, h - pad_b - pad_t
    vmax = max(vols)
    bw = iw / len(vols) - 3
    bars, ticks = "", ""
    for i, (v, s) in enumerate(zip(vols, shares)):
        x = pad_l + i * iw / len(vols)
        bh = v / vmax * ih
        cb_h = bh * s / 100
        bars += (f'<g><rect x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{bw:.1f}" height="{bh-cb_h:.1f}" '
                 f'fill="var(--s1l)" rx="3"/>'
                 f'<rect x="{x:.1f}" y="{pad_t+ih-cb_h:.1f}" width="{bw:.1f}" height="{cb_h:.1f}" '
                 f'fill="var(--crit)" rx="2"/>'
                 f'<title>{months[i]}: {v} tickets, {s}% charging &amp; battery</title></g>')
        if i % 3 == 0:
            ticks += f'<text x="{x+bw/2:.1f}" y="{h-8}" text-anchor="middle">{months[i][2:]}</text>'
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly volume">'
            f'<text x="6" y="{pad_t+6}">{vmax}</text>{bars}{ticks}</svg>')


def svg_lots(lots, w=860, h=230):
    lots = [l for l in lots if l["orders"] >= 10]
    pad_l, pad_b, pad_t = 40, 60, 14
    iw, ih = w - pad_l - 12, h - pad_b - pad_t
    vmax = max(l["tickets_per_order"] for l in lots)
    bw = iw / len(lots) - 2
    bars = ""
    for i, l in enumerate(lots):
        x = pad_l + i * iw / len(lots)
        bh = l["tickets_per_order"] / vmax * ih
        col = "var(--crit)" if l["bad"] else "var(--s1l)"
        bars += (f'<g><rect x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}" rx="3"/>'
                 f'<title>{l["lot"]}: {l["tickets"]} tickets / {l["orders"]} orders = {l["tickets_per_order"]}</title></g>')
        if l["bad"] or i % 6 == 0:
            bars += (f'<text x="{x+bw/2:.1f}" y="{h-46}" text-anchor="end" '
                     f'transform="rotate(-45 {x+bw/2:.1f} {h-46})">{l["lot"][4:]}</text>')
    for g in (0.25, 0.5, 0.75, 1.0):
        if g <= vmax:
            y = pad_t + ih - g / vmax * ih
            bars = (f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-12}" y2="{y:.1f}" stroke="var(--grid)"/>'
                    f'<text x="6" y="{y+4:.1f}">{g}</text>') + bars
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Tickets per order by lot">'
            f'{bars}</svg>')


def main():
    F = json.load(open(OUT / "findings.json"))
    agents = list(csv.DictReader(open(OUT / "agent_scorecard.csv")))
    m = F["monthly"]
    csat_now = [v for v in m["csat"] if v][-1]
    trough = min(v for v in m["csat"] if v)
    wave = F["defect_wave_cost_inr"]
    rep = F["repeat_contacts"]

    def row(a):
        cls = ' class="flag"' if a["flag_retrain"] == "Y" else ""
        adj = a["csat_adj_residual"]
        ci = a["adj_ci95"]
        return (f'<tr{cls}><td>{a["agent_id"]}</td><td>{a["name"]}</td><td>{a["team"]}</td>'
                f'<td>{a["site"]}/{a["shift"]}</td><td>{a["tickets"]}</td><td>{a["csat_raw"]}</td>'
                f'<td>{adj} ± {ci}</td><td>{a["median_handle_hrs"]}</td>'
                f'<td>{a["breach_rate_pct"]}%</td><td>{a["repeat_rate_pct"]}%</td>'
                f'<td>{"RETRAIN" if a["flag_retrain"]=="Y" else ""}</td></tr>')

    t1 = "".join(row(a) for a in agents if a["tier"] == "1")
    t2 = "".join(row(a) for a in agents if a["tier"] == "2")
    thead = ("<tr><th>ID</th><th>Name</th><th>Team</th><th>Site/Shift</th><th>Tickets</th>"
             "<th>CSAT raw</th><th>CSAT vs expected ±95% CI</th><th>Median handle (h)</th>"
             "<th>FR breach</th><th>Repeat</th><th>Flag</th></tr>")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vireo Support — CSAT &amp; Agent Scorecard</title><style>{CSS}</style></head><body>
<h1>Vireo Support — what moved CSAT, and who to retrain</h1>
<div class="sub">Jan 2025 – Jun 2026 · {rep['resolved']:,} resolved tickets · built from tickets.csv + orders.csv lot codes · policy v3.2 cost standards</div>

<div class="tiles">
<div class="tile"><div class="v crit">{trough}</div><div class="l">CSAT trough (Feb 2026)</div><div class="d">now {csat_now}, recovering</div></div>
<div class="tile"><div class="v">₹{wave['total']/100000:.1f}L</div><div class="l">direct cost of 3 festive Pulse&nbsp;2 lots</div><div class="d">{wave['tickets']:,} tickets traced via lot codes</div></div>
<div class="tile"><div class="v">{rep['rate_pct']}%</div><div class="l">repeat-contact rate (30-day)</div><div class="d">₹{rep['cost_18mo']/100000:.1f}L re-handling / 18&nbsp;mo</div></div>
<div class="tile"><div class="v">{len(F['flagged_for_retraining'])}</div><div class="l">agents truly below expectation</div><div class="d">not 10 — after ticket-mix adjustment</div></div>
</div>

<h2>Monthly CSAT (surveyed tickets only — blanks excluded per policy §8)</h2>
<div class="wrap">{svg_line(m['months'], m['csat'])}</div>

<h2>Ticket volume, with Charging &amp; Battery share</h2>
<div class="legend"><span class="sw" style="background:var(--s1l)"></span>all other tickets
<span class="sw" style="background:var(--crit)"></span>Charging &amp; Battery</div>
<div class="wrap">{svg_bars(m['months'], m['volume'], m['charging_share_pct'])}</div>

<h2>Pulse 2 — tickets per order sold, by manufacturing lot</h2>
<div class="legend"><span class="sw" style="background:var(--crit)"></span>festive lots (Oct–Dec 2025 production)
<span class="sw" style="background:var(--s1l)"></span>all other lots · baseline {F['lot_summary']['baseline_tickets_per_order']}/order</div>
<div class="wrap">{svg_lots(F['lots'])}</div>
<p class="note">The three festive production lots generate ~2× the ticket rate of every other lot.
{F['lot_summary']['excess_tickets']} excess tickets, ₹{wave['total']/100000:.1f}L of direct cost
(replacements ₹{wave['replacements']/100000:.1f}L, refunds ₹{wave['refunds']/100000:.1f}L,
handling ₹{wave['contacts']/100000:.1f}L, SLA credits ₹{wave['sla_credits']/100000:.1f}L).
This — not agent performance — is what dragged CSAT from Nov 2025.</p>

<h2>Tier 1 agents — CSAT adjusted for the ticket mix each agent actually handles</h2>
<p class="note">"CSAT vs expected" compares each agent's scores with the average for the same
category×channel cell, so an agent who drew hard warranty chats is not punished for the draw.
Flagged rows are below expectation even at the bottom of their 95% confidence interval
(min 20 surveys).</p>
<div class="wrap"><table>{thead}{t1}</table></div>

<h2>Tier 2 — Escalations &amp; Warranty (reported separately per policy §6)</h2>
<p class="note">Policy: Tier 2 handles multi-touch warranty work and "is not to be compared
with Tier 1 on volume metrics." Their low raw CSAT is dominated by the defect wave; retraining
budget should not target them on this evidence.</p>
<div class="wrap"><table>{thead}{t2}</table></div>
</body></html>"""
    (OUT / "dashboard.html").write_text(html)
    print(f"Wrote {OUT/'dashboard.html'} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
