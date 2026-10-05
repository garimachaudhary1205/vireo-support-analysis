"""Generate output/dashboard.html from findings.json + agent_scorecard.csv.

Branded, client-facing single file: hero header with logo, splash loader,
tab-switch loaders, count-up KPIs, tabbed layout, inline SVG charts, hover
tooltips, sortable tables, light/dark. No CDN, no deps.
`python3 src/dashboard.py` after pipeline.py.
"""

import csv
import html as htmllib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# Brand: deep pine + teal, red reserved for the defect/retrain story.
CSS = """
:root {
  --surface:#0b1411; --card:#13211b; --ink:#eef5f1; --ink2:#b1c4ba; --ink3:#7e928a;
  --grid:#223129; --line:#2c3e34;
  --acc:#2fc4a4; --acc-deep:#07241f; --acc-mid:#0b5c4b; --acc-soft:rgba(47,196,164,.13); --acc-ink:#4bd7b6;
  --s1:#2fc4a4; --s1l:#2e9a7e; --s1xl:rgba(47,196,164,.09);
  --crit:#e05d5d; --crit-soft:rgba(224,93,93,.13);
  --good:#3fd068; --good-soft:rgba(63,208,104,.13);
  --shadow:0 1px 2px rgba(0,0,0,.35), 0 8px 24px rgba(0,0,0,.25);
  --shadow-lg:0 2px 6px rgba(0,0,0,.45), 0 18px 44px rgba(0,0,0,.4);
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:var(--surface); color:var(--ink);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Inter",sans-serif;
  -webkit-font-smoothing:antialiased; }
.container { max-width:1120px; margin:0 auto; padding:0 28px 72px; }

/* ---- splash loader ---- */
#splash { position:fixed; inset:0; z-index:200; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:20px; color:#eafff9;
  background:radial-gradient(1200px 700px at 20% -10%, #11624f 0%, #07241f 55%, #051a16 100%);
  transition:opacity .5s ease, visibility .5s; }
#splash.done { opacity:0; visibility:hidden; }
#splash .sp-logo { animation:pulse 1.6s ease-in-out infinite; }
#splash .sp-name { font-size:15px; font-weight:700; letter-spacing:.22em; }
#splash .sp-sub { font-size:11.5px; color:rgba(234,255,249,.6); letter-spacing:.08em; margin-top:-14px; }
#splash .sp-bar { width:190px; height:3px; border-radius:99px; overflow:hidden; background:rgba(255,255,255,.16); }
#splash .sp-bar i { display:block; height:100%; width:42%; border-radius:99px; background:#5fe0c2; animation:slide 1.1s ease-in-out infinite; }
@keyframes pulse { 0%,100%{ transform:scale(1); opacity:1;} 50%{ transform:scale(1.06); opacity:.85;} }
@keyframes slide { 0%{ transform:translateX(-110%);} 100%{ transform:translateX(560%);} }

/* ---- top progress bar (tab switches) ---- */
#loadbar { position:fixed; top:0; left:0; height:3px; width:0; z-index:150;
  background:linear-gradient(90deg, var(--acc), #5fe0c2); border-radius:0 99px 99px 0;
  opacity:0; transition:width .28s ease, opacity .25s ease .15s; }

/* ---- hero ---- */
.hero { color:#f2fffb; padding:34px 0 86px;
  background:radial-gradient(1100px 520px at 12% -18%, #16745c 0%, transparent 62%),
             linear-gradient(180deg, #0a3a2f 0%, #07241f 58%, #0b1411 100%); }
.hero-inner { max-width:1120px; margin:0 auto; padding:0 28px; }
.hero-top { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; flex-wrap:wrap; }
.logo { display:flex; align-items:center; gap:13px; }
.logo .word { font-size:17px; font-weight:800; letter-spacing:.16em; }
.logo .word span { font-weight:400; color:rgba(242,255,251,.65); }
.logo .prod { font-size:11.5px; color:#5fe0c2; letter-spacing:.1em; font-weight:600; margin-top:2px; text-transform:uppercase; }
.hero-meta { text-align:right; font-size:12px; color:rgba(242,255,251,.72); line-height:1.7; }
.hero-meta b { color:#fff; font-weight:600; }
.hero h1 { font-size:27px; letter-spacing:-.02em; margin:34px 0 10px; max-width:680px; line-height:1.25; }
.hero .lede { color:rgba(242,255,251,.78); font-size:13.5px; max-width:620px; margin:0 0 20px; }
.hero .chips { display:flex; gap:8px; flex-wrap:wrap; }
.hero .chip { font-size:11.5px; font-weight:600; padding:5px 12px; border-radius:99px;
  background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.16); color:rgba(242,255,251,.9); }

/* ---- tab bar ---- */
.tabbar { position:sticky; top:0; z-index:60; margin-top:-54px;
  background:transparent; }
.tabbar.stuck { background:color-mix(in srgb, var(--surface) 86%, transparent);
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px);
  border-bottom:1px solid var(--grid); margin-top:0; }
.tabbar-inner { max-width:1120px; margin:0 auto; padding:10px 28px; }
nav.tabs { display:inline-flex; gap:4px; padding:5px; border-radius:14px;
  background:var(--card); box-shadow:var(--shadow-lg); border:1px solid var(--grid); }
nav.tabs button { appearance:none; border:0; background:none; color:var(--ink2);
  font:600 13px/1 inherit; padding:9px 18px; cursor:pointer; border-radius:10px;
  white-space:nowrap; transition:background .15s, color .15s; display:flex; align-items:center; gap:7px; }
nav.tabs button .dot { width:6px; height:6px; border-radius:99px; background:var(--ink3); opacity:.5; }
nav.tabs button:hover { color:var(--ink); background:var(--surface); }
nav.tabs button.active { color:#fff; background:linear-gradient(135deg, var(--acc), var(--acc-mid)); box-shadow:0 2px 8px rgba(12,140,114,.35); }
nav.tabs button.active .dot { background:#5fe0c2; opacity:1; }

section.tab { display:none; padding-top:26px; }
section.tab.active { display:block; animation:rise .25s ease; }
@keyframes rise { from { transform:translateY(6px); opacity:.6;} to { transform:none; opacity:1;} }

/* ---- shimmer while a tab "loads" ---- */
.tab.shimmer .card > *, .tab.shimmer .kpi > *, .tab.shimmer .grid2 > * { opacity:.3; }
.tab.shimmer .card, .tab.shimmer .kpi { position:relative; overflow:hidden; }
.tab.shimmer .card::after, .tab.shimmer .kpi::after { content:""; position:absolute; inset:0;
  background:linear-gradient(100deg, transparent 32%, color-mix(in srgb, var(--ink) 7%, transparent) 50%, transparent 68%);
  animation:sheen .9s linear infinite; }
@keyframes sheen { 0%{ transform:translateX(-100%);} 100%{ transform:translateX(100%);} }
@media (prefers-reduced-motion: reduce) {
  #splash, #splash .sp-logo, #splash .sp-bar i { animation:none !important; transition:none; }
  section.tab.active { animation:none; } .tab.shimmer .card::after { animation:none; }
}

/* ---- KPI cards ---- */
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:16px; margin-bottom:26px; }
.kpi { background:var(--card); border:1px solid var(--grid); border-radius:16px;
  padding:18px 20px 16px; box-shadow:var(--shadow); transition:transform .15s ease, box-shadow .15s ease; }
.kpi:hover { transform:translateY(-2px); box-shadow:var(--shadow-lg); }
.kpi .ic { width:32px; height:32px; border-radius:9px; display:flex; align-items:center;
  justify-content:center; font-size:15px; font-weight:700; margin-bottom:12px;
  background:var(--acc-soft); color:var(--acc-ink); }
.kpi.bad .ic { background:var(--crit-soft); color:var(--crit); }
.kpi.good .ic { background:var(--good-soft); color:var(--good); }
.kpi .v { font-size:31px; font-weight:750; letter-spacing:-.03em; font-variant-numeric:tabular-nums; line-height:1.1; }
.kpi .v .den { font-size:16px; color:var(--ink3); font-weight:600; }
.kpi.bad .v { color:var(--crit); }
.kpi .l { color:var(--ink2); font-size:12.5px; margin-top:5px; font-weight:500; }
.kpi .d { font-size:11.5px; color:var(--ink3); margin-top:4px; }

/* ---- cards ---- */
.card { background:var(--card); border:1px solid var(--grid); border-radius:18px;
  box-shadow:var(--shadow); padding:26px 28px; margin-bottom:22px; }
.eyebrow { font-size:10.5px; font-weight:800; letter-spacing:.14em; color:var(--acc-ink);
  text-transform:uppercase; margin-bottom:6px; }
.card h2 { font-size:17px; margin:0 0 3px; letter-spacing:-.015em; }
.card .sub { color:var(--ink2); font-size:12.5px; margin:0 0 18px; }
.card .note { color:var(--ink2); font-size:12.5px; line-height:1.6; max-width:780px; }
.callout { border-left:3px solid var(--acc); padding:12px 16px; background:var(--acc-soft);
  border-radius:0 12px 12px 0; font-size:13px; margin-top:16px; line-height:1.55; }
.callout.red { border-left-color:var(--crit); background:var(--crit-soft); }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:22px; }
@media (max-width:880px){ .grid2 { grid-template-columns:1fr; } .hero-meta{ text-align:left; } }

.legend { display:flex; gap:18px; flex-wrap:wrap; font-size:12px; color:var(--ink2); margin:0 0 10px; }
.legend .it { display:flex; align-items:center; gap:7px; }
.sw { width:10px; height:10px; border-radius:3px; display:inline-block; }

.wrap { overflow-x:auto; }
svg.chart { display:block; }
svg.chart text { fill:var(--ink3); font-size:11px; font-family:inherit; }
svg.chart .lbl { fill:var(--ink); font-weight:600; font-size:11.5px; }
svg.chart .hover-dot { opacity:0; }
svg.chart g[data-tip]:hover .hover-dot { opacity:1; }
svg.chart g[data-tip]:hover rect.bar { filter:brightness(1.12); }

/* ---- tables ---- */
table { border-collapse:collapse; width:100%; font-size:12.5px; font-variant-numeric:tabular-nums; }
thead th { text-align:left; color:var(--ink3); font-weight:700; font-size:10.5px;
  text-transform:uppercase; letter-spacing:.06em; padding:9px 8px; cursor:pointer;
  border-bottom:1px solid var(--line); user-select:none; white-space:nowrap;
  position:sticky; top:0; background:var(--card); }
thead th:hover { color:var(--acc-ink); }
thead th .arr { font-size:9px; opacity:.7; }
tbody td { padding:9px 8px; border-bottom:1px solid var(--grid); white-space:nowrap; }
tbody tr:hover td { background:color-mix(in srgb, var(--acc) 5%, transparent); }
tr.flag td { background:var(--crit-soft); }
tr.flag:hover td { background:color-mix(in srgb, var(--crit) 15%, transparent); }
tr.bonus td { background:var(--good-soft); }
.pill { display:inline-block; font-size:10.5px; font-weight:800; padding:2.5px 10px;
  border-radius:99px; letter-spacing:.05em; text-transform:uppercase; }
.pill.retrain { color:#fff; background:var(--crit); }
.pill.bonus { color:#fff; background:var(--good); }
.pill.t2 { color:var(--ink2); background:transparent; border:1px solid var(--line); text-transform:none; letter-spacing:0; font-weight:600; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
.chiprow { display:flex; flex-wrap:wrap; gap:8px; }
.tchip { font-family:ui-monospace,Menlo,monospace; font-size:12px; padding:5px 11px;
  border:1px solid var(--line); border-radius:9px; background:var(--surface); }

#tip { position:fixed; z-index:110; pointer-events:none; background:var(--acc-deep);
  color:#eafff9; font-size:12px; line-height:1.45; padding:8px 11px; border-radius:9px;
  box-shadow:0 6px 20px rgba(0,0,0,.3); opacity:0; transition:opacity .08s; max-width:270px;
  border:1px solid rgba(95,224,194,.25); }
#tip b { font-weight:650; color:#5fe0c2; }
footer.site { color:var(--ink3); font-size:12px; margin-top:34px; display:flex;
  justify-content:space-between; gap:14px; flex-wrap:wrap; align-items:center;
  border-top:1px solid var(--grid); padding-top:18px; }
footer.site .fbrand { display:flex; align-items:center; gap:8px; font-weight:600; color:var(--ink2); }
@media print {
  :root { --surface:#ffffff; --card:#ffffff; --ink:#0c1b17; --ink2:#48584f; --ink3:#7d8c85;
    --grid:#e3eae7; --line:#d5dfdb; --acc-soft:#dcf2ec; --acc-ink:#0a6e5a;
    --s1:#0f9478; --s1l:#8fd4c3; --crit:#d03b3b; --shadow:none; --shadow-lg:none; }
  nav.tabs,#splash,#loadbar { display:none; } section.tab { display:block !important; }
  .tabbar { position:static; } .hero { padding-bottom:30px; } }
"""

