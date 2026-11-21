"""Persona expression language: AST sandbox and pure series functions."""

from __future__ import annotations

import ast
import logging
import math
import re
from typing import Any, Iterable

import pandas as pd

log = logging.getLogger(__name__)

# ── 表达式函数 ─────────────────────────────────────────────────────────


def _as_series(value: Any) -> pd.Series | None:
    if isinstance(value, pd.Series):
        return pd.to_numeric(value, errors="coerce")
    return None


def _z(series: Any, win: int = 250, min_obs: int = 60) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    window = max(2, int(win))
    mean = data.rolling(window, min_periods=min_obs).mean()
    std = data.rolling(window, min_periods=min_obs).std()
    return (data - mean) / std.replace(0, float("nan"))


def _last_rank(window) -> float:
    last = window[-1]
    if not math.isfinite(last):
        return float("nan")
    return float((window <= last).mean())


def _pctile(series: Any, win: int = 2500, min_obs: int = 250) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    window = max(2, int(win))
    return data.rolling(window, min_periods=min_obs).apply(_last_rank, raw=True)


def _chg(series: Any, days: int = 63) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    return data - data.shift(max(1, int(days)))


def _pct(series: Any, days: int = 63) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    return (data / data.shift(max(1, int(days))) - 1.0) * 100.0


def _yoy(series: Any) -> pd.Series:
    return _pct(series, 365)


def _ma(series: Any, n: int = 20) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    return data.rolling(max(1, int(n)), min_periods=1).mean()


def _shift(series: Any, n: int = 1) -> pd.Series:
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    return data.shift(int(n))


def _sum12(series: Any, months: int = 12) -> pd.Series:
    """月度序列的滚动 12 个月合计，并回填到原日频索引（TTM 口径）。

    月度序列在面板里已被前值填充为日频，直接 rolling 会按「行」而不是按「月」求和，
    因此先按月取末值再滚动求和，最后按日频索引 reindex 回填。
    """
    data = _as_series(series)
    if data is None or data.empty:
        return pd.Series(dtype="float64")
    monthly = data.dropna().resample("ME").last()
    if monthly.empty:
        return pd.Series(dtype="float64")
    summed = monthly.rolling(max(1, int(months)), min_periods=1).sum()
    return summed.reindex(data.index, method="ffill")


FUNCTIONS: dict[str, Any] = {
    "z": _z,
    "pctile": _pctile,
    "chg": _chg,
    "pct": _pct,
    "yoy": _yoy,
    "ma": _ma,
    "shift": _shift,
    "sum12": _sum12,
    "ttm": _sum12,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

# A 股代码 000300 之类以数字开头的列名不是合法 Python 标识符，
# 统一映射为 SYM_000300 这类前缀名，表达式里照常写 pct(000300, 20)。
_NUMERIC_COLUMN_RE = re.compile(r"(?<![\w.])0\d{5}(?![\w.])")


class ExpressionError(ValueError):
    """YAML 里的表达式不合法（未知函数、未知列、不允许的语法）。"""


def normalize_expression(expr: str, columns: Iterable[str] | None = None) -> str:
    """把以数字开头的列名替换为合法标识符（``000300`` → ``SYM_000300``）。"""
    text = str(expr or "")
    source = () if columns is None else columns
    known = {str(column) for column in source if _NUMERIC_COLUMN_RE.fullmatch(str(column))}
    if not known:
        return _NUMERIC_COLUMN_RE.sub(lambda match: f"SYM_{match.group(0)}", text)
    for column in sorted(known, key=len, reverse=True):
        text = re.sub(rf"(?<![\w.]){column}(?![\w.])", f"SYM_{column}", text)
    return text


def evaluate_expression(expr: str, frame: pd.DataFrame) -> pd.Series:
    """把 YAML 表达式求值为一条序列；未知列返回全 NaN 序列。"""
    text = normalize_expression(expr, frame.columns).strip()
    if not text:
        return pd.Series(dtype="float64")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - 配置错误
        raise ExpressionError(f"表达式语法错误：{expr!r}（{exc.msg}）") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(f"表达式含不允许的语法：{type(node).__name__}（{expr!r}）")
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", "")
            if name not in FUNCTIONS:
                raise ExpressionError(f"未知函数 {name!r}（{expr!r}）")
    namespace: dict[str, Any] = dict(FUNCTIONS)
    for column in frame.columns:
        namespace[str(column)] = frame[column]
        if _NUMERIC_COLUMN_RE.fullmatch(str(column)):
            namespace[f"SYM_{column}"] = frame[column]
    try:
        result = eval(compile(tree, "<persona>", "eval"), {"__builtins__": {}}, namespace)  # noqa: S307
    except NameError:
        # 未知列：按缺失处理，让读数降级而不是中断整次运行。
        log.info("persona expression references unknown column: %s", expr)
        return pd.Series(float("nan"), index=frame.index)
    if isinstance(result, pd.Series):
        return pd.to_numeric(result, errors="coerce")
    if isinstance(result, (int, float)):
        return pd.Series(float(result), index=frame.index)
    return pd.Series(float("nan"), index=frame.index)
