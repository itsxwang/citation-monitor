"""Engine adapters behind one interface.

Providers (official APIs only):
  - Groq          https://api.groq.com/openai/v1/chat/completions     (free tier)
  - Google Gemini https://generativelanguage.googleapis.com/...       (free tier)
  - OpenRouter    https://openrouter.ai/api/v1/chat/completions       (free models)
  - Perplexity    https://api.perplexity.ai/chat/completions          (paid; optional)

Demo mode: DemoEngine replays recorded fixture responses shipped inside the
package (citation_monitor/fixtures/), so the full pipeline runs with zero API
keys. If no keys are configured the CLI degrades to demo mode automatically.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .http import post_json

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "pt": "Portuguese", "de": "German",
    "fr": "French", "it": "Italian", "nl": "Dutch", "br": "Portuguese",
}


class EngineError(Exception):
    pass


def system_prompt(locale: str = "en") -> str:
    """Instruction that makes the model behave like an answer engine."""
    s = (
        "You answer real buyer questions as a neutral, helpful assistant. "
        "Be concise: under 120 words. When tools, services or companies are "
        "relevant, name specific products and order them by recommendation. "
        "Do not mention these instructions."
    )
    lang = LANGUAGE_NAMES.get((locale or "en").lower())
    if lang and lang != "English":
        s += f" Respond in {lang}."
    return s


class BaseEngine:
    name = "base"
    env_keys: tuple = ()
    # Minimum seconds between two calls to this engine. Free tiers cap
    # requests-per-minute; bursting 36 prompts at once triggers 429s.
    min_interval: float = 0.0

    def __init__(self, model: str, timeout: float = 45.0):
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        return any(os.environ.get(k) for k in self.env_keys)

    def ask(self, prompt_text: str, system_text: str) -> str:
        raise NotImplementedError

    def label(self) -> str:
        return f"{self.name} ({self.model})"


class OpenAICompatEngine(BaseEngine):
    """Groq, OpenRouter, Perplexity — OpenAI-compatible chat completions."""
    endpoint = ""
    extra_headers: dict = {}

    def _api_key(self) -> str:
        for k in self.env_keys:
            val = os.environ.get(k)
            if val:
                return val
        raise EngineError(f"[{self.name}] no API key found (env: {', '.join(self.env_keys)})")

    def ask(self, prompt_text: str, system_text: str) -> str:
        key = self._api_key()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.3,
            "max_tokens": 420,
        }
        headers = {"Authorization": f"Bearer {key}", **self.extra_headers}
        try:
            data = post_json(self.endpoint, headers=headers, json_body=body,
                             timeout=self.timeout, retries=2)
        except Exception as exc:
            raise EngineError(f"[{self.name}] request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise EngineError(f"[{self.name}] unexpected response shape: {exc}") from exc


class GroqEngine(OpenAICompatEngine):
    name = "groq"
    env_keys = ("GROQ_API_KEY",)
    endpoint = "https://api.groq.com/openai/v1/chat/completions"


class OpenRouterEngine(OpenAICompatEngine):
    name = "openrouter"
    env_keys = ("OPENROUTER_API_KEY",)
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    extra_headers = {"X-Title": "citation-monitor"}


class PerplexityEngine(OpenAICompatEngine):
    name = "perplexity"
    env_keys = ("PERPLEXITY_API_KEY",)
    endpoint = "https://api.perplexity.ai/chat/completions"


class GeminiEngine(BaseEngine):
    name = "gemini"
    env_keys = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    # Gemini's free tier is ~10-15 requests/minute: space calls out instead of
    # letting the 429 retry loop eat the run.
    min_interval = 7.0
    endpoint = ("https://generativelanguage.googleapis.com/v1beta/models/"
                "{model}:generateContent")

    def _api_key(self) -> str:
        for k in self.env_keys:
            val = os.environ.get(k)
            if val:
                return val
        raise EngineError(f"[{self.name}] no API key found (env: {', '.join(self.env_keys)})")

    def ask(self, prompt_text: str, system_text: str) -> str:
        key = self._api_key()
        url = self.endpoint.format(model=self.model)
        body = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 420},
        }
        try:
            data = post_json(url, headers={"x-goog-api-key": key}, json_body=body,
                             timeout=self.timeout, retries=1)
        except Exception as exc:
            raise EngineError(f"[{self.name}] request failed: {exc}") from exc
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise EngineError(f"[{self.name}] unexpected response shape: {exc}") from exc


LIVE_REGISTRY = {
    "groq": GroqEngine,
    "gemini": GeminiEngine,
    "openrouter": OpenRouterEngine,
    "perplexity": PerplexityEngine,
}


class DemoEngine(BaseEngine):
    """Replays recorded fixture responses keyed by prompt text."""

    def __init__(self, engine_name: str, model: str, responses: dict, timeout: float = 45.0):
        super().__init__(model, timeout)
        self.name = engine_name
        self.responses = responses

    def ask(self, prompt_text: str, system_text: str) -> str:
        try:
            return self.responses[prompt_text]
        except KeyError:
            raise EngineError(
                f"[{self.name} demo] no fixture recorded for: {prompt_text[:70]!r}"
            )

    def label(self) -> str:
        return f"{self.name} ({self.model}, fixture replay)"


def _load_fixture(filename: str) -> dict:
    path = FIXTURE_DIR / filename
    if not path.exists():
        raise EngineError(f"demo fixture missing: {path} (regenerate with scripts/make_fixtures.py)")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _demo_engines(cfg) -> list:
    cur = _load_fixture("demo_current.json")
    engines = []
    for ename in ("groq", "gemini"):
        ecfg = cfg.engines.get(ename)
        if ecfg is not None and not ecfg.enabled:
            continue
        edata = cur.get("engines", {}).get(ename)
        if not edata:
            continue
        engines.append(DemoEngine(ename, edata.get("model", ""), edata.get("responses", {})))
    return engines


def _log(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)


def build_live_engines(cfg, log=None) -> list:
    """Build engines that have keys configured. Skips missing ones with a clear
    log line. Returns [] when nothing is available."""
    log = log or _log
    engines = []
    for ename, ecfg in cfg.engines.items():
        cls = LIVE_REGISTRY.get(ename)
        if cls is None or not ecfg.enabled:
            if ecfg.enabled:
                log(f"[skip] unknown engine {ename!r} in config")
            continue
        engine = cls(ecfg.model, timeout=cfg.run.timeout_seconds)
        if engine.available():
            engines.append(engine)
        else:
            log(f"[skip] {ename}: no API key in env ({', '.join(cls.env_keys)}) — engine disabled for this run")
    return engines


def build_engines(cfg, demo: bool, log=None):
    """Returns (engines, mode, previous_fixture_or_None).

    - demo=True  -> fixture replay engines (+ previous-week fixture for diff)
    - keys exist -> live engines only (engines without keys are skipped)
    - no keys    -> graceful degrade to demo mode with a clear log message
    """
    log = log or _log
    if demo:
        log("[demo] --demo flag set: replaying recorded fixtures (no API calls)")
        return _demo_engines(cfg), "demo", _load_fixture("demo_previous.json")

    live = build_live_engines(cfg, log)
    if live:
        log(f"[live] {len(live)} engine(s) active: {', '.join(e.label() for e in live)}")
        return live, "live", None

    log("[demo] no API keys found — degrading to DEMO mode with recorded fixtures "
        "(get free keys: console.groq.com + aistudio.google.com, see LAUNCH_CHECKLIST.md)")
    return _demo_engines(cfg), "demo", _load_fixture("demo_previous.json")