JS = """
(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // splash
  var splash = document.getElementById('splash');
  function dismiss() { splash.classList.add('done'); }
  if (reduced) { dismiss(); }
  else {
    window.addEventListener('load', function () { setTimeout(dismiss, 650); });
    document.addEventListener('DOMContentLoaded', function () { setTimeout(dismiss, 900); });
    setTimeout(dismiss, 2200); /* hard cap */
  }

  // tabs + loaders
  var tabs = document.querySelectorAll('nav.tabs button');
  var secs = document.querySelectorAll('section.tab');
  var loadbar = document.getElementById('loadbar');
  var counted = {};

  function countUp(sec) {
    if (counted[sec.id] || reduced) { counted[sec.id] = true; return; }
    counted[sec.id] = true;
    sec.querySelectorAll('.num[data-cv]').forEach(function (el) {
      var target = parseFloat(el.dataset.cv), dec = +(el.dataset.dec || 0);
      var pre = el.dataset.pre || '', suf = el.dataset.suf || '';
      var t0 = performance.now(), dur = 850;
      var final = pre + target.toFixed(dec) + suf;
      (function frame(t) {
        var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        el.textContent = p < 1 ? pre + (target * e).toFixed(dec) + suf : final;
        if (p < 1) requestAnimationFrame(frame);
      })(t0);
      setTimeout(function () { el.textContent = final; }, dur + 120);
    });
  }

  function activate(id, withLoader) {
    tabs.forEach(function (b) { b.classList.toggle('active', b.dataset.tab === id); });
    secs.forEach(function (s) { s.classList.toggle('active', s.id === id); });
    if (history.replaceState) history.replaceState(null, '', '#' + id);
    var sec = document.getElementById(id);
    if (withLoader && !reduced) {
      loadbar.style.opacity = 1; loadbar.style.width = '65%';
      sec.classList.add('shimmer');
      setTimeout(function () { loadbar.style.width = '100%'; }, 180);
      setTimeout(function () {
        sec.classList.remove('shimmer');
        loadbar.style.opacity = 0;
        setTimeout(function () { loadbar.style.width = '0'; }, 260);
        countUp(sec);
      }, 420);
    } else { countUp(sec); }
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
  }
  tabs.forEach(function (b) { b.addEventListener('click', function () { activate(b.dataset.tab, true); }); });
  var h = location.hash.replace('#', '');
  activate(document.getElementById(h) ? h : secs[0].id, false);

  // sticky tab bar style flip
  var tabbar = document.querySelector('.tabbar');
  var onScroll = function () { tabbar.classList.toggle('stuck', window.scrollY > 170); };
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

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
      th.closest('tr').querySelectorAll('th').forEach(function (o) { delete o.dataset.dir; var a = o.querySelector('.arr'); if (a) a.remove(); });
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

# Logo: soundwave bars + flight swoosh. Swap this block for a real client
# logo (SVG or <img>) — the layout holds either way.
LOGO = """<svg width="{s}" height="{s}" viewBox="0 0 48 48" aria-label="Vireo logo">
<defs><linearGradient id="lg{u}" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#1cc39e"/><stop offset="1" stop-color="#0a5847"/></linearGradient></defs>
<rect width="48" height="48" rx="12" fill="url(#lg{u})"/>
<g stroke="#eafff9" stroke-width="3.4" stroke-linecap="round">
<line x1="12" y1="21" x2="12" y2="31"/><line x1="19.5" y1="15" x2="19.5" y2="37"/>
<line x1="27" y1="19" x2="27" y2="33"/><line x1="34.5" y1="24" x2="34.5" y2="28"/></g>
<path d="M9 11.5 q10 7 30 1.5" stroke="#5fe0c2" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>"""


def logo(size, uid):
    return LOGO.replace("{s}", str(size)).replace("{u}", uid)


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


def svg_line(months, values, w=1020, h=250):
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
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly CSAT">{grid}'
            f'<path d="{area}" fill="var(--s1)" opacity="0.08"/>'
            f'<path d="{path}" fill="none" stroke="var(--s1)" stroke-width="2.25" stroke-linejoin="round"/>'
            f'<circle cx="{lowest[0]:.1f}" cy="{lowest[1]:.1f}" r="4.5" fill="var(--crit)"/>'
            f'<text class="lbl" x="{lowest[0]:.1f}" y="{lowest[1]-12:.1f}" text-anchor="middle">{lowest[3]} · {lowest[2]}</text>'
            f'{hover}{ticks}</svg>')


def svg_stacked(months, vols, shares, w=1020, h=260):
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
    return f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Monthly ticket volume">{grid}{bars}{ticks}</svg>'


def svg_lots(lots, baseline, w=1020, h=290):
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
    return f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Tickets per order by lot">{out}</svg>'


def svg_replacements(by_month, w=1020, h=230):
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
    return f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Replacements per month">{out}</svg>'


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
            cls, pill = ' class="flag"', ' <span class="pill retrain">retrain</span>'
        elif a.get("flag_top5_bonus") == "Y":
            cls, pill = ' class="bonus"', ' <span class="pill bonus">bonus ★</span>'
        else:
            cls, pill = "", ""
        cells = ""
        for key, _ in AGENT_COLS:
            if key == "name":
                cells += f"<td>{esc(a[key])}{pill}</td>"
            elif key == "csat_adj_residual":
                v, ci = a[key], a["adj_ci95"]
                col = "var(--crit)" if v and float(v) < -0.15 else ("var(--good)" if v and float(v) > 0.15 else "inherit")
                cells += (f'<td data-v="{v}" style="color:{col};font-weight:600">'
                          f'{"+" if v and float(v) > 0 else ""}{v} <span style="color:var(--ink3);font-weight:400">± {ci}</span></td>')
            else:
                cells += f"<td>{esc(a[key])}</td>"
        body += f"<tr{cls}>{cells}</tr>"
    return (f'<div class="wrap"><table class="sortable" id="{tid}">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def inr_l(v):
    return f"₹{v/100000:.1f}L"


def kpi(value_html, label, detail, cls="", icon="●"):
    return (f'<div class="kpi {cls}"><div class="ic">{icon}</div>'
            f'<div class="v">{value_html}</div>'
            f'<div class="l">{label}</div><div class="d">{detail}</div></div>')


def num(cv, dec, pre="", suf=""):
    shown = f"{pre}{cv:.{dec}f}{suf}"
    return (f'<span class="num" data-cv="{round(cv, dec)}" data-dec="{dec}" data-pre="{pre}" '
            f'data-suf="{suf}">{shown}</span>')


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
    bonus_names = ", ".join(a["name"] for a in agents if a.get("flag_top5_bonus") == "Y")
    fl, pe = rota["flagged"], rota["peer_chat_t1"]
    favicon = ("data:image/svg+xml," + logo(48, "f").replace("#", "%23").replace("\n", "")
               .replace('"', "'"))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="{favicon}">
<title>Vireo Birdseye — Support Intelligence</title><style>{CSS}</style></head><body>

<div id="splash"><div class="sp-logo">{logo(64, "s")}</div>
<div class="sp-name">VIREO · BIRDSEYE</div><div class="sp-sub">SUPPORT INTELLIGENCE</div>
<div class="sp-bar"><i></i></div></div>
<div id="loadbar"></div><div id="tip"></div>

<header class="hero"><div class="hero-inner">
  <div class="hero-top">
    <div class="logo">{logo(42, "h")}
      <div><div class="word">VIREO <span>AUDIO</span></div>
      <div class="prod">Birdseye · Support Intelligence</div></div>
    </div>
    <div class="hero-meta">Prepared for <b>Priya Raman</b> · Head of Customer Experience<br>
    Data: Jan 2025 – Jun 2026 · Confidential · v1.0</div>
  </div>
  <h1>What moved CSAT — and where the ₹4L training budget should actually go</h1>
  <p class="lede">Agent scorecards adjusted for ticket mix, the root cause of the festive-season
  slide traced to three manufacturing lots, and every number costed at policy v3.2 rates.</p>
  <div class="chips"><span class="chip">{rep['resolved']:,} resolved tickets</span>
  <span class="chip">44 agents · 2 sites</span><span class="chip">18 months</span>
  <span class="chip">policy v3.2 cost standards</span></div>
</div></header>

<div class="tabbar"><div class="tabbar-inner">
  <nav class="tabs">
    <button data-tab="overview"><span class="dot"></span>Overview</button>
    <button data-tab="rootcause"><span class="dot"></span>Root cause</button>
    <button data-tab="agents"><span class="dot"></span>Agents</button>
    <button data-tab="money"><span class="dot"></span>Money</button>
  </nav>
</div></div>

<div class="container">

<section class="tab" id="overview">
  <div class="kpis">
    {kpi(num(trough, 2), "CSAT trough — Feb 2026", f"now {csat_now}, recovering", "bad", "▾")}
    {kpi(num(wave['total']/100000, 1, "₹", "L"), "direct cost of 3 festive Pulse 2 lots", f"{wave['tickets']:,} tickets traced via lot codes", "", "₹")}
    {kpi(num(rep['rate_pct'], 1, "", "%"), "repeat-contact rate (30-day)", f"{inr_l(rep['cost_18mo'])} re-handling over 18 mo", "", "⟳")}
    {kpi(num(4, 0) + '<span class="den"> / 44</span>', "agents genuinely below expectation", "not 10 — after ticket-mix adjustment", "good", "✓")}
  </div>

  <div class="card">
    <div class="eyebrow">Trend</div>
    <h2>Monthly CSAT</h2>
    <p class="sub">Surveyed tickets only — blank scores excluded per policy §8 (~44% response rate)</p>
    {svg_line(m['months'], m['csat'])}
    <div class="callout red"><b>The slide is a product story, not a people story.</b>
    The fall from Nov 2025 tracks the Pulse 2 festive production lots — see the Root cause tab.</div>
  </div>

  <div class="card">
    <div class="eyebrow">Mix</div>
    <h2>Ticket volume, with Charging &amp; Battery share</h2>
    <p class="sub">Charging &amp; Battery went from ~6% of tickets to 20% at the peak — and it is the lowest-CSAT category (2.73)</p>
    <div class="legend"><span class="it"><span class="sw" style="background:var(--s1l)"></span>all other tickets</span>
    <span class="it"><span class="sw" style="background:var(--crit)"></span>Charging &amp; Battery</span></div>
    {svg_stacked(m['months'], m['volume'], m['charging_share_pct'])}
  </div>
</section>

<section class="tab" id="rootcause">
  <div class="card">
    <div class="eyebrow">Root cause</div>
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
    <div class="eyebrow">Verification</div>
    <h2>Replacements per month</h2>
    <p class="sub">Settles the Finance vs warehouse question: volume was up ~30%, replacements went up ~5× — defect rate, not festive volume</p>
    {svg_replacements(F['replacements_by_month'])}
  </div>

  <div class="card">
    <div class="eyebrow">Impact</div>
    <h2>What the wave cost, at policy v3.2 rates</h2>
    <div class="kpis" style="margin-top:14px">
      {kpi(num(wave['replacements']/100000, 1, "₹", "L"), "replacement units", "unit cost + ₹340 logistics each", "", "₹")}
      {kpi(num(wave['refunds']/100000, 1, "₹", "L"), "refunds on bad-lot tickets", "as raised by agents", "", "₹")}
      {kpi(num(wave['contacts']/100000, 1, "₹", "L"), "contact handling", "₹210–520 per contact by channel", "", "₹")}
      {kpi(num(wave['sla_credits']/100000, 1, "₹", "L"), "SLA breach credits", "₹350 auto-credit per breach", "", "₹")}
    </div>
    <div class="callout"><b>{inr_l(wave['total'])} total — ~{inr_l(wave['total']/2)} per quarter while the wave ran.</b>
    It was visible in this data by mid-November 2025 and ran unflagged for four months. A weekly
    tickets-per-order-per-lot check (this chart) catches the next one in weeks.</div>
  </div>
</section>

<section class="tab" id="agents">
  <div class="card">
    <div class="eyebrow">People</div>
    <h2>Tier 1 — CSAT adjusted for the ticket mix each agent actually drew</h2>
    <p class="sub">"vs expected" compares each score with the average for the same category×channel cell, so an agent
    handed charging complaints all day isn't punished for the draw. Click any column to sort.</p>
    <div class="callout red" style="margin:0 0 12px"><b>Flagged for retraining:</b> {flagged_names} —
    below expectation even at the bottom of their 95% CI, min 20 surveys.</div>
    <div class="callout" style="margin:0 0 16px"><b>Diwali bonus (top five, same basis):</b> {bonus_names}.</div>
    {agent_table(t1, 'tbl-t1')}
    <p class="note" style="margin-top:16px"><b>Ops' triage-rota objection, tested.</b> "The hardware rota gets the
    angriest customers by design." Checked three ways: the flagged four's queues are <b>no angrier</b> than their
    chat peers' ({fl['angry_queue_pct']}% vs {pe['angry_queue_pct']}% angry-language share); their deficit
    <b>persists on calm tickets only</b> ({fl['csat_resid_nonangry']:+} vs {pe['csat_resid_nonangry']:+}); and it
    <b>predates the defect wave</b> ({fl['csat_resid_prewave']:+} before Nov 2025). The flag reflects the person,
    not the queue.</p>
  </div>

  <div class="card">
    <div class="eyebrow">People · Tier 2</div>
    <h2>Escalations &amp; Warranty <span class="pill t2">reported separately per policy §6</span></h2>
    <p class="sub">Tier 2 handles multi-touch warranty work and "is not to be compared with Tier 1 on volume
    metrics." Their low raw CSAT is dominated by the defect wave — six of a naive "bottom ten" would have been these agents.</p>
    {agent_table(t2, 'tbl-t2')}
  </div>
</section>

<section class="tab" id="money">
  <div class="kpis">
    {kpi(num(wave['total']/100000, 1, "₹", "L"), "festive-lot defect wave", "one-off, traced via lot codes", "bad", "₹")}
    {kpi(num(rep['cost_18mo']/100000, 1, "₹", "L"), "repeat-contact re-handling / 18 mo", f"{rep['repeat']:,} repeats · {rep['rate_pct']}% of resolved", "", "⟳")}
    {kpi(num(F['sla']['credits_inr']/100000, 1, "₹", "L"), "SLA breach credits / 18 mo", f"{F['sla']['breaches']:,} breaches × ₹350", "", "✕")}
    {kpi(num(F['transfers']['cost_inr']/100000, 1, "₹", "L"), "internal transfers / 18 mo", f"{F['transfers']['count']:,} hand-offs × ₹305", "", "⇄")}
  </div>

  <div class="grid2">
    <div class="card">
      <div class="eyebrow">Routing</div>
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
      <div class="eyebrow">Governance</div>
      <h2>Policy violations found on the way</h2>
      <p class="note">Six tickets gave the customer <b>both a refund and a replacement</b> — policy §5 says
      same-day escalation to Team Lead and Finance:</p>
      <div class="chiprow" style="margin-top:10px">{''.join(f'<span class="tchip">{t}</span>' for t in F['double_dip_tickets'])}</div>
      <p class="note" style="margin-top:12px">Also: SLA breach credits are charged to the <i>resolving</i> agent
      even when the delay happened before a transfer (§3) — fix before managing anyone on that number.</p>
    </div>
  </div>

  <div class="card">
    <div class="eyebrow">Recommendation</div>
    <h2>Where the Q3 ₹4L training budget should go</h2>
    <p class="note">① The four flagged chat agents — real coaching at ₹1L a head, not a spray across ten.
    ② First-contact-resolution coaching for chat: {rep['rate_pct']}% of resolved tickets return within 30 days
    ({inr_l(rep['cost_18mo'] * 2 / 3)} a year in re-handling).
    ③ Nothing to Tier 2 on this evidence — their numbers are the defect wave, not a skills gap.</p>
  </div>
</section>

<footer class="site">
  <div class="fbrand">{logo(20, "ft")} Birdseye · Support Intelligence for Vireo Audio</div>
  <div>Confidential</div>
</footer>

</div><script>{JS}</script></body></html>"""
    (OUT / "dashboard.html").write_text(page)
    print(f"Wrote {OUT/'dashboard.html'} ({len(page)//1024} KB)")


if __name__ == "__main__":
    main()
