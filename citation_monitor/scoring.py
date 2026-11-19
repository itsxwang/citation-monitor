"""Share-of-voice and citation-rate scoring.

Definitions (documented in the digest footer too):
  - citation rate: share of (prompt x engine) answers that name the brand
  - per-answer SOV: brand share among named entities in one answer
    = mentioned_brand / (mentioned_brand + count(distinct competitors named))
  - aggregate SOV: mean per-answer SOV across all answers where anything was named
"""
from __future__ import annotations


def _sov_row(brand: int, n_comp: int):
    total = brand + n_comp
    if total == 0:
        return None
    return brand / total


def score_run(rows: list) -> dict:
    """rows: list of result dicts (see store.get_rows / pipeline building).

    Rows whose engine call errored are excluded from every metric: a failed
    request is not evidence the brand was absent, so counting it would
    understate the citation rate and share of voice.
    """
    n_attempted = len(rows)
    valid = [r for r in rows if not r.get("error") and (r.get("raw_text") or "").strip()]
    n_rows = len(valid)
    cited = [r for r in valid if r["brand_mentioned"]]
    citation_rate = (len(cited) / n_rows) if n_rows else 0.0

    sov_values = []
    for r in valid:
        v = _sov_row(1 if r["brand_mentioned"] else 0, len(r["competitors"]))
        if v is not None:
            sov_values.append(v)
    sov = (sum(sov_values) / len(sov_values) * 100.0) if sov_values else 0.0

    per_engine = {}
    for r in valid:
        per_engine.setdefault(r["engine"], []).append(r)
    engines = {}
    for ename, erows in sorted(per_engine.items()):
        e_cited = [r for r in erows if r["brand_mentioned"]]
        e_sov_vals = [v for r in erows
                      if (v := _sov_row(1 if r["brand_mentioned"] else 0, len(r["competitors"]))) is not None]
        engines[ename] = {
            "model": erows[0].get("model", ""),
            "n": len(erows),
            "citation_rate": (len(e_cited) / len(erows) * 100.0) if erows else 0.0,
            "sov": (sum(e_sov_vals) / len(e_sov_vals) * 100.0) if e_sov_vals else 0.0,
        }

    # aggregate by prompt (across engines)
    per_prompt = {}
    for r in valid:
        p = per_prompt.setdefault(r["prompt_id"], {
            "prompt_id": r["prompt_id"], "prompt_text": r["prompt_text"],
            "locale": r["locale"], "style": r["style"], "engines": [],
            "brand_any": False, "competitors": set(), "sov_vals": [],
        })
        p["engines"].append(r["engine"])
        p["brand_any"] = p["brand_any"] or bool(r["brand_mentioned"])
        p["competitors"].update(c["name"] for c in r["competitors"])
        v = _sov_row(1 if r["brand_mentioned"] else 0, len(r["competitors"]))
        if v is not None:
            p["sov_vals"].append(v)
    prompt_list = []
    for pid in sorted(per_prompt):
        p = per_prompt[pid]
        prompt_list.append({
            "prompt_id": p["prompt_id"], "prompt_text": p["prompt_text"],
            "locale": p["locale"], "style": p["style"], "engines": p["engines"],
            "brand_any": p["brand_any"], "competitors": sorted(p["competitors"]),
            "sov": (sum(p["sov_vals"]) / len(p["sov_vals"]) * 100.0) if p["sov_vals"] else None,
        })

    comp_counts = {}
    for r in valid:
        for c in r["competitors"]:
            comp_counts[c["name"]] = comp_counts.get(c["name"], 0) + 1
    competitors = dict(sorted(comp_counts.items(), key=lambda kv: -kv[1]))

    style_stats = {}
    for p in prompt_list:
        s = style_stats.setdefault(p["style"], {"n": 0, "brand": 0, "comp": 0})
        s["n"] += 1
        s["brand"] += 1 if p["brand_any"] else 0
        s["comp"] += 1 if p["competitors"] else 0

    tokens_est = sum(r.get("tokens_est", 0) for r in rows)

    return {
        "n_prompts": len(prompt_list),
        "n_rows": n_rows,
        "n_attempted": n_attempted,
        "n_failed": n_attempted - n_rows,
        "citation_rate": citation_rate * 100.0,
        "sov": sov,
        "engines": engines,
        "prompts": prompt_list,
        "competitors": competitors,
        "style_stats": style_stats,
        "tokens_est": tokens_est,
        "errors": [r for r in rows if r.get("error")],
    }
