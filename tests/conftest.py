import os
from pathlib import Path

import pytest

# 测试沙箱：把运行时数据放在工作区内（DSH 沙箱不允许写系统临时目录）。
# EPIC_TEST_ROOT lets parallel test agents/CI shards isolate their databases.
_default_root = Path(__file__).resolve().parents[1] / "data" / "test" / "m0"
_test_root = Path(os.environ.get("EPIC_TEST_ROOT", str(_default_root)))
_test_root.mkdir(parents=True, exist_ok=True)
_tmp_root = _test_root.parent / "tmp" / "system"
_tmp_root.mkdir(parents=True, exist_ok=True)
os.environ["EPIC_DATA_DIR"] = str(_test_root)
os.environ["EPIC_DATABASE_URL"] = f"sqlite:///{(_test_root / 'epic-test.db').as_posix()}"
os.environ.setdefault("EPIC_ENV", "test")
# Third-party libraries (esbuild, openpyxl, ...) must not touch the system temp dir.
for _key in ("TMP", "TEMP", "TMPDIR"):
    os.environ[_key] = str(_tmp_root)


def pytest_collection_modifyitems(config, items):
    """Skip OS-specific modules instead of letting them fail."""
    if os.name == "nt":
        skip_posix = pytest.mark.skip(reason="POSIX-only test")
        for item in items:
            if "posix" in item.keywords:
                item.add_marker(skip_posix)
    else:
        skip_windows = pytest.mark.skip(reason="Windows-only test")
        for item in items:
            if "windows" in item.keywords:
                item.add_marker(skip_windows)
