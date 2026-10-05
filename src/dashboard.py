"""Generate output/dashboard.html from findings.json + agent_scorecard.csv.

Single self-contained file: tabbed layout, inline SVG, hover tooltips,
sortable tables, light/dark via prefers-color-scheme. No CDN, no deps.
`python3 src/dashboard.py` after pipeline.py.
"""

import csv
import html as htmllib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# ---------------------------------------------------------------- CSS / JS --
# dataviz reference palette (validated); plain strings so braces stay literal.

CSS = """
:root {
  --surface:#f6f5f2; --card:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --ink3:#8a887f;
  --grid:#e8e7e3; --line:#dddbd4;
  --s1:#2a78d6; --s1l:#86b6ef; --s1xl:#cde2fb;
  --crit:#d03b3b; --crit-soft:rgba(208,59,59,.10);
  --good:#0ca30c; --good-soft:rgba(12,163,12,.10);
  --amber:#eda100; --shadow:0 1px 2px rgba(0,0,0,.05), 0 4px 16px rgba(0,0,0,.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface:#121211; --card:#1d1d1c; --ink:#f4f3ef; --ink2:#c3c2b7; --ink3:#8a887f;
    --grid:#34332f; --line:#3c3b36;
    --s1:#3987e5; --s1l:#1c5cab; --s1xl:#104281;
    --crit:#e66767; --crit-soft:rgba(230,103,103,.14);
    --good:#2fbf2f; --good-soft:rgba(47,191,47,.12);
    --amber:#c98500; --shadow:0 1px 2px rgba(0,0,0,.4);
  }
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:var(--surface); color:var(--ink);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Inter",sans-serif;
  -webkit-font-smoothing:antialiased; }
.container { max-width:1100px; margin:0 auto; padding:0 24px 64px; }

header.site { position:sticky; top:0; z-index:40; background:var(--surface);
  border-bottom:1px solid var(--grid); margin-bottom:28px; }
.site-inner { max-width:1100px; margin:0 auto; padding:18px 24px 0; }
.brand { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
.brand h1 { font-size:19px; margin:0; letter-spacing:-.01em; }
.brand .tag { color:var(--ink3); font-size:12.5px; }
nav.tabs { display:flex; gap:4px; margin-top:14px; overflow-x:auto; }
nav.tabs button { appearance:none; border:0; background:none; color:var(--ink2);
  font:600 13.5px/1 inherit; padding:10px 14px 12px; cursor:pointer;
  border-bottom:2px solid transparent; white-space:nowrap; border-radius:8px 8px 0 0; }
nav.tabs button:hover { color:var(--ink); background:var(--card); }
nav.tabs button.active { color:var(--s1); border-bottom-color:var(--s1); }

section.tab { display:none; animation:fade .18s ease; }
section.tab.active { display:block; }
@keyframes fade { from { transform:translateY(4px);} to { transform:none;} }

.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-bottom:22px; }
.kpi { background:var(--card); border:1px solid var(--grid); border-radius:14px;
  padding:16px 18px 14px; box-shadow:var(--shadow); }
.kpi .v { font-size:28px; font-weight:700; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }
.kpi .l { color:var(--ink2); font-size:12.5px; margin-top:2px; }
.kpi .d { font-size:12px; color:var(--ink3); margin-top:6px; }
.kpi.bad .v { color:var(--crit); } .kpi.good .v { color:var(--good); }

.card { background:var(--card); border:1px solid var(--grid); border-radius:14px;
  box-shadow:var(--shadow); padding:20px 22px; margin-bottom:18px; }
.card h2 { font-size:15.5px; margin:0 0 2px; letter-spacing:-.01em; }
.card .sub { color:var(--ink2); font-size:12.5px; margin:0 0 14px; }
.card .note { color:var(--ink2); font-size:12.5px; line-height:1.55; max-width:760px; }
.callout { border-left:3px solid var(--s1); padding:10px 14px; background:var(--s1xl);
  border-radius:0 10px 10px 0; font-size:13px; margin-top:14px; }
@media (prefers-color-scheme: dark){ .callout{ background:rgba(57,135,229,.12);} }
.callout.red { border-left-color:var(--crit); background:var(--crit-soft); }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:860px){ .grid2 { grid-template-columns:1fr; } }

.legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--ink2); margin:0 0 8px; }
.legend .it { display:flex; align-items:center; gap:6px; }
.sw { width:10px; height:10px; border-radius:3px; display:inline-block; }

.wrap { overflow-x:auto; }
svg { display:block; }
svg text { fill:var(--ink3); font-size:11px; font-family:inherit; }
svg .lbl { fill:var(--ink); font-weight:600; font-size:11.5px; }
svg .hover-dot { opacity:0; }
svg g[data-tip]:hover .hover-dot { opacity:1; }
svg g[data-tip]:hover rect.bar { filter:brightness(1.12); }

table { border-collapse:collapse; width:100%; font-size:12.5px; font-variant-numeric:tabular-nums; }
thead th { text-align:left; color:var(--ink3); font-weight:600; font-size:11px;
  text-transform:uppercase; letter-spacing:.03em; padding:8px 7px; cursor:pointer;
  border-bottom:1px solid var(--line); user-select:none; white-space:nowrap;
  position:sticky; top:0; background:var(--card); }
thead th:hover { color:var(--ink); }
thead th .arr { font-size:9px; opacity:.6; }
tbody td { padding:8px 7px; border-bottom:1px solid var(--grid); white-space:nowrap; }
tbody tr:hover td { background:color-mix(in srgb, var(--s1) 5%, transparent); }
tr.flag td { background:var(--crit-soft); }
tr.flag:hover td { background:color-mix(in srgb, var(--crit) 16%, transparent); }
tr.bonus td { background:var(--good-soft); }
.pill { display:inline-block; font-size:11px; font-weight:700; padding:2px 9px;
  border-radius:99px; letter-spacing:.03em; }
.pill.retrain { color:var(--crit); background:var(--crit-soft); border:1px solid var(--crit); }
.pill.bonus { color:var(--good); background:var(--good-soft); border:1px solid var(--good); }
.pill.t2 { color:var(--ink2); background:transparent; border:1px solid var(--line); }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { font-family:ui-monospace,Menlo,monospace; font-size:12px; padding:4px 10px;
  border:1px solid var(--line); border-radius:8px; background:var(--surface); }

#tip { position:fixed; z-index:99; pointer-events:none; background:var(--ink);
  color:var(--card); font-size:12px; line-height:1.4; padding:7px 10px; border-radius:8px;
  box-shadow:0 4px 14px rgba(0,0,0,.25); opacity:0; transition:opacity .08s; max-width:260px; }
#tip b { font-weight:650; }
footer { color:var(--ink3); font-size:12px; margin-top:28px; }
@media print { nav.tabs { display:none; } section.tab { display:block !important; } header.site{ position:static; } }
"""

