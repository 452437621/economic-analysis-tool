"""Persona spec loading and validation."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from app.lens.persona_expression import FUNCTIONS, ExpressionError, normalize_expression

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
