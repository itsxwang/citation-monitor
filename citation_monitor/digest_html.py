"""Weekly digest — single-file HTML report (inline CSS + inline SVG sparkline,
no external assets, no JavaScript). Safe for GitHub Pages or email attach.
"""
from __future__ import annotations

import html
import math


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _sparkline(points: list) -> str:
    """points: list of floats (0-100). Returns inline SVG string."""
    if not points:
        return ""
    w, h, pad = 560, 90, 8
    n = len(points)
    if n == 1:
        x = y = None
    xs = [pad + i * (w - 2 * pad) / max(1, n - 1) for i in range(n)]
    ys = [h - pad - (v / 100.0) * (h - 2 * pad) for v in points]
    if n == 1:
        dot = f'<circle cx="{xs[0]:.1f}" cy="{ys[0]:.1f}" r="4" fill="#6d5dfc"/>'
        return (f'<svg viewBox="0 0 {w} {h}" class="spark">{dot}</svg>')
    pline = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#6d5dfc"/>'
                   for x, y in zip(xs, ys))
    labels = ""
    if n >= 2:
        labels = (f'<text x="{xs[0]:.1f}" y="{h - 1}" class="sparklbl">{esc("start")}</text>'
                  f'<text x="{xs[-1]:.1f}" y="{h - 1}" class="sparklbl" text-anchor="end">{esc("now")}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="spark"><polyline fill="none" stroke="#6d5dfc" stroke-width="3" points="{pline}"/>{dots}{labels}</svg>'


CSS = """
:root { --ink:#1c2130; --muted:#6b7280; --line:#e5e7eb; --bg:#f7f7fb; --card:#ffffff;
        --accent:#6d5dfc; --good:#0e9f6e; --bad:#e02424; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.55 -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
.wrap { max-width: 860px; margin: 0 auto; padding: 32px 20px 64px; }
header h1 { font-size: 26px; margin: 0 0 4px; }
header .sub { color: var(--muted); margin-bottom: 18px; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px;
         font-weight:600; letter-spacing:.03em; }
.badge.demo { background:#fef3c7; color:#92400e; border:1px solid #fcd34d; }
.badge.live { background:#d1fae5; color:#065f46; border:1px solid #6ee7b7; }
.cards { display:flex; gap:14px; flex-wrap:wrap; margin: 18px 0; }
.card { flex:1 1 180px; background:var(--card); border:1px solid var(--line);
        border-radius:12px; padding:14px 16px; }
.card .label { font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
.card .value { font-size:30px; font-weight:700; margin-top:2px; }
.card .delta { font-size:12.5px; margin-top:2px; color:var(--muted); }
.card .delta.up { color:var(--good); } .card .delta.down { color:var(--bad); }
.card.trend { flex-basis:100%; }
.spark { width:100%; height:96px; }
.sparklbl { font-size:10px; fill:#9ca3af; }
h2 { font-size:17px; margin: 30px 0 10px; }
table { width:100%; border-collapse: collapse; background:var(--card);
        border:1px solid var(--line); border-radius:10px; overflow:hidden; }
th, td { padding:9px 12px; text-align:left; border-bottom:1px solid var(--line); font-size:14px; }
th { background:#fafafc; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
tr:last-child td { border-bottom:none; }
.snippet { background:var(--card); border:1px solid var(--line); border-left:3px solid var(--accent);
           border-radius:8px; padding:10px 14px; margin:10px 0; font-size:13.5px; color:#374151; }
.chg { background:var(--card); border:1px solid var(--line); border-radius:8px;
       padding:9px 14px; margin:8px 0; font-size:14px; }
.chg.gain { border-left:3px solid var(--good); }
.chg.loss { border-left:3px solid var(--bad); }
.rec { background:var(--card); border:1px solid var(--line); border-radius:12px;
       padding:16px 18px; margin:12px 0; }
.rec h3 { margin:0 0 8px; font-size:16px; }
.rec .pri { display:inline-block; background:var(--accent); color:#fff; border-radius:6px;
            padding:1px 8px; font-size:12px; font-weight:700; margin-right:8px; }
.rec .why { color:#374151; font-size:14px; margin-bottom:10px; }
.rec ul { margin:0; padding-left:20px; }
.rec li { margin:4px 0; font-size:14px; }
.rec .targets { margin-top:10px; font-size:12.5px; color:var(--muted); }
footer { margin-top:40px; border-top:1px solid var(--line); padding-top:14px;
         color:var(--muted); font-size:12.5px; }
code { background:#eef0f6; border-radius:4px; padding:0 4px; }
"""


def _delta_chip(delta: float, invert: bool = False) -> str:
    eps = 0.05
    if abs(delta) < eps:
        return "<span class='delta'>→ unchanged</span>"
    up = (delta > 0) != invert
    cls = "delta up" if up else "delta down"
    sign = "+" if delta > 0 else ""
    return f"<span class='{cls}'>{sign}{delta:.1f} pts vs last week</span>"


def render_html(brand, week, mode, score, d, recs, history_rows, snippets) -> str:
    prev = d.get("prev_summary") or {}
    n_cited_prompts = sum(1 for p in score["prompts"] if p["brand_any"])
    answers_note = ", ".join(score["engines"].keys())
    if score.get("n_failed"):
        answers_note = (f"of {score['n_attempted']} attempted · "
                        f"{score['n_failed']} failed (excluded)")

    engine_rows = "".join(
        f"<tr><td><b>{esc(k)}</b></td><td><code>{esc(v['model'])}</code></td>"
        f"<td>{v['n']}</td><td>{round(v['citation_rate']/100*v['n'])}/{v['n']}</td>"
        f"<td>{v['sov']:.1f}%</td></tr>"
        for k, v in score["engines"].items()
    )

    def _comp_delta(name: str) -> str:
        if d["first_run"]:
            return "—"
        delta = d["competitor_deltas"].get(name, 0)
        return f"{delta:+d}"

    comp_rows = "".join(
        f"<tr><td><b>{esc(name)}</b></td><td>{count}</td>"
        f"<td>{_comp_delta(name)}</td></tr>"
        for name, count in score["competitors"].items()
    )

    snips = []
    for name in list(score["competitors"].keys())[:4]:
        for prompt_text, snip in snippets.get(name, [])[:1]:
            snips.append(
                f"<div class='snippet'><b>{esc(name)}</b> · prompt “{esc(prompt_text)}”<br>“{esc(snip)}”</div>"
            )

    chgs = []
    for g in d.get("gained", []):
        chgs.append(f"<div class='chg gain'>✅ <b>Gained:</b> “{esc(g['prompt_text'])}” ({esc(g['engine'])}) — brand absent last week, cited now</div>")
    for g in d.get("lost", []):
        comp = ", ".join(g["now"]["competitors"]) or "—"
        chgs.append(f"<div class='chg loss'>❌ <b>Lost:</b> “{esc(g['prompt_text'])}” ({esc(g['engine'])}) — cited last week, dropped now · competitors still named: {esc(comp)}</div>")
    if not chgs:
        chgs = ["<div class='chg'>No citation changes week-over-week.</div>" if not d["first_run"]
                else "<div class='chg'>First stored run — diffs begin next week.</div>"]

    trend_rows = "".join(
        f"<tr><td>{esc(h['week'])}</td><td>{h['sov']:.1f}%</td><td>{h['citation_rate']:.1f}%</td></tr>"
        for h in history_rows
    ) if len(history_rows) >= 2 else "<tr><td colspan=3>First run — trend starts next week.</td></tr>"

    rec_html = []
    for i, r in enumerate(recs, start=1):
        acts = "".join(f"<li>{esc(a)}</li>" for a in r.actions)
        targets = ""
        if r.targets:
            targets = ("<div class='targets'>Target prompts: "
                       + "; ".join("“" + esc(t) + "”" for t in r.targets[:3]) + "</div>")
        rec_html.append(
            f"<div class='rec'><h3><span class='pri'>{esc(r.priority)}</span>"
            f"{esc(r.title)}</h3><div class='why'><b>Why:</b> {esc(r.why)}</div>"
            f"<ul>{acts}</ul>{targets}</div>"
        )

    mode_badge = ("<span class='badge demo'>DEMO DATA — fixture replay</span>" if mode == "demo"
                  else "<span class='badge live'>LIVE RUN</span>")

    sov_delta_html = ""
    if not d["first_run"]:
        sov_delta_html = _delta_chip(d["sov_delta"])
    cite_delta_html = ""
    if not d["first_run"]:
        cite_delta_html = _delta_chip(d["citation_delta"])

    demo_note = (
        "<p><i>Demo disclosure: fixture responses are synthetic and recorded by the pipeline authors; "
        "no live API calls were made for this report.</i></p>" if mode == "demo" else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Visibility Digest — {esc(brand.name)} ({esc(week)})</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Weekly AI Visibility Digest — {esc(brand.name)}</h1>
    <div class="sub">{esc(week)} · {mode_badge} · does ChatGPT-style &amp; Perplexity-style AI name you when buyers ask?</div>
  </header>

  <div class="cards">
    <div class="card"><div class="label">Share of voice</div>
      <div class="value">{score['sov']:.1f}%</div>{sov_delta_html}</div>
    <div class="card"><div class="label">Citation rate</div>
      <div class="value">{score['citation_rate']:.0f}%</div>
      <div class="delta">{n_cited_prompts}/{score['n_prompts']} prompts named {esc(brand.name)}{(' · ' + cite_delta_html) if cite_delta_html else ''}</div></div>
    <div class="card"><div class="label">Answers analyzed</div>
      <div class="value">{score['n_rows']}</div>
      <div class="delta">{esc(answers_note)}</div></div>
    <div class="card trend"><div class="label">Score trend (share of voice by week)</div>
      {_sparkline([h['sov'] for h in history_rows])}</div>
  </div>

  <h2>Score trend</h2>
  <table><tr><th>Week</th><th>Share of voice</th><th>Citation rate</th></tr>{trend_rows}</table>

  <h2>Per-engine breakdown</h2>
  <table><tr><th>Engine</th><th>Model</th><th>Answers</th><th>Brand cited</th><th>SOV</th></tr>{engine_rows}</table>

  <h2>Which competitors got cited — and why</h2>
  <table><tr><th>Competitor</th><th>Answers naming it</th><th>Δ vs last week</th></tr>{comp_rows}</table>
  {''.join(snips) if snips else ''}

  <h2>What changed this week</h2>
  {''.join(chgs)}

  <h2>This week's 3 actions (prioritized)</h2>
  {''.join(rec_html)}

  <footer>
    <p><b>Methodology.</b> Answers are collected weekly from official LLM APIs (free tiers of
    Groq/Llama and Google Gemini by default) responding to your buyer-phrase prompts; these serve as
    proxies for the AI answer engines buyers actually use. Mention detection uses exact + alias
    matching with typo tolerance. <b>Share of voice</b> = your share of named products per answer,
    averaged across answers. <b>Citation rate</b> = share of answers naming your brand at all.
    Token use per weekly run is intentionally tiny (pennies at paid rates; $0 on free tiers).</p>
    {demo_note}
    <p>Generated by citation-monitor · crypto-native · $19/mo</p>
  </footer>
</div>
</body>
</html>
"""
