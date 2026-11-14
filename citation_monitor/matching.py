"""Mention detection: exact + alias matching with word boundaries, plus a
fuzzy pass (token-level) that catches typos like 'StabelDesk'.

Deliberately conservative: aliases shorter than 4 characters are never fuzzy
matched, and fuzzy matches always record `fuzzy=True` so digests can show them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
FUZZY_THRESHOLD = 0.86


@dataclass
class Entity:
    name: str
    aliases: list = field(default_factory=list)

    def all_names(self) -> list:
        names = [self.name] + list(self.aliases)
        seen, out = set(), []
        for n in names:
            key = n.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(n.strip())
        return out


@dataclass
class Mention:
    first_pos: int   # char index of first mention, -1 if absent
    alias: str       # which alias/name matched
    fuzzy: bool


def alias_regex(alias: str) -> re.Pattern:
    parts = [re.escape(p) for p in alias.strip().split()]
    body = r"[\s\-]*".join(parts)
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", re.IGNORECASE)


def _exact_positions(text: str, alias: str) -> list:
    return [m.start() for m in alias_regex(alias).finditer(text)]


def _fuzzy_position(text: str, alias: str):
    """Return (pos, matched_token) for typo-tolerant matching, or (None, None).

    Guard: a fuzzy candidate must not be SHORTER than the alias. Typos keep
    roughly the same length; common-word truncations (e.g. 'crypto' vs the
    alias 'Cryptio') are false positives and rejected.
    """
    alias_tokens = [t for t in TOKEN_RE.findall(alias) if len(t) >= 4]
    if not alias_tokens:
        return None, None
    from difflib import SequenceMatcher
    alias_joined = "".join(t for t in alias_tokens)
    alias_joined = re.sub(r"[._+-]", "", alias_joined).lower()
    tokens = [(m.start(), m.group(0)) for m in TOKEN_RE.finditer(text)]
    n = len(alias_tokens)
    if n == 1:
        a = alias_tokens[0].lower()
        if len(a) < 5:
            return None, None  # too risky for short aliases
        for start, tok in tokens:
            cand = re.sub(r"[._+-]", "", tok).lower()
            if cand == a:
                continue  # exact pass already handled it
            # typos keep ~alias length: never shorter, at most +1 char longer
            if not (len(a) <= len(cand) <= len(a) + 1):
                continue
            if SequenceMatcher(None, cand, a).ratio() >= FUZZY_THRESHOLD:
                return start, tok
    else:
        for i in range(0, len(tokens) - n + 1):
            window = tokens[i:i + n]
            cand = "".join(re.sub(r"[._+-]", "", t) for _, t in window).lower()
            if cand == alias_joined:
                continue
            if not (len(alias_joined) <= len(cand) <= len(alias_joined) + 1):
                continue
            if SequenceMatcher(None, cand, alias_joined).ratio() >= FUZZY_THRESHOLD:
                return window[0][0], window[0][1]
    return None, None


def detect_entity(text: str, entity: Entity):
    """Return Mention (first_pos=-1 when absent) for one entity."""
    best = None
    for alias in entity.all_names():
        positions = _exact_positions(text, alias)
        if positions:
            cand = Mention(min(positions), alias, fuzzy=False)
            if best is None or cand.first_pos < best.first_pos:
                best = cand
    if best is not None:
        return best
    for alias in entity.all_names():
        pos, tok = _fuzzy_position(text, alias)
        if pos is not None:
            return Mention(pos, tok or alias, fuzzy=True)
    return Mention(-1, "", fuzzy=False)


def detect_entities(text: str, entities: list) -> dict:
    """entities: list[Entity] -> dict name -> Mention"""
    return {e.name: detect_entity(text, e) for e in entities}


def extract_snippet(text: str, pos: int, alias_len: int = 0, width: int = 150) -> str:
    if pos < 0:
        return ""
    start = max(0, pos - width // 2 - alias_len // 2)
    end = min(len(text), pos + alias_len + width // 2)
    raw = text[start:end].strip()
    raw = re.sub(r"\s+", " ", raw)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{raw}{suffix}"