JS = """
(function () {
  var tabs = document.querySelectorAll('nav.tabs button');
  var secs = document.querySelectorAll('section.tab');
  function activate(id) {
    tabs.forEach(function (b) { b.classList.toggle('active', b.dataset.tab === id); });
    secs.forEach(function (s) { s.classList.toggle('active', s.id === id); });
    if (history.replaceState) history.replaceState(null, '', '#' + id);
  }
  tabs.forEach(function (b) { b.addEventListener('click', function () { activate(b.dataset.tab); }); });
  var h = location.hash.replace('#', '');
  activate(document.getElementById(h) ? h : secs[0].id);

  // tooltip layer
  var tip = document.getElementById('tip');
  document.addEventListener('mouseover', function (e) {
    var g = e.target.closest('[data-tip]');
    if (!g) { tip.style.opacity = 0; return; }
    tip.innerHTML = g.getAttribute('data-tip');
    tip.style.opacity = 1;
  });
  document.addEventListener('mousemove', function (e) {
    if (tip.style.opacity == 1) {
      var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = x + 'px';
      tip.style.top = (e.clientY + 16) + 'px';
    }
  });

  // sortable tables
  document.querySelectorAll('table.sortable thead th').forEach(function (th, i) {
    th.addEventListener('click', function () {
      var tb = th.closest('table').tBodies[0];
      var rows = Array.from(tb.rows);
      var dir = th.dataset.dir === 'asc' ? -1 : 1;
      th.closest('tr').querySelectorAll('th').forEach(function (o) { delete o.dataset.dir; o.querySelector('.arr') && o.querySelector('.arr').remove(); });
      th.dataset.dir = dir === 1 ? 'asc' : 'desc';
      th.insertAdjacentHTML('beforeend', '<span class="arr"> ' + (dir === 1 ? '▲' : '▼') + '</span>');
      rows.sort(function (a, b) {
        var x = a.cells[i].dataset.v !== undefined ? a.cells[i].dataset.v : a.cells[i].textContent;
        var y = b.cells[i].dataset.v !== undefined ? b.cells[i].dataset.v : b.cells[i].textContent;
        var nx = parseFloat(x), ny = parseFloat(y);
        if (!isNaN(nx) && !isNaN(ny)) return (nx - ny) * dir;
        return String(x).localeCompare(String(y)) * dir;
      });
      rows.forEach(function (r) { tb.appendChild(r); });
    });
  });
})();
"""


