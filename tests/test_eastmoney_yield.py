"""东财「中美国债收益率」报表的翻页逻辑。

只请求第 1 页曾经让中国国债收益率序列只从 2024-12 开始（一页封顶 500 行，
全量 9389 行 / 19 页），历史趋势图看起来「突然从某天起才有数据」。
"""

from __future__ import annotations

from app.ingest.providers import eastmoney_yield


class _FakeResponse:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"result": {"data": self._rows}}


class _FakeResponse:
    def __init__(self, rows: list[dict], total_pages: int = 1) -> None:
        self._rows = rows
        self._total_pages = total_pages

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"result": {"data": self._rows, "pages": self._total_pages}}


class _FakeClient:
    """按 pageNumber 返回不同页数据，并记录请求过的页码。"""

    def __init__(self, pages: dict[int, list[dict]], total_pages: int) -> None:
        self._pages = pages
        self._total_pages = total_pages
        self.requested: list[int] = []

    def get(self, _url, params=None, **_kwargs):  # noqa: ANN001
        page = int(params["pageNumber"])
        self.requested.append(page)
        assert params["pageSize"] == eastmoney_yield.PAGE_SIZE
        rows = self._pages.get(page, [])
        return _FakeResponse(rows, self._total_pages)


def _row(day: str, value: float | None = 2.0) -> dict:
    fields = {field: value for field in eastmoney_yield.FIELDS.values()}
    return {"SOLAR_DATE": f"{day} 00:00:00", **fields}


class _FakeResponse:
    def __init__(self, rows: list[dict], total_pages: int) -> None:
        self._rows = rows
        self._total_pages = total_pages

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"result": {"data": self._rows, "pages": self._total_pages}}


def test_fetch_rates_walks_every_page():
    """第 2 页的数据必须被收进来，否则历史会被截断在「第一页最老一天」。"""
    client = _FakeClient(
        {
            1: [_row("2026-11-16"), _row("2026-11-13")],  # 每页按日期倒序
            2: [_row("2025-01-02"), _row("2024-12-31")],
        },
        total_pages=2,
    )
    out = eastmoney_yield.fetch_rates(client, start_year=2022)
    assert client.requested == [1, 2]
    days = [point.ts.date().isoformat() for point in out["CN10Y"]]
    assert days == ["2024-12-31", "2025-01-02", "2026-11-13", "2026-11-16"]
    assert len(out["CN2Y"]) == 4


def test_fetch_rates_stops_when_page_reaches_start_year():
    """翻到早于 start_year 的页就停，不再无意义地翻到底。"""
    client = _FakeClient(
        {
            1: [_row("2026-11-16")],
            2: [_row("2023-06-30"), _row("2023-06-29")],
            3: [_row("2021-01-04")],
        },
        total_pages=19,
    )
    out = eastmoney_yield.fetch_rates(client, start_year=2022)
    assert client.requested == [1, 2, 3]
    assert {point.ts.date().isoformat() for point in out["CN10Y"]} == {
        "2026-11-16", "2023-06-30", "2023-06-29",
    }


def test_fetch_rates_handles_empty_and_bad_rows():
    bad = {"SOLAR_DATE": "not-a-date", **{field: None for field in eastmoney_yield.FIELDS.values()}}
    client = _FakeClient({1: [bad, _row("2026-11-16", None)]}, total_pages=19)
    out = eastmoney_yield.fetch_rates(client, start_year=2022)
    # 第 1 页全是坏行/空值 → 继续翻到第 2 页（空页）才停。
    assert client.requested == [1, 2]
    assert all(points == [] for points in out.values())


def test_fetch_rates_default_start_year_is_recent():
    """不传 start_year 时默认回溯 4 年。"""
    client = _FakeClient({1: [_row("2026-11-16")]}, total_pages=1)
    out = eastmoney_yield.fetch_rates(client, start_year=None)
    assert len(out["CN10Y"]) == 1


def test_page_size_matches_server_cap():
    """服务端一页封顶 500 行：pageSize 写大了也不会多给，翻页才是唯一出路。"""
    assert eastmoney_yield.PAGE_SIZE == 500
    assert eastmoney_yield.MAX_PAGES >= 19
