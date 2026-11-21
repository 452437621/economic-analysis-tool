"""Gold monitoring collector + composite score persistence."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.gold.providers import PROVIDERS, ProviderResult
from app.gold.registry import INDICATORS
from app.gold.scoring import compute_gold_score
from app.models.core import AnalyticsResult, GoldMetric, GoldProviderRun
from app.platform.db import SessionLocal
from app.platform.quality_gate import assess as assess_quality
from app.provenance import RunRecorder

logger = logging.getLogger(__name__)


def _upsert_metrics(session, records: list[dict]) -> tuple[int, int]:
    if not records:
        return 0, 0
    codes = {record["code"] for record in records}
    existing_rows = session.scalars(select(GoldMetric).where(GoldMetric.code.in_(codes))).all()
    existing = {(row.code, _key(row.as_of)): row for row in existing_rows}
    inserted = updated = 0
    for record in records:
        code = record["code"]
        if code not in INDICATORS:
            continue
        key = (code, _key(record["as_of"]))
        row = existing.get(key)
        if row is None:
            row = GoldMetric(
                code=code,
                as_of=record["as_of"],
                value=record["value"],
                source=record.get("source"),
                extra=record.get("extra"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            existing[key] = row
            inserted += 1
        else:
            row.value = record["value"]
            row.source = record.get("source")
            if record.get("extra"):
                row.extra = record["extra"]
            updated += 1
    session.commit()
    return inserted, updated


def _key(value: datetime) -> str:
    # SQLite returns naive datetimes: treat them as UTC instead of local time.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()


def _record_provider_run(session, result: ProviderResult) -> None:
    session.add(
        GoldProviderRun(
            provider=result.name,
            ok=result.ok,
            records=len(result.records),
            error=(result.error or "")[:2000] or None,
            checked_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def _store_score(session, score: dict) -> None:
    asof = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    row = session.scalar(
        select(AnalyticsResult).where(
            AnalyticsResult.kind == "gold",
            AnalyticsResult.subject == "GOLD",
            AnalyticsResult.asof == asof,
        )
    )
    if row is None:
        row = AnalyticsResult(kind="gold", subject="GOLD", asof=asof)
        session.add(row)
    row.payload = score
    session.commit()


def _derive_composite(rec: RunRecorder, score: dict, failed: list[str]):  # noqa: ANN001
    factors = score.get("factors") or []
    codes = [factor.get("code") for factor in factors if factor.get("code")]
    coverage = float(score.get("coverage") or 0.0)
    confidence = round(min(0.85, 0.40 + 0.50 * coverage), 2)
    caveats = [
        f"覆盖率 {coverage:.0%}：{len(codes)} 个因子可用，缺失因子按中性处理",
        "计分权重为人工设定，未经样本外权重优化",
    ]
    if failed:
        caveats.append(f"本次 {len(failed)} 个数据源失败：{', '.join(failed)}")
    return rec.derive(
        code="gold.composite",
        subject="GOLD",
        claim=f"黄金综合评分 {score.get('score')}（{score.get('label')}）",
        value={
            "score": score.get("score"),
            "label": score.get("label"),
            "coverage": coverage,
            "factors": codes,
        },
        confidence=confidence,
        evidence_grade="E3",
        method_id="gold.composite.v1",
        inputs=codes,
        steps=[
            {"name": "因子标准化", "detail": "每个因子按 5 年分位映射到 0–100"},
            {"name": "方向对齐", "detail": "利多黄金记为正贡献"},
            {"name": "加权合成", "detail": "按 registry 权重加权平均，再映射到 -100..100"},
        ],
        caveats=caveats,
        falsifiers=[
            "后续 60 个交易日黄金与该分值相关性为负，说明方向定反",
            "覆盖率低于 50% 且分值极端（|score|>60），视为噪声信号",
        ],
        opposing=[
            "实际利率与美元同向走强时，黄金可能同时受两者压制而偏离计分",
            "央行购金等慢变量对短期金价解释力弱",
        ],
    )


def collect_gold() -> dict:
    """Run all gold providers, persist observations and refresh the composite score."""
    summary = {"providers": {}, "records": 0, "quality": None}
    with SessionLocal() as session:
        rec = RunRecorder(
            session, kind="gold", subject="GOLD", method_id="gold.composite.v1"
        )
        try:
            rec.start()
            quality = assess_quality(session)
            summary["quality"] = quality
            if quality["status"] != "ok":
                rec.degrade(
                    "gold.quality.gate",
                    quality.get("caveat") or f"数据质量门控：{quality['status']}",
                    severity="critical" if quality["status"] == "blocked" else "warn",
                )
            failed: list[str] = []
            with rec.step("collect_providers", kind="fetch") as step:
                for name, fetcher in PROVIDERS:
                    try:
                        result = fetcher()
                    except Exception as exc:  # noqa: BLE001 - provider isolation
                        logger.exception("gold provider %s crashed", name)
                        result = ProviderResult(name, False, error=str(exc))
                    inserted, updated = _upsert_metrics(session, result.records)
                    _record_provider_run(session, result)
                    if not result.ok:
                        failed.append(name)
                        rec.degrade(
                            f"gold.provider.{name}", (result.error or "provider not ok")[:300]
                        )
                    summary["providers"][name] = {
                        "ok": result.ok,
                        "records": len(result.records),
                        "inserted": inserted,
                        "updated": updated,
                        "error": result.error,
                    }
                    summary["records"] += len(result.records)
                step.outputs = {
                    "providers": len(PROVIDERS),
                    "failed": failed,
                    "records": summary["records"],
                }

            with rec.step("score", kind="compute") as step:
                score = compute_gold_score(session)
                _store_score(session, score)
                summary["score"] = score["score"]
                summary["label"] = score["label"]
                summary["coverage"] = score["coverage"]
                _derive_composite(rec, score, failed)
                step.outputs = {
                    "score": score["score"],
                    "label": score["label"],
                    "coverage": score["coverage"],
                }

            rec.finish(summary=summary)
            session.commit()
        except Exception as exc:
            rec.fail(exc)
            session.commit()
            logger.exception("collect_gold failed")
            raise
        logger.info("collect_gold: %s", summary)
    return summary


def latest_provider_runs(session) -> list[dict]:
    rows = session.scalars(
        select(GoldProviderRun).order_by(GoldProviderRun.checked_at.desc()).limit(100)
    ).all()
    latest: dict[str, GoldProviderRun] = {}
    for row in rows:
        latest.setdefault(row.provider, row)
    return [
        {
            "provider": row.provider,
            "ok": row.ok,
            "records": row.records,
            "error": row.error,
            "checked_at": row.checked_at.isoformat() if row.checked_at else None,
        }
        for row in latest.values()
    ]
