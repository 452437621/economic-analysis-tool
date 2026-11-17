"""报价优先源：东财的 100.NDX 实际是纳斯达克综合指数，NDX 必须优先走腾讯。

回归保护：2026-11-16 盘中东财 NDX 报价 24817.5（纳斯达克综合），日线却换成了腾讯的
纳斯达克100（27943.74），同一页面差出 11%。这里锁住「NDX 只从腾讯取、不再打东财」。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ingest import pipeline
from app.ingest.contracts import Quote
from app.ingest.symbols import EM_QUOTE_SECID, TENCENT_QUOTE, TENCENT_QUOTE_PREFERRED


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args) -> bool:  # noqa: ANN002
        return False


class _FakeSession(_FakeClient):
    """collect_quotes 只依赖 session 的少数方法，其余（execute/flush…）当无操作。"""

    def __getattr__(self, name: str):  # noqa: ANN401
        return lambda *args, **kwargs: None


class _FakeStore:
    def __init__(self) -> None:
        self.groups: list[tuple[object, list[str]]] = []

    def get_source(self, session, **kwargs):  # noqa: ANN001, ANN003, ANN201
        return SimpleNamespace(id=kwargs.get("name") or "src")

    def upsert_quotes(self, session, quotes, symbol_ids, source_id, **kwargs):  # noqa: ANN001, ANN003, ANN201
        self.groups.append((source_id, [quote.symbol for quote in quotes]))
        return len(quotes)

    def record_health(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass


def test_ndx_quote_prefers_tencent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_store = _FakeStore()
    em_symbols: list[str] = []
    tencent_calls: list[dict[str, str]] = []

    def fake_em_quote(client, secid, symbol):  # noqa: ANN001, ANN202
        em_symbols.append(symbol)
        return Quote(symbol=symbol, ts=None, price=1.0)

    def fake_tencent_quotes(client, mapping):  # noqa: ANN001, ANN202
        tencent_calls.append(dict(mapping))
        return {
            symbol: Quote(symbol=symbol, ts=None, price=27464.28)
            for symbol in mapping.values()
            if symbol in TENCENT_QUOTE_PREFERRED
        }

    monkeypatch.setattr(pipeline, "HttpClient", _FakeClient)
    monkeypatch.setattr(pipeline, "SessionLocal", _FakeSession)
    monkeypatch.setattr(pipeline, "store", fake_store)
    monkeypatch.setattr(pipeline, "_quote_symbols", lambda session: {})
    monkeypatch.setattr(pipeline.sina, "fetch_domestic_quotes", lambda *a, **k: {})
    monkeypatch.setattr(pipeline.sina, "fetch_overseas_quotes", lambda *a, **k: {})
    monkeypatch.setattr(pipeline.sina, "fetch_fx_quotes", lambda *a, **k: {})
    monkeypatch.setattr(pipeline.sina, "fetch_global_quotes", lambda *a, **k: {}, raising=False)
    monkeypatch.setattr(pipeline.tencent, "fetch_quotes", fake_tencent_quotes)
    monkeypatch.setattr(pipeline.eastmoney, "fetch_quote", fake_em_quote)

    pipeline.collect_quotes()

    # NDX 走腾讯且只走了一次（映射方向是 code→symbol），东财循环里被跳过
    assert tencent_calls == [{"usNDX": "NDX"}]
    assert "NDX" not in em_symbols
    assert "SPX" in em_symbols
    assert len([s for _, symbols in fake_store.groups for s in symbols if s == "NDX"]) == 1


def test_preferred_symbols_have_fallback_codes() -> None:
    """优先源挂掉时会退回 TENCENT_QUOTE 兜底，两张表必须都有代码。"""
    assert TENCENT_QUOTE_PREFERRED["NDX"] == "usNDX"
    for symbol, code in TENCENT_QUOTE_PREFERRED.items():
        assert TENCENT_QUOTE[symbol] == code
    # 东财 secid 仍保留（腾讯整组失败时的退路），注释说明了两者口径不同
    assert EM_QUOTE_SECID["NDX"] == "100.NDX"
