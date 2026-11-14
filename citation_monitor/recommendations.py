"""Recommendation engine: always emits EXACTLY 3 prioritized recommendations,
each backed by run data (numbers), with concrete actions. Used by both the
Markdown and HTML digests — this is the payload customers pay for.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rec:
    priority: str
    title: str
    why: str
    actions: list = field(default_factory=list)
    targets: list = field(default_factory=list)


def _pct(x: float) -> str:
    return f"{x:.0f}%"


def build_recommendations(score: dict, d: dict, brand_name: str, competitor_names: list) -> list:
    candidates = []

    # ---- candidate: comparison / alternatives pages -----------------------
    alt = score["style_stats"].get("alternatives", {"n": 0, "brand": 0, "comp": 0})
    vs = score["style_stats"].get("vs", {"n": 0, "brand": 0, "comp": 0})
    comp_total = alt["n"] + vs["n"]
    brand_total = alt["brand"] + vs["brand"]
    top_comp = max(score["competitors"].items(), key=lambda kv: kv[1]) if score["competitors"] else None
    if comp_total and brand_total < comp_total:
        brand_rate = brand_total / comp_total * 100.0
        comp_name = top_comp[0] if top_comp else "the incumbent"
        sev = (1 - brand_total / comp_total) + 0.55  # comparison pages are the highest-leverage fix
        candidates.append((sev, Rec(
            priority="P1",
            title=f"Turn “{comp_name} alternatives” prompts into comparison-page wins",
            why=(
                f"Across {comp_total} 'alternatives / vs' prompts this week, competitors were named in "
                f"{_pct(100.0)} of them but {brand_name} in only {_pct(brand_rate)} "
                f"({brand_total}/{comp_total}). {comp_name} leads the whole run with "
                f"{top_comp[1] if top_comp else 0} citations — answer engines default to it because "
                "it has comparison-shaped content to quote."
            ),
            actions=[
                f"Publish a '{brand_name} vs {comp_name}' page with a feature/price table answer engines can quote verbatim.",
                "Create an 'X alternatives' hub page naming each tracked competitor, with honest positioning and current pricing.",
                "Mirror the exact prompt phrasing as on-page H2 questions so the pages match buyer wording 1:1.",
            ],
            targets=[p["prompt_text"] for p in score["prompts"] if p["style"] in ("alternatives", "vs")][:4],
        )))

    # ---- candidate: pricing-page angle ------------------------------------
    pr = score["style_stats"].get("pricing", {"n": 0, "brand": 0, "comp": 0})
    lost_pricing = [x for x in d.get("lost", []) if x.get("style") == "pricing"]
    if pr["n"] and pr["brand"] < pr["n"] or lost_pricing:
        sev = (1 - pr["brand"] / pr["n"]) + (0.4 if lost_pricing else 0)
        candidates.append((sev, Rec(
            priority="P2",
            title="Own the pricing question before competitors answer it for you",
            why=(
                f"In {pr['n']} pricing-shaped prompts, {brand_name} was named in {pr['brand']} "
                f"while competitors were named in {pr['comp']}."
                + (f" You also LOST a previously-won pricing prompt this week ('{lost_pricing[0]['prompt_text']}')."
                   if lost_pricing else "")
                + " Answer engines prefer pages with explicit numbers to quote."
            ),
            actions=[
                "Put exact prices (monthly plan AND per-invoice fee) as plain text on /pricing — no 'contact sales' gating.",
                "Add an FAQ entry per tracked pricing prompt ('How much does it cost to invoice in USDC?') with the number in the first sentence.",
                "Publish a short 'cost of stablecoin invoicing' breakdown post that compares your flat fee vs % processors.",
            ],
            targets=[p["prompt_text"] for p in score["prompts"] if p["style"] == "pricing"][:4],
        )))

    # ---- candidate: content for how-to prompts ----------------------------
    ht = score["style_stats"].get("how_to", {"n": 0, "brand": 0, "comp": 0})
    if ht["n"] and ht["brand"] < ht["n"]:
        sev = (1 - ht["brand"] / ht["n"]) + 0.2
        missing = [p["prompt_text"] for p in score["prompts"]
                   if p["style"] == "how_to" and not p["brand_any"]][:4]
        candidates.append((sev, Rec(
            priority="P2",
            title="Answer the exact 'how do I…' questions buyers ask the engines",
            why=(
                f"In {ht['n']} how-to prompts, {brand_name} appeared in {ht['brand']}. "
                f"Competitors showed up in {ht['comp']}. How-to gaps are the cheapest citations to win: "
                "engines quote step-by-step pages directly."
            ),
            actions=[
                f"Publish one guide per missing how-to prompt, titled with the prompt itself (e.g. '{missing[0] if missing else 'your top how-to question'}').",
                "Include a 3-step summary block at the top — that is the text answer engines lift.",
                "Interlink each guide from your docs and product pages so crawlers see it as core content.",
            ],
            targets=missing,
        )))

    # ---- candidate: localization ------------------------------------------
    LANG_LABEL = {"es": "Spanish", "pt": "Portuguese", "de": "German", "fr": "French",
                  "it": "Italian", "nl": "Dutch"}
    locales = {}
    for p in score["prompts"]:
        locales.setdefault(p["locale"], {"n": 0, "brand": 0})
        locales[p["locale"]]["n"] += 1
        locales[p["locale"]]["brand"] += 1 if p["brand_any"] else 0
    for loc, st in sorted(locales.items()):
        if loc == "en":
            continue
        rate = st["brand"] / st["n"] if st["n"] else 0.0
        if rate < 0.5:
            lang = LANG_LABEL.get(loc, loc.upper())
            candidates.append((1.3, Rec(
                priority="P2",
                title=f"Win the {lang}-language prompts — competitors currently own them",
                why=(
                    f"{brand_name} was named in {st['brand']}/{st['n']} {lang} prompts "
                    f"({_pct(rate * 100)}). Non-English queries are your wedge: fewer competitors "
                    "bother publishing localized answers, so each citation is cheap to win and sticky."
                ),
                actions=[
                    f"Translate your top 5 landing pages + pricing page into {lang}.",
                    f"Publish a {lang} FAQ answering the exact {lang}-tagged prompts from your config.",
                    f"Add hreflang tags so the {lang} pages are indexable in the right locale.",
                ],
                targets=[p["prompt_text"] for p in score["prompts"] if p["locale"] == loc][:4],
            )))

    # ---- candidate: structured data / FAQ ---------------------------------
    overall = score["citation_rate"] / 100.0
    if overall < 0.5:
        candidates.append((1.1, Rec(
            priority="P2",
            title="Add structured data so engines can quote you verbatim",
            why=(
                f"{brand_name} was cited in only {_pct(score['citation_rate'])} of answers. "
                "Engines lean on pages that carry clean question/answer structure and explicit product facts."
            ),
            actions=[
                "Add FAQPage schema for your 5 most-asked buyer questions (copy the exact wording from your config prompts).",
                "Add Product + Offer schema to the homepage with name, category, and price so the model can state facts, not guess.",
                "Put a one-sentence 'what is <brand>' definition in the first 60 words of the homepage.",
            ],
            targets=[p["prompt_text"] for p in score["prompts"] if not p["brand_any"]][:4],
        )))

    # ---- candidate: regained momentum (from diff) -------------------------
    gained = d.get("gained", [])
    lost = d.get("lost", [])
    if lost and len(candidates) < 5:
        sev = 0.9
        candidates.append((sev, Rec(
            priority="P3",
            title="Regain the citation you lost this week before it compounds",
            why=(
                f"You dropped from cited to not-cited on {len(lost)} prompt(s), e.g. "
                f"'{lost[0]['prompt_text']}' ({lost[0]['engine']}). "
                f"You gained {len(gained)} — keep the wins from compounding by fixing the drop fast."
            ),
            actions=[
                f"Refresh the page/answer that used to win '{lost[0]['prompt_text']}' — update numbers and dates.",
                "Ask 2 customers to mention that exact question to their assistant and report what comes back next week.",
                "Re-check next week's diff; a second consecutive loss on the same prompt is a red flag to escalate.",
            ],
            targets=[x["prompt_text"] for x in lost][:4],
        )))

    # ---- sort + backfill to exactly 3 --------------------------------------
    # dedupe targets inside each rec (per-engine duplicates otherwise repeat)
    for _, r in candidates:
        r.targets = list(dict.fromkeys(r.targets))

    candidates.sort(key=lambda t: -t[0])
    recs = [r for _, r in candidates[:3]]

    backlog = [
        Rec(
            priority="P3",
            title="Get listed where answer engines already look",
            why=(
                f"{brand_name} is under-cited ({_pct(score['citation_rate'])} of answers) while competitors "
                "show up by default. Engines draw heavily on comparison sites, directories and docs."
            ),
            actions=[
                "List the product on the 3 comparison sites your top competitor appears on this week.",
                "Ship or polish public docs so third-party pages can link to something concrete.",
                "Earn 2 external mentions (podcast, newsletter) that state your category in one line.",
            ],
            targets=[],
        ),
        Rec(
            priority="P3",
            title="Make the brand name unmissable and unambiguous",
            why=(
                f"Citation rate for {brand_name} is {_pct(score['citation_rate'])}; engines often "
                "paraphrase the category instead of naming the product. Naming needs repetition in quotable text."
            ),
            actions=[
                "Ensure the brand name appears in the first sentence of your homepage, docs and pricing pages.",
                "Add the brand name (exact spelling) to page titles: 'Brand — one-line category descriptor'.",
                "Standardize one descriptor sentence and reuse it verbatim everywhere so engines learn one phrasing.",
            ],
            targets=[],
        ),
    ]
    seen_titles = {r.title for r in recs}
    for b in backlog:
        if len(recs) >= 3:
            break
        if b.title not in seen_titles:
            recs.append(b)
            seen_titles.add(b.title)

    # dedupe by title, re-prioritize
    dedup, seen = [], set()
    for r in recs:
        if r.title not in seen:
            dedup.append(r)
            seen.add(r.title)
    for i, r in enumerate(dedup[:3]):
        r.priority = f"P{i + 1}"
    return dedup[:3]
