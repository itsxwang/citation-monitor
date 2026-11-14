"""Week-over-week diff against the previous stored run."""
from __future__ import annotations


def _key(engine: str, prompt_text: str):
    return (engine, prompt_text)


def diff_runs(cur_rows: list, prev_rows: list | None) -> dict:
    if not prev_rows:
        return {
            "first_run": True,
            "gained": [], "lost": [],
            "sov_delta": 0.0, "citation_delta": 0.0,
            "competitor_deltas": {},
            "prev_summary": None,
        }

    prev_map = {_key(r["engine"], r["prompt_text"]): r for r in prev_rows}
    gained, lost = [], []

    for r in cur_rows:
        p = prev_map.get(_key(r["engine"], r["prompt_text"]))
        if p is None:
            continue
        if r["brand_mentioned"] and not p["brand_mentioned"]:
            gained.append({"prompt_text": r["prompt_text"], "engine": r["engine"],
                           "style": r["style"], "locale": r["locale"],
                           "was": _entity_summary(p), "now": _entity_summary(r)})
        elif not r["brand_mentioned"] and p["brand_mentioned"]:
            lost.append({"prompt_text": r["prompt_text"], "engine": r["engine"],
                         "style": r["style"], "locale": r["locale"],
                         "was": _entity_summary(p), "now": _entity_summary(r)})

    def _agg(rows):
        cited = [r for r in rows if r["brand_mentioned"]]
        rate = len(cited) / len(rows) * 100.0 if rows else 0.0
        sov_vals = []
        for r in rows:
            b = 1 if r["brand_mentioned"] else 0
            c = len(r["competitors"])
            if b + c:
                sov_vals.append(b / (b + c))
        sov = sum(sov_vals) / len(sov_vals) * 100.0 if sov_vals else 0.0
        return rate, sov

    cur_rate, cur_sov = _agg(cur_rows)
    prev_rate, prev_sov = _agg(prev_rows)

    cur_comp, prev_comp = {}, {}
    for r in cur_rows:
        for c in r["competitors"]:
            cur_comp[c["name"]] = cur_comp.get(c["name"], 0) + 1
    for r in prev_rows:
        for c in r["competitors"]:
            prev_comp[c["name"]] = prev_comp.get(c["name"], 0) + 1
    comp_deltas = {name: cur_comp.get(name, 0) - prev_comp.get(name, 0)
                   for name in sorted(set(cur_comp) | set(prev_comp))}

    return {
        "first_run": False,
        "gained": gained, "lost": lost,
        "sov_delta": cur_sov - prev_sov,
        "citation_delta": cur_rate - prev_rate,
        "competitor_deltas": comp_deltas,
        "prev_summary": {"citation_rate": prev_rate, "sov": prev_sov},
    }


def _entity_summary(row: dict) -> dict:
    return {
        "brand": bool(row["brand_mentioned"]),
        "competitors": [c["name"] for c in row["competitors"]],
    }
