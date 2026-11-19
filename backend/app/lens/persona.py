"""通用人物透镜：由 ``config/personas/*.yaml`` 驱动，无需为每位人物写 Python。

设计目标与其余透镜（美联储、宋鸿兵、宏观层、微观层）保持一致：把一个人
（或一组政策制定者）的框架压缩成可复算的**读数 → 规则 → 资产评分**三层，
落成 provenance 推导。差别只在于：

* 读数、规则、评分全部是 YAML 里的表达式，新增人物 = 新增一个 YAML 文件；
* 表达式只允许调用下面 ``FUNCTIONS`` 里声明的纯函数与面板列名，不接受任意代码。

表达式语言（与 ``docs/27`` §12.2 一致）::

    z(US10Y_REAL, 250)          滚动 z 分数
    pctile(DXY, 2500)           N 日分位（0–1）
    chg(US10Y, 63)              63 日变化
    pct(XAUUSD, 63)             63 日涨跌幅（%）
    yoy(WB_US_CPI)              同比（%）
    ma(SPX, 200)                移动平均
    shift(SOFR_EFFR, 1)         滞后一期
    sum12(US_MTS_DEFICIT)       近 12 个月求和（TTM，回填到日频）

求值上下文内的列就是面板列（宏观 code / 行情 symbol / 黄金指标 code），
缺失列会以全 NaN 序列出现，于是读数落到 ``missing_reason``，规则落到
``unknown``，不会抛异常中断整次运行。
"""

from __future__ import annotations

import ast
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from app.lens.common import (
    Reading,
    build_reading,
    clamp,
    evaluate_rule,
    metric_map,
    round_opt,
    score_label,
)

log = logging.getLogger(__name__)

PERSONA_DIR = Path(__file__).resolve().parents[3] / "config" / "personas"
ASSET_IDS: tuple[str, ...] = (
    "us_equity",
    "gold",
    "silver",
    "usd",
    "cn_equity",
    "long_bond",
    "commodities",
)
RULE_FIELDS = ("value", "chg", "z", "pct")
RULE_OPS = (">", ">=", "<", "<=", "abs_gt", "abs_lt")
SEVERITIES = ("info", "watch", "warn", "critical")
# 面板尾部窗口：约 6 年日频，足够 250 日 z 分数与 5 年分位，也避免 1960 年
# 以来的稀疏年度行把按行位移的 yoy/chg 拉偏。
TAIL_ROWS = 2600


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


# ── 规格加载与校验 ────────────────────────────────────────────────────


@dataclass
class PersonaSpec:
    """一份 YAML 透镜规格。"""

    id: str
    name: str
    title: str = ""
    school: str = ""
    key_question: str = ""
    thesis: str = ""
    readings: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    scores: dict[str, str] = field(default_factory=dict)
    triggers: list[str] = field(default_factory=list)
    path: str = ""

    def catalog(self) -> dict[str, dict[str, Any]]:
        return {str(item.get("id")): item for item in self.readings}


def _load_spec(path: Path) -> PersonaSpec:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ExpressionError(f"{path.name} 顶层必须是映射")
    persona_id = str(raw.get("id") or path.stem)
    spec = PersonaSpec(
        id=persona_id,
        name=str(raw.get("name") or persona_id),
        title=str(raw.get("title") or ""),
        school=str(raw.get("school") or ""),
        key_question=str(raw.get("key_question") or ""),
        thesis=str(raw.get("thesis") or ""),
        readings=[dict(item) for item in (raw.get("readings") or [])],
        rules=[dict(item) for item in (raw.get("rules") or [])],
        scores={str(k): str(v) for k, v in (raw.get("scores") or {}).items()},
        triggers=[str(item) for item in (raw.get("triggers") or [])],
        path=str(path),
    )
    return spec


_cache: dict[str, Any] = {"mtime": None, "specs": []}


def load_specs(directory: Path | None = None) -> list[PersonaSpec]:
    """加载并缓存全部人物规格；目录 mtime 变化时自动重载。"""
    base = Path(directory) if directory else PERSONA_DIR
    if not base.is_dir():
        return []
    stamp = max((item.stat().st_mtime for item in base.glob("*.yaml")), default=0.0)
    if _cache["mtime"] == stamp and _cache["specs"]:
        return list(_cache["specs"])
    specs: list[PersonaSpec] = []
    for path in sorted(base.glob("*.yaml")):
        try:
            specs.append(_load_spec(path))
        except (ExpressionError, yaml.YAMLError) as exc:  # pragma: no cover - 配置错误
            log.warning("skip persona spec %s: %s", path.name, exc)
    _cache["mtime"] = stamp
    _cache["specs"] = specs
    return list(specs)


