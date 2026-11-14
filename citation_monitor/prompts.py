"""Prompt list handling: parse locale tags, classify buyer-intent style."""
from __future__ import annotations

import re
from dataclasses import dataclass

_LOCALE_RE = re.compile(r"^\[(?P<loc>[a-z]{2}(?:[-_][A-Za-z]{2})?)\]\s*")

STYLES = ("alternatives", "vs", "pricing", "how_to", "best_tool", "general")


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str          # text sent to engines (locale tag stripped)
    config_text: str   # original line from brand.yaml
    locale: str
    style: str


def classify_style(text: str) -> str:
    t = text.lower()
    if "alternativ" in t or "instead of" in t:
        return "alternatives"
    if " vs " in t or "versus" in t or "comparison" in t:
        return "vs"
    if any(w in t for w in ("cheapest", "cost", "price", "pricing", "fee", "expensive", "free")):
        return "pricing"
    if t.startswith("how") or "how do" in t or "how can" in t:
        return "how_to"
    if "best" in t or re.search(r"\btop\b", t) or "which" in t:
        return "best_tool"
    return "general"


def build_prompts(cfg, limit=None) -> list:
    prompts = []
    default_locale = cfg.brand.locales[0] if cfg.brand.locales else "en"
    for i, raw in enumerate(cfg.prompts_raw, start=1):
        m = _LOCALE_RE.match(raw)
        if m:
            locale = m.group("loc").replace("_", "-").lower()
            text = raw[m.end():].strip()
        else:
            locale = default_locale
            text = raw.strip()
        prompts.append(Prompt(
            id=f"p{i:02d}",
            text=text,
            config_text=raw,
            locale=locale,
            style=classify_style(text),
        ))
    if limit:
        prompts = prompts[: int(limit)]
    return prompts
