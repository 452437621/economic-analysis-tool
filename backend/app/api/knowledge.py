"""Knowledge APIs: documents, claims and briefs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import DAILY_KINDS, brief_payload, brief_summary, kind_filter
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
    offset: int = Query(0, ge=0),
    kind: str | None = Query(None, description="daily/weekly/monthly/manual/premarket/postmarket"),
    session: Session = Depends(get_session),
) -> dict:
    """简报历史列表（支持日报/周报/月报分组与分页，供前端上一期/下一期使用）。"""
    kinds = kind_filter(kind)
    stmt = select(Brief)
    count_stmt = select(func.count()).select_from(Brief)
    if kinds:
        stmt = stmt.where(Brief.kind.in_(kinds))
        count_stmt = count_stmt.where(Brief.kind.in_(kinds))
    total = int(session.scalar(count_stmt) or 0)
    rows = session.scalars(
        stmt.order_by(Brief.trade_date.desc(), Brief.created_at.desc()).offset(offset).limit(limit)
    ).all()
    kind_counts = dict(
        session.execute(select(Brief.kind, func.count()).group_by(Brief.kind)).all()
    )
    return {
        "data": [brief_summary(row) for row in rows],
        "meta": {
            "count": len(rows),
            "total": total,
            "offset": offset,
            "has_more": offset + len(rows) < total,
            "kinds": {key: int(value) for key, value in kind_counts.items()},
        },
    }


@router.get("/briefs/kinds")
def brief_kinds(session: Session = Depends(get_session)) -> dict:
    """可用简报类型与分组计数（前端 tab 徽标 / 空态判断）。"""
    counts = dict(session.execute(select(Brief.kind, func.count()).group_by(Brief.kind)).all())
    return {
        "data": {
            "kinds": {key: int(value) for key, value in counts.items()},
            "groups": {
                "daily": sum(int(counts.get(kind, 0)) for kind in DAILY_KINDS),
                "weekly": int(counts.get("weekly", 0)),
                "monthly": int(counts.get("monthly", 0)),
            },
        }
    }


@router.get("/briefs/latest")
def latest_brief(
    kind: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    """最新一期简报。``kind=daily`` 聚合 manual/premarket/postmarket。"""
    kinds = kind_filter(kind)
    if kinds:
        stmt = (
            select(Brief)
            .where(Brief.kind.in_(kinds))
            .order_by(Brief.created_at.desc(), Brief.trade_date.desc())
            .limit(1)
        )
    else:
        # 看板默认展示日常简报，周报/月报只在显式查询时返回
        stmt = (
            select(Brief)
            .where(Brief.kind.in_(DAILY_KINDS))
            .order_by(Brief.created_at.desc())
            .limit(1)
        )
    brief = session.scalar(stmt)
    if brief is None and not kinds:
        brief = session.scalar(select(Brief).order_by(Brief.created_at.desc()).limit(1))
    if brief is None:
        return {"data": None, "neighbors": {"previous_id": None, "next_id": None}}
    group = kinds or DAILY_KINDS
    previous = session.scalar(
        select(Brief)
        .where(Brief.kind.in_(group), Brief.trade_date < brief.trade_date)
        .order_by(Brief.trade_date.desc())
        .limit(1)
    )
    following = session.scalar(
        select(Brief)
        .where(Brief.kind.in_(group), Brief.trade_date > brief.trade_date)
        .order_by(Brief.trade_date.asc())
        .limit(1)
    )
    return {
        "data": brief_payload(brief),
        "neighbors": {
            "previous_id": previous.id if previous else None,
            "next_id": following.id if following else None,
        },
    }


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: str, session: Session = Depends(get_session)) -> dict:
    brief = session.get(Brief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return brief_payload(brief)


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
.up {{ color: #c0392b; }} .down {{ color: #2e8b57; }}
b {{ color: #0b5f94; }}
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
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    filename = f"epic-evidence-{document.id[:8]}.json"
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
