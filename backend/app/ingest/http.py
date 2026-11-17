"""Shared HTTP client: UA, timeout, per-host rate limiting and retries."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

RETRY_STATUS = {429, 500, 502, 503, 504}

# 东财 push2 系列边缘会对非 Windows 原生 TLS 栈（OpenSSL / BoringSSL）在 TLS 握手
# 完成后直接丢弃 HTTP 请求，httpx 只能看到 RemoteProtocolError("Server disconnected
# without sending a response.")。系统自带的 curl.exe 走 Schannel，能正常拿到响应，
# 因此对这类拒绝改用 curl 兜底；某个 host 走通一次后记住它，后续请求直接走 curl。
CURL_ONLY_HOSTS: set[str] = set()
CURL_STATUS_MARKER = b"\n__EPIC_CURL_STATUS__:"


def _parse_curl_output(raw: bytes) -> tuple[int, bytes]:
    """Split `curl -w <marker>%{http_code}` output into (status, body)."""
    idx = raw.rfind(CURL_STATUS_MARKER)
    if idx < 0:
        return 0, raw
    try:
        status = int(raw[idx + len(CURL_STATUS_MARKER) :].strip())
    except ValueError:
        return 0, raw
    return status, raw[:idx]


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        min_interval: float = 0.35,
        retries: int = 3,
        headers: dict[str, str] | None = None,
        ipv4_only: bool = True,
        curl_fallback: bool = True,
    ) -> None:
        # 东财 push2 系列的 AAAA 边缘节点在 TLS 握手后直接断开 HTTP 请求
        # （RemoteProtocolError / curl 56），而 IPv4 边缘正常；本机 IPv6 到这些
        # CDN 只有这一条坏路径。绑定 0.0.0.0 让 httpcore 只用 AF_INET 连接。
        transport = httpx.HTTPTransport(local_address="0.0.0.0") if ipv4_only else None
        self._headers = {"User-Agent": DEFAULT_UA, **(headers or {})}
        self._client = httpx.Client(
            headers=self._headers,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._timeout = timeout
        self._min_interval = min_interval
        self._retries = retries
        self._curl_fallback = curl_fallback
        self._curl_bin: str | None = None
        self._curl_resolved = False
        self._last_request: dict[str, float] = {}

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self._min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _curl_path(self) -> str | None:
        if not self._curl_resolved:
            self._curl_resolved = True
            self._curl_bin = shutil.which("curl")
        return self._curl_bin

    def _get_via_curl(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """GET through the OS curl (Schannel on Windows) and adapt it to httpx."""
        curl = self._curl_path()
        if curl is None:
            raise httpx.ConnectError("curl not found for TLS-fingerprint fallback")
        target = str(httpx.URL(url, params=params))
        command = [
            curl,
            "-4",
            "-sS",
            "--max-time",
            str(max(1, int(self._timeout))),
            "-H",
            f"User-Agent: {self._headers.get('User-Agent', DEFAULT_UA)}",
            "-o",
            "-",
            "-w",
            CURL_STATUS_MARKER.decode("ascii") + "%{http_code}",
            target,
        ]
        for key, value in (headers or {}).items():
            command += ["-H", f"{key}: {value}"]
        try:
            proc = subprocess.run(command, capture_output=True, timeout=self._timeout + 10)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise httpx.TransportError(f"curl fallback failed: {type(exc).__name__}") from exc
        status, body = _parse_curl_output(proc.stdout)
        if status == 0:
            detail = proc.stderr.decode("utf-8", "replace").strip()[:200]
            raise httpx.TransportError(f"curl fallback failed (exit {proc.returncode}): {detail}")
        return httpx.Response(status, content=body, request=httpx.Request("GET", target))

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
        retries: int | None = None,
    ) -> httpx.Response:
        # retries=None 用构造时的默认值；调用方（例如有备用通道的报价接口）可以要求
        # 只试一次、快速失败，把重试留给整条兜底链路，避免每个标的都卡好几秒。
        attempts = retries if retries is not None else self._retries
        host = urlparse(url).netloc
        use_curl = self._curl_fallback and host in CURL_ONLY_HOSTS
        if use_curl:
            self._throttle(host)
            return self._get_via_curl(url, headers=headers, params=params)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url, headers=headers, params=params)
                if resp.status_code in RETRY_STATUS and attempt < attempts:
                    logger.warning("retry %s %s (status %s)", attempt, url, resp.status_code)
                    time.sleep(0.8 * attempt)
                    continue
                return resp
            except httpx.RemoteProtocolError as exc:
                # 对端在 TLS 之后直接断开：本机 TLS 指纹被边缘风控，换 Schannel 的 curl。
                last_exc = exc
                if self._curl_fallback and self._curl_path() is not None:
                    logger.info("httpx rejected by %s (%s); retrying via curl", host, type(exc).__name__)
                    resp = self._get_via_curl(url, headers=headers, params=params)
                    CURL_ONLY_HOSTS.add(host)
                    return resp
                logger.warning("retry %s %s (%s)", attempt, url, type(exc).__name__)
                if attempt < attempts:
                    time.sleep(0.8 * attempt)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning("retry %s %s (%s)", attempt, url, type(exc).__name__)
                if attempt < attempts:
                    time.sleep(0.8 * attempt)
        assert last_exc is not None
        raise last_exc

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc_info) -> None:  # noqa: ANN002
        self.close()
