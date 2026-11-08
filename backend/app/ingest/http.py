"""Shared HTTP client: UA, timeout, per-host rate limiting and retries."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        min_interval: float = 0.35,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": DEFAULT_UA, **(headers or {})},
            timeout=timeout,
            follow_redirects=True,
        )
        self._min_interval = min_interval
        self._retries = retries
        self._last_request: dict[str, float] = {}

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self._min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(1, self._retries + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url, headers=headers, params=params)
                if resp.status_code in RETRY_STATUS and attempt < self._retries:
                    logger.warning("retry %s %s (status %s)", attempt, url, resp.status_code)
                    time.sleep(0.8 * attempt)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning("retry %s %s (%s)", attempt, url, type(exc).__name__)
                if attempt < self._retries:
                    time.sleep(0.8 * attempt)
        assert last_exc is not None
        raise last_exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc_info) -> None:  # noqa: ANN002
        self.close()
