"""Markdown renderer escaping."""

from __future__ import annotations

import pytest

from app.narrative.render import markdown_to_html

pytestmark = pytest.mark.unit


def test_markdown_render_escapes_html():
    html = markdown_to_html("## 标题\n\n<script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<h3>标题</h3>" in html
    assert "&lt;script&gt;" in html
    assert "<table>" in html
    assert 'class="mainline"' in markdown_to_html("> **一句话主线：** 测试")
