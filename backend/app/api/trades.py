"""交易 API（V2.0）：交易记录 CRUD、筛选分页、汇总统计与统计页。

设计约定：
- 一条建仓（含计划单）= 一条 ``trade_records`` 记录，与按日复盘的 ``/api/journal`` 区分；
- ``pnl`` / ``pnl_pct`` / ``rr`` 允许手工录入；缺省时由开平仓价、手续费与保证金推导；
- 列表的 ``summary`` 统计的是「满足筛选条件的全部记录」，不是当前页；
- ``win_rate`` 分母为已平仓数（``closed``），``pnl == 0`` 或为空不计入胜负；
- ``avg_loss`` 取亏损记录的均值（负数），与 ``app.decision.backtest`` 的口径一致；
- ``/stats`` 必须注册在 ``/{trade_id}`` 之前，否则 ``stats`` 会被当成 id。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.serializers import iso
from app.models.v2 import TradeRecord
from app.platform.db import get_session

router = APIRouter(prefix="/api/trades", tags=["trades"])

AssetClass = Literal["futures", "stock", "option", "forex", "crypto", "other"]
Direction = Literal["long", "short"]
TradeStatus = Literal["planned", "open", "closed", "cancelled"]
SortField = Literal["trade_date", "pnl", "created_at"]
SortOrder = Literal["desc", "asc"]

ASSET_CLASSES = ("futures", "stock", "option", "forex", "crypto", "other")
DIRECTIONS = ("long", "short")
STATUSES = ("planned", "open", "closed", "cancelled")
SORT_COLUMNS = {
    "trade_date": TradeRecord.trade_date,
    "pnl": TradeRecord.pnl,
    "created_at": TradeRecord.created_at,
}

MAX_TAGS = 8
MAX_TAG_LEN = 16
STATS_MONTHS = 24
MAX_QUERY_LEN = 200

NUMERIC_FIELDS = (
    "planned_qty",
    "filled_qty",
    "entry_price",
    "exit_price",
    "stop_price",
    "target_price",
    "margin",
    "leverage",
    "fee",
    "pnl",
    "pnl_pct",
    "risk_amount",
    "rr",
    "planned_win_rate",
)


def _enum(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    """枚举校验：去空白、转小写，非法值抛 ValueError（FastAPI 转 422）。"""
    if value is None:
        return None
    clean = str(value).strip().lower()
    if clean not in allowed:
        raise ValueError(f"{field} 必须是 {' / '.join(allowed)} 之一")
    return clean


def _clean_tags(tags: list[str] | None) -> list[str] | None:
    """标签清洗：去空白、去重、最多 8 个、每个最长 16 字符（超长截断）。"""
    if tags is None:
        return None
    clean: list[str] = []
    for raw in tags:
        tag = str(raw).strip()[:MAX_TAG_LEN]
        if tag and tag not in clean:
            clean.append(tag)
        if len(clean) >= MAX_TAGS:
            break
    return clean


class TradePatch(BaseModel):
    """部分更新入参：除 id / 时间戳外全部字段可选。"""

    trade_date: date | None = None
    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=64)
    asset_class: str | None = None
    direction: str | None = None
    status: str | None = None
    strategy: str | None = Field(default=None, max_length=200)
    planned_qty: float | None = None
    filled_qty: float | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    margin: float | None = None
    leverage: float | None = None
    fee: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    risk_amount: float | None = None
    rr: float | None = None
    planned_win_rate: float | None = None
    attribution: str | None = Field(default=None, max_length=400)
    plan_note: str | None = Field(default=None, max_length=2000)
    review_note: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None

    @field_validator(*NUMERIC_FIELDS)
    @classmethod
    def _finite(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("数值字段必须是有限数")
        return float(value)

    @field_validator("asset_class")
    @classmethod
    def _check_asset_class(cls, value: str | None) -> str | None:
        return _enum(value, ASSET_CLASSES, "asset_class")

    @field_validator("direction")
    @classmethod
    def _check_direction(cls, value: str | None) -> str | None:
        return _enum(value, DIRECTIONS, "direction")

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        return _enum(value, STATUSES, "status")

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value)

    @model_validator(mode="after")
    def _required_not_null(self) -> TradePatch:
        """必填字段可以被省略，但不接受显式 null。"""
        for name in ("trade_date", "symbol", "asset_class", "direction"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} 不能为空")
        return self


class TradeInput(TradePatch):
    """创建入参：trade_date / symbol / asset_class / direction 必填。"""

    trade_date: date
    symbol: str = Field(min_length=1, max_length=32)
    asset_class: str
    direction: str


def _compute_pnl(
    direction: str,
    entry_price: float | None,
    exit_price: float | None,
    filled_qty: float | None,
    fee: float | None,
) -> float | None:
    """按方向计算盈亏：多单 (exit-entry)*qty，空单取反，再扣手续费。"""
    if entry_price is None or exit_price is None or filled_qty is None:
        return None
    sign = 1.0 if direction == "long" else -1.0
    return (exit_price - entry_price) * filled_qty * sign - (fee or 0.0)


def _compute_pnl_pct(pnl: float | None, margin: float | None) -> float | None:
    """收益率 = 盈亏 / 保证金（保证金必须为正）。"""
    if pnl is None or margin is None or margin <= 0:
        return None
    return pnl / margin


def _compute_rr(
    entry_price: float | None,
    stop_price: float | None,
    target_price: float | None,
) -> float | None:
    """盈亏比 = |目标-开仓| / |开仓-止损|，分母为 0 不计算。"""
    if entry_price is None or stop_price is None or target_price is None:
        return None
    risk = abs(entry_price - stop_price)
    if risk == 0:
        return None
    return abs(target_price - entry_price) / risk


_iso = iso


def _serialize(row: TradeRecord) -> dict:
    """TradeItem：字段顺序固定，前端按契约直接渲染。"""
    return {
        "id": row.id,
        "trade_date": row.trade_date.isoformat(),
        "symbol": row.symbol,
        "name": row.name,
        "asset_class": row.asset_class,
        "direction": row.direction,
        "status": row.status,
        "strategy": row.strategy,
        "planned_qty": row.planned_qty,
        "filled_qty": row.filled_qty,
        "entry_price": row.entry_price,
        "exit_price": row.exit_price,
        "stop_price": row.stop_price,
        "target_price": row.target_price,
        "margin": row.margin,
        "leverage": row.leverage,
        "fee": row.fee,
        "pnl": row.pnl,
        "pnl_pct": row.pnl_pct,
        "risk_amount": row.risk_amount,
        "rr": row.rr,
        "planned_win_rate": row.planned_win_rate,
        "attribution": row.attribution,
        "plan_note": row.plan_note,
        "review_note": row.review_note,
        "tags": row.tags or [],
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _summary(rows: Sequence[TradeRecord]) -> dict:
    """汇总统计：基于传入的全部（已筛选）记录，而非当前页。"""
    closed_rows = [row for row in rows if row.status == "closed"]
    closed_pnls = [row.pnl for row in closed_rows if row.pnl is not None]
    wins = sum(1 for value in closed_pnls if value > 0)
    losses = sum(1 for value in closed_pnls if value < 0)
    gross_profit = sum(value for value in closed_pnls if value > 0)
    gross_loss = sum(value for value in closed_pnls if value < 0)
    rr_values = [row.rr for row in rows if row.rr is not None]
    fees = [row.fee for row in rows if row.fee is not None]
    return {
        "count": len(rows),
        "closed": len(closed_rows),
        "open": sum(1 for row in rows if row.status == "open"),
        "planned": sum(1 for row in rows if row.status == "planned"),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(closed_rows) if closed_rows else 0.0,
        "total_pnl": sum(closed_pnls),
        "avg_pnl": sum(closed_pnls) / len(closed_pnls) if closed_pnls else 0.0,
        "avg_win": gross_profit / wins if wins else 0.0,
        "avg_loss": gross_loss / losses if losses else 0.0,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss else 0.0,
        "avg_rr": sum(rr_values) / len(rr_values) if rr_values else 0.0,
        "total_fee": sum(fees),
    }


def _filters(
    q: str | None,
    asset_class: str | None,
    direction: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list:
    """构造列表与统计共用的筛选条件。"""
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                TradeRecord.symbol.ilike(pattern),
                TradeRecord.name.ilike(pattern),
                TradeRecord.strategy.ilike(pattern),
                TradeRecord.plan_note.ilike(pattern),
                TradeRecord.review_note.ilike(pattern),
            )
        )
    if asset_class:
        filters.append(TradeRecord.asset_class == asset_class)
    if direction:
        filters.append(TradeRecord.direction == direction)
    if status:
        filters.append(TradeRecord.status == status)
    if date_from is not None:
        filters.append(TradeRecord.trade_date >= date_from)
    if date_to is not None:
        filters.append(TradeRecord.trade_date <= date_to)
    return filters


def _month_keys(today: date, months: int = STATS_MONTHS) -> list[str]:
    """近 N 个自然月的月份键（含当月，按时间升序）。"""
    keys: list[str] = []
    year, month = today.year, today.month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


@router.get("")
def list_trades(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=MAX_QUERY_LEN),
    asset_class: AssetClass | None = Query(default=None),
    direction: Direction | None = Query(default=None),
    status: TradeStatus | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort: SortField = Query(default="trade_date"),
    order: SortOrder = Query(default="desc"),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(TradeRecord)
    filters = _filters(q, asset_class, direction, status, date_from, date_to)
    if filters:
        stmt = stmt.where(*filters)
    column = SORT_COLUMNS[sort]
    ordering = column.desc() if order == "desc" else column.asc()
    stmt = stmt.order_by(ordering, TradeRecord.created_at.desc(), TradeRecord.id.asc())
    rows = list(session.scalars(stmt).all())
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "items": [_serialize(row) for row in page],
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": _summary(rows),
    }


@router.get("/stats")
def trade_stats(session: Session = Depends(get_session)) -> dict:
    """交易统计页：总览 + 按品种 + 近 24 个月（按 trade_date 归月）。"""
    rows = list(session.scalars(select(TradeRecord)).all())
    payload = _summary(rows)

    by_asset_class = []
    for asset_class in ASSET_CLASSES:
        group = [row for row in rows if row.asset_class == asset_class]
        if not group:
            continue
        closed = [row for row in group if row.status == "closed"]
        wins = sum(1 for row in closed if row.pnl is not None and row.pnl > 0)
        by_asset_class.append(
            {
                "asset_class": asset_class,
                "count": len(group),
                "pnl": sum(row.pnl for row in group if row.pnl is not None),
                "win_rate": wins / len(closed) if closed else 0.0,
            }
        )

    buckets = {key: {"month": key, "count": 0, "pnl": 0.0} for key in _month_keys(date.today())}
    for row in rows:
        key = row.trade_date.strftime("%Y-%m")
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["count"] += 1
        if row.pnl is not None:
            bucket["pnl"] += row.pnl

    payload["by_asset_class"] = by_asset_class
    payload["by_month"] = list(buckets.values())
    return payload


@router.post("", status_code=201)
def create_trade(payload: TradeInput, session: Session = Depends(get_session)) -> dict:
    data = payload.model_dump()
    data["status"] = data["status"] or "closed"
    row = TradeRecord(**data)
    # 服务端补齐派生字段（显式传入的值优先）。
    if row.planned_qty is None:
        row.planned_qty = row.filled_qty
    if row.pnl is None:
        row.pnl = _compute_pnl(
            row.direction, row.entry_price, row.exit_price, row.filled_qty, row.fee
        )
    if row.pnl_pct is None:
        row.pnl_pct = _compute_pnl_pct(row.pnl, row.margin)
    if row.rr is None:
        row.rr = _compute_rr(row.entry_price, row.stop_price, row.target_price)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.get("/{trade_id}")
def get_trade(trade_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(TradeRecord, trade_id)
    if row is None:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return _serialize(row)


@router.patch("/{trade_id}")
def update_trade(trade_id: str, payload: TradePatch, session: Session = Depends(get_session)) -> dict:
    row = session.get(TradeRecord, trade_id)
    if row is None:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    touched = payload.model_fields_set
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, name, value)

    # 只重算「输入被改动、且本次未显式给值」的派生字段，避免覆盖手工录入。
    if "planned_qty" not in touched and "filled_qty" in touched and row.planned_qty is None:
        row.planned_qty = row.filled_qty
    pnl_inputs = {"direction", "entry_price", "exit_price", "filled_qty", "fee"}
    recomputed_pnl = bool(touched & pnl_inputs) and "pnl" not in touched
    if recomputed_pnl:
        row.pnl = _compute_pnl(
            row.direction, row.entry_price, row.exit_price, row.filled_qty, row.fee
        )
    if "pnl_pct" not in touched and (recomputed_pnl or touched & {"pnl", "margin"}):
        row.pnl_pct = _compute_pnl_pct(row.pnl, row.margin)
    if "rr" not in touched and touched & {"entry_price", "stop_price", "target_price"}:
        row.rr = _compute_rr(row.entry_price, row.stop_price, row.target_price)

    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.delete("/{trade_id}")
def delete_trade(trade_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(TradeRecord, trade_id)
    if row is None:
        raise HTTPException(status_code=404, detail="交易记录不存在")
    session.delete(row)
    session.commit()
    return {"deleted": True, "id": trade_id}
