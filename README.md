# citation-monitor — Weekly AI Visibility Digest

**Live product page:** https://itsxwang.github.io/citation-monitor/ · **Sample digest (real engine data):** https://itsxwang.github.io/citation-monitor/digest-2026-W46.html · **Order:** https://itsxwang.github.io/cash-register/checkout.html?item=citation-monitor-weekly-digest

**Does ChatGPT, Perplexity or Gemini name your product when buyers ask?** Most founders
have no idea. Big monitoring tools charge $29–$399/mo and are built for marketing teams.
This is the under-served wedge: a **simple $19/mo weekly digest for indie SaaS founders** —
payable in **BTC / ETH / SOL** (no Stripe, no PayPal), built for founders outside the US
where crypto payment is natural.

Every week the tool asks your buyer-phrase questions to AI answer engines (free tiers of
Groq/Llama and Google Gemini), detects whether **you or your competitors** get named,
scores your **share of voice**, diffs it against last week, and renders a clean
Markdown + single-file HTML digest with **exactly 3 prioritized recommendations**.

> Naming note: product copy intentionally avoids the softening "GEO" term — we say
> **"AI visibility"** and **"AI answer citations"**.

---

## Quick start (zero API keys, $0, today)

```bash
python3 -m citation_monitor run --config brand.yaml --demo
```

That replays recorded fixture responses through the entire pipeline — matching,
scoring, SQLite history, week-over-week diff, recommendations — and writes:

- `output/digest-<week>.md` — Markdown digest
- `output/digest-<week>.html` — single-file HTML report (the public demo artifact)

A committed sample lives in `sample-output/` (labelled DEMO DATA).

## Live run (free API keys)

```bash
export GROQ_API_KEY="..."        # console.groq.com — free tier
export GEMINI_API_KEY="..."      # aistudio.google.com — free tier
# optional: OPENROUTER_API_KEY (free models), PERPLEXITY_API_KEY (paid)
python3 -m citation_monitor run --config brand.yaml
```

No key present → automatic, logged degrade to demo mode; a partially-keyed setup runs
only the keyed engines. Engine calls never crash the run — errors are recorded per
prompt and shown in the digest.

```bash
python3 -m citation_monitor init mybrand.yaml   # starter config (edit it)
python3 -m citation_monitor report --config brand.yaml   # re-render digest from history
python3 -m unittest discover -s tests           # 38 tests
```

## Architecture

```
brand.yaml ──► prompts (locale-tagged, style-classified)
                    │
                    ▼
   engines.py ── Groq ── Gemini ── (OpenRouter) ── (Perplexity) ── DemoEngine(fixtures)
                    │   official APIs only, env-var keys, single retry on 429/5xx
                    ▼
   matching.py ── exact + alias + boundary + typo-tolerant mention detection
                    ▼
   scoring.py ── per-answer share-of-voice, citation rate, per-engine + per-prompt
                    ▼
   store.py (SQLite: runs + results) ──► diff.py (gained / lost / deltas vs last week)
                    ▼
   recommendations.py ── EXACTLY 3 prioritized, data-backed recommendations
                    ▼
   digest_markdown.py + digest_html.py (single-file, inline CSS, inline SVG trend)
```

Key design decisions:

- **One engine interface.** `ask(prompt, system) -> text`. Demo replay is just another
  engine, so the entire pipeline is exercised identically with and without keys.
- **Mention detection is conservative.** Word-boundary alias matching first; fuzzy
  matching only for same-or-plus-one-length tokens (so `crypto` never matches the
  competitor "Cryptio", and "unstable desk" never matches "StableDesk"). Regressions
  like these are unit-tested.
- **History is SQLite.** Every run is stored, so week-over-week diffs and the trend
  chart come from real data, not from state in memory.
- **Recommendations are generated from the run data** (style-level gaps, lost citations,
  localization gaps, competitor leaderboards) with a ranked candidate backlog, so every
  digest ships exactly 3 prioritized, evidence-backed actions.

## Cost math (why this is pennies)

Default live run = **30 prompts × 2 engines = 60 calls/week** (config here has 36 prompts
— run everything or set `run.max_prompts: 30`).

Per call (measured on the demo data): ~150 tokens in, ~200 tokens out.

| | per weekly run | per month (×4.33) |
|---|---|---|
| Requests | 60 | 260 |
| Tokens (est.) | ~15,000 | ~65,000 |
| Gemini 2.5 Flash paid rates ($0.30/M in, $2.50/M out) | ~$0.001 | ~$0.05 |
| Groq llama-3.1-8b-instant paid rates | ~$0.0005 | ~$0.03 |
| **On free tiers** | **$0.00** | **$0.00** |

Free-tier headroom (Nov 2026, check current limits): Gemini free tier ~1500 requests/day
and Groq free tier ~14,400 requests/day — a 60-request weekly run is a rounding error.
Even if every customer ran on paid keys, unit cost is <$0.10/customer/month against
$19/mo revenue. **Gross margin ≈ 99%+**, and the founder's own demo/dev runs are $0.

## Revenue (crypto-only by design)

- $19/mo per brand — weekly digest delivered as a private page (GitHub Pages link) or email.
- Payment: BTC / ETH / SOL via the shared crypto checkout project (see
  LAUNCH_CHECKLIST.md for wiring). No Stripe/PayPal — deliberate.
- Renewal is manual-ish at this scale: a payment reminder with last week's digest as the hook.

## Roadmap

1. **Multi-brand agency tier — $39/mo.** N brands × M prompts in one config per client;
   digest batches per client. Same engine budget (token cost grows linearly but stays
   in cents; the real constraint is prompt curation quality).
2. **Non-English locale packs — ES / PT / DE.** The config already carries locale-tagged
   prompts and the pipeline is locale-aware (prompt + engine instruction + digest
   sections). Ships as curated prompt packs per market — the wedge is that non-US
   founders pay in crypto and are ignored by US-centric tools.
3. **Agency white-label reports.** Same HTML renderer with a logo/color parameter and
   a footer swap; agencies resell the digest at 3–5× with zero marginal build cost.
4. Later: citation persistence tracking (does a URL stay cited), OpenRouter auto-rotation
   across free models, digest email delivery, churn-save offer automation.

## Known limits (honest list)

- LLM answers are **proxies** for ChatGPT/Perplexity consumer answers, not the products
  themselves. That's what every monitoring tool at this price point does; the digest
  methodology footer says so in plain words.
- Competitor alias precision is on you: an alias like "Coinbase" also matches
  "Coinbase Wallet" mentions. Prefer full product names as aliases.
- Model names move; they're config values (`engines:` in brand.yaml), not code.
- Weekly diffs need ≥2 stored runs (the demo seeds a previous-week fixture run).
