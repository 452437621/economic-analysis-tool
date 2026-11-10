"""Knowledge APIs: documents, claims and briefs."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Brief, Claim, Document, DocumentBody, DocumentSpan, Source
from app.platform.db import get_session

router = APIRouter(prefix="/api", tags=["knowledge"])


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@router.get("/documents/{document_id}")
def document_detail(document_id: str, session: Session = Depends(get_session)) -> dict:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    source = session.get(Source, document.source_id) if document.source_id else None
    body = session.scalar(select(DocumentBody).where(DocumentBody.document_id == document.id))
    rows = session.execute(
        select(Claim, DocumentSpan)
        .join(DocumentSpan, DocumentSpan.claim_id == Claim.id, isouter=True)
        .where(Claim.document_id == document.id)
    ).all()
    return {
        "id": document.id,
        "title": document.title,
        "url": document.url,
        "published_at": _iso(document.published_at or document.fetched_at),
        "source": {"name": source.name, "tier": source.tier} if source else None,
        "status": document.body_status,
        "body": {
            "text": body.text if body else None,
            "sha256": body.sha256 if body else None,
            "word_count": body.word_count if body else None,
            "extracted_at": _iso(body.extracted_at) if body else None,
        },
        "claims": [
            {
                "id": claim.id,
                "type": claim.type,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "value": claim.value,
                "unit": claim.unit,
                "confidence": claim.confidence,
                "span": {
                    "start": span.start if span else None,
                    "end": span.end if span else None,
                    "quote": span.quote if span else None,
                },
            }
            for claim, span in rows
        ],
    }


@router.get("/claims")
def claims(
    limit: int = Query(30, ge=1, le=200),
    subject: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    session: Session = Depends(get_session),
) -> dict:
    stmt = (
        select(Claim, Document)
        .join(Document, Document.id == Claim.document_id)
        .where(Claim.confidence >= min_confidence)
        .order_by(Claim.created_at.desc())
        .limit(limit)
    )
    if subject:
        stmt = stmt.where(Claim.subject == subject)
    rows = session.execute(stmt).all()
    return {
        "data": [
            {
                "id": claim.id,
                "document_id": document.id,
                "document_title": document.title,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "value": claim.value,
                "unit": claim.unit,
                "confidence": claim.confidence,
                "created_at": _iso(claim.created_at),
            }
            for claim, document in rows
        ]
    }


@router.get("/briefs")
def list_briefs(
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.scalars(select(Brief).order_by(Brief.created_at.desc()).limit(limit)).all()
    return {
        "data": [
            {
                "id": row.id,
                "kind": row.kind,
                "trade_date": row.trade_date.isoformat(),
                "created_at": _iso(row.created_at),
                "chars": len(row.markdown),
            }
            for row in rows
        ]
    }


@router.get("/briefs/latest")
def latest_brief(
    kind: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    if kind:
        stmt = select(Brief).where(Brief.kind == kind).order_by(Brief.created_at.desc()).limit(1)
    else:
        # 看板默认展示日常简报，周报只在显式查询时返回
        stmt = (
            select(Brief)
            .where(Brief.kind != "weekly")
            .order_by(Brief.created_at.desc())
            .limit(1)
        )
    brief = session.scalar(stmt)
    if brief is None and not kind:
        brief = session.scalar(select(Brief).order_by(Brief.created_at.desc()).limit(1))
    if brief is None:
        return {"data": None}
    return {
        "data": {
            "id": brief.id,
            "kind": brief.kind,
            "trade_date": brief.trade_date.isoformat(),
            "created_at": _iso(brief.created_at),
            "markdown": brief.markdown,
            "meta": brief.meta,
        }
    }


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, session: Session = Depends(get_session)) -> dict:
    brief = session.get(Brief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return {
        "id": brief.id,
        "kind": brief.kind,
        "trade_date": brief.trade_date.isoformat(),
        "created_at": _iso(brief.created_at),
        "markdown": brief.markdown,
        "meta": brief.meta,
    }


@router.get("/briefs/{brief_id}/print", response_class=HTMLResponse)
def print_brief(brief_id: str, session: Session = Depends(get_session)) -> HTMLResponse:
    from app.narrative.render import markdown_to_html

    brief = session.get(Brief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    body = markdown_to_html(brief.markdown)
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>EPIC 简报 {brief.trade_date.isoformat()}</title>
<style>
body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; max-width: 900px; margin: 32px auto; padding: 0 18px; color: #111; line-height: 1.7; }}
h1,h2,h3 {{ line-height: 1.35; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 13px; text-align: left; }}
th {{ background: #f2f2f2; }}
.mainline {{ font-size: 18px; font-weight: 700; line-height: 1.6; background: #f7f7f7;
  border-left: 4px solid #0b6fb3; padding: 10px 14px; margin: 8px 0 14px; }}
code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }}
@media print {{ body {{ margin: 0; }} }}
</style></head>
<body>
<p style="color:#666;font-size:12px;">EPIC · {brief.kind} · {brief.trade_date.isoformat()} · 生成于 {brief.created_at.isoformat()[:16].replace('T', ' ')}</p>
{body}
<p style="color:#999;font-size:11px;margin-top:32px;">仅供个人研究，不构成投资建议。</p>
</body></html>"""
    return HTMLResponse(page)


@router.get("/briefs/{brief_id}/markdown")
def export_brief(brief_id: str, session: Session = Depends(get_session)) -> PlainTextResponse:
    brief = session.get(Brief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    filename = f"epic-brief-{brief.kind}-{brief.trade_date.isoformat()}.md"
    return PlainTextResponse(
        brief.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/documents/{document_id}/evidence")
def export_evidence(document_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    body = session.scalar(select(DocumentBody).where(DocumentBody.document_id == document.id))
    claims = session.scalars(select(Claim).where(Claim.document_id == document.id)).all()
    payload = {
        "document": {
            "id": document.id,
            "title": document.title,
            "url": document.url,
            "published_at": _iso(document.published_at or document.fetched_at),
            "sha256": body.sha256 if body else None,
        },
        "body": body.text if body else None,
        "claims": [
            {
                "id": claim.id,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "value": claim.value,
                "unit": claim.unit,
                "confidence": claim.confidence,
            }
            for claim in claims
        ],
        "exported_at": datetime.now().isoformat(),
    }
    filename = f"epic-evidence-{document.id[:8]}.json"
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
