"""Rule-based and LLM claim extraction."""

from __future__ import annotations

import logging
import time

from sqlalchemy import func, select

from app.ingest import store
from app.knowledge.extract import extract_numeric_claims
from app.knowledge.store import save_claims
from app.models.core import Document, DocumentBody
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def extract_claims(limit: int = 30) -> dict:
    """Extract numeric claims + spans from stored bodies (rule-based v1)."""
    started = time.perf_counter()
    stats: dict = {"documents": 0, "claims": 0, "errors": []}

    with SessionLocal() as session:
        from app.models.core import Claim

        source_names = {
            row.id: row.name for row in session.scalars(select(store.Source)).all()
        }
        documents = session.scalars(
            select(Document)
            .where(Document.body_status == "extracted")
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit)
        ).all()
        for document in documents:
            body = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if body is None:
                document.body_status = "no_body"
                continue
            existing = session.scalar(
                select(func.count()).select_from(Claim).where(Claim.document_id == document.id)
            )
            if not existing:
                claims = extract_numeric_claims(
                    body.text, default_subject=source_names.get(document.source_id)
                )
                if claims:
                    stats["claims"] += save_claims(session, document, claims, method="rule")
            document.body_status = "claims_extracted"
            stats["documents"] += 1
            session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("extract_claims: %s", stats)
    return stats

def extract_claims_llm(limit: int = 8) -> dict:
    """LLM claim extraction (requires DEEPSEEK_API_KEY). Falls back cleanly."""
    from app.knowledge.llm_extract import extract_claims_with_llm
    from app.llm.client import LLMClient
    from app.models.core import Source

    client = LLMClient()
    if not client.available:
        return {"skipped": "no_api_key"}
    stats: dict = {"documents": 0, "claims": 0, "errors": []}

    with SessionLocal() as session:
        source_names = {row.id: row.name for row in session.scalars(select(Source)).all()}
        documents = session.scalars(
            select(Document)
            .where(Document.body_status.in_(["extracted", "claims_extracted"]))
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit * 3)
        ).all()
        processed = 0
        for document in documents:
            if processed >= limit:
                break
            meta = dict(document.meta or {})
            if meta.get("llm_extracted"):
                continue
            body = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if body is None:
                continue
            try:
                claims = extract_claims_with_llm(
                    client, body.text, default_subject=source_names.get(document.source_id)
                )
                if claims:
                    stats["claims"] += save_claims(session, document, claims, method="llm")
                meta["llm_extracted"] = True
                document.meta = meta
                session.commit()
                stats["documents"] += 1
                processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("llm extraction failed for %s: %s", document.id, exc)
                session.rollback()
                stats["errors"].append(f"{document.id}: {exc}")
    return stats