def validate_spec(spec: PersonaSpec, columns: Iterable[str] | None = None) -> list[str]:
    """返回规格问题列表（空表示通过）。供测试与 /personas 诊断使用。"""
    problems: list[str] = []
    known = set(columns) if columns is not None else None
    reading_ids = {str(item.get("id")) for item in spec.readings}
    if len(reading_ids) != len(spec.readings):
        problems.append("readings 存在重复 id")
    for item in spec.readings:
        rid = str(item.get("id") or "")
        if not rid:
            problems.append("reading 缺少 id")
            continue
        expr = str(item.get("expr") or "")
        if not expr:
            problems.append(f"{rid} 缺少 expr")
            continue
        try:
            tree = ast.parse(normalize_expression(expr, known), mode="eval")
        except SyntaxError:
            problems.append(f"{rid} 表达式语法错误")
            continue
        keyword_names = {
            node.arg for node in ast.walk(tree) if isinstance(node, ast.keyword) and node.arg
        }
        allowed_columns = set(known or ()) | {f"SYM_{name}" for name in (known or ())}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in FUNCTIONS and node.id not in keyword_names:
                if known is not None and node.id not in allowed_columns:
                    problems.append(f"{rid} 引用未知列 {node.id}")
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", "")
                if name not in FUNCTIONS:
                    problems.append(f"{rid} 调用未知函数 {name}")
        for key in ("label",):
            if not str(item.get(key) or ""):
                problems.append(f"{rid} 缺少 {key}")
    for rule in spec.rules:
        rid = str(rule.get("id") or "")
        if not rid:
            problems.append("rule 缺少 id")
        if str(rule.get("severity") or "info") not in SEVERITIES:
            problems.append(f"{rid} severity 非法")
        when = rule.get("when") or {}
        all_conditions = list(when.get("all") or [])
        any_conditions = list(when.get("any") or [])
        if bool(all_conditions) == bool(any_conditions):
            problems.append(f"{rid} when 必须且只能有 all 或 any")
        for condition in all_conditions + any_conditions:
            metric = str(condition.get("metric") or "")
            if metric and metric not in reading_ids:
                problems.append(f"{rid} 引用未知读数 {metric}")
            if str(condition.get("field") or "value") not in RULE_FIELDS:
                problems.append(f"{rid} field 非法")
            if str(condition.get("op") or ">") not in RULE_OPS:
                problems.append(f"{rid} op 非法")
    missing_assets = [key for key in ASSET_IDS if key not in spec.scores]
    if missing_assets:
        problems.append(f"scores 缺少：{', '.join(missing_assets)}")
    extra_assets = [key for key in spec.scores if key not in ASSET_IDS]
    if extra_assets:
        problems.append(f"scores 含未知资产：{', '.join(extra_assets)}")
    return problems


# ── 求值 ──────────────────────────────────────────────────────────────


