"""HTTP helper: prefers `requests`, falls back to stdlib urllib so the
package runs with zero third-party dependencies. Never raises past the
retry wrapper except as EngineError in callers.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - exercised only without requests
    requests = None

RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def post_json(url: str, *, headers: dict, json_body: dict, timeout: float,
              retries: int = 1, backoff_seconds: float = 4.0) -> dict:
    """POST JSON, return parsed JSON body. Retries once on 429/5xx/timeout."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            if requests is not None:
                resp = requests.post(url, headers=headers, json=json_body, timeout=timeout)
                if resp.status_code in RETRY_STATUS and attempt < retries:
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    time.sleep(backoff_seconds)
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
                time.sleep(backoff_seconds)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            if attempt < retries:
                last_err = exc
                time.sleep(backoff_seconds)
                continue
            raise
        except Exception as exc:  # requests' HTTPError etc.
            status = getattr(exc, "response", None)
            status_code = getattr(status, "status_code", None)
            if status_code in RETRY_STATUS and attempt < retries:
                last_err = exc
                time.sleep(backoff_seconds)
                continue
            raise
    raise last_err if last_err else RuntimeError("unreachable")
