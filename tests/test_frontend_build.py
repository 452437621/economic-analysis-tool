"""Vue 前端（V1.1）源码与构建产物检查。

旧版零构建看板已迁移到 web-legacy/（过渡期回退入口），
web/ 现在是 Vite 构建产物（index.html + assets/*）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
WEB_INDEX = ROOT / "web" / "index.html"
ASSETS = ROOT / "web" / "assets"
LEGACY = ROOT / "web-legacy" / "index.html"


def test_frontend_project_present():
    package = FRONTEND / "package.json"
    assert package.exists(), "frontend/package.json 缺失"
    data = json.loads(package.read_text(encoding="utf-8"))
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for required in ("vue", "vue-router", "pinia", "vite", "typescript", "echarts", "tailwindcss"):
        assert required in deps, f"缺少前端依赖: {required}"
    for required_file in ("src/main.ts", "src/App.vue", "src/router/index.ts", "vite.config.ts"):
        assert (FRONTEND / required_file).exists(), f"缺少 {required_file}"


def test_no_external_cdn_in_source():
    allowed = ("w3.org", "127.0.0.1", "localhost", "example.com")
    for path in (FRONTEND / "src").rglob("*"):
        if path.suffix not in {".ts", ".vue", ".css"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for url in re.findall(r"https?://[^\s\"'`)]+", text):
            assert any(host in url for host in allowed), f"{path} 引用外部资源 {url}"


def test_vite_builds_into_web():
    config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")
    assert "../web" in config, "vite.config.ts 的 build.outDir 必须指向 ../web"
    assert "/api" in config, "vite dev server 需要 /api 代理"


def test_spa_fallback_routes_present():
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "spa_fallback" in main
    assert '"/legacy"' in main
    assert "full_path:path" in main


def test_built_frontend_if_present():
    if not WEB_INDEX.exists():
        return  # 允许未构建的纯 Python 环境（CI 会先构建）
    html = WEB_INDEX.read_text(encoding="utf-8")
    assert 'id="app"' in html, "web/index.html 不是 Vue 入口"
    assert "/assets/" in html, "web/index.html 未引用 /assets"
    assert ASSETS.exists(), "web/assets 缺失"
    assert any(ASSETS.glob("*.js")), "web/assets 缺少 JS 产物"
    css = "".join(path.read_text(encoding="utf-8") for path in ASSETS.glob("*.css"))
    assert "--up-color" in css and "--down-color" in css, "构建 CSS 缺少涨跌色 token"
    assert "--bg:" in css, "构建 CSS 缺少设计 token"


def test_legacy_fallback_present():
    assert LEGACY.exists(), "web-legacy/index.html 缺失（过渡期回退入口）"
    html = LEGACY.read_text(encoding="utf-8")
    assert 'id="watchlist"' in html
    assert "initSectionNav" in html
