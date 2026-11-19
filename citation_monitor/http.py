"""HTTP helper: prefers `requests`, falls back to stdlib urllib so the
package runs with zero third-party dependencies. Never raises past the
retry wrapper except as EngineError in callers.

Retries use exponential backoff and honour `Retry-After` (Gemini sends it on
429). Free tiers throttle aggressively, so the default is 3 retries; the
engines also pace themselves (see BaseEngine.min_interval) to avoid bursting.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - exercised only without requests
    requests = None

RETRY_STATUS = {408, 429, 500, 502, 503, 504}

# Some hosts (this one included) have broken IPv6 egress: TCP connects but the
# response never arrives, so every call burns its full timeout. urllib/requests
# use the first getaddrinfo result — put IPv4 first unless explicitly disabled.
if os.environ.get("CITATION_MONITOR_IPV6", "") != "1":
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_first(host, port, *args, **kwargs):
        infos = _orig_getaddrinfo(host, port, *args, **kwargs)
        return sorted(infos, key=lambda i: 0 if i[0] == socket.AF_INET else 1)

    socket.getaddrinfo = _ipv4_first
MAX_SLEEP_SECONDS = 60.0


def _sleep(attempt: int, backoff_seconds: float, headers=None) -> None:
    """Exponential backoff, stretched to Retry-After when the server sends one."""
    delay = backoff_seconds * (2 ** attempt)
    if headers is not None:
        raw = headers.get("Retry-After")
        try:
            if raw is not None:
                delay = max(delay, float(raw))
        except (TypeError, ValueError):
            pass
    time.sleep(min(MAX_SLEEP_SECONDS, max(1.0, delay)))


def post_json(url: str, *, headers: dict, json_body: dict, timeout: float,
              retries: int = 3, backoff_seconds: float = 5.0) -> dict:
    """POST JSON, return parsed JSON body. Retries with backoff on 429/5xx/timeout."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            if requests is not None:
                resp = requests.post(url, headers=headers, json=json_body, timeout=timeout)
                if resp.status_code in RETRY_STATUS:
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    if attempt < retries:
                        _sleep(attempt, backoff_seconds, resp.headers)
                        continue
                resp.raise_for_status()
                return resp.json()
            data = json.dumps(json_body).encode("utf-8")
            hdrs = dict(headers)
            hdrs.setdefault("Content-Type", "application/json")
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", None)
            if code in RETRY_STATUS and attempt < retries:
                last_err = exc
                _sleep(attempt, backoff_seconds, getattr(exc, "headers", None))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            if attempt < retries:
                last_err = exc
                _sleep(attempt, backoff_seconds)
                continue
            raise
        except Exception as exc:  # requests' HTTPError etc.
            status = getattr(exc, "response", None)
            status_code = getattr(status, "status_code", None)
            if status_code in RETRY_STATUS and attempt < retries:
                last_err = exc
                _sleep(attempt, backoff_seconds, getattr(status, "headers", None))
                continue
            raise
    raise last_err if last_err else RuntimeError("unreachable")
