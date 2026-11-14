"""Brand configuration loading.

Uses PyYAML when available; otherwise falls back to a small indent-based
parser that covers the YAML subset used by brand.yaml (nested dicts, lists of
scalars, flow lists, flow dicts). Zero-dependency friendly.
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field


class ConfigError(Exception):
    pass


@dataclass
class BrandCfg:
    name: str
    category: str = ""
    descriptor: str = ""
    site_url: str = ""
    aliases: list = field(default_factory=list)
    locales: list = field(default_factory=lambda: ["en"])


@dataclass
class CompetitorCfg:
    name: str
    aliases: list = field(default_factory=list)


@dataclass
class EngineCfg:
    model: str
    enabled: bool = True


@dataclass
class RunCfg:
    max_prompts: object = None
    timeout_seconds: int = 45
    storage: str = "data/history.db"
    output_dir: str = "output"


@dataclass
class Config:
    path: str
    brand: BrandCfg
    competitors: list  # list[CompetitorCfg]
    engines: dict      # name -> EngineCfg
    run: RunCfg
    prompts_raw: list  # list[str], unvalidated prompt strings


DEFAULT_ENGINE_MODELS = {
    "groq": "llama-3.1-8b-instant",
    "gemini": "gemini-2.5-flash",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
    "perplexity": "sonar",
}
DEFAULT_ENGINE_ENABLED = {
    "groq": True,
    "gemini": True,
    "openrouter": True,
    "perplexity": False,  # paid API; only enable if you have budget
}
ENGINE_ORDER = ["groq", "gemini", "openrouter", "perplexity"]


# --------------------------------------------------------------------------
# YAML loading (PyYAML if present, else minimal subset parser)
# --------------------------------------------------------------------------

def _strip_comment(line: str) -> str:
    out = []
    quote = None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        else:
            if ch in ("'", '"'):
                quote = ch
                out.append(ch)
            elif ch == "#":
                break
            else:
                out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(tok: str):
    tok = tok.strip()
    if tok == "":
        return None
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ("'", '"'):
        return tok[1:-1]
    low = tok.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _split_top_level(s: str, sep: str = ",") -> list:
    parts, depth, quote, cur = [], 0, None, []
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur and "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _parse_flow(tok: str):
    tok = tok.strip()
    if tok.startswith("[") and tok.endswith("]"):
        return [_parse_scalar(p) for p in _split_top_level(tok[1:-1])]
    if tok.startswith("{") and tok.endswith("}"):
        out = {}
        for part in _split_top_level(tok[1:-1]):
            if ":" not in part:
                raise ConfigError(f"bad flow mapping entry: {part!r}")
            k, v = part.split(":", 1)
            out[k.strip()] = _parse_flow(v)
        return out
    return _parse_scalar(tok)


def _mini_yaml(text: str):
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw.replace("\t", "  "))
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, line.strip()))
    if not lines:
        return {}
    value, idx = _parse_block(lines, 0, lines[0][0])
    if idx != len(lines):
        raise ConfigError(f"could not parse YAML near: {lines[idx][1]!r}")
    return value


def _parse_block(lines, i, indent):
    if lines[i][1].startswith("- "):
        out = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            item = lines[i][1][2:].strip()
            if item.startswith("{") or item.startswith("["):
                out.append(_parse_flow(item))
                i += 1
            elif ":" in item:
                # dict item: "- key: value" possibly followed by deeper keys
                d = {}
                k, v = _split_key(item)
                if v:
                    d[k] = _parse_flow(v)
                    i += 1
                else:
                    i += 1
                    val, i = _parse_block(lines, i, lines[i][0] if i < len(lines) else indent)
                    d[k] = val
                out.append(d)
            else:
                out.append(_parse_flow(item))
                i += 1
        return out, i
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        line = lines[i][1]
        if line.startswith("- "):
            break
        k, v = _split_key(line)
        if v:
            out[k] = _parse_flow(v)
            i += 1
        else:
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                val, i = _parse_block(lines, i, lines[i][0])
            else:
                val = None
            out[k] = val
    return out, i


def _split_key(item: str):
    m = item.find(":")
    if m < 0:
        raise ConfigError(f"expected 'key: value', got {item!r}")
    return item[:m].strip(), item[m + 1:].strip()


def _load_yaml(text: str):
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _mini_yaml(text)


# --------------------------------------------------------------------------
# Config assembly
# --------------------------------------------------------------------------

def load_config(path: str) -> Config:
    if not os.path.exists(path):
        raise ConfigError(f"config file not found: {path} (run `python -m citation_monitor init` first)")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        data = _load_yaml(text)
    except ConfigError:
        raise
    except Exception as exc:  # malformed yaml
        raise ConfigError(f"could not parse {path}: {exc}")
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")

    brand_raw = data.get("brand") or {}
    name = str(brand_raw.get("name") or "").strip()
    if not name:
        raise ConfigError("brand.name is required in the config")
    brand = BrandCfg(
        name=name,
        category=str(brand_raw.get("category") or ""),
        descriptor=str(brand_raw.get("descriptor") or ""),
        site_url=str(brand_raw.get("site_url") or ""),
        aliases=[str(a) for a in (brand_raw.get("aliases") or []) if str(a).strip()],
        locales=[str(x) for x in (brand_raw.get("locales") or ["en"])],
    )

    competitors = []
    for c in data.get("competitors") or []:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        competitors.append(CompetitorCfg(
            name=str(c["name"]),
            aliases=[str(a) for a in (c.get("aliases") or []) if str(a).strip()],
        ))

    engines = {}
    engines_raw = data.get("engines") or {}
    for ename in ENGINE_ORDER:
        eraw = engines_raw.get(ename) or {}
        engines[ename] = EngineCfg(
            model=str(eraw.get("model") or DEFAULT_ENGINE_MODELS[ename]),
            enabled=bool(eraw.get("enabled", DEFAULT_ENGINE_ENABLED[ename])),
        )

    run_raw = data.get("run") or {}
    run = RunCfg(
        max_prompts=(run_raw.get("max_prompts") if run_raw.get("max_prompts") is not None else None),
        timeout_seconds=int(run_raw.get("timeout_seconds") or 45),
        storage=str(run_raw.get("storage") or "data/history.db"),
        output_dir=str(run_raw.get("output_dir") or "output"),
    )

    prompts_raw = [str(p) for p in (data.get("prompts") or []) if str(p).strip()]
    if not prompts_raw:
        raise ConfigError("the `prompts:` list is empty — add the buyer questions you want to monitor")

    return Config(path=path, brand=brand, competitors=competitors,
                  engines=engines, run=run, prompts_raw=prompts_raw)


def to_dict(cfg: Config) -> dict:
    return dataclasses.asdict(cfg)


# --------------------------------------------------------------------------
# Starter config template (StableDesk = fictional sample brand: a stablecoin
# invoicing SaaS). `python -m citation_monitor init` writes this to brand.yaml.
# --------------------------------------------------------------------------

TEMPLATE = """\
# AI Answer Citation Monitor — brand config
# Edit the brand block, competitor list and prompts for your product.
# Lines starting with [xx] mark non-English prompts (locale packs).

