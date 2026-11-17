"""交易日志 API（V2.0）：按交易日的复盘记录，独立页面维护。

设计约定：
- 每个交易日一条记录（模型上 ``entry_date`` 唯一），因此保存是按日 upsert；
- ``title`` / ``tags`` 存放在 ``meta`` JSON 字段，避免为两个可选字段加迁移；
- 列表支持关键词、日期区间与分页；删除与编辑按 id；
- 与每周复盘脚本共用同一张表，保持向后兼容。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.core import JournalEntry
from app.platform.db import get_session

router = APIRouter(prefix="/api/journal", tags=["journal"])

MAX_CONTENT = 20000
MAX_TITLE = 120
MAX_TAGS = 8
MAX_TAG_LEN = 16


class JournalIn(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT)
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    tags: list[str] | None = None


class JournalPatch(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT)
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    tags: list[str] | None = None


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: list[str] = []
    for raw in tags:
        tag = str(raw).strip()[:MAX_TAG_LEN]
        if tag and tag not in seen:
            seen.append(tag)
        if len(seen) >= MAX_TAGS:
            break
    return seen


def _meta(title: str | None, tags: list[str] | None) -> dict:
    meta: dict = {}
    clean_title = (title or "").strip()
    if clean_title:
        meta["title"] = clean_title[:MAX_TITLE]
    clean_tags = _clean_tags(tags)
    if clean_tags:
        meta["tags"] = clean_tags
    return meta


def _serialize(row: JournalEntry) -> dict:
    meta = row.meta or {}
    return {
        "id": row.id,
        "entry_date": row.entry_date.isoformat(),
        "title": meta.get("title") or "",
        "tags": meta.get("tags") or [],
        "content": row.content,
        "length": len(row.content or ""),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def list_entries(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=120),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(JournalEntry)
    count_stmt = select(func.count()).select_from(JournalEntry)
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                JournalEntry.content.like(pattern),
                cast(JournalEntry.meta, String).like(pattern),
            )
        )
    if date_from is not None:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(JournalEntry.entry_date <= date_to)
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = session.scalar(count_stmt) or 0
    rows = session.scalars(
        stmt.order_by(JournalEntry.entry_date.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [_serialize(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{entry_id}")
def get_entry(entry_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(JournalEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    return _serialize(row)


@router.post("")
def upsert_entry(payload: JournalIn, session: Session = Depends(get_session)) -> dict:
    entry_date = payload.entry_date or date.today()
    row = session.scalar(select(JournalEntry).where(JournalEntry.entry_date == entry_date))
    created = row is None
    if row is None:
        row = JournalEntry(entry_date=entry_date, content=payload.content, meta=_meta(payload.title, payload.tags))
        session.add(row)
    else:
        row.content = payload.content
        row.meta = _meta(payload.title, payload.tags)
    session.commit()
    session.refresh(row)
    return {"item": _serialize(row), "created": created}


@router.patch("/{entry_id}")
def update_entry(
    entry_id: str, payload: JournalPatch, session: Session = Depends(get_session)
) -> dict:
    row = session.get(JournalEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    if payload.entry_date is not None and payload.entry_date != row.entry_date:
        clash = session.scalar(
            select(JournalEntry).where(
                JournalEntry.entry_date == payload.entry_date, JournalEntry.id != entry_id
            )
        )
        if clash is not None:
            raise HTTPException(status_code=409, detail="another entry already exists for that date")
        row.entry_date = payload.entry_date
    if payload.content is not None:
        row.content = payload.content
    meta = dict(row.meta or {})
    if payload.title is not None:
        clean_title = payload.title.strip()[:MAX_TITLE]
        if clean_title:
            meta["title"] = clean_title
        else:
            meta.pop("title", None)
    if payload.tags is not None:
        clean_tags = _clean_tags(payload.tags)
        if clean_tags:
            meta["tags"] = clean_tags
        else:
            meta.pop("tags", None)
    row.meta = meta or None
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.delete("/{entry_id}")
def delete_entry(entry_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(JournalEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    session.delete(row)
    session.commit()
    return {"deleted": True, "id": entry_id}
