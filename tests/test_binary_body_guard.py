"""证据抽屉乱码回归：PDF/二进制正文不得入库，存量坏正文可清理。"""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ingest.pipeline import purge_binary_bodies
from app.ingest.providers.html_extract import extract_main_text, looks_like_binary
from app.models.base import Base
from app.models.core import Claim, Document, DocumentBody, DocumentSpan

PDF_TEXT = (
    "%PDF-1.6\n%\ufffd\ufffd\ufffd\ufffd\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\n"
    "stream\n\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\nendstream\n"
)
HTML = "<html><body><main><p>FOMC statement: inflation 2.8%, unemployment 4.1%.</p></main></body></html>"


def test_looks_like_binary_detects_pdf_payloads():
    assert looks_like_binary(PDF_TEXT) is True
    assert looks_like_binary("\ufffd" * 500) is True
    assert looks_like_binary("FOMC statement: inflation 2.8%, unemployment 4.1%.") is False


def test_extract_main_text_returns_empty_for_binary_payload():
    assert extract_main_text(PDF_TEXT) == ""
    assert "FOMC" in extract_main_text(HTML)


def test_purge_binary_bodies_removes_garbled_text_and_claims():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                Document(
                    id="doc-pdf",
                    url="https://www.ecb.europa.eu/press/speech.en.pdf",
                    url_hash="hash-pdf",
                    body_status="claims_extracted",
                ),
                Document(
                    id="doc-ok",
                    url="https://www.federalreserve.gov/statement.htm",
                    url_hash="hash-ok",
                    body_status="claims_extracted",
                ),
            ]
        )
        session.add_all(
            [
                DocumentBody(id="body-pdf", document_id="doc-pdf", text=PDF_TEXT, word_count=200),
                DocumentBody(
                    id="body-ok", document_id="doc-ok", text="Inflation was 2.8% in October." * 5,
                    word_count=180,
                ),
            ]
        )
        session.add_all(
            [
                Claim(
                    id="claim-pdf",
                    document_id="doc-pdf",
                    type="data",
                    subject="欧洲央行",
                    predicate="通胀",
                    confidence=0.5,
                ),
                Claim(
                    id="claim-ok",
                    document_id="doc-ok",
                    type="data",
                    subject="美联储",
                    predicate="通胀",
                    confidence=0.6,
                ),
            ]
        )
        session.add(
            DocumentSpan(
                id="span-pdf",
                document_id="doc-pdf",
                start=0,
                end=8,
                quote=PDF_TEXT[:8],
                claim_id="claim-pdf",
            )
        )
        session.commit()

        stats = purge_binary_bodies(session=session)

    assert stats == {"scanned": 2, "purged": 1, "claims": 1, "spans": 1}

    with Session(engine) as session:
        kept = session.scalars(select(DocumentBody)).all()
        assert [body.document_id for body in kept] == ["doc-ok"]
        assert session.get(Claim, "claim-pdf") is None
        assert session.get(Claim, "claim-ok") is not None
        assert session.get(DocumentSpan, "span-pdf") is None
        assert session.get(Document, "doc-pdf").body_status == "unsupported"
        assert session.get(Document, "doc-ok").body_status == "claims_extracted"
