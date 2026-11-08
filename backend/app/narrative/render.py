"""Minimal Markdown → HTML renderer for printable briefs.

Supports headings, pipe tables, bullet lists, bold and inline code. Escapes all
HTML first, so untrusted text cannot inject markup.
"""

from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = _BOLD.sub(r"<b>\1</b>", escaped)
    escaped = _CODE.sub(r"<code>\1</code>", escaped)
    return escaped


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_parts: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|"):
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            rows = [row for row in block if not re.fullmatch(r"\|[\s\-:|]+\|", row)]
            html_parts.append("<table>")
            for row_index, row in enumerate(rows):
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                tag = "th" if row_index == 0 else "td"
                html_parts.append(
                    "<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in cells) + "</tr>"
                )
            html_parts.append("</table>")
            continue
        if re.match(r"^#{1,3} ", line):
            level = len(line) - len(line.lstrip("#"))
            html_parts.append(f"<h{level + 1}>{_inline(line[level + 1:])}</h{level + 1}>")
        elif line.startswith("- "):
            html_parts.append(f"<li>{_inline(line[2:])}</li>")
        elif line.strip() == "":
            html_parts.append("")
        else:
            html_parts.append(f"<p>{_inline(line)}</p>")
        index += 1
    return "\n".join(html_parts)
