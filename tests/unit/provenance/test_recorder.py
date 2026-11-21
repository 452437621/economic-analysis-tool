"""透明化地基（M0）：运行记录、步骤、推导谱系与玻璃盒读接口。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.v2 import AnalysisRun, AnalysisStep, Derivation, MethodRegistry
from app.platform.db import SessionLocal, init_db
from app.provenance import RunRecorder, derive_id, ensure_methods

pytestmark = pytest.mark.unit

CODE = "test.provenance.regime"


def _records() -> int:
    with SessionLocal() as session:
        return len(session.scalars(select(AnalysisRun).where(AnalysisRun.kind == "forecast")).all())


def test_run_recorder_writes_steps_and_derivation():
    init_db()
    with SessionLocal() as session:
        rec = RunRecorder(
            session, kind="forecast", subject="test", method_id="analytics.regime.v1"
        )
        rec.start()
        with rec.step("load", kind="fetch") as step:
            step.outputs = {"rows": 3}
        with rec.step("compute", kind="compute") as step:
            step.outputs = {"score": 42}
        derived = rec.derive(
            code=CODE,
            claim="测试推导",
            value={"score": 42},
            confidence=0.61,
            evidence_grade="E3",
            inputs=["US10Y", "US2Y"],
            steps=[{"name": "z 分数"}],
            caveats=["仅测试"],
            falsifiers=["后续 20 日相关性为负"],
            opposing=["期限溢价"],
        )
        rec.finish(summary={"ok": True})
        session.commit()
        run_id = rec.run.id
        derivation_id = derived.id

    with SessionLocal() as session:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        assert run.status == "ok"
        assert run.finished_at is not None
        assert run.summary == {"ok": True}
        steps = session.scalars(
            select(AnalysisStep).where(AnalysisStep.run_id == run_id).order_by(AnalysisStep.seq)
        ).all()
        assert [step.name for step in steps] == ["load", "compute"]
        assert steps[0].outputs == {"rows": 3}
        row = session.get(Derivation, derivation_id)
        assert row is not None
        assert row.code == CODE
        assert row.confidence == 0.61
        assert row.evidence_grade == "E3"
        assert row.inputs == ["US10Y", "US2Y"]
        assert row.caveats == ["仅测试"]
        assert row.falsifiers == ["后续 20 日相关性为负"]
        assert row.run_id == run_id


def test_derive_is_idempotent_for_same_inputs():
    init_db()
    code = "test.provenance.idempotent"
    # 共享测试库可能保留了推导 id 规则变更前写入的旧行，先清掉这个测试专用的 code。
    with SessionLocal() as session:
        for stale in session.scalars(select(Derivation).where(Derivation.code == code)).all():
            session.delete(stale)
        session.commit()
    ids = []
    for _ in range(2):
        with SessionLocal() as session:
            rec = RunRecorder(
                session, kind="forecast", subject="test", method_id="analytics.regime.v1"
            )
            rec.start()
            row = rec.derive(code=code, claim="幂等推导", value={"score": 42}, inputs=["US10Y"])
            rec.finish()
            session.commit()
            ids.append(row.id)
    assert ids[0] == ids[1]
    with SessionLocal() as session:
        rows = session.scalars(select(Derivation).where(Derivation.code == code)).all()
        assert len(rows) == 1
        # 同一推导被后一次运行刷新（保留最新 run_id），但仍是一行
        assert rows[0].id == ids[0]


def test_degrade_marks_run_degraded():
    init_db()
    with SessionLocal() as session:
        rec = RunRecorder(session, kind="forecast", subject="test-degrade")
        rec.start()
        rec.degrade("test.source_down", "数据源不可用")
        with rec.step("fetch", kind="fetch"):
            pass
        rec.finish()
        session.commit()
        run_id = rec.run.id
    with SessionLocal() as session:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        assert run.status == "degraded"
        assert run.degraded is True
        assert run.degraded_reasons[0]["code"] == "test.source_down"


def test_fail_records_error_and_reraises():
    init_db()
    run_id = None
    with SessionLocal() as session:
        rec = RunRecorder(session, kind="forecast", subject="test-fail")
        rec.start()
        run_id = rec.run.id
        try:
            with rec.step("boom", kind="compute"):
                raise RuntimeError("模拟失败")
        except RuntimeError as exc:
            assert "模拟失败" in str(exc)
            rec.fail(exc)
            session.commit()
        else:  # pragma: no cover - 必须抛出
            raise AssertionError("异常必须继续抛出，调度层才能记录失败")

    with SessionLocal() as session:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert "RuntimeError" in (run.error or "")


def test_derive_id_changes_with_inputs_and_code_sha():
    base = derive_id("analytics.regime.v1", "1.0", ["A"], None, "abc")
    assert base == derive_id("analytics.regime.v1", "1.0", ["A"], None, "abc")
    assert base != derive_id("analytics.regime.v1", "1.0", ["B"], None, "abc")
    assert base != derive_id("analytics.wind.v1", "1.0", ["A"], None, "abc")
    assert base != derive_id("analytics.regime.v1", "1.1", ["A"], None, "abc")
    assert base != derive_id("analytics.regime.v1", "1.0", ["A"], {"x": 1}, "abc")


def test_methods_are_registered_with_code_sha():
    init_db()
    with SessionLocal() as session:
        ensure_methods(session)
        session.commit()
        rows = session.scalars(select(MethodRegistry)).all()
        by_id = {row.method_id: row for row in rows}
        assert "analytics.run.v1" in by_id
        assert "gold.composite.v1" in by_id
        assert by_id["analytics.run.v1"].code_sha
        assert len(by_id["analytics.run.v1"].code_sha or "") == 16


def test_glassbox_status_endpoint():
    init_db()
    with TestClient(app) as client:
        response = client.get("/api/v2/status")
    assert response.status_code == 200
    body = response.json()
    assert "last_run" in body
    assert {"runs", "degraded", "failed", "derivations", "observations", "methods"} <= set(
        body["counts"]
    )


def test_glassbox_runs_detail_and_derivation_endpoints():
    init_db()
    with SessionLocal() as session:
        rec = RunRecorder(session, kind="forecast", subject="test-api", method_id="analytics.wind.v1")
        rec.start()
        with rec.step("fetch", kind="fetch") as step:
            step.outputs = {"rows": 1}
        rec.degrade("test.api", "接口测试降级")
        row = rec.derive(code="test.provenance.api", claim="接口推导", confidence=0.5)
        rec.finish()
        session.commit()
        run_id, derivation_id = rec.run.id, row.id

    with TestClient(app) as client:
        runs = client.get("/api/v2/runs", params={"kind": "forecast", "limit": 5})
        assert runs.status_code == 200
        assert any(item["id"] == run_id for item in runs.json()["items"])

        detail = client.get(f"/api/v2/runs/{run_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["run"]["status"] == "degraded"
        assert payload["steps"][0]["name"] == "fetch"
        assert payload["rules"][0]["rule_id"] == "degrade.test.api"
        assert payload["derivations"][0]["code"] == "test.provenance.api"

        one = client.get(f"/api/v2/derivations/{derivation_id}")
        assert one.status_code == 200
        body = one.json()
        assert body["derivation"]["id"] == derivation_id
        assert body["method"]["method_id"] == "analytics.wind.v1"
        assert body["parents"] == [] and body["children"] == []

        missing = client.get("/api/v2/derivations/does-not-exist")
        assert missing.status_code == 404
        missing_run = client.get("/api/v2/runs/does-not-exist")
        assert missing_run.status_code == 404
