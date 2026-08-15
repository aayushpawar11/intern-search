"""Rate-limited HTTP session with retries and polite delays."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

logger = logging.getLogger("intern_monitor")

SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15"
)

try:
    from curl_cffi import requests as http_lib

    _IMPERSONATE = "safari184"
    _USING = "curl_cffi"
except ImportError:  # pragma: no cover
    import requests as http_lib

    _IMPERSONATE = None
    _USING = "requests"


class RateLimitedSession:
    """One shared session for all career-page requests."""

    def __init__(self, min_delay: float = 1.5, timeout: float = 25.0) -> None:
        self.min_delay = min_delay
        self.timeout = timeout
        self._last_request = 0.0
        kwargs: dict[str, Any] = {}
        if _IMPERSONATE:
            kwargs["impersonate"] = _IMPERSONATE
        self.session = http_lib.Session(**kwargs)
        self.session.headers.update(
            {
                "User-Agent": SAFARI_UA,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        logger.debug("HTTP backend: %s", _USING)

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        pause = self.min_delay + random.uniform(0.1, 0.6)
        if elapsed < pause:
            time.sleep(pause - elapsed)
        self._last_request = time.monotonic()

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: Any | None = None,
        form_data: Any | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        allow_redirects: bool = True,
    ):
        self._wait()
        extra = headers or {}
        logger.debug("%s %s", method, url)
        kwargs: dict[str, Any] = {
            "params": params,
            "headers": extra,
            "timeout": self.timeout,
            "allow_redirects": allow_redirects,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        if form_data is not None:
            kwargs["data"] = form_data
        if _IMPERSONATE:
            kwargs["impersonate"] = _IMPERSONATE
        resp = self.session.request(method, url, **kwargs)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After") or 8)
            logger.warning("Rate limited on %s; sleeping %.1fs", url, retry_after)
            time.sleep(retry_after)
            self._last_request = time.monotonic()
            resp = self.session.request(method, url, **kwargs)
        return resp

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)
