"""Assemble the Luoyang topic ``TopicOverview`` payload."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.topics import storage
from app.topics.config import TopicSpec
from app.topics.luoyang import analysis
from app.topics.luoyang.data import LuoyangData, load_data

DISCLAIMER = "本页为研究辅助，所有结论均为公开数据的量化推演，不构成投资建议。"

CAVEATS = [
    "财务数据为年内累计口径，TTM = 上年年报 + 本期累计 − 上年同期累计。",
    "主力资金流接口通常仅覆盖约 120 个交易日，资金面结论只覆盖近半年。",
    "估值序列自 2018 年起，5 年分位窗口为 2021 年至今。",
    "钴/钼/钨无公开现货日线，若使用同业股价代理，不能当作现货价格。",
    "持仓成本与回本使用不复权价格；收益与因子使用前复权价格。",
]


def _fmt(value: Any, digits: int = 2) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return round(number, digits)


def _normalized(series: pd.Series) -> list[float | None]:
    cleaned = pd.to_numeric(series, errors="coerce")
    base = cleaned.dropna()
    if base.empty or float(base.iloc[0]) == 0:
        return [None for _ in cleaned]
    first = float(base.iloc[0])
    return [_fmt((value / first - 1) * 100, 2) if pd.notna(value) else None for value in cleaned]


def _kpis(data: LuoyangData, valuation_block: dict, technical_block: dict, position_block: dict, scenario_block: dict) -> list[dict[str, Any]]:
    panel = data.panel
    last = panel.iloc[-1] if not panel.empty else {}
    items: list[dict[str, Any]] = []

    def add(key: str, label: str, value: Any, unit: str, note: str = "", tone: str = "flat") -> None:
        items.append({"key": key, "label": label, "value": _fmt(value) if isinstance(value, (int, float)) else value, "unit": unit, "note": note, "tone": tone})

    snapshot = data.snapshots.get("a") or {}
    price_date = snapshot.get("as_of") or (data.latest_date.isoformat() if data.latest_date else "—")
    add("price", "最新价", data.latest_price, "元", f"截至 {price_date}")
    add("pct_chg", "当日涨跌", snapshot.get("pct_chg") if snapshot.get("pct_chg") is not None else (last.get("pct_chg") if hasattr(last, "get") else None), "%", "", "up" if (_fmt(snapshot.get("pct_chg") or last.get("pct_chg")) or 0) >= 0 else "down")
    cap = _fmt(last.get("total_market_cap")) if hasattr(last, "get") else None
    add("market_cap", "总市值", cap / 1e8 if cap is not None else None, "亿元")
    add("pe_ttm", "PE(TTM)", valuation_block.get("pe_ttm"), "x", "周期股需结合 PB/EV 看")
    add("pb_mrq", "PB(MRQ)", valuation_block.get("pb_mrq"), "x", "5 年分位见估值分区")
    add("ev_ebitda", "EV/EBITDA 法每股价值", (scenario_block.get("scenarios", {}).get("base") or {}).get("target_ev_ebitda"), "元", "目标情景下的每股价值，非当前倍数")
    add("div_yield", "股息率", (valuation_block.get("dividend") or {}).get("current_yield_pct"), "%")
    add("rsi14", "RSI14", technical_block.get("rsi14"), "", technical_block.get("rsi14_zone") or "")
    add("technical_score", "技术评分", technical_block.get("technical_score"), "/100", technical_block.get("ma_alignment") or "")
    add("position_pnl", "持仓浮亏", position_block.get("pnl_pct") if position_block.get("ok") else None, "%", "不含分红", "down" if (position_block.get("pnl_pct") or 0) < 0 else "up")
    add("expected_return", "期望收益", (scenario_block.get("weighted") or {}).get("expected_return_pct") if scenario_block.get("ok") else None, "%", "概率加权")
    return items


def _ohlc_usable(ohlc: list[list[float | None]]) -> bool:
    """True when candles carry a real high/low range (not a flat close copy)."""
    complete = [row for row in ohlc if len(row) == 4 and all(value is not None for value in row)]
    if len(complete) < 5:
        return False
    ranged = sum(1 for row in complete if float(row[3]) - float(row[2]) > 1e-9)
    return ranged >= max(5, len(complete) // 10)


def _charts(
    data: LuoyangData,
    position_block: dict,
    technical_block: dict,
    valuation_block: dict,
    factor_block: dict,
    *,
    limit: int = 750,
) -> list[dict[str, Any]]:
    panel = data.panel
    charts: list[dict[str, Any]] = []
    if panel.empty:
        return charts
    tail = panel.tail(max(60, min(int(limit), len(panel))))
    dates = [item.date().isoformat() for item in tail.index]
    ohlc = []
    for _, row in tail.iterrows():
        ohlc.append([_fmt(row.get("open")), _fmt(row.get("close")), _fmt(row.get("low")), _fmt(row.get("high"))])
    marks = []
    buy_price = position_block.get("buy_price") if position_block.get("ok") else None
    if buy_price:
        marks.append({"type": "line", "value": _fmt(buy_price), "label": "成本价", "color": "warn"})
    for support in (technical_block.get("levels") or {}).get("supports", [])[:2]:
        marks.append({"type": "line", "value": support["price"], "label": f"支撑 {support['type']}", "color": "up"})
    for resistance in (technical_block.get("levels") or {}).get("resistances", [])[:2]:
        marks.append({"type": "line", "value": resistance["price"], "label": f"阻力 {resistance['type']}", "color": "down"})
    volume_values = [_fmt(value, 0) for value in tail.get("volume", pd.Series(dtype=float))]
    if _ohlc_usable(ohlc):
        charts.append(
            {
                "key": "price_kline",
                "title": "日 K 线",
                "subtitle": "前复权价格 · 成本线与支撑/阻力（成本线按不复权口径）",
                "kind": "candlestick",
                "unit": "元",
                "height": 380,
                "wide": True,
                "dates": dates,
                "ohlc": ohlc,
                "series": [
                    {
                        "name": "成交量",
                        "type": "bar",
                        "axis": 1,
                        "values": volume_values,
                    }
                ],
                "marks": marks,
                "note": "持仓成本用不复权价；技术支撑/阻力由摆动点、成交密集区、均线与 52 周高低聚合。",
                "hasData": True,
            }
        )
    else:
        # Upstream has no real open/high/low: a candlestick would render as
        # invisible flat bars, so show the close line instead.
        close_values = [_fmt(value, 3) for value in tail.get("close", pd.Series(dtype=float))]
        series: list[dict[str, Any]] = [{"name": "收盘价", "values": close_values, "axis": 0}]
        if any(value is not None for value in volume_values):
            series.append({"name": "成交量", "type": "bar", "axis": 1, "values": volume_values})
        charts.append(
            {
                "key": "price_kline",
                "title": "日 K 线",
                "subtitle": "上游未提供开高低收，暂以收盘价折线展示",
                "kind": "line",
                "unit": "元",
                "height": 380,
                "wide": True,
                "dates": dates,
                "series": series,
                "marks": marks,
                "note": "行情端点未返回 OHLC/成交量；价格与持仓成本仍按收盘价与快照价计算。",
                "hasData": any(value is not None for value in close_values),
            }
        )
    if "shfe_cu" in panel.columns and panel["shfe_cu"].notna().any():
        copper = tail["shfe_cu"].ffill()
        charts.append(
            {
                "key": "price_vs_copper",
                "title": "股价 vs 沪铜",
                "subtitle": "归一化（区间起点 = 0%）",
                "kind": "line",
                "unit": "%",
                "height": 280,
                "dates": dates,
                "series": [
                    {"name": "洛阳钼业", "values": _normalized(tail["close"]), "axis": 0},
                    {"name": "沪铜主连", "values": _normalized(copper), "axis": 0},
                ],
                "note": "铜价是公司盈利与股价的核心驱动之一。",
                "hasData": True,
            }
        )
    series = valuation_block.get("series") or {}
    if series.get("dates"):
        pe_dates = series["dates"]
        charts.append(
            {
                "key": "pe_band",
                "title": "PE(TTM) 与分位带",
                "subtitle": "1/3/5 年分位见估值分区",
                "kind": "line",
                "unit": "x",
                "height": 260,
                "dates": pe_dates,
                "series": [{"name": "PE(TTM)", "values": series.get("pe_ttm"), "axis": 0}],
                "bands": valuation_block.get("pe_band_5y") or {},
                "note": "周期股盈利高点时 PE 会被系统性压低，PB 更稳定。",
                "hasData": True,
            }
        )
        charts.append(
            {
                "key": "pb_band",
                "title": "PB(MRQ) 与分位带",
                "subtitle": "周期股主锚",
                "kind": "line",
                "unit": "x",
                "height": 260,
                "dates": pe_dates,
                "series": [{"name": "PB(MRQ)", "values": series.get("pb_mrq"), "axis": 0}],
                "bands": valuation_block.get("pb_band_5y") or {},
                "note": "PB 分位是持仓评分的主要估值输入。",
                "hasData": True,
            }
        )
    rolling = factor_block.get("rolling") or {}
    if rolling.get("dates"):
        charts.append(
            {
                "key": "rolling_beta",
                "title": "铜 beta 与相关性",
                "subtitle": "60/120 日滚动",
                "kind": "line",
                "unit": "",
                "height": 260,
                "dates": rolling["dates"],
                "series": [
                    {"name": "β60(沪铜)", "values": rolling.get("beta60_cu"), "axis": 0},
                    {"name": "β120(沪铜)", "values": rolling.get("beta120_cu"), "axis": 0},
                    {"name": "60 日相关", "values": rolling.get("corr60_cu"), "axis": 1},
                ],
                "note": "beta 高说明股价对铜价更敏感；相关性走弱时需警惕背离。",
                "hasData": True,
            }
        )
    flows = factor_block.get("flows") or {}
    if flows.get("ok") and (flows.get("series") or {}).get("dates"):
        flow_series = flows["series"]
        charts.append(
            {
                "key": "flows",
                "title": "主力资金与融资",
                "subtitle": "近 120 个交易日",
                "kind": "combo",
                "unit": "亿元",
                "height": 260,
                "dates": flow_series["dates"],
                "series": [
                    {"name": "主力净流入", "type": "bar", "values": flow_series.get("main_net_yi"), "axis": 0},
                    {"name": "收盘价", "type": "line", "values": flow_series.get("close"), "axis": 1},
                ],
                "note": "东财资金流接口通常只覆盖约 120 个交易日。",
                "hasData": True,
            }
        )
    return charts


def _factor_tables(factor_block: dict) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    leverage = factor_block.get("leverage") or {}
    if leverage.get("ok") and leverage.get("latest"):
        tables.append(
            {
                "id": "leverage",
                "title": "两融杠杆",
                "columns": [
                    {"key": "date", "label": "日期"},
                    {"key": "rz_balance_yi", "label": "融资余额(亿)", "align": "right", "format": "number", "digits": 2},
                    {"key": "rz_change_5d_pct", "label": "5 日变化", "align": "right", "format": "signed", "digits": 2},
                    {"key": "pct_rank_5y", "label": "5 年分位", "align": "right", "format": "number", "digits": 1},
                ],
                "rows": [leverage["latest"]],
                "note": "融资余额反映杠杆资金情绪，分位越高越拥挤。",
            }
        )
    single = (factor_block.get("single_factor") or {}).get("5y", {}).get("single") or {}
    if single:
        rows = [
            {
                "name": value.get("label") or code,
                "beta": value.get("beta"),
                "t": value.get("t"),
                "p": value.get("p"),
                "stars": value.get("stars"),
                "r2": value.get("r2"),
            }
            for code, value in single.items()
            if value.get("ok")
        ]
        tables.append(
            {
                "id": "single_factor",
                "title": "单因子回归（5 年，日频）",
                "columns": [
                    {"key": "name", "label": "因子"},
                    {"key": "beta", "label": "β", "align": "right", "format": "signed", "digits": 3},
                    {"key": "t", "label": "t", "align": "right", "format": "number", "digits": 2},
                    {"key": "p", "label": "p", "align": "right", "format": "number", "digits": 3},
                    {"key": "stars", "label": "显著性"},
                    {"key": "r2", "label": "R²", "align": "right", "format": "number", "digits": 3},
                ],
                "rows": rows,
            }
        )
    multi = (factor_block.get("multifactor") or {}).get("5y") or {}
    if multi.get("ok"):
        rows = [
            {
                "name": key,
                "beta": value.get("beta"),
                "t": value.get("t"),
                "p": value.get("p"),
                "stars": value.get("stars"),
            }
            for key, value in (multi.get("coef") or {}).items()
            if key != "const"
        ]
        tables.append(
            {
                "id": "multifactor",
                "title": "多因子回归（铜 + 沪深300 + 美元 + 汇率，Newey-West）",
                "columns": [
                    {"key": "name", "label": "因子"},
                    {"key": "beta", "label": "β", "align": "right", "format": "signed", "digits": 3},
                    {"key": "t", "label": "t", "align": "right", "format": "number", "digits": 2},
                    {"key": "p", "label": "p", "align": "right", "format": "number", "digits": 3},
                    {"key": "stars", "label": "显著性"},
                ],
                "rows": rows,
                "note": f"R²={multi.get('r2')}，样本 {multi.get('n')}。",
            }
        )
    decomposition = factor_block.get("decomposition") or {}
    if decomposition:
        rows = [
            {
                "period": key,
                "price_chg": value.get("price_chg_pct"),
                "earnings": value.get("contrib_earnings_pctpts"),
                "valuation": value.get("contrib_valuation_pctpts"),
            }
            for key, value in decomposition.items()
        ]
        tables.append(
            {
                "id": "decomposition",
                "title": "收益分解：股价 = 盈利 × 估值",
                "columns": [
                    {"key": "period", "label": "区间"},
                    {"key": "price_chg", "label": "股价变化", "align": "right", "format": "signed", "digits": 2},
                    {"key": "earnings", "label": "盈利贡献", "align": "right", "format": "signed", "digits": 2},
                    {"key": "valuation", "label": "估值贡献", "align": "right", "format": "signed", "digits": 2},
                ],
                "rows": rows,
            }
        )
    lead_lag = factor_block.get("lead_lag") or {}
    if lead_lag:
        rows = [
            {
                "name": value.get("label"),
                "zero": value.get("zero_lag_r"),
                "best_lag": value.get("best_lag"),
                "best_r": value.get("best_r"),
            }
            for value in lead_lag.values()
        ]
        tables.append(
            {
                "id": "lead_lag",
                "title": "领先滞后（因子领先个股为正）",
                "columns": [
                    {"key": "name", "label": "因子"},
                    {"key": "zero", "label": "同期相关", "align": "right", "format": "signed", "digits": 3},
                    {"key": "best_lag", "label": "最佳滞后(日)", "align": "right", "format": "number"},
                    {"key": "best_r", "label": "最佳相关", "align": "right", "format": "signed", "digits": 3},
                ],
                "rows": rows,
            }
        )
    return tables


def build_overview(
    spec: TopicSpec,
    session: Session,
    *,
    config_version: str = "",
    series_limit: int = 750,
    **_kwargs: Any,
) -> dict[str, Any]:
    data = load_data(session, spec.id)
    technical_block = analysis.technicals(data.panel)
    valuation_block = analysis.valuation(data, technical_block)
    factor_block = analysis.factors(data.panel, data)
    assumptions = (spec.params or {}).get("assumptions") or {}
    scenario_block = analysis.scenarios(data, valuation_block, factor_block, assumptions)
    defaults = (spec.params or {}).get("position_defaults") or {}
    overrides, _updated = storage.get_setting(session, spec.id)
    position_block = analysis.position(data, valuation_block, technical_block, scenario_block, defaults, overrides, assumptions)
    event_rows = analysis.events(data, data.panel)
    composite_block = analysis.composite(
        valuation_block,
        technical_block,
        scenario_block,
        factor_block,
        (spec.params or {}).get("score_weights") or {},
    )
    verdict_block = analysis.verdict(composite_block, valuation_block, factor_block, scenario_block, position_block)
    charts = _charts(
        data,
        position_block,
        technical_block,
        valuation_block,
        factor_block,
        limit=series_limit,
    )
    kpis = _kpis(data, valuation_block, technical_block, position_block, scenario_block)
    sources = storage.latest_source_runs(session, spec.id)
    catalog = data.catalog

    hero = {
        "score": composite_block["score"],
        "label": composite_block["label"],
        "coverage": composite_block["coverage"],
        "available_weight": composite_block["combined"]["available_weight"],
        "total_weight": composite_block["combined"]["total_weight"],
        "conclusion": f"{verdict_block['headline']}。{verdict_block['driver']['headline']}",
        "badges": [
            {"label": composite_block["label"], "tone": "up" if composite_block["score"] > 0 else ("down" if composite_block["score"] < 0 else "flat")},
            {"label": f"覆盖率 {composite_block['coverage']:.0f}%", "tone": "flat"},
            {"label": (data.status or "unknown").upper(), "tone": "warn" if data.status != "ok" else "flat"},
        ],
        "drivers": composite_block["factors"],
        "score_0_100": round((composite_block["score"] + 100) / 2, 1),
    }
    if composite_block["coverage"] <= 0:
        hero["score"] = None
        hero["label"] = "数据不足"
        hero["score_0_100"] = None
        hero["conclusion"] = "洛阳钼业专题数据尚未采集。点击「刷新数据」或等待 collect_luoyang 任务完成后即可生成研判。"
        hero["badges"] = [{"label": "数据不足", "tone": "warn"}]
        hero["drivers"] = []

    sections: list[dict[str, Any]] = []
    for section in spec.sections:
        if not section.enabled:
            continue
        if section.kind == "hero":
            data_out: Any = hero
        elif section.kind == "kpis":
            data_out = {"items": kpis}
        elif section.kind == "charts":
            data_out = {"charts": charts}
        elif section.kind == "table":
            tables = _factor_tables(factor_block)
            if not tables:
                tables = [{"id": "empty", "title": "因子归因", "columns": [], "rows": [], "note": "因子数据不足"}]
            data_out = {"tables": tables, "note": "收益分解使用对数口径：ln(P) = ln(EPS) + ln(PE)。"}
        elif section.kind == "valuation":
            data_out = {
                **valuation_block,
                "scorecards": valuation_block.get("scorecard") or [],
                "peers": (valuation_block.get("relative") or {}).get("peers") or [],
                "relative": valuation_block.get("relative") or {},
            }
        elif section.kind == "scenarios":
            data_out = {
                **scenario_block,
                "methods": [
                    {"name": "PE band", "weight": (assumptions.get("method_weights") or {}).get("pe_band")},
                    {"name": "PB band", "weight": (assumptions.get("method_weights") or {}).get("pb_band")},
                    {"name": "EV/EBITDA", "weight": (assumptions.get("method_weights") or {}).get("ev_ebitda")},
                    {"name": "DCF", "weight": (assumptions.get("method_weights") or {}).get("dcf")},
                ],
                "weighted": scenario_block.get("weighted") if scenario_block.get("ok") else {},
                "verdict": verdict_block.get("target"),
            }
        elif section.kind == "events":
            data_out = {
                "rows": event_rows,
                "columns": [
                    {"key": "date", "label": "日期"},
                    {"key": "type", "label": "类型"},
                    {"key": "title", "label": "事件", "wrap": True},
                    {"key": "next_day", "label": "次日", "align": "right", "format": "signed", "digits": 2},
                    {"key": "five_day", "label": "5 日", "align": "right", "format": "signed", "digits": 2},
                ],
                "note": "事件后收益按前复权收盘价计算；公告仅保留回购/增持/减持/业绩预告等关键类型。",
            }
        elif section.kind == "position":
            data_out = {**position_block, "editable": True}
        elif section.kind == "health":
            today = storage.today_local()
            dataset_meta = (spec.params or {}).get("datasets") or {}

            def _fresh(item: dict[str, Any]) -> bool:
                latest = item.get("latest_as_of")
                if not latest:
                    return False
                try:
                    latest_date = date.fromisoformat(str(latest)[:10])
                except ValueError:
                    return False
                max_age = (dataset_meta.get(item.get("dataset")) or {}).get("max_age_days")
                if max_age is None:
                    return True
                return (today - latest_date).days <= int(max_age)

            data_out = {
                "datasets": [
                    {
                        "name": item.get("name") or item.get("dataset"),
                        "rows": item.get("row_count") or 0,
                        "first": None,
                        "last": item.get("latest_as_of"),
                        "fresh": _fresh(item),
                        "note": item.get("source") or "",
                    }
                    for item in catalog
                ],
                "gaps": data.notes,
                "providers": sources,
                "status": data.status,
            }
        elif section.kind == "methodology":
            weights = (spec.params or {}).get("score_weights") or {}
            labels = {"valuation": "估值", "technical": "技术", "copper": "铜价", "scenario": "情景", "relative": "相对强弱"}
            weight_text = " + ".join(
                f"{label} {weights.get(key, 0):g}%" for key, label in labels.items() if weights.get(key)
            ) or "由 config/topics/luoyang.yaml 配置"
            data_out = {
                "text": f"洛阳钼业研判分 = {weight_text}；持仓评分单独展示。权重与情景假设可在 config/topics/luoyang.yaml 调整。",
                "caveats": CAVEATS + data.notes,
                "disclaimer": DISCLAIMER,
            }
        elif section.kind == "sources":
            data_out = {"providers": sources, "manual": [], "manualEditable": False}
        elif section.kind == "bullets":
            data_out = {"title": verdict_block["driver"]["headline"], "items": verdict_block["driver"]["evidence"]}
        else:
            data_out = {"note": f"未实现的分区类型：{section.kind}"}
        sections.append(
            {
                "id": section.id,
                "label": section.label,
                "kind": section.kind,
                "anchor": section.anchor,
                "order": section.order,
                "data": data_out,
            }
        )

    return {
        "meta": {
            "topic_id": spec.id,
            "name": spec.label,
            "subtitle": spec.subtitle,
            "asset": spec.asset,
            "as_of": data.latest_date.isoformat() if data.latest_date else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_version": config_version,
            "adapter": spec.adapter,
            "refresh_job": spec.refresh_job,
            "status": data.status,
            "notes": data.notes,
        },
        "hero": hero,
        "sections": sections,
        "verdict": verdict_block,
    }
