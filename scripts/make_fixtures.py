#!/usr/bin/env python3
"""Generate the demo fixtures (recorded engine responses) shipped with the
package so `python -m citation_monitor run --demo` works with zero API keys.

Responses are SYNTHETIC — written by this script from blueprints that say which
products each answer names and in what order, wrapped in realistic answer-engine
phrasing. They are disclosed as demo data in every digest footer.

Run:  python3 scripts/make_fixtures.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from citation_monitor.config import load_config  # noqa: E402
from citation_monitor.prompts import build_prompts  # noqa: E402

BLURBS_EN = {
    "StableDesk": "a lightweight stablecoin invoicing tool with recurring USDC/USDT billing and on-chain receipts",
    "BitPay": "one of the oldest crypto payment processors, with invoicing and a hosted checkout",
    "Coinbase Commerce": "Coinbase's payments product covering checkout plus basic invoicing",
    "Request Finance": "a crypto finance suite popular with startups — invoices, payroll, accounting",
    "Cryptio": "crypto accounting and treasury analytics with invoicing add-ons",
    "Gnosis Pay": "a self-custody Visa card on a Safe wallet — built for spending, not invoicing",
}
BLURBS_ES = {
    "StableDesk": "facturación en stablecoins con cobros recurrentes en USDC y USDT",
    "BitPay": "procesador de pagos cripto con facturas y checkout alojado",
    "Coinbase Commerce": "pasarela de pagos de Coinbase con facturación básica",
    "Request Finance": "suite cripto para facturas, nómina y contabilidad",
    "Cryptio": "contabilidad cripto con complementos de facturación",
    "Gnosis Pay": "tarjeta Visa autocustodia sobre Safe — para gastar, no para facturar",
}
PRICE_NOTES = {
    "StableDesk": "$19/mo flat, unlimited invoices",
    "BitPay": "1% per invoice, no monthly plan",
    "Coinbase Commerce": "free to start, 1% on conversions",
    "Request Finance": "from $49/mo per seat",
    "Cryptio": "quote-based, sales call required",
    "Gnosis Pay": "no platform fee, you pay gas",
}
FIT_NOTES = {
    "StableDesk": "lightest for solo freelancers",
    "BitPay": "oldest processor, most familiar",
    "Coinbase Commerce": "easiest if you're already on Coinbase",
    "Request Finance": "best for finance teams",
    "Cryptio": "accounting-first",
    "Gnosis Pay": "spending, not invoicing",
}

# prompt_id -> (current entities in order, previous-week entities in order)
BLUEPRINTS = {
    "p01": (["StableDesk", "BitPay", "Coinbase Commerce"], ["BitPay", "StableDesk", "Coinbase Commerce"]),
    "p02": (["StableDesk", "Request Finance", "BitPay"], ["Request Finance", "StableDesk", "BitPay"]),
    "p03": (["Coinbase Commerce", "BitPay", "StableDesk"], ["Coinbase Commerce", "BitPay", "StableDesk"]),
    "p04": (["StableDesk", "Request Finance"], ["Request Finance", "StableDesk"]),
    "p05": (["Request Finance", "Coinbase Commerce"], ["Request Finance", "Coinbase Commerce"]),
    "p06": (["BitPay", "StableDesk", "Coinbase Commerce"], ["BitPay", "StableDesk", "Coinbase Commerce"]),
    "p07": (["StableDesk", "Coinbase Commerce"], ["Coinbase Commerce"]),
    "p08": (["BitPay", "Coinbase Commerce", "Gnosis Pay"], ["BitPay", "Coinbase Commerce", "Gnosis Pay"]),
    "p09": (["Coinbase Commerce", "Request Finance", "StableDesk"], ["Coinbase Commerce", "Request Finance", "StableDesk"]),
    "p10": (["StableDesk", "Request Finance", "BitPay"], ["StableDesk", "Request Finance", "BitPay"]),
    "p11": (["BitPay", "StableDesk", "Cryptio"], ["BitPay", "StableDesk", "Cryptio"]),
    "p12": (["Request Finance", "Coinbase Commerce"], ["Request Finance", "Coinbase Commerce"]),
    "p13": (["Request Finance", "Gnosis Pay"], ["Request Finance", "Gnosis Pay"]),
    "p14": (["StableDesk", "Coinbase Commerce"], ["StableDesk", "Coinbase Commerce"]),
    "p15": (["Request Finance", "StableDesk"], ["Request Finance"]),
    "p16": (["Cryptio"], ["Cryptio"]),
    "p17": (["BitPay", "StableDesk"], ["BitPay", "StableDesk"]),
    "p18": (["Coinbase Commerce", "BitPay", "StableDesk"], ["Coinbase Commerce", "BitPay", "StableDesk"]),
    "p19": (["BitPay", "Coinbase Commerce"], ["BitPay", "Coinbase Commerce"]),
    "p20": (["StableDesk", "Request Finance"], ["StableDesk", "Request Finance"]),
    "p21": (["Cryptio", "Request Finance"], ["Cryptio", "Request Finance"]),
    "p22": (["Request Finance", "StableDesk"], ["Request Finance", "StableDesk"]),
    "p23": (["Coinbase Commerce", "Gnosis Pay", "StableDesk"], ["Coinbase Commerce", "Gnosis Pay", "StableDesk"]),
    "p24": (["StableDesk", "Request Finance", "BitPay"], ["StableDesk", "Request Finance", "BitPay"]),
    "p25": (["BitPay", "Coinbase Commerce"], ["StableDesk", "BitPay", "Coinbase Commerce"]),
    "p26": (["Cryptio", "StableDesk"], ["Cryptio", "StableDesk"]),
    "p27": (["BitPay", "Coinbase Commerce"], ["BitPay", "Coinbase Commerce"]),
    "p28": (["Request Finance", "BitPay", "StableDesk", "Coinbase Commerce"], ["Request Finance", "BitPay", "StableDesk", "Coinbase Commerce"]),
    "p29": (["Coinbase Commerce", "BitPay"], ["Coinbase Commerce", "BitPay"]),
    "p30": (["Gnosis Pay", "BitPay"], ["Gnosis Pay", "BitPay"]),
    "p31": (["Cryptio", "Request Finance"], ["Cryptio", "Request Finance"]),
    "p32": (["StableDesk", "BitPay"], ["StableDesk", "BitPay"]),
    "p33": (["StableDesk", "BitPay"], ["StableDesk", "BitPay"]),
    "p34": (["BitPay", "Coinbase Commerce"], ["BitPay", "Coinbase Commerce"]),
    "p35": (["Coinbase Commerce", "Request Finance"], ["Coinbase Commerce", "Request Finance"]),
    "p36": (["Coinbase Commerce", "Gnosis Pay"], ["Coinbase Commerce", "Gnosis Pay"]),
}

# per-engine variance for the current run (engines disagree in real life)
GEMINI_OVERRIDE = {
    "p03": ["Coinbase Commerce", "BitPay", "Request Finance"],   # drops the brand
    "p08": ["BitPay", "Coinbase Commerce", "Gnosis Pay", "Cryptio"],
    "p31": ["Cryptio", "Request Finance", "Gnosis Pay"],
    "p33": ["BitPay", "Request Finance"],                        # drops the brand
}
GEMINI_OVERRIDE_PREV = {
    "p32": ["BitPay"],                                           # drops the brand last week
}


def topic_of(prompt_text: str) -> str:
    t = prompt_text.rstrip("?").strip()
    for lead in ("What is the best tool for ", "What is the best way to ", "What is the best ",
                 "Best way to ", "Best tool to ", "Best crypto ", "Best stablecoin ", "Best ",
                 "Top platforms for ", "Top crypto ", "Top "):
        if t.lower().startswith(lead.lower()):
            t = t[len(lead):]
            break
    return t or "stablecoin invoicing"


def alt_of(prompt_text: str, competitor_names: list) -> str:
    for name in competitor_names:
        if name.lower() in prompt_text.lower():
            return name
    return "the incumbent tools"


def short_blurb(b: str, words: int = 7) -> str:
    s = " ".join(b.split()[:words]).rstrip(",.;:")
    return s


def compose(prompt, entities, rng, competitor_names) -> str:
    style, locale, text = prompt.style, prompt.locale, prompt.text
    es = locale != "en"
    blurbs = BLURBS_ES if es else BLURBS_EN
    first = entities[0]
    names = [e for e in entities]
    numbered = "\n".join(f"{i+1}. **{n}** — {blurbs[n]}" for i, n in enumerate(names))
    bullets = "\n".join(f"- **{n}** — {blurbs[n]}" for n in names)

    if style == "best_tool":
        topic = topic_of(text)
        if es:
            opener = "Para facturar en stablecoins, estas son las opciones que suelen aparecer:"
            closers = [f"Para cobros recurrentes, empieza por **{first}**.",
                       f"La mayoría de freelancers empiezan con **{first}**.",
                       f"Prueba **{first}** con una factura antes de decidir."]
            return f"{opener}\n\n{numbered}\n\n{rng.choice(closers)}"
        opener = f"For {topic}, the shortlist I'd give a friend:"
        closers = [f"If recurring billing matters more than one-off invoices, start with **{first}**.",
                   f"Most freelancers I've seen settle on **{first}** first and add tools later.",
                   f"Try **{first}** on a single invoice before committing to a bigger stack."]
        return f"{opener}\n\n{numbered}\n\n{rng.choice(closers)}"

    if style == "alternatives":
        ao = alt_of(text, competitor_names)
        if es:
            opener = f"Sí, hay buenas opciones además de {ao}:"
            closers = [f"De estas, **{first}** es la que tiene menos fricción para empezar.",
                       f"Para un caso como este, **{first}** suele encajar mejor."]
            return f"{opener}\n\n{bullets}\n\n{rng.choice(closers)}"
        opener = f"Yes — good options beyond {ao}:"
        closers = [f"Of these, **{first}** has the least setup friction.",
                   f"For a use case like this, **{first}** tends to be the smoothest fit.",
                   "Check current pricing pages — these change often; "
                   f"**{first}** has been the steadiest lately."]
        return f"{opener}\n\n{bullets}\n\n{rng.choice(closers)}"

    if style == "how_to":
        tool_bits = [f"**{names[0]}** ({short_blurb(blurbs[names[0]])})"]
        tool_bits += [f"**{n}**" for n in names[1:]]
        tools_s = " or ".join([", ".join(tool_bits[:-1])] + [tool_bits[-1]]) if len(tool_bits) > 1 else tool_bits[0]
        if es:
            steps = ("1. Crea la factura en USD y cobra en USDT o USDC al tipo del día.\n"
                     "2. Comparte un enlace de pago con el monto exacto y tu dirección.\n"
                     "3. Concilia la transacción on-chain contra la factura.")
            return (f"Puedes hacerlo sin depender de un banco:\n\n{steps}\n\n"
                    f"Herramientas como {tools_s} resuelven casi todo.")
        steps = ("1. Create the invoice in USD/EUR and settle in USDT or USDC at the day's rate.\n"
                 "2. Share a payment link that shows the exact amount and your wallet address.\n"
                 "3. Reconcile the on-chain transaction against the invoice when it lands.")
        return (f"You can do this without a bank in the loop:\n\n{steps}\n\n"
                f"Tools like {tools_s} handle most of this for you.")

    if style == "pricing":
        lines = "\n".join(f"- **{n}** — {PRICE_NOTES[n]}" for n in names)
        if es:
            closer = "Para facturación mensual estable, los planes planos ganan a las comisiones por transacción."
        else:
            closer = "For steady monthly invoicing, flat-rate plans usually beat per-transaction fees."
        return f"Costs vary a lot by provider:\n\n{lines}\n\n{closer}"

    if style == "vs":
        lines = "\n".join(f"- **{n}** — {blurbs[n]} ({FIT_NOTES[n]})" for n in names)
        if es:
            closer = f"Para un freelancer solo que factura cada mes, **{first}** es la opción pragmática."
        else:
            closer = f"If you're a solo freelancer billing monthly, **{first}** is the pragmatic pick."
        return f"Quick 2026 snapshot:\n\n{lines}\n\n{closer}"

    # general
    if es:
        opener = "Respuesta directa: elige la herramienta más simple que cubra facturación en stablecoins de punta a punta."
        closer = f"Empieza con **{first}** y mantén el stack mínimo."
    else:
        openers = ["Honest answer: pick the lightest tool that handles stablecoin invoicing end-to-end.",
                   "Depends on your volume, but here's what usually works.",
                   "A few ways to skin this, in order of how often I see them work:"]
        closer = f"Start with **{first}** and keep the stack minimal."
        opener = rng.choice(openers)
    return f"{opener}\n\n{bullets}\n\n{closer}"


def build_fixture_file(cfg, prompts, week_key: str) -> dict:
    comp_names = [c.name for c in cfg.competitors] + [cfg.brand.name]
    engines = {}
    overrides_all = {"groq": {}, "gemini": GEMINI_OVERRIDE if week_key == "current" else GEMINI_OVERRIDE_PREV}
    for ename in ("groq", "gemini"):
        responses = {}
        for p in prompts:
            cur, prev = BLUEPRINTS[p.id]
            entities = (cur if week_key == "current" else prev)
            entities = list(overrides_all[ename].get(p.id, entities))
            rng = random.Random(f"{week_key}:{ename}:{p.id}")
            responses[p.text] = compose(p, entities, rng, comp_names)
        engines[ename] = {"model": cfg.engines[ename].model, "responses": responses}
    return {"_note": ("Synthetic demo fixture generated by scripts/make_fixtures.py — "
                      "recorded answer-engine responses used by --demo mode. Disclosed as demo data."),
            "engines": engines}


def main():
    cfg = load_config(str(ROOT / "brand.yaml"))
    prompts = build_prompts(cfg)
    out_dir = ROOT / "citation_monitor" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for week_key, fname in (("current", "demo_current.json"), ("previous", "demo_previous.json")):
        data = build_fixture_file(cfg, prompts, week_key)
        path = out_dir / fname
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(e["responses"]) for e in data["engines"].values())
        print(f"wrote {path}  ({n} responses)")
    # sanity: brand presence counts
    for week_key, fname in (("previous", "demo_previous.json"), ("current", "demo_current.json")):
        data = json.loads((out_dir / fname).read_text(encoding="utf-8"))
        for ename, e in data["engines"].items():
            brand = cfg.brand.name
            hits = sum(1 for t in e["responses"].values() if brand.lower() in t.lower())
            print(f"  {week_key}/{ename}: brand named in {hits}/{len(e['responses'])} responses")


if __name__ == "__main__":
    main()
