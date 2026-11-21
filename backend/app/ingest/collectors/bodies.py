"""Document body fetching and binary-body cleanup."""

from __future__ import annotations

import hashlib
import logging
import time

from sqlalchemy import func, select

from app.ingest.http import HttpClient
from app.ingest.providers.html_extract import extract_main_text, looks_like_binary
from app.models.core import Document, DocumentBody
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_bodies(limit: int = 20) -> dict:
    """Fetch full text of official documents and keep a content hash.

    PDF / 二进制原文（例如央行统计 PDF）不解析、不入库：文本抽不出可读正文，
    硬塞进 ``document_bodies`` 只会让证据抽屉显示乱码。这类文档标记为
    ``body_status="unsupported"``，前端只给「打开原文」。
    """
    started = time.perf_counter()
    stats: dict = {"fetched": 0, "skipped": 0, "failed": 0, "unsupported": 0, "errors": []}

    with HttpClient(min_interval=0.8) as client, SessionLocal() as session:
        documents = session.scalars(
            select(Document)
            .where(Document.body_status == "metadata")
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit)
        ).all()
        for document in documents:
            existing = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if existing is not None:
                document.body_status = "extracted"
                stats["skipped"] += 1
                continue
            if document.url.lower().split("?")[0].endswith(".pdf"):
                document.body_status = "unsupported"
                stats["unsupported"] += 1
                continue
            try:
                resp = client.get(document.url)
                resp.raise_for_status()
                content_type = (resp.headers.get("content-type") or "").lower()
                raw = resp.text
                if "pdf" in content_type or "octet-stream" in content_type or looks_like_binary(raw):
                    document.body_status = "unsupported"
                    stats["unsupported"] += 1
                    continue
                text = extract_main_text(raw)
                if len(text) < 80:
                    document.body_status = "no_body"
                    stats["skipped"] += 1
                    continue
                session.add(
                    DocumentBody(
                        document_id=document.id,
                        text=text,
                        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        word_count=len(text),
                    )
                )
                document.body_status = "extracted"
                stats["fetched"] += 1
                session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("body fetch failed %s: %s", document.id, exc)
                document.body_status = "failed"
                stats["failed"] += 1
                stats["errors"].append(f"{document.id}: {exc}")
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_bodies: %s", stats)
    return stats

def purge_binary_bodies(limit: int | None = None, session=None) -> dict:
    """清理历史上被当成文本入库的 PDF/二进制正文，以及它们派生的断言与片段。

    修复证据抽屉乱码的存量数据：删掉坏正文 → 断言/片段级联清理 → 文档标记
    ``body_status="unsupported"``，之后证据抽屉只显示「打开原文」。
    ``session`` 仅用于测试注入；生产走默认 SessionLocal。
    """
    from app.models.core import Claim, DocumentSpan

    stats: dict = {"scanned": 0, "purged": 0, "claims": 0, "spans": 0}
    own_session = session is None
    session = SessionLocal() if own_session else session
    try:
        stmt = select(DocumentBody)
        if limit is not None:
            stmt = stmt.limit(limit)
        for body in session.scalars(stmt).all():
            stats["scanned"] += 1
            document = session.get(Document, body.document_id)
            url = (document.url if document is not None else "") or ""
            if not (
                url.lower().split("?")[0].endswith(".pdf") or looks_like_binary(body.text)
            ):
                continue
            spans = session.scalars(
                select(DocumentSpan).where(DocumentSpan.document_id == body.document_id)
            ).all()
            for span in spans:
                session.delete(span)
            claims = session.scalars(
                select(Claim).where(Claim.document_id == body.document_id)
            ).all()
            for claim in claims:
                session.delete(claim)
            session.delete(body)
            if document is not None:
                document.body_status = "unsupported"
            stats["purged"] += 1
            stats["claims"] += len(claims)
            stats["spans"] += len(spans)
            session.commit()
    finally:
        if own_session:
            session.close()
    logger.info("purge_binary_bodies: %s", stats)
    return stats
