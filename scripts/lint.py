"""Offline static checks (no third-party deps).

Covers the blind spots unit tests miss: syntax/AST smells, unused imports,
Vue 前端结构与构建产物、外部资源引用、markdown links and version drift.

Usage:
    python scripts/lint.py            # full check, exit 1 on errors
    python scripts/lint.py --quiet    # only print failures
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "app"
WEB = ROOT / "web" / "index.html"
FRONTEND = ROOT / "frontend"

errors: list[str] = []
warnings: list[str] = []


def err(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def _py_files() -> list[Path]:
    return sorted(BACKEND.rglob("*.py"))


def check_python_syntax() -> None:
    for path in _py_files():
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:  # pragma: no cover - only on a broken tree
            err(f"syntax: {path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")


def check_ast_smells() -> None:
    """Bare excepts, mutable defaults and naive local-time calls."""
    for path in _py_files():
        rel = path.relative_to(ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Track enclosing function so CLI entrypoints may print to stdout.
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                err(f"bare-except: {rel}:{node.lineno}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d]
                for default in defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        err(f"mutable-default: {rel}:{default.lineno} in {node.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "now" and not node.args and not node.keywords:
                    warn(f"naive-datetime: {rel}:{node.lineno} (use timezone.utc)")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print" and "backend" in str(rel):
                    current = parents.get(node)
                    enclosing = None
                    while current is not None:
                        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            enclosing = current.name
                            break
                        current = parents.get(current)
                    if enclosing != "main":
                        warn(f"print-in-backend: {rel}:{node.lineno} (use logging)")


def check_unused_imports() -> None:
    """Heuristic: an imported name appearing exactly once in the file is unused.

    ``__init__.py`` files are skipped because re-exporting is their job.
    """
    for path in _py_files():
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(ROOT)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = (alias.asname or alias.name).split(".")[0]
                if name == "annotations":
                    continue
                uses = len(re.findall(rf"\b{re.escape(name)}\b", source))
                if uses <= 1:
                    err(f"unused-import: {rel}:{node.lineno} {name}")


def check_encoding() -> None:
    for path in [*_py_files(), WEB, *sorted((ROOT / "docs").glob("*.md"))]:
        if not path.exists():
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            err(f"encoding: {path.relative_to(ROOT)} not UTF-8 ({exc.reason})")
            continue
        if "\ufffd" in text:
            err(f"encoding: {path.relative_to(ROOT)} contains U+FFFD replacement chars")


def check_frontend() -> None:
    """Vue 前端：源码结构 + 依赖 + 无外部 CDN + 构建产物（存在时校验）。"""
    if not FRONTEND.exists():
        err("frontend: frontend/ 目录缺失")
        return

    package = FRONTEND / "package.json"
    if not package.exists():
        err("frontend: frontend/package.json 缺失")
        return
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"frontend: package.json 解析失败: {exc}")
        return
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for required in ("vue", "vue-router", "pinia", "vite", "typescript", "echarts", "tailwindcss"):
        if required not in deps:
            err(f"frontend: package.json 缺少依赖 {required}")
    for required_file in ("src/main.ts", "src/App.vue", "src/router/index.ts", "vite.config.ts", "index.html"):
        if not (FRONTEND / required_file).exists():
            err(f"frontend: 缺少 {required_file}")

    allowed_hosts = ("w3.org", "127.0.0.1", "localhost", "vuejs.org", "example.com")
    for path in (FRONTEND / "src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".vue", ".css"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for url in re.findall(r"https?://[^\s\"'`)]+", text):
            if any(host in url for host in allowed_hosts):
                continue
            err(f"frontend: {path.relative_to(ROOT)} 引用外部资源 {url}")

    if WEB.exists():
        html = WEB.read_text(encoding="utf-8")
        if 'id="app"' not in html:
            err('frontend: web/index.html 不是 Vue 入口（缺少 id="app"）')
        if "/assets/" not in html:
            err("frontend: web/index.html 未引用 /assets（构建产物异常）")
        assets = ROOT / "web" / "assets"
        if not assets.exists() or not any(assets.glob("*.js")):
            err("frontend: web/assets 缺少构建产物")
    else:
        warn("frontend: web/index.html 尚未构建（运行 scripts\\build.ps1）")


def check_docs_links() -> None:
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if target.startswith(("http", "#", "mailto:")):
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                err(f"docs: {path.relative_to(ROOT)} -> missing {target}")


def check_version() -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    from app import __version__ as package_version  # noqa: PLC0415

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if not project_version:
        err("version: pyproject.toml has no [project] version")
        return
    if project_version.group(1) != package_version:
        err(
            "version: pyproject "
            f"{project_version.group(1)} != app/__init__ {package_version}"
        )
    for doc in (ROOT / "README.md", ROOT / "docs" / "10-发布说明与验收.md"):
        text = doc.read_text(encoding="utf-8")
        short = package_version.replace("1.0.0-", "1.0-")  # V1.0-rc1 style
        if not any(token in text for token in (package_version, short)):
            warn(f"version: {doc.name} does not mention {package_version}")


def check_env_example() -> None:
    env = ROOT / ".env.example"
    if not env.exists():
        err("env: .env.example missing")
        return
    text = env.read_text(encoding="utf-8")
    for key in ("EPIC_HOST", "EPIC_PORT", "EPIC_ACCOUNT_EQUITY", "EPIC_RISK_PER_TRADE_PCT"):
        if key not in text:
            warn(f"env: .env.example lacks {key}")


def check_powershell() -> None:
    """Windows scripts must be BOM-prefixed (5.1 misparses UTF-8 Chinese) and syntactically valid."""
    scripts = sorted((ROOT / "scripts").glob("*.ps1"))
    if not scripts:
        return
    for path in scripts:
        data = path.read_bytes()
        if not data.startswith(b"\xef\xbb\xbf") and any(byte > 0x7F for byte in data):
            err(f"powershell: {path.name} contains non-ASCII text without UTF-8 BOM")

    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        warn("powershell: no PowerShell interpreter found, syntax check skipped")
        return
    checker = ROOT / "scripts" / "_lint_ps.ps1"
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(checker),
            "-Files",
            ",".join(str(path) for path in scripts),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        err(f"powershell: syntax errors:\n{result.stdout.strip()[:600]}")


CHECKS = (
    ("syntax", check_python_syntax),
    ("ast", check_ast_smells),
    ("imports", check_unused_imports),
    ("encoding", check_encoding),
    ("frontend", check_frontend),
    ("powershell", check_powershell),
    ("docs", check_docs_links),
    ("version", check_version),
    ("env", check_env_example),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="EPIC offline lint")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    parser.add_argument("--json", action="store_true", help="emit machine-readable result")
    args = parser.parse_args()

    for name, check in CHECKS:
        before = len(errors)
        try:
            check()
        except Exception as exc:  # noqa: BLE001 - a check must never crash the gate
            err(f"{name}: crashed: {exc}")
        if not args.quiet and not args.json:
            status = "FAIL" if len(errors) > before else "ok"
            print(f"[lint] {name:<9} {status}")

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        for warning in warnings:
            print(f"[lint] WARN {warning}")
        for message in errors:
            print(f"[lint] ERROR {message}")
        print(f"[lint] {'PASSED' if not errors else 'FAILED'} ({len(errors)} errors, {len(warnings)} warnings)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
