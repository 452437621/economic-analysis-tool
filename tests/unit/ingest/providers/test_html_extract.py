"""HTML main-text extraction tests (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers.html_extract import extract_main_text

pytestmark = pytest.mark.unit

HTML = """
<html><head><script>var x = 1;</script><style>.a{}</style></head>
<body>
<nav>Home | Markets</nav>
<main>
  <h1>FOMC statement</h1>
  <p>Recent indicators suggest that economic activity has continued to expand.</p>
  <p>Inflation remains somewhat elevated at 2.8% while unemployment is 4.1%.</p>
</main>
<footer>Disclaimer</footer>
</body></html>
"""


def test_extract_main_text_removes_noise():
    text = extract_main_text(HTML)
    assert "FOMC statement" in text
    assert "2.8%" in text
    assert "Home | Markets" not in text
    assert "var x = 1" not in text
    assert "Disclaimer" not in text