# ------------------------------------------------------------- SVG helpers --

def esc(s):
    return htmllib.escape(str(s), quote=True)


def yaxis(lo, hi, steps, pad_t, ih, w, pad_l, fmt=lambda v: f"{v:g}"):
    out = ""
    for g in steps:
        y = pad_t + (hi - g) / (hi - lo) * ih
        out += (f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-10}" y2="{y:.1f}" stroke="var(--grid)"/>'
                f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end">{fmt(g)}</text>')
    return out


def svg_line(months, values, w=1020, h=240):
    lo, hi = 2.5, 4.2
    pad_l, pad_b, pad_t = 44, 28, 12
    iw, ih = w - pad_l - 10, h - pad_b - pad_t
    pts = [(pad_l + i * iw / (len(values) - 1),
            pad_t + (hi - v) / (hi - lo) * ih, v, months[i]) for i, v in enumerate(values)]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y, *_ in pts)
    area = path + f" L{pts[-1][0]:.1f},{pad_t+ih} L{pts[0][0]:.1f},{pad_t+ih} Z"
    grid = yaxis(lo, hi, (2.5, 3.0, 3.5, 4.0), pad_t, ih, w, pad_l)
    ticks = "".join(f'<text x="{pts[i][0]:.1f}" y="{h-8}" text-anchor="middle">{months[i][2:].replace("-", "·")}</text>'
                    for i in range(0, len(months), 2))
    lowest = min(pts, key=lambda p: p[2])
    hover = "".join(
        f'<g data-tip="<b>{m}</b><br>CSAT {v}">'
        f'<rect x="{x-iw/len(pts)/2:.1f}" y="{pad_t}" width="{iw/len(pts):.1f}" height="{ih}" fill="transparent"/>'
        f'<circle class="hover-dot" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--s1)"/></g>'
        for x, y, v, m in pts)
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly CSAT">{grid}'
            f'<path d="{area}" fill="var(--s1)" opacity="0.07"/>'
            f'<path d="{path}" fill="none" stroke="var(--s1)" stroke-width="2.25" stroke-linejoin="round"/>'
            f'<circle cx="{lowest[0]:.1f}" cy="{lowest[1]:.1f}" r="4.5" fill="var(--crit)"/>'
            f'<text class="lbl" x="{lowest[0]:.1f}" y="{lowest[1]-12:.1f}" text-anchor="middle">{lowest[3]} · {lowest[2]}</text>'
            f'{hover}{ticks}</svg>')


