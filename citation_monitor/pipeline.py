"""Pipeline orchestration: engines -> analysis -> storage -> diff -> digest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import diff as diff_mod
from . import scoring, store
from .digest_html import render_html
from .digest_markdown import render_md
from .engines import EngineError, build_engines, system_prompt
from .matching import Entity, detect_entities, extract_snippet
from .prompts import build_prompts
from .recommendations import build_recommendations


def _entities(cfg) -> list:
    ents = [Entity(name=cfg.brand.name, aliases=list(cfg.brand.aliases))]
    ents.extend(Entity(name=c.name, aliases=list(c.aliases)) for c in cfg.competitors)
    return ents


def _analyze_row(row: dict, entities: list) -> dict:
    text = row["raw_text"] or ""
    mentions = detect_entities(text, entities)
    brand = mentions.get(row["_brand_name"])
    competitors = []
    for name, m in mentions.items():
        if name == row["_brand_name"] or m.first_pos < 0:
            continue
        competitors.append({
            "name": name, "pos": m.first_pos, "alias": m.alias, "fuzzy": m.fuzzy,
            "snippet": extract_snippet(text, m.first_pos, len(m.alias)),
        })
    competitors.sort(key=lambda c: c["pos"])
    row.update({
        "brand_mentioned": bool(brand and brand.first_pos >= 0),
        "brand_pos": brand.first_pos if brand else -1,
        "brand_alias": brand.alias if brand else "",
        "brand_fuzzy": bool(brand and brand.fuzzy),
        "competitors": competitors,
    })
    return row


def _run_engine_calls(engines, prompts, cfg, log=print) -> list:
    entities = _entities(cfg)
    rows = []
    total = len(prompts) * len(engines)
    done = 0
    for p in prompts:
        for e in engines:
            done += 1
            row = {
                "engine": e.name, "model": e.model, "prompt_id": p.id,
                "prompt_text": p.text, "locale": p.locale, "style": p.style,
                "raw_text": "", "error": None,
                "_brand_name": cfg.brand.name,
            }
            try:
                text = e.ask(p.text, system_prompt(p.locale))
                row["raw_text"] = text or ""
            except EngineError as exc:
                row["error"] = str(exc)
                if done <= 3 or done == total:
                    log(f"  [warn] {exc}")
            row["tokens_est"] = (len(system_prompt(p.locale)) + len(p.text) + len(row["raw_text"])) // 4
            _analyze_row(row, entities)
            rows.append(row)
    return rows


def _rows_from_fixture(engines, prompts, fixture, cfg) -> list:
    """Build analyzed rows from a recorded fixture (used to seed demo history)."""
    entities = _entities(cfg)
    rows = []
    for p in prompts:
        for e in engines:
            responses = fixture.get("engines", {}).get(e.name, {}).get("responses", {})
            text = responses.get(p.text, "")
            row = {
                "engine": e.name, "model": fixture.get("engines", {}).get(e.name, {}).get("model", e.model),
                "prompt_id": p.id, "prompt_text": p.text, "locale": p.locale, "style": p.style,
                "raw_text": text, "error": None, "_brand_name": cfg.brand.name,
                "tokens_est": (len(system_prompt(p.locale)) + len(p.text) + len(text)) // 4,
            }
            _analyze_row(row, entities)
            rows.append(row)
    return rows


def _collect_snippets(rows, brand_name: str, limit_per_entity: int = 2) -> dict:
    snippets = {}
    for r in rows:
        src = []
        if r["brand_mentioned"] and r["raw_text"]:
            src.append((brand_name, r["brand_pos"], r["brand_alias"]))
        for c in r["competitors"]:
            src.append((c["name"], c["pos"], c["alias"]))
        for name, pos, alias in src:
            if pos is None or pos < 0:
                continue
            snip = extract_snippet(r["raw_text"], pos, len(alias))
            bucket = snippets.setdefault(name, [])
            if len(bucket) < limit_per_entity and snip:
                bucket.append((r["prompt_text"], snip))
    return snippets


def _write_digest(out_dir: str, week: str, brand, mode, score, d, recs, history_rows, snippets, log=print):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / f"digest-{week}.md"
    html_path = out / f"digest-{week}.html"
    md_path.write_text(render_md(brand, week, mode, score, d, recs, history_rows, snippets), encoding="utf-8")
    html_path.write_text(render_html(brand, week, mode, score, d, recs, history_rows, snippets), encoding="utf-8")
    log(f"  digest written: {md_path}")
    log(f"                {html_path}")
    return str(md_path), str(html_path)


def run_pipeline(cfg, demo: bool = False, out_dir: str | None = None,
                 limit: int | None = None, log=print) -> dict:
    prompts = build_prompts(cfg, limit if limit is not None else cfg.run.max_prompts)
    log(f"AI Answer Citation Monitor — weekly run for {cfg.brand.name!r} "
        f"({len(prompts)} prompts)")

    engines, mode, prev_fixture = build_engines(cfg, demo=demo, log=log)

    conn = store.connect(cfg.run.storage)

    if mode == "demo":
        # Seed a previous-week demo run once, so the digest has a real diff.
        if not store.has_run(conn, store.prev_week_label(1), "demo"):
            prev_rows = _rows_from_fixture(engines, prompts, prev_fixture, cfg)
            prev_score = scoring.score_run(prev_rows)
            prev_meta = {
                "created_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                "week": store.prev_week_label(1), "mode": "demo", "brand": cfg.brand.name,
                "engines": [e.name for e in engines], "tokens_est": prev_score["tokens_est"],
                "citation_rate": prev_score["citation_rate"], "sov": prev_score["sov"],
            }
            store.save_run(conn, prev_meta, prev_rows)
            log(f"  [demo] seeded previous-week fixture run ({prev_meta['week']}) so the diff is real")

    rows = _run_engine_calls(engines, prompts, cfg, log=log)
    score = scoring.score_run(rows)
    if score["errors"] and mode == "live":
        log(f"  [warn] {len(score['errors'])}/{score['n_rows']} engine calls errored — see results in the digest")

    week = store.iso_week()
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "week": week, "mode": mode, "brand": cfg.brand.name,
        "engines": [e.name for e in engines], "tokens_est": score["tokens_est"],
        "citation_rate": score["citation_rate"], "sov": score["sov"],
    }
    run_id = store.save_run(conn, meta, rows)

    prev_run = store.previous_run(conn, run_id, mode=mode)
    prev_rows = store.get_rows(conn, prev_run["id"]) if prev_run else None
    d = diff_mod.diff_runs(rows, prev_rows)
    recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
    snippets = _collect_snippets(rows, cfg.brand.name)
    history_rows = store.history(conn, mode=mode)

    out = out_dir or cfg.run.output_dir
    md_path, html_path = _write_digest(out, week, cfg.brand, mode, score, d, recs, history_rows, snippets, log=log)

    top_comp = next(iter(score["competitors"].items()), None)
    summary = {
        "run_id": run_id, "week": week, "mode": mode,
        "engines": [e.label() for e in engines],
        "citation_rate": score["citation_rate"], "sov": score["sov"],
        "sov_delta": d["sov_delta"], "gained": len(d["gained"]), "lost": len(d["lost"]),
        "top_competitor": top_comp[0] if top_comp else None,
        "tokens_est": score["tokens_est"], "md_path": md_path, "html_path": html_path,
        "prompts": len(prompts), "n_rows": score["n_rows"],
    }
    return summary


def report_pipeline(cfg, out_dir: str | None = None, log=print) -> dict:
    conn = store.connect(cfg.run.storage)
    latest = store.latest_run(conn)
    if latest is None:
        raise SystemExit("no stored runs yet — run `python -m citation_monitor run --config brand.yaml` first")
    rows = store.get_rows(conn, latest["id"])
    prev_run = store.previous_run(conn, latest["id"], mode=latest["mode"])
    prev_rows = store.get_rows(conn, prev_run["id"]) if prev_run else None

    score = scoring.score_run(rows)
    d = diff_mod.diff_runs(rows, prev_rows)
    recs = build_recommendations(score, d, latest["brand"], [])
    snippets = _collect_snippets(rows, latest["brand"])
    history_rows = store.history(conn, mode=latest["mode"])

    out = out_dir or cfg.run.output_dir
    md_path, html_path = _write_digest(out, latest["week"], cfg.brand, latest["mode"],
                                       score, d, recs, history_rows, snippets, log=log)
    return {"run_id": latest["id"], "week": latest["week"], "mode": latest["mode"],
            "md_path": md_path, "html_path": html_path}