def _last(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return None
    value = float(cleaned.iloc[-1])
    if not math.isfinite(value):
        return None
    return value


def build_readings(spec: PersonaSpec, frame: pd.DataFrame) -> list[Reading]:
    """按规格求值读数；单条失败只影响该条。"""
    readings: list[Reading] = []
    for item in spec.readings:
        rid = str(item.get("id") or "")
        label = str(item.get("label") or rid)
        unit = str(item.get("unit") or "")
        digits = int(item.get("digits") or 2)
        source = str(item.get("source") or "")
        evidence = str(item.get("evidence") or "E3")
        note = str(item.get("note") or "")
        try:
            series = evaluate_expression(str(item.get("expr") or ""), frame)
        except ExpressionError as exc:
            log.warning("persona %s reading %s: %s", spec.id, rid, exc)
            readings.append(
                Reading(
                    id=rid,
                    label=label,
                    unit=unit,
                    digits=digits,
                    source=source,
                    evidence=evidence,
                    note=note,
                    missing_reason=f"表达式不可用：{exc}",
                )
            )
            continue
        readings.append(
            build_reading(
                rid,
                label,
                series,
                unit=unit,
                digits=digits,
                source=source,
                evidence=evidence,
                note=note,
                missing_reason="该读数依赖的序列本地无数据",
            )
        )
    return readings


def build_scores(spec: PersonaSpec, frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """求值七类资产评分（−2…+2，long_bond 正 = 债券价格看多）。"""
    scores: dict[str, dict[str, Any]] = {}
    for asset in ASSET_IDS:
        expr = spec.scores.get(asset)
        if not expr:
            scores[asset] = {"score": 0.0, "label": "未给出", "why": "该透镜未对该资产建模"}
            continue
        try:
            series = evaluate_expression(expr, frame)
        except ExpressionError as exc:
            scores[asset] = {"score": 0.0, "label": "表达式错误", "why": str(exc)}
            continue
        raw = _last(series)
        if raw is None:
            scores[asset] = {"score": 0.0, "label": "数据不足", "why": f"表达式无有效值：{expr}"}
            continue
        value = clamp(raw, -2.0, 2.0) or 0.0
        scores[asset] = {
            "score": round(float(value), 2),
            "label": score_label(value),
            "why": expr,
        }
    return scores


def build_state(
    spec: PersonaSpec,
    readings: list[Reading],
    scores: dict[str, dict[str, Any]],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """汇总透镜立场：净评分、可用度、最强读数、命中规则。"""
    available = [item for item in readings if item.value is not None]
    score_values = [item["score"] for item in scores.values() if item["score"]]
    net = round(sum(score_values) / len(score_values), 2) if score_values else 0.0
    ranked = sorted(
        (item for item in available if item.z is not None),
        key=lambda item: abs(item.z or 0.0),
        reverse=True,
    )[:5]
    fired = [rule for rule in rules if rule.get("fired")]
    narrative_parts = [spec.thesis.strip()] if spec.thesis else []
    if ranked:
        narrative_parts.append(
            "最极端的读数："
            + "、".join(f"{item.label}（{item.value:.{item.digits}f}{item.unit or ''}，z={item.z:+.2f}）" for item in ranked[:3])
        )
    if fired:
        narrative_parts.append("命中规则：" + "、".join(f"{rule['id']} {rule.get('name') or ''}".strip() for rule in fired))
    else:
        narrative_parts.append("本轮无规则命中，框架给出的只是方向性倾斜。")
    return {
        "lean": {
            "score": net,
            "label": score_label(net),
        },
        "coverage": {
            "available": len(available),
            "total": len(readings),
        },
        "fired_rules": [rule["id"] for rule in fired],
        "critical_rules": [rule["id"] for rule in fired if rule.get("severity") == "critical"],
        "key_readings": [
            {
                "id": item.id,
                "label": item.label,
                "value": round_opt(item.value, item.digits),
                "unit": item.unit,
                "z": round_opt(item.z, 2),
            }
            for item in ranked
        ],
        "narrative": " ".join(part for part in narrative_parts if part),
    }


def build_persona(spec: PersonaSpec, frame: pd.DataFrame) -> dict[str, Any]:
    """运行一份人物透镜，返回 {spec, readings, metrics, rules, scores, state}。"""
    readings = build_readings(spec, frame)
    metrics = metric_map(readings)
    rules = [evaluate_rule(rule, metrics) for rule in spec.rules]
    scores = build_scores(spec, frame)
    state = build_state(spec, readings, scores, rules)
    return {
        "id": spec.id,
        "name": spec.name,
        "title": spec.title,
        "school": spec.school,
        "key_question": spec.key_question,
        "thesis": spec.thesis,
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metrics,
        "rules": rules,
        "scores": scores,
        "state": state,
        "catalog": spec.catalog(),
        "triggers": spec.triggers,
    }


def build_personas(frame: pd.DataFrame, specs: list[PersonaSpec] | None = None) -> list[dict[str, Any]]:
    """运行全部人物透镜；任何一份出错都不影响其它份。"""
    out: list[dict[str, Any]] = []
    for spec in specs if specs is not None else load_specs():
        try:
            out.append(build_persona(spec, frame))
        except Exception as exc:  # pragma: no cover - 防御性兜底
            log.warning("persona %s failed: %s", spec.id, exc)
            out.append(
                {
                    "id": spec.id,
                    "name": spec.name,
                    "title": spec.title,
                    "school": spec.school,
                    "key_question": spec.key_question,
                    "thesis": spec.thesis,
                    "readings": [],
                    "metrics": {},
                    "rules": [],
                    "scores": {asset: {"score": 0.0, "label": "运行失败", "why": str(exc)} for asset in ASSET_IDS},
                    "state": {"lean": {"score": 0.0, "label": "运行失败"}, "coverage": {"available": 0, "total": 0},
                              "fired_rules": [], "critical_rules": [], "key_readings": [], "narrative": str(exc)},
                    "catalog": spec.catalog(),
                    "triggers": spec.triggers,
                }
            )
    return out
