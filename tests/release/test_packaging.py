"""Packaging regression: every ``app`` subpackage must be discoverable.

The editable install masks packaging mistakes because it only adds ``backend``
to ``sys.path``.  This test checks the setuptools discovery configuration and
simulates the wheel layout without invoking pip (the local sandbox has no
network, so CI is the place that builds a real wheel).
"""

from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from tests.helpers import ROOT

pytestmark = [pytest.mark.release, pytest.mark.slow]

BACKEND = ROOT / "backend"
BACKEND_APP = BACKEND / "app"


def _discovered_packages() -> set[str]:
    packages = set()
    for init in BACKEND_APP.rglob("__init__.py"):
        relative = init.parent.relative_to(BACKEND).as_posix().replace("/", ".")
        packages.add(relative)
    packages.add("app")
    return packages


def test_pyproject_discovers_all_app_subpackages() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    find = data["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["backend"]
    assert find["include"] == ["app", "app.*"]

    discovered = _discovered_packages()
    for required in (
        "app.cycle",
        "app.api",
        "app.ingest",
        "app.ingest.providers",
        "app.ingest.collectors",
        "app.lens",
        "app.platform",
        "app.timeline",
    ):
        assert required in discovered, required


def _synthetic_wheel(destination: Path) -> Path:
    """Write the wheel layout setuptools would produce for ``packages.find``."""
    wheel = destination / "epic_market_analysis-3.0.0-py3-none-any.whl"
    dist_info = "epic_market_analysis-3.0.0.dist-info"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in BACKEND_APP.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".yaml", ".json", ".md"}:
                archive.write(path, path.relative_to(BACKEND).as_posix())
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\nName: epic-market-analysis\nVersion: 3.0.0\n",
        )
        archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n")
    return wheel


@pytest.mark.slow
def test_synthetic_wheel_contains_and_imports_every_module(tmp_path: Path) -> None:
    wheel = _synthetic_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    for init in BACKEND_APP.rglob("__init__.py"):
        relative = init.relative_to(BACKEND).as_posix()
        assert relative in names, f"wheel is missing {relative}"
    assert not any(name.startswith("tests/") for name in names)

    extracted = tmp_path / "site"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(extracted)
    script = (
        "import sys, pkgutil, importlib\n"
        f"sys.path.insert(0, r'{extracted}')\n"
        "import app\n"
        "assert app.__file__.startswith(r'%s'), app.__file__\n"
        "mods = [m.name for m in pkgutil.walk_packages(app.__path__, 'app.')]\n"
        "[importlib.import_module(name) for name in mods]\n"
        "print('imported', len(mods))\n" % extracted
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "imported" in result.stdout


def test_every_app_module_imports() -> None:
    import app

    modules = [info.name for info in pkgutil.walk_packages(app.__path__, "app.")]
    assert len(modules) > 50
    for name in modules:
        importlib.import_module(name)