def svg_stacked(months, vols, shares, w=1020, h=250):
    pad_l, pad_b, pad_t = 44, 28, 14
    iw, ih = w - pad_l - 10, h - pad_b - pad_t
    vmax = max(vols) * 1.05
    bw = iw / len(vols) - 4
    bars, ticks = "", ""
    for i, (v, s) in enumerate(zip(vols, shares)):
        x = pad_l + i * iw / len(vols)
        bh = v / vmax * ih
        cb = bh * s / 100
        cb_n = round(v * s / 100)
        bars += (f'<g data-tip="<b>{months[i]}</b><br>{v} tickets<br>{cb_n} Charging &amp; Battery ({s}%)">'
                 f'<rect class="bar" x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{bw:.1f}" height="{max(0,bh-cb-1):.1f}" fill="var(--s1l)" rx="3"/>'
                 f'<rect class="bar" x="{x:.1f}" y="{pad_t+ih-cb:.1f}" width="{bw:.1f}" height="{cb:.1f}" fill="var(--crit)" rx="2"/></g>')
        if i % 2 == 0:
            ticks += f'<text x="{x+bw/2:.1f}" y="{h-8}" text-anchor="middle">{months[i][2:].replace("-", "·")}</text>'
    grid = yaxis(0, vmax, (0, 400, 800, 1200), pad_t, ih, w, pad_l, lambda v: f"{int(v)}")
    return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly ticket volume">{grid}{bars}{ticks}</svg>'


def svg_lots(lots, baseline, w=1020, h=280):
    lots = [l for l in lots if l["orders"] >= 10]
    pad_l, pad_b, pad_t = 44, 64, 16
    iw, ih = w - pad_l - 10, h - pad_b - pad_t
    vmax = max(l["tickets_per_order"] for l in lots) * 1.08
    bw = iw / len(lots) - 2.5
    out = yaxis(0, vmax, (0, 0.25, 0.5, 0.75, 1.0), pad_t, ih, w, pad_l)
    yb = pad_t + (vmax - baseline) / vmax * ih
    out += (f'<line x1="{pad_l}" y1="{yb:.1f}" x2="{w-10}" y2="{yb:.1f}" stroke="var(--ink3)" '
            f'stroke-dasharray="4 4"/><text x="{w-12}" y="{yb-5:.1f}" text-anchor="end">baseline {baseline}</text>')
    for i, l in enumerate(lots):
        x = pad_l + i * iw / len(lots)
        bh = l["tickets_per_order"] / vmax * ih
        col = "var(--crit)" if l["bad"] else "var(--s1l)"
        tag = " · <b>festive lot</b>" if l["bad"] else ""
        out += (f'<g data-tip="<b>{l["lot"]}</b>{tag}<br>{l["tickets"]} tickets / {l["orders"]} orders'
                f'<br>{l["tickets_per_order"]} tickets per order">'
                f'<rect class="bar" x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}" rx="3"/></g>')
        if i % 4 == 0 or (l["bad"] and i % 2 == 0):
            out += (f'<text x="{x+bw/2:.1f}" y="{h-48}" text-anchor="end" '
                    f'transform="rotate(-45 {x+bw/2:.1f} {h-48})">{l["lot"][4:]}</text>')
    return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Tickets per order by lot">{out}</svg>'


