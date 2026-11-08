"""HTML main-content extraction for official pages (BeautifulSoup)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

NOISE_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg")
CANDIDATE_SELECTORS = (
    "main",
    "article",
    "div.article",
    "div#article",
    "div.content",
    "div#content",
    "div.col-xs-12",
    "section",
)

_WS = re.compile(r"[ \t\r\f\v]+")
_MULTI_NL = re.compile(r"\n{3,}")


def extract_main_text(html: str, max_chars: int = 20000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(NOISE_TAGS)):
        tag.decompose()

    node = None
    for selector in CANDIDATE_SELECTORS:
        candidate = soup.select_one(selector)
        if candidate is not None and len(candidate.get_text(strip=True)) > 200:
            node = candidate
            break
    if node is None:
        node = soup.body or soup

    parts: list[str] = []
    for element in node.find_all(["p", "h1", "h2", "h3", "li", "blockquote", "td"]):
        text = element.get_text(" ", strip=True)
        if text:
            parts.append(text)
    if not parts:
        parts = [node.get_text(" ", strip=True)]

    text = "\n".join(parts)
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    text = _MULTI_NL.sub("\n\n", text).strip()
    return text[:max_chars]
