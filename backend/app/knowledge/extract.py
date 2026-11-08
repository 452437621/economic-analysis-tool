"""Rule-based claim extraction (offline fallback before LLM is configured).

The extractor pulls numeric statements (with units) and attributes them to the
nearest known entity. Every claim keeps an exact character span in the document
body, so the evidence UI can highlight the original sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "美联储": ("Federal Reserve", "Fed", "FOMC", "美联储"),
    "欧洲央行": ("ECB", "European Central Bank", "欧洲央行"),
    "日本央行": ("BOJ", "Bank of Japan", "日本央行"),
    "中国央行": ("PBOC", "People's Bank of China", "中国央行", "人民银行"),
    "美国财政部": ("Treasury", "美国财政部", "财政部"),
    "白宫": ("White House", "白宫", "Trump", "特朗普"),
    "美国劳工部": ("BLS", "Labor Department", "劳工部"),
    "OPEC": ("OPEC", "欧佩克"),
}

INDICATOR_WORDS = (
    "CPI",
    "PCE",
    "GDP",
    "PMI",
    "通胀",
    "失业率",
    "利率",
    "收益率",
    "就业",
    "薪资",
    "产量",
    "库存",
    "出口",
    "进口",
    "赤字",
    "债务",
)

UNIT_PATTERN = (
    r"(?:%|个百分点|个基点|基点|bp|bps|美元|欧元|日元|人民币|元|万桶|亿吨|万吨|吨|"
    r"亿|万亿|万|百万|千|点|倍)"
)
NUMBER_RE = re.compile(rf"(?<![\w.])(-?\d+(?:,\d{{3}})*(?:\.\d+)?)\s*{UNIT_PATTERN}", re.IGNORECASE)
SENTENCE_SPLIT = re.compile(r"(?<=[。！？.!?])\s+|\n+")


@dataclass(slots=True)
class ExtractedClaim:
    subject: str
    predicate: str
    value: float | None
    unit: str | None
    quote: str
    start: int
    end: int
    confidence: float


def _find_entity(sentence: str) -> str | None:
    for canonical, aliases in ENTITY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in sentence.lower():
                return canonical
    return None


def _find_indicator(sentence: str) -> str | None:
    for word in INDICATOR_WORDS:
        if word in sentence:
            return word
    return None


def _to_float(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def extract_numeric_claims(
    text: str, max_claims: int = 40, default_subject: str | None = None
) -> list[ExtractedClaim]:
    """Return numeric claims with exact spans in ``text``.

    ``default_subject`` is used when a sentence has no known entity (typically
    the document's publisher, e.g. 欧洲央行), so claims stay attributable.
    """
    claims: list[ExtractedClaim] = []
    position = 0
    for part in SENTENCE_SPLIT.split(text):
        if not part:
            continue
        sentence = part.strip()
        start = text.find(sentence, position)
        if start < 0:
            start = text.find(sentence)
        if start < 0:
            continue
        end = start + len(sentence)
        position = end

        matches = list(NUMBER_RE.finditer(sentence))
        if not matches:
            continue
        subject = _find_entity(sentence) or default_subject or "市场"
        indicator = _find_indicator(sentence) or "数值"
        for match in matches[:3]:
            raw = match.group(1)
            unit = match.group(0)[len(raw) :].strip()
            claims.append(
                ExtractedClaim(
                    subject=subject,
                    predicate=f"{indicator}变动",
                    value=_to_float(raw),
                    unit=unit,
                    quote=sentence[:500],
                    start=start,
                    end=end,
                    confidence=0.45,
                )
            )
        if len(claims) >= max_claims:
            break
    return claims
