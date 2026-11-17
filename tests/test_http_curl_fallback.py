"""Offline tests for the curl (Schannel) fallback in the shared HTTP client."""

from __future__ import annotations

import httpx

from app.ingest import http as ingest_http


def _response(url: str, *, status: int = 200, body: bytes = b"{}") -> httpx.Response:
    return httpx.Response(status, content=body, request=httpx.Request("GET", url))


class _BrokenHTTPX:
    """Stands in for httpx.Client against an edge that drops requests after TLS."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, *, headers=None, params=None) -> httpx.Response:  # noqa: ANN001
        self.calls.append(str(httpx.URL(url, params=params)))
        raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

    def close(self) -> None:
        pass


def test_parse_curl_output_splits_status_from_body():
    status, body = ingest_http._parse_curl_output(b'{"data":1}\n__EPIC_CURL_STATUS__:200')
    assert status == 200
    assert body == b'{"data":1}'


def test_parse_curl_output_rejects_missing_or_bad_marker():
    assert ingest_http._parse_curl_output(b'{"data":1}') == (0, b'{"data":1}')
    broken = b"oops\n__EPIC_CURL_STATUS__:not-a-code"
    assert ingest_http._parse_curl_output(broken) == (0, broken)


def test_remote_protocol_error_switches_host_to_curl(monkeypatch):
    ingest_http.CURL_ONLY_HOSTS.clear()
    client = ingest_http.HttpClient()
    broken = _BrokenHTTPX()
    client._client = broken
    client._curl_resolved = True
    client._curl_bin = "curl"
    seen: list[str] = []

    def fake_curl(url, *, headers=None, params=None):  # noqa: ANN001
        seen.append(str(httpx.URL(url, params=params)))
        return _response(url)

    monkeypatch.setattr(client, "_get_via_curl", fake_curl)
    resp = client.get("https://push2.eastmoney.com/api/qt/stock/get", params={"secid": "1.000300"})
    assert resp.status_code == 200
    assert len(broken.calls) == 1
    assert len(seen) == 1
    assert "secid=1.000300" in seen[0]
    assert "push2.eastmoney.com" in ingest_http.CURL_ONLY_HOSTS

    # 记住的 host 后续请求直接走 curl，不再浪费一次 httpx 握手
    client.get("https://push2.eastmoney.com/api/qt/stock/trends2/get")
    assert len(broken.calls) == 1
    assert len(seen) == 2
    client.close()
    ingest_http.CURL_ONLY_HOSTS.clear()


def test_remote_protocol_error_without_curl_is_raised():
    ingest_http.CURL_ONLY_HOSTS.clear()
    client = ingest_http.HttpClient(retries=1)
    broken = _BrokenHTTPX()
    client._client = broken
    client._curl_resolved = True
    client._curl_bin = None
    try:
        client.get("https://push2.eastmoney.com/api/qt/stock/get")
    except httpx.RemoteProtocolError:
        pass
    else:  # pragma: no cover - 必须抛出
        raise AssertionError("RemoteProtocolError should propagate when curl is unavailable")
    finally:
        client.close()