brand:
  name: StableDesk
  category: crypto invoicing
  descriptor: stablecoin invoicing and subscription billing for freelancers and small businesses
  site_url: https://stabledesk.example
  aliases: ["Stable Desk", "stabledesk.com", "StableDesk.io"]
  locales: ["en", "es"]

# Track the competitors answer engines name instead of you.
competitors:
  - {name: BitPay, aliases: ["bitpay.com"]}
  - {name: Coinbase Commerce, aliases: ["coinbase.com"]}
  - {name: Request Finance, aliases: ["request.finance", "requestfinance.xyz"]}
  - {name: Cryptio, aliases: ["cryptio.co"]}
  - {name: Gnosis Pay, aliases: ["gnosispay.com", "gnosis.com"]}

# Engine models are editable — check provider docs for current free-tier names.
engines:
  groq:
    model: llama-3.1-8b-instant
    enabled: true
  gemini:
    model: gemini-2.5-flash
    enabled: true
  openrouter:
    model: meta-llama/llama-3.1-8b-instruct:free
    enabled: true
  perplexity:
    model: sonar
    enabled: false   # paid API; enable only if you have budget

run:
  max_prompts: null          # null = use all prompts
  timeout_seconds: 45
  storage: data/history.db
  output_dir: output

# ~30 buyer-phrase prompts: "best tool", "alternatives", "how do I solve",
# pricing, and comparison styles — the exact questions buyers ask AI assistants.
prompts:
  - "What is the best tool for invoicing clients in USDC?"
  - "Best stablecoin invoicing software for freelancers"
  - "Top crypto invoicing tools for small businesses"
  - "Best way to send recurring invoices in USDT"
  - "Best crypto billing software for agencies"
  - "Best tool to invoice clients in crypto without chargebacks"
  - "Top platforms for USDC subscription billing"
  - "Best crypto payment tools with built-in invoicing"
  - "BitPay alternatives for invoicing"
  - "Coinbase Commerce alternatives for recurring billing"
  - "Request Finance alternatives for freelancer invoicing"
  - "Gnosis Pay alternatives for business payments"
  - "Cryptio alternatives for crypto accounting and invoicing"
  - "Cheaper alternatives to BitPay invoices"
  - "Alternatives to Coinbase Commerce for international clients"
  - "Open source alternatives to crypto invoicing platforms"
  - "How do I invoice a client in USDT?"
  - "How do freelancers bill clients in crypto?"
  - "How to accept stablecoin payments for services"
  - "How to set up recurring crypto invoices"
  - "How to send an invoice paid in USDC on-chain"
  - "How to handle crypto invoicing for international clients"
  - "How do I get paid in USDC as a remote contractor?"
  - "How to automate monthly crypto billing for retainers"
  - "Cheapest way to accept USDC invoice payments"
  - "Crypto invoicing tools with no monthly fee"
  - "What does it cost to invoice in stablecoins?"
  - "Crypto invoicing software comparison 2026"
  - "My client wants to pay in USDT — what invoicing tool should I use?"
  - "How do I invoice without a bank account using crypto?"
  - "What tools let me bill in stablecoins and track taxes?"
  - "Is there a simple tool for monthly stablecoin invoices?"
  - "[es] Cuál es la mejor herramienta para facturar en USDT"
  - "[es] Cómo facturar a clientes en criptomonedas desde Argentina"
  - "[es] Alternativas a BitPay para facturación"
  - "[es] Cómo recibir pagos en USDC como freelancer"
"""
