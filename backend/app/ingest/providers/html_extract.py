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

# 二进制/乱码比例阈值：PDF、zip、图片等被当作文本解码时，正文里会出现大量替换符与控制字符。
_BINARY_SAMPLE = 4000
_MAX_REPLACEMENT_RATIO = 0.002
_MAX_CONTROL_RATIO = 0.005


def looks_like_binary(text: str) -> bool:
    """判断抓取到的内容是否其实是二进制（PDF 等被解码成文本）。

    证据抽屉里的乱码就是 PDF 正文被当 HTML 解析后入库造成的，这里在入库前拦掉：
    以 ``%PDF`` 开头、替换符（U+FFFD）占比过高、控制字符占比过高，三者命中其一即视为二进制。
    """
    if not text:
        return True
    if text.lstrip()[:4] == "%PDF":
        return True
    sample = text[:_BINARY_SAMPLE]
    if not sample:
        return True
    if sample.count("\ufffd") / len(sample) > _MAX_REPLACEMENT_RATIO:
        return True
    control = sum(1 for ch in sample if ord(ch) < 9 or 13 < ord(ch) < 32)
    return control / len(sample) > _MAX_CONTROL_RATIO


def extract_main_text(html: str, max_chars: int = 20000) -> str:
    if looks_like_binary(html):
        # 不是可读 HTML：返回空串，让调用方按「无正文」处理，避免把二进制垃圾写进证据库。
        return ""
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
