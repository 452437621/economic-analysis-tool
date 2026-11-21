"""Gold topic adapter: existing gold score + golden_analysis signal blocks."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.gold.registry import CATEGORY_LABELS, INDICATORS, SERIES_CODES, manual_codes
from app.gold.runner import latest_provider_runs
from app.gold.scoring import compute_gold_score, history
from app.topics.config import TopicSpec

DISCLAIMER = "本页为研究辅助，所有评分与模型均为公开数据的量化推演，不构成投资建议。"

CAVEATS = [
    "实际利率估值模型使用滚动 OLS（对数金价 ~ 10Y 实际利率），残差反映模型无法解释的溢价，不代表必然回归。",
    "金银比、波动率与季节性都是弱信号，极端行情下可能长期失效。",
    "CFTC 分类持仓与银行参与报告是公开可得的最佳代理，不等同于个体做市商账簿。",
    "BIS 黄金掉期/存储无公开可机读序列，保留手动录入且默认不参与评分。",
]


def _fmt_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:10]


def _top_drivers(factors: list[dict], signals: list[dict], limit: int = 5) -> list[dict]:
    merged = [item for item in [*factors, *signals] if item.get("available")]
    merged.sort(key=lambda item: abs(float(item.get("contribution") or 0)), reverse=True)
    return merged[:limit]


def _conclusion(hero: dict, drivers: list[dict]) -> str:
    if not drivers:
        return "暂无可用的关键因子，等待采集任务写入数据。"
    bullish = [item["name"] for item in drivers if float(item.get("contribution") or 0) > 0.05]
    bearish = [item["name"] for item in drivers if float(item.get("contribution") or 0) < -0.05]
    parts: list[str] = []
    if bullish:
        parts.append(f"{'、'.join(bullish)}偏多")
    if bearish:
        parts.append(f"{'、'.join(bearish)}偏空")
    head = "；".join(parts) if parts else "多空因子势均力敌"
    return f"{head}，综合判断「{hero['label']}」（{hero['score']:+.1f} / 100），覆盖率 {hero['coverage']:.0f}%。"


def _chart(
    key: str,
    title: str,
    unit: str,
    series_map: dict[str, list[dict]],
    codes: list[tuple[str, str]],
    *,
    note: str = "",
    height: int = 260,
    wide: bool = False,
) -> dict[str, Any]:
    points_by_code = {code: series_map.get(code) or [] for code, _ in codes}
    # Union of every series' dates: mixed weekly/monthly sources must each keep
    # their own observations instead of being dropped by the longest series' grid.
    dates = sorted(
        {
            str(point["t"])[:10]
            for points in points_by_code.values()
            for point in points
        }
    )
    series: list[dict[str, Any]] = []
    for index, (code, label) in enumerate(codes):
        by_date = {str(point["t"])[:10]: point["v"] for point in points_by_code.get(code) or []}
        values = [by_date.get(item) for item in dates] if dates else []
        series.append({"name": label, "values": values, "axis": index, "code": code})
    return {
        "key": key,
        "title": title,
        "unit": unit,
        "kind": "line",
        "height": height,
        "wide": wide,
        "dates": dates,
        "series": series,
        "note": note,
        "emptyText": "暂无数据",
        "hasData": any(any(value is not None for value in item["values"]) for item in series),
    }


def _build_charts(series_map: dict[str, list[dict]], limit: int) -> list[dict[str, Any]]:
    charts = [
        _chart(
            "gold_price",
            "黄金价格与动量",
            "美元/盎司",
            series_map,
            [("GOLD_PRICE_USD", "伦敦金现")],
            note="XAUUSD 快照/日线；动量见关键读数。",
        ),
        _chart(
            "real_yield",
            "美债 10Y 实际利率",
            "%",
            series_map,
            [("US10Y_REAL", "10Y 实际利率")],
            note="实际利率上行通常压制金价。",
        ),
        _chart(
            "etf_holdings",
            "全球黄金 ETF 持仓",
            "吨",
            series_map,
            [("ETF_GLOBAL_TONNES", "全球 ETF 持仓"), ("ETF_FLOW_1M_TONNES", "近月净流入")],
            note="持仓与资金流同向时置信度更高。",
        ),
        _chart(
            "inventory",
            "伦敦金库与 COMEX 库存",
            "吨",
            series_map,
            [("LBMA_GOLD_TONNES", "伦敦金库"), ("COMEX_GOLD_INVENTORY_TONNES", "COMEX 库存")],
            note="库存回升通常对应实物紧张缓解。",
        ),
        _chart(
            "cot",
            "COMEX 持仓",
            "张",
            series_map,
            [("COT_MONEY_NET", "管理基金净持仓"), ("COT_SWAP_NET", "掉期商净持仓")],
            note="极端仓位采用逆向打分。",
        ),
        _chart(
            "premium",
            "上海金溢价与租赁",
            "%",
            series_map,
            [("CN_GOLD_PREMIUM_PCT", "上海金溢价"), ("SGE_GOLD_LEASE_3M_PCT", "3M 租借费率")],
            note="溢价走阔反映亚洲实物需求；租赁紧张反映现货挤兑。",
        ),
    ]
    for chart in charts:
        for item in chart["series"]:
            if len(item["values"]) > limit:
                item["values"] = item["values"][-limit:]
        if chart["dates"] and len(chart["dates"]) > limit:
            chart["dates"] = chart["dates"][-limit:]
    return charts


def _gold_providers(session) -> list[dict[str, Any]]:
    """Normalise gold provider runs to the topic provider shape (needs ``dataset``)."""
    return [
        {**item, "dataset": item.get("dataset") or item.get("provider") or ""}
        for item in latest_provider_runs(session)
    ]


def _kpi_items(
    factors: list[dict],
    analytics: dict | None,
    series_map: dict[str, list[dict]] | None = None,
) -> list[dict[str, Any]]:
    by_code = {item["code"]: item for item in factors}
    wanted = [
        ("GOLD_PRICE_USD", "伦敦金现", "美元/盎司"),
        ("US10Y_REAL", "美债 10Y 实际利率", "%"),
        ("ETF_GLOBAL_TONNES", "全球黄金 ETF", "吨"),
        ("COT_MONEY_NET", "管理基金净持仓", "张"),
        ("CN_GOLD_PREMIUM_PCT", "上海金溢价", "%"),
        ("GOLD_MOM_20D_PCT", "黄金动量", "%"),
    ]
    items: list[dict[str, Any]] = []
    for code, label, unit in wanted:
        item = by_code.get(code)
        value = item.get("value") if item else None
        as_of = item.get("as_of") if item else None
        if value is None and series_map:
            points = series_map.get(code) or []
            if points:
                value = points[-1].get("v")
                as_of = points[-1].get("t")
        if value is None:
            tone = "flat"
        elif item is not None:
            tone = {"bullish": "up", "bearish": "down"}.get(str(item.get("signal")), "flat")
        else:
            tone = "flat"
        items.append(
            {
                "key": code,
                "label": label,
                "value": value,
                "unit": unit,
                "tone": tone,
                "note": (item.get("explain") if item else None) or ("尚未采集" if value is None else "来自行情序列"),
                "as_of": as_of,
            }
        )
    return items


def _performance_items(analytics: dict | None) -> list[dict[str, Any]]:
    perf = (analytics or {}).get("performance") or {}
    items: list[dict[str, Any]] = []
    for key, label, unit in (
        ("r_1d", "近 1 日", "%"),
        ("r_1w", "近 1 周", "%"),
        ("r_1m", "近 1 月", "%"),
        ("r_3m", "近 3 月", "%"),
        ("r_ytd", "年初至今", "%"),
        ("r_1y", "近 1 年", "%"),
        ("r_3y_ann", "近 3 年年化", "%"),
        ("vol_20d", "20 日波动率", "%"),
        ("vol_60d", "60 日波动率", "%"),
        ("max_drawdown_pct", "最大回撤", "%"),
        ("var_95_pct", "VaR 95%", "%"),
        ("sharpe_1y", "近 1 年 Sharpe", ""),
    ):
        value = perf.get(key)
        items.append(
            {
                "key": f"perf_{key}",
                "label": label,
                "value": value,
                "unit": unit,
                "tone": "flat" if value is None else ("up" if float(value) >= 0 else "down"),
                "note": "基于黄金日线" if value is not None else "样本不足",
            }
        )
    tech = (analytics or {}).get("technical") or {}
    if tech.get("rsi14") is not None:
        items.append(
            {
                "key": "rsi14",
                "label": "RSI14",
                "value": tech["rsi14"],
                "unit": "",
                "tone": "flat",
                "note": "70 以上超买 / 30 以下超卖",
            }
        )
    regime = (analytics or {}).get("regime") or {}
    if regime.get("vol_state"):
        items.append(
            {
                "key": "vol_state",
                "label": "波动状态",
                "value": regime.get("vol_state"),
                "unit": "",
                "tone": "flat",
                "note": f"趋势 {regime.get('trend_state') or '—'}",
            }
        )
    return items


def _groups(factors: list[dict], signals: list[dict]) -> list[dict[str, Any]]:
    merged = [*factors, *signals]
    order = [(key, label) for key, label in CATEGORY_LABELS.items()]
    groups: list[dict[str, Any]] = []
    for key, label in order:
        items = [item for item in merged if item.get("category") == key]
        if not items:
            continue
        groups.append(
            {
                "key": key,
                "label": label,
                "contribution": round(sum(float(item.get("contribution") or 0) for item in items), 2),
                "available": sum(1 for item in items if item.get("available")),
                "items": items,
            }
        )
    return groups


def build_overview(
    spec: TopicSpec,
    session: Session,
    *,
    series_limit: int = 2500,
    config_version: str = "",
) -> dict[str, Any]:
    score = compute_gold_score(session)
    factors = score["factors"]
    signals = score.get("signals") or []
    analytics = score.get("analytics") or {}
    series_map = {code: [{"t": as_of.isoformat(), "v": round(value, 4)} for as_of, value in history(session, code, limit=series_limit)] for code in SERIES_CODES}
    manual: list[dict[str, Any]] = []
    for code in manual_codes():
        item = INDICATORS[code]
        obs = history(session, code, limit=2)
        manual.append(
            {
                "code": code,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "freq": item.freq,
                "source": item.source,
                "weight": item.weight,
                "available": bool(obs),
                "value": round(obs[-1][1], 4) if obs else None,
                "as_of": obs[-1][0].isoformat() if obs else None,
                "note": item.note,
            }
        )
    providers = _gold_providers(session)
    drivers = _top_drivers(factors, signals)
    as_of_values = [item.get("as_of") for item in factors if item.get("available") and item.get("as_of")]
    # Use the earliest available factor date: one fresh daily series must not
    # hide a monthly source that stopped updating months ago.
    as_of = min(as_of_values) if as_of_values else None
    hero = {
        "score": score["score"],
        "label": score["label"],
        "coverage": float(score["coverage"]),
        "available_weight": score["available_weight"],
        "total_weight": score["total_weight"],
        "conclusion": "",
        "badges": [
            {"label": score["label"], "tone": "up" if score["score"] > 0 else ("down" if score["score"] < 0 else "flat")},
            {"label": f"覆盖率 {score['coverage']:.0f}%", "tone": "flat"},
            {"label": f"{score['combined']['available_count']}/{score['combined']['total_count']} 项可用", "tone": "flat"},
        ],
        "drivers": drivers,
        "score_0_100": score.get("score_0_100"),
    }
    hero["conclusion"] = _conclusion(hero, drivers)
    if hero["coverage"] <= 0:
        hero["score"] = None
        hero["score_0_100"] = None
        hero["label"] = "数据不足"
        hero["conclusion"] = "黄金专题数据尚未采集。点击「刷新数据」或等待 collect_gold 任务完成后即可生成研判。"
        hero["badges"] = [{"label": "数据不足", "tone": "warn"}]
        hero["drivers"] = []

    sections: list[dict[str, Any]] = []
    for section in spec.sections:
        if not section.enabled:
            continue
        if section.kind == "hero":
            data = hero
        elif section.id == "kpis":
            data = {"items": _kpi_items(factors, analytics, series_map)}
        elif section.id == "performance":
            data = {
                "items": _performance_items(analytics),
                "regime": analytics.get("regime"),
                "text": "波动状态与趋势由 20 日年化波动率、MA50/MA200 判定；高波动阶段建议降低仓位。",
            }
        elif section.kind == "factors":
            data = {
                "groups": _groups(factors, signals),
                "factors": factors,
                "signals": signals,
            }
        elif section.kind == "charts":
            data = {"charts": _build_charts(series_map, series_limit), "series": series_map}
        elif section.kind == "valuation":
            data = analytics.get("valuation") or {"ok": False, "reason": "实际利率模型样本不足"}
        elif section.id == "signals":
            data = {
                "columns": [
                    {"key": "name", "label": "信号"},
                    {"key": "weight", "label": "权重", "align": "right", "format": "number"},
                    {"key": "score", "label": "得分", "align": "right", "format": "signed", "digits": 2},
                    {"key": "direction", "label": "方向"},
                    {"key": "weighted", "label": "是否计权"},
                    {"key": "detail", "label": "说明", "wrap": True},
                ],
                "rows": score.get("signal_details") or [],
                "note": "实际利率/美元/央行购金/ETF/COT 已由现有指标覆盖，不重复计权；其余 6 项与复合动量并入综合评分。",
            }
        elif section.id == "correlations":
            rows = analytics.get("correlations") or []
            data = {
                "columns": [
                    {"key": "name", "label": "因子"},
                    {"key": "corr_60d", "label": "60 日", "align": "right", "format": "number", "digits": 2},
                    {"key": "corr_1y", "label": "1 年", "align": "right", "format": "number", "digits": 2},
                    {"key": "corr_3y", "label": "3 年", "align": "right", "format": "number", "digits": 2},
                    {"key": "n", "label": "样本", "align": "right", "format": "number"},
                ],
                "rows": rows,
                "note": "收益率相关；利率类用差分。缺失序列自动跳过。",
            }
        elif section.kind == "sources":
            data = {"providers": providers, "manual": manual, "manualEditable": True}
        elif section.kind == "health":
            coverage = analytics.get("coverage") or []
            today = datetime.now(timezone.utc).date()

            def _fresh(item: dict[str, Any]) -> bool:
                end = item.get("end")
                if not end:
                    return False
                try:
                    latest = date.fromisoformat(str(end)[:10])
                except ValueError:
                    return False
                return (today - latest).days <= 10

            datasets = [
                {
                    "name": item.get("name") or item.get("code"),
                    "rows": item.get("count") or 0,
                    "first": item.get("start"),
                    "last": item.get("end"),
                    "fresh": _fresh(item),
                    "note": item.get("note") or "",
                }
                for item in coverage
            ]
            gaps = [
                item.get("note")
                or f"{item.get('name') or item.get('code')} 最新 {item.get('end') or '无'} 已超过 10 天"
                for item, dataset in zip(coverage, datasets)
                if not dataset["fresh"]
            ]
            data = {
                "datasets": datasets,
                "gaps": [item for item in gaps if item],
                "providers": providers,
            }
        elif section.kind == "methodology":
            data = {
                "text": score["methodology"],
                "caveats": CAVEATS,
                "disclaimer": DISCLAIMER,
            }
        else:
            data = {"note": f"未实现的分区类型：{section.kind}"}
        sections.append(
            {
                "id": section.id,
                "label": section.label,
                "kind": section.kind,
                "anchor": section.anchor,
                "order": section.order,
                "data": data,
            }
        )

    return {
        "meta": {
            "topic_id": spec.id,
            "name": spec.label,
            "subtitle": spec.subtitle,
            "asset": spec.asset,
            "as_of": as_of,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_version": config_version,
            "adapter": spec.adapter,
            "refresh_job": spec.refresh_job,
        },
        "hero": hero,
        "sections": sections,
    }