def svg_replacements(by_month, w=1020, h=220):
    months = sorted(by_month)
    vals = [by_month[m] for m in months]
    pad_l, pad_b, pad_t = 44, 28, 14
    iw, ih = w - pad_l - 10, h - pad_b - pad_t
    vmax = max(vals) * 1.1
    bw = iw / len(vals) - 4
    out = yaxis(0, vmax, (0, 100, 200, 300), pad_t, ih, w, pad_l, lambda v: f"{int(v)}")
    for i, (m, v) in enumerate(zip(months, vals)):
        x = pad_l + i * iw / len(vals)
        bh = v / vmax * ih
        hot = "2025-12" <= m <= "2026-04"
        out += (f'<g data-tip="<b>{m}</b><br>{v} replacements">'
                f'<rect class="bar" x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'fill="{"var(--crit)" if hot else "var(--s1l)"}" rx="3"/></g>')
        if i % 2 == 0:
            out += f'<text x="{x+bw/2:.1f}" y="{h-8}" text-anchor="middle">{m[2:].replace("-", "·")}</text>'
    return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Replacements per month">{out}</svg>'


# ------------------------------------------------------------------ tables --

AGENT_COLS = [("agent_id", "ID"), ("name", "Name"), ("team", "Team"),
              ("site", "Site"), ("shift", "Shift"), ("tickets", "Tickets"),
              ("csat_raw", "CSAT raw"), ("csat_adj_residual", "vs expected"),
              ("median_handle_hrs", "Handle (h)"), ("breach_rate_pct", "FR breach %"),
              ("repeat_rate_pct", "Repeat %")]


def agent_table(agents, tid):
    head = "".join(f"<th>{lbl}</th>" for _, lbl in AGENT_COLS)
    body = ""
    for a in agents:
        if a["flag_retrain"] == "Y":
            cls, pill = ' class="flag"', '<span class="pill retrain">retrain</span>'
        elif a.get("flag_top5_bonus") == "Y":
            cls, pill = ' class="bonus"', '<span class="pill bonus">bonus ★</span>'
        else:
            cls, pill = "", ""
        cells = ""
        for key, _ in AGENT_COLS:
            if key == "name":
                cells += f"<td>{esc(a[key])} {pill}</td>"
            elif key == "csat_adj_residual":
                v, ci = a[key], a["adj_ci95"]
                col = "var(--crit)" if v and float(v) < -0.15 else ("var(--good)" if v and float(v) > 0.15 else "inherit")
                cells += f'<td data-v="{v}" style="color:{col};font-weight:600">{"+" if v and float(v)>0 else ""}{v} <span style="color:var(--ink3);font-weight:400">± {ci}</span></td>'
            else:
                cells += f"<td>{esc(a[key])}</td>"
        body += f"<tr{cls}>{cells}</tr>"
    return f'<div class="wrap"><table class="sortable" id="{tid}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def inr_l(v):
    return f"₹{v/100000:.1f}L"


# -------------------------------------------------------------------- page --

def main():
    F = json.load(open(OUT / "findings.json"))
    agents = list(csv.DictReader(open(OUT / "agent_scorecard.csv")))
    m = F["monthly"]
    wave, rep, rota = F["defect_wave_cost_inr"], F["repeat_contacts"], F["rota_check"]
    csat_now = [v for v in m["csat"] if v][-1]
    trough = min(v for v in m["csat"] if v)
    t1 = [a for a in agents if a["tier"] == "1"]
    t2 = [a for a in agents if a["tier"] == "2"]
    flagged_names = ", ".join(f'{a["name"]} ({a["agent_id"]})' for a in agents if a["flag_retrain"] == "Y")
    bonus_names = ", ".join(f'{a["name"]}' for a in agents if a.get("flag_top5_bonus") == "Y")
    fl, pe = rota["flagged"], rota["peer_chat_t1"]

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vireo Support — CSAT &amp; Agent Scorecard</title><style>{CSS}</style></head><body>
<div id="tip"></div>
<header class="site"><div class="site-inner">
  <div class="brand"><h1>Vireo Support</h1>
  <span class="tag">Jan 2025 – Jun 2026 · {rep['resolved']:,} resolved tickets · policy v3.2 cost standards</span></div>
  <nav class="tabs">
    <button data-tab="overview">Overview</button>
    <button data-tab="rootcause">Root cause</button>
    <button data-tab="agents">Agents</button>
    <button data-tab="money">Money</button>
  </nav>
</div></header>
<div class="container">

<section class="tab" id="overview">
  <div class="kpis">
    <div class="kpi bad"><div class="v">{trough}</div><div class="l">CSAT trough — Feb 2026</div><div class="d">now {csat_now}, recovering</div></div>
    <div class="kpi"><div class="v">{inr_l(wave['total'])}</div><div class="l">direct cost of 3 festive Pulse 2 lots</div><div class="d">{wave['tickets']:,} tickets traced via lot codes</div></div>
    <div class="kpi"><div class="v">{rep['rate_pct']}%</div><div class="l">repeat-contact rate (30-day)</div><div class="d">{inr_l(rep['cost_18mo'])} re-handling over 18 mo</div></div>
    <div class="kpi"><div class="v">{len(F['flagged_for_retraining'])}<span style="font-size:16px;color:var(--ink3)"> / 44</span></div><div class="l">agents genuinely below expectation</div><div class="d">not 10 — after ticket-mix adjustment</div></div>
  </div>

  <div class="card">
    <h2>Monthly CSAT</h2>
    <p class="sub">Surveyed tickets only — blank scores excluded per policy §8 (~44% response rate)</p>
    {svg_line(m['months'], m['csat'])}
    <div class="callout red"><b>The slide is a product story, not a people story.</b>
    The fall from Nov 2025 tracks the Pulse 2 festive production lots — see the Root cause tab.</div>
  </div>

  <div class="card">
    <h2>Ticket volume, with Charging &amp; Battery share</h2>
    <p class="sub">Charging &amp; Battery went from ~6% of tickets to 20% at the peak — and it is the lowest-CSAT category (2.73)</p>
    <div class="legend"><span class="it"><span class="sw" style="background:var(--s1l)"></span>all other tickets</span>
    <span class="it"><span class="sw" style="background:var(--crit)"></span>Charging &amp; Battery</span></div>
    {svg_stacked(m['months'], m['volume'], m['charging_share_pct'])}
  </div>
</section>

<section class="tab" id="rootcause">
  <div class="card">
    <h2>Pulse 2 — tickets per order sold, by manufacturing lot</h2>
    <p class="sub">Joined tickets.csv → orders.csv on order_id; lot code is printed on the box ("ignore what you don't need" — we didn't)</p>
    <div class="legend"><span class="it"><span class="sw" style="background:var(--crit)"></span>festive lots (built Oct–Dec 2025)</span>
    <span class="it"><span class="sw" style="background:var(--s1l)"></span>all other lots</span></div>
    {svg_lots(F['lots'], F['lot_summary']['baseline_tickets_per_order'])}
    <div class="callout red">The three festive lots (PL2-2510x · 2511x · 2512x) generate ~2× the ticket
    rate of every other lot ever shipped — {F['lot_summary']['excess_tickets']} excess tickets.
    Most say the same thing: <i>"left earbud won't charge in the case."</i></div>
  </div>

  <div class="card">
    <h2>Replacements per month</h2>
    <p class="sub">Settles the Finance vs warehouse question: volume was up ~30%, replacements went up ~5× — defect rate, not festive volume</p>
    {svg_replacements(F['replacements_by_month'])}
  </div>

  <div class="card">
    <h2>What the wave cost, at policy v3.2 rates</h2>
    <div class="kpis" style="margin-top:12px">
      <div class="kpi"><div class="v">{inr_l(wave['replacements'])}</div><div class="l">replacement units (cost + ₹340 logistics)</div></div>
      <div class="kpi"><div class="v">{inr_l(wave['refunds'])}</div><div class="l">refunds on bad-lot tickets</div></div>
      <div class="kpi"><div class="v">{inr_l(wave['contacts'])}</div><div class="l">contact handling (₹210–520 / channel)</div></div>
      <div class="kpi"><div class="v">{inr_l(wave['sla_credits'])}</div><div class="l">SLA breach credits (₹350 each)</div></div>
    </div>
    <div class="callout"><b>{inr_l(wave['total'])} total — ~{inr_l(wave['total']/2)} per quarter while the wave ran.</b>
    It was visible in this data by mid-November 2025 and ran unflagged for four months. A weekly
    tickets-per-order-per-lot check (this chart) catches the next one in weeks.</div>
  </div>
</section>

<section class="tab" id="agents">
  <div class="card">
    <h2>Tier 1 — CSAT adjusted for the ticket mix each agent actually drew</h2>
    <p class="sub">"vs expected" compares each score with the average for the same category×channel cell, so an agent
    handed charging complaints all day isn't punished for the draw. Click any column to sort.</p>
    <div class="callout red" style="margin:0 0 14px"><b>Flagged for retraining:</b> {flagged_names} —
    below expectation even at the bottom of their 95% CI, min 20 surveys.</div>
    <div class="callout" style="margin:0 0 14px"><b>Diwali bonus (top five, same basis):</b> {bonus_names}.</div>
    {agent_table(t1, 'tbl-t1')}
    <p class="note" style="margin-top:14px"><b>Ops' triage-rota objection, tested.</b> "The hardware rota gets the
    angriest customers by design." Checked three ways: the flagged four's queues are <b>no angrier</b> than their
    chat peers' ({fl['angry_queue_pct']}% vs {pe['angry_queue_pct']}% angry-language share); their deficit
    <b>persists on calm tickets only</b> ({fl['csat_resid_nonangry']:+} vs {pe['csat_resid_nonangry']:+}); and it
    <b>predates the defect wave</b> ({fl['csat_resid_prewave']:+} before Nov 2025). The flag reflects the person,
    not the queue.</p>
  </div>

  <div class="card">
    <h2>Tier 2 — Escalations &amp; Warranty <span class="pill t2">reported separately</span></h2>
    <p class="sub">Policy §6: Tier 2 handles multi-touch warranty work and "is not to be compared with Tier 1 on volume
    metrics." Their low raw CSAT is dominated by the defect wave — six of a naive "bottom ten" would have been these agents.</p>
    {agent_table(t2, 'tbl-t2')}
  </div>
</section>

<section class="tab" id="money">
  <div class="kpis">
    <div class="kpi"><div class="v">{inr_l(wave['total'])}</div><div class="l">festive-lot defect wave</div><div class="d">one-off, traced via lot codes</div></div>
    <div class="kpi"><div class="v">{inr_l(rep['cost_18mo'])}</div><div class="l">repeat-contact re-handling / 18 mo</div><div class="d">{rep['repeat']:,} repeats · {rep['rate_pct']}% of resolved</div></div>
    <div class="kpi"><div class="v">{inr_l(F['sla']['credits_inr'])}</div><div class="l">SLA breach credits / 18 mo</div><div class="d">{F['sla']['breaches']:,} breaches × ₹350</div></div>
    <div class="kpi"><div class="v">{inr_l(F['transfers']['cost_inr'])}</div><div class="l">internal transfers / 18 mo</div><div class="d">{F['transfers']['count']:,} hand-offs × ₹305</div></div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Intake bot mis-tagging feeds the transfer bill</h2>
      <p class="note">{F['other_total']:,} tickets (15%) land in category "Other" and get routed by guesswork.
      The free-text classifier re-files {sum(F['other_reclassified'].values()):,} of them automatically
      (77.8% agreement with agent-corrected tags; abstains rather than guesses).
      Biggest buckets: Delivery &amp; Shipping ({F['other_reclassified'].get('Delivery & Shipping', 0)}),
      Billing ({F['other_reclassified'].get('Billing & Payments', 0)}),
      Connectivity ({F['other_reclassified'].get('Connectivity', 0)}).
      Transferred tickets score ~0.4 CSAT lower.</p>
    </div>
    <div class="card">
      <h2>Policy violations found on the way</h2>
      <p class="note">Six tickets gave the customer <b>both a refund and a replacement</b> — policy §5 says
      same-day escalation to Team Lead and Finance:</p>
      <div class="chips">{''.join(f'<span class="chip">{t}</span>' for t in F['double_dip_tickets'])}</div>
      <p class="note" style="margin-top:10px">Also: SLA breach credits are charged to the <i>resolving</i> agent
      even when the delay happened before a transfer (§3) — fix before managing anyone on that number.</p>
    </div>
  </div>

  <div class="card">
    <h2>Where the Q3 ₹4L training budget should go</h2>
    <p class="note">① The four flagged chat agents — real coaching at ₹1L a head, not a spray across ten.
    ② First-contact-resolution coaching for chat: {rep['rate_pct']}% of resolved tickets return within 30 days
    ({inr_l(rep['cost_18mo'] * 2 / 3)} a year in re-handling).
    ③ Nothing to Tier 2 on this evidence — their numbers are the defect wave, not a skills gap.</p>
  </div>

  <footer>Generated by <span class="mono">src/dashboard.py</span> from <span class="mono">output/findings.json</span> ·
  all rates from support-policy.pdf v3.2 · CSAT blanks excluded per §8 · legacy timestamps corrected +5:30 per §9</footer>
</section>

</div><script>{JS}</script></body></html>"""
    (OUT / "dashboard.html").write_text(page)
    print(f"Wrote {OUT/'dashboard.html'} ({len(page)//1024} KB)")


if __name__ == "__main__":
    main()
