"""透明化运行记录器（玻璃盒 L1–L3）。

用法::

    with SessionLocal() as session:
        with RunRecorder(session, kind="analytics", subject="market") as rec:
            with rec.step("load", kind="fetch") as step:
                data = load()
                step.outputs = {"rows": len(data)}
            rec.derive(code="regime.US", claim="…", value={...}, confidence=0.5)
            rec.finish(summary={"ok": True})

约定：
- run/step/derivation 与业务写操作共用同一个 session，由调用方统一提交；
  这样一次运行要么整体成功，要么留下明确的 failed 运行记录。
- ``derive`` 的 id 由 (method_id, version, 输入 ids, params, code_sha) 计算，
  同样输入得到同样 id（幂等 upsert），避免每日重复行。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import new_id, utcnow
from app.models.v2 import (
    AnalysisRun,
    AnalysisStep,
    Derivation,
    DerivationLink,
    MethodRegistry,
    Observation,
    RuleHit,
)

logger = logging.getLogger(__name__)

EVIDENCE_GRADES = ("E0", "E1", "E2", "E3", "E4")


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def file_sha(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "rb") as handle:  # noqa: PTH123 - pathlib 无 bytes 读
            return hashlib.sha256(handle.read()).hexdigest()[:16]
    except OSError:  # pragma: no cover - 文件缺失时不影响运行
        return None


def module_sha(module_name: str) -> str | None:
    import importlib

    try:
        module = importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - 方法登记前模块可能尚未存在
        return None
    return file_sha(getattr(module, "__file__", None))


def derive_id(
    method_id: str,
    version: str,
    inputs: list[str] | None,
    params: dict | None,
    code_sha: str | None,
    code: str | None = None,
) -> str:
    """稳定推导 id：同方法、同输入、同参数、同代码得到同一 id。

    推导 ``code``（如 ``cycle.scenarios``）也参与哈希，否则同一运行里
    输入相同、结论不同的多条推导会撞 id。
    """
    payload = "|".join(
        [
            f"{method_id}@{version}",
            code or "",
            canonical_json(sorted(inputs or [])),
            canonical_json(params or {}),
            code_sha or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class StepHandle:
    """``rec.step(...)`` 上下文里可写的步骤对象。"""

    def __init__(self, name: str, kind: str, inputs: dict | None, params: dict | None) -> None:
        self.name = name
        self.kind = kind
        self.inputs = inputs
        self.outputs: dict | None = None
        self.params = params
        self.status = "ok"
        self.error: str | None = None


class RunRecorder:
    """一次分析运行的记录器。可作上下文管理器使用。"""

    def __init__(
        self,
        session: Session,
        kind: str,
        subject: str = "all",
        method_id: str | None = None,
        asof: datetime | None = None,
        code_version: str = "m3.0",
    ) -> None:
        if kind not in {"analytics", "gold", "cycle", "timeline", "ledger", "forecast", "ingest"}:
            raise ValueError(f"unknown run kind: {kind}")
        self.session = session
        self.kind = kind
        self.subject = subject
        self.method_id = method_id
        self.asof = asof or utcnow()
        self.code_version = code_version
        self.run: AnalysisRun | None = None
        self._seq = 0
        self._started = time.perf_counter()
        self._degraded: list[dict] = []

    # -- lifecycle -----------------------------------------------------
    def start(self) -> AnalysisRun:
        self.run = AnalysisRun(
            id=new_id(),
            kind=self.kind,
            subject=self.subject,
            asof=self.asof,
            status="running",
            method_id=self.method_id,
            code_version=self.code_version,
            started_at=utcnow(),
        )
        self.session.add(self.run)
        self.session.flush()
        return self.run

    def __enter__(self) -> "RunRecorder":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        if exc_type is not None:
            self.fail(exc)
            return False
        return False

    def degrade(self, code: str, message: str, *, severity: str = "warn") -> None:
        """记录一次降级（数据缺失/源失败），最终体现在 run.degraded_reasons。"""
        self._degraded.append({"code": code, "message": message, "severity": severity})
        self.session.add(
            RuleHit(
                id=new_id(),
                run_id=self.run.id if self.run else None,
                rule_id=f"degrade.{code}",
                severity=severity,
                fired=True,
                message=message,
            )
        )

    @contextmanager
    def step(
        self,
        name: str,
        kind: str = "compute",
        inputs: dict | None = None,
        params: dict | None = None,
    ) -> Iterator[StepHandle]:
        handle = StepHandle(name, kind, inputs, params)
        self._seq += 1
        started = utcnow()
        clock = time.perf_counter()
        try:
            yield handle
        except Exception as exc:
            handle.status = "error"
            handle.error = str(exc)[:2000]
            self._add_step(handle, started, clock)
            raise
        else:
            self._add_step(handle, started, clock)

    def _add_step(self, handle: StepHandle, started: datetime, clock: float) -> None:
        run_id = self.run.id if self.run else None
        self.session.add(
            AnalysisStep(
                id=new_id(),
                run_id=run_id,
                seq=self._seq,
                name=handle.name,
                kind=handle.kind,
                status=handle.status,
                started_at=started,
                finished_at=utcnow(),
                duration_ms=int((time.perf_counter() - clock) * 1000),
                inputs=handle.inputs,
                outputs=handle.outputs,
                params=handle.params,
                error=handle.error,
            )
        )

    def finish(self, summary: dict | None = None, status: str | None = None) -> AnalysisRun:
        if self.run is None:
            raise RuntimeError("run not started")
        self.run.status = status or ("degraded" if self._degraded else "ok")
        self.run.finished_at = utcnow()
        self.run.duration_ms = int((time.perf_counter() - self._started) * 1000)
        self.run.degraded = bool(self._degraded)
        self.run.degraded_reasons = self._degraded or None
        self.run.summary = summary
        return self.run

    def fail(self, exc: BaseException) -> None:
        if self.run is None:
            return
        self.run.status = "failed"
        self.run.finished_at = utcnow()
        self.run.duration_ms = int((time.perf_counter() - self._started) * 1000)
        self.run.error = f"{type(exc).__name__}: {exc}"[:2000]
        self.run.degraded = True
        logger.exception("analysis run failed: kind=%s", self.kind)

    # -- derivations ---------------------------------------------------
    def derive(
        self,
        *,
        code: str,
        claim: str,
        value: dict | None = None,
        confidence: float | None = None,
        evidence_grade: str = "E3",
        subject: str | None = None,
        method_id: str | None = None,
        method_version: str = "1.0",
        inputs: list[str] | None = None,
        steps: list[dict] | None = None,
        rules_hit: list[dict] | None = None,
        caveats: list[str] | None = None,
        falsifiers: list[str] | None = None,
        opposing: list[str] | None = None,
        asof: datetime | None = None,
        parents: list[str] | None = None,
    ) -> Derivation:
        if evidence_grade not in EVIDENCE_GRADES:
            raise ValueError(f"invalid evidence grade: {evidence_grade}")
        method = method_id or self.method_id or "unregistered"
        resolved = self.session.get(MethodRegistry, method)
        code_sha = resolved.code_sha if resolved else None
        version = resolved.version if resolved else method_version
        ref = resolve_method_code_sha(method) or code_sha
        did = derive_id(method, version, inputs, None, ref, code)
        row = self.session.get(Derivation, did)
        if row is None:
            row = Derivation(id=did, created_at=utcnow())
            self.session.add(row)
        row.run_id = self.run.id if self.run else None
        row.code = code
        row.subject = subject or self.subject
        row.claim = claim
        row.value = value
        row.confidence = confidence
        row.evidence_grade = evidence_grade
        row.method_id = method
        row.inputs = inputs
        row.steps = steps
        row.rules_hit = rules_hit
        row.caveats = caveats
        row.falsifiers = falsifiers
        row.opposing = opposing
        row.asof = asof or self.asof
        for parent in parents or []:
            self.session.add(
                DerivationLink(id=new_id(), parent_id=parent, child_id=did, relation="supports")
            )
        return row

    # -- convenience ---------------------------------------------------
    def record_rule(
        self, rule_id: str, message: str, *, severity: str = "info", inputs: dict | None = None, fired: bool = True
    ) -> RuleHit:
        row = RuleHit(
            id=new_id(),
            run_id=self.run.id if self.run else None,
            rule_id=rule_id,
            severity=severity,
            fired=fired,
            message=message,
            inputs=inputs,
        )
        self.session.add(row)
        return row


def resolve_method_code_sha(method_id: str) -> str | None:
    """方法 id 形如 ``analytics.regime.v1``，用前两段推断模块路径并取文件摘要。"""
    parts = method_id.split(".")
    if len(parts) < 2:
        return None
    module = ".".join(["app", *parts[:2]])
    return module_sha(module)


def record_observations(session: Session, rows: list[dict]) -> int:
    """写入带 vintage 的观测；同 (code, asof, vintage) 幂等更新。"""
    if not rows:
        return 0
    count = 0
    for item in rows:
        code = item.get("code")
        asof = item.get("asof")
        if not code or asof is None:
            continue
        existing = session.scalar(
            select(Observation).where(
                Observation.code == code,
                Observation.asof == asof,
                Observation.vintage_date == item.get("vintage_date"),
            )
        )
        if existing is None:
            existing = Observation(id=new_id(), code=code, asof=asof)
            session.add(existing)
        existing.value = item.get("value")
        existing.unit = item.get("unit")
        existing.source = item.get("source")
        existing.evidence_grade = item.get("evidence_grade", "E0")
        existing.extra = item.get("extra")
        count += 1
    return count


def latest_derivations(session: Session, code: str | None = None, limit: int = 50) -> list[Derivation]:
    stmt = select(Derivation).order_by(Derivation.asof.desc(), Derivation.created_at.desc())
    if code:
        stmt = stmt.where(Derivation.code == code)
    return list(session.scalars(stmt.limit(limit)).all())
