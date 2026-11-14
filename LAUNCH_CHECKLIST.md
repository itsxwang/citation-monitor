# LAUNCH CHECKLIST — human steps only

Everything below needs a human. Total time: ~2–3 hours to first live digest,
plus 1 hour/week for distribution. Budget: $0 (all free tiers).

## 1. Create free API keys (15 min)

- [ ] Groq: sign up at console.groq.com → API Keys → create → copy.
      Free tier is plenty (this product needs ~60 requests/week).
- [ ] Google Gemini: aistudio.google.com → Get API key → copy.
      If Gemini's key alone is active the run still works (engines are independent).
- [ ] Optional, later: openrouter.ai key (free models), perplexity.ai key (paid — skip).

## 2. Set env vars (5 min)

Add to `~/.bashrc` / `~/.zshrc` (never commit these):

```bash
export GROQ_API_KEY="gsk_..."
export GEMINI_API_KEY="AIza..."
```

- [ ] `source ~/.bashrc`, then verify:
      `python3 -m citation_monitor run --config brand.yaml --limit 3`
      You should see `[live] 1 engine(s) active` or `[live] 2 engine(s) active`.
- [ ] First full live run: `python3 -m citation_monitor run --config brand.yaml`
- [ ] Sanity-check the digest numbers by re-asking 3 prompts manually in a chat UI.

## 3. Replace the sample brand (30 min)

- [ ] `cp brand.yaml mybrand.yaml` (or edit in place) — put a REAL paying customer's
      brand in, or use your own product as customer #0 (recommended: dogfood first).
- [ ] Edit: `brand.name`, `aliases` (include domain), `site_url`, `competitors`
      (use FULL product names as aliases — avoid short ambiguous aliases),
      and the 30+ prompts using the buyer phrasing your customers actually say.
- [ ] Set `run.output_dir` / `run.storage` if you host multiple brands on one machine.

## 4. Schedule the weekly cron (10 min)

Same weekday every week — diffs and trend assume weekly cadence.

```cron
# Mondays 08:30 — live run
30 8 * * 1 cd /home/xion/venture-01-citation-monitor && /usr/bin/env python3 -m citation_monitor run --config mybrand.yaml >> cron.log 2>&1
```

- [ ] `crontab -e` and add the line above (adjust path + python).
- [ ] After week 2, confirm the digest shows "Δ vs last week" values (not "first run").

## 5. Publish digest pages to GitHub Pages (20 min)

The HTML digest is a single self-contained file — perfect for Pages.

- [ ] Create a public repo (or use this one) → Settings → Pages → deploy from `main`
      branch `/docs` folder.
- [ ] Add a copy step after each run (manual or in the cron):
      `mkdir -p docs && cp output/digest-*.html docs/ && git add docs && git commit -m "digest" && git push`
- [ ] Per customer, use a separate repo or a `docs/<brand>/` subfolder. Send the customer
      the link in the weekly payment-reminder email.
- [ ] Keep `sample-output/` as the public marketing demo (already committed here).

## 6. Wire crypto checkout (20 min — separate project)

Revenue is BTC / SOL / USDT only — no Stripe/PayPal, deliberately.

- [ ] In the shared crypto checkout project, create the product:
      `citation-monitor-weekly-digest` — **$19/mo**.
- [ ] Paste your receiving addresses (BTC + SOL + USDT on your chosen chain(s)) into
      the checkout config. Verify a $1 test payment end-to-end first.
- [ ] Define the fulfillment flow (manual at this scale): payment seen → send customer
      their digest page link + the Markdown version → calendar reminder for renewal in 30d.
- [ ] Write the invoice line into the payment memo: "AI visibility weekly digest — month N".

## 7. First-week distribution plan (1 hour)

Post the FREE sample digest (`sample-output/digest-2026-W46.html`) + the $19/mo offer in
5 places. Lead with the artifact, not the pitch — the digest IS the demo.

1. **Indie Hackers** — post: "I built a weekly digest that shows whether ChatGPT/Perplexity
   name your product — here's a real sample" + link to the sample HTML. Reply to every comment.
2. **r/SaaS** (and r/SideProject as secondary) — read self-promo rules first; comment-first
   in 2–3 recent "how do I rank in ChatGPT" threads, then post your own with the sample link.
3. **X build-in-public** — thread: the 3 headline numbers from the sample digest as images,
   the link, price, and "pay in USDT/SOL/BTC" as the hook for non-US founders. #buildinpublic
4. **Crypto-adjacent SaaS groups** — Telegram/Discord crypto-founder groups and payments
   communities: offer a FREE first digest for their brand in exchange for a testimonial
   (3-5 DMs). Crypto-native products feel this pain hardest.
5. **Non-English SaaS communities** — Spanish/Portuguese/German founder groups: lead with
   the ES prompts angle ("your market's answers are in Spanish and nobody is monitoring
   them"). This maps directly to the localization rec in the sample digest.

- [ ] Track which community converts; double down there in week 2.
- [ ] Collect testimonials from the free-digest-for-testimonial DMs and add to the sales post.

## 8. Week-2+ loop

- [ ] Every Monday: run cron → glance at digest → send to paying customers.
- [ ] Monthly: check model names still valid (they're config values, not code), check
      free-tier dashboards once, reconcile crypto payments.
- [ ] When you have 3+ paying customers: open the $39/mo multi-brand tier (roadmap item 1).
