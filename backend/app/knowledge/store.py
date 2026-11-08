"""Claim persistence: claims + exact document spans."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.knowledge.extract import ExtractedClaim
from app.models.core import Claim, Document, DocumentBody, DocumentSpan


def save_claims(
    session: Session,
    document: Document,
    claims: list[ExtractedClaim],
    *,
    method: str = "rule",
) -> int:
    saved = 0
    for item in claims:
        claim = Claim(
            document_id=document.id,
            type="data" if item.value is not None else "fact",
            subject=item.subject,
            predicate=item.predicate,
            object={"quote": item.quote},
            value=item.value,
            unit=item.unit,
            confidence=item.confidence,
            status="active",
            extracted_by=method,
        )
        session.add(claim)
        session.flush()
        session.add(
            DocumentSpan(
                document_id=document.id,
                start=item.start,
                end=item.end,
                quote=item.quote,
                claim_id=claim.id,
            )
        )
        saved += 1
    return saved


def body_for(session: Session, document_id: str) -> DocumentBody | None:
    from sqlalchemy import select

    return session.scalar(select(DocumentBody).where(DocumentBody.document_id == document_id))
