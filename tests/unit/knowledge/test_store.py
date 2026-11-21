"""Claim and document-span persistence."""

from __future__ import annotations

import pytest

from sqlalchemy import select

from app.knowledge.extract import ExtractedClaim
from app.knowledge.store import body_for, save_claims
from app.models.core import Claim, Document, DocumentBody, DocumentSpan
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _document(session) -> Document:
    document = Document(url_hash="hash-1", url="https://example.com/a", title="test")
    session.add(document)
    session.flush()
    return document


def test_save_claims_creates_claims_and_spans(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            document = _document(session)
            claims = [
                ExtractedClaim("美国CPI", "同比", 3.2, "%", "CPI 同比 3.2%", 0, 10, 0.9),
                ExtractedClaim("美联储", "降息", None, None, "美联储降息", 11, 16, 0.8),
            ]
            assert save_claims(session, document, claims) == 2
            session.commit()
            stored = session.scalars(select(Claim)).all()
            spans = session.scalars(select(DocumentSpan)).all()
        assert len(stored) == 2
        assert {claim.type for claim in stored} == {"data", "fact"}
        assert len(spans) == 2
        assert all(span.document_id == document.id for span in spans)
    finally:
        engine.dispose()


def test_body_for_returns_document_body(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            document = _document(session)
            body = DocumentBody(document_id=document.id, text="正文")
            session.add(body)
            session.commit()
            assert body_for(session, document.id).text == "正文"
            assert body_for(session, "missing") is None
    finally:
        engine.dispose()
