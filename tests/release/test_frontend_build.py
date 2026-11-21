"""Vue 前端源码与构建产物检查。

web/ 是 Vite 构建产物（index.html + assets/*），不入版本库（由 scripts/build.ps1 生成）；
过渡期旧看板 web-legacy/ 已在 V1.3 收尾时删除。
"""

from __future__ import annotations

import json
import re

import pytest

from tests.helpers import ROOT

pytestmark = pytest.mark.release

FRONTEND = ROOT / "frontend"
WEB_INDEX = ROOT / "web" / "index.html"
ASSETS = ROOT / "web" / "assets"


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
    assert "full_path:path" in main
    assert "/legacy" not in main, "过渡期 /legacy 路由已删除"


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
