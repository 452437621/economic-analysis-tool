"""Estimate line coverage without third-party packages (Python 3.12+).

CI uses ``pytest-cov`` (see pyproject.toml).  This helper exists for offline
sandboxes where pip cannot reach an index: it uses ``sys.monitoring`` (PEP 669)
to record executed lines under ``backend/app`` and compares them with the
executable statements found by ``ast``.

Usage:
    python scripts/coverage_estimate.py [pytest args...]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "backend" / "app").resolve()
TOOL_ID = 3


def _executable_lines(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring / bare literal
        lines.add(node.lineno)
    return lines


def _module_files() -> list[Path]:
    return sorted(path for path in APP.rglob("*.py") if "__pycache__" not in path.parts)


def main(argv: list[str]) -> int:
    if not hasattr(sys, "monitoring"):
        print("sys.monitoring requires Python 3.12+", file=sys.stderr)
        return 2

    monitoring = sys.monitoring
    monitoring.use_tool_id(TOOL_ID, "epic-coverage")
    executed: set[tuple[str, int]] = set()

    def on_line(code, line):  # noqa: ANN001 - monitoring callback signature
        filename = code.co_filename
        if filename.startswith(str(APP)):
            executed.add((filename, line))

    monitoring.register_callback(TOOL_ID, monitoring.events.LINE, on_line)
    monitoring.set_events(TOOL_ID, monitoring.events.LINE)

    import pytest

    code = pytest.main(["-q", *argv])
    monitoring.set_events(TOOL_ID, 0)
    monitoring.free_tool_id(TOOL_ID)

    total = hit = 0
    rows = []
    for path in _module_files():
        lines = _executable_lines(path)
        if not lines:
            continue
        covered = {line for filename, line in executed if filename == str(path)}
        module_hit = len(lines & covered)
        total += len(lines)
        hit += module_hit
        rows.append((path.relative_to(ROOT), module_hit, len(lines)))

    print()
    print(f"coverage estimate: {hit}/{total} executable lines = {100 * hit / total:.1f}%")
    print("lowest modules:")
    for relative, module_hit, module_total in sorted(rows, key=lambda row: row[1] / row[2])[:20]:
        print(f"  {module_hit:4d}/{module_total:<4d} {100 * module_hit / module_total:5.1f}%  {relative}")
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
