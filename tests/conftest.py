import os
from pathlib import Path

# 测试沙箱：把运行时数据放在工作区内（DSH 沙箱不允许写系统临时目录）。
_test_root = Path(__file__).resolve().parents[1] / "data" / "test" / "m0"
_test_root.mkdir(parents=True, exist_ok=True)
os.environ["EPIC_DATA_DIR"] = str(_test_root)
os.environ["EPIC_DATABASE_URL"] = f"sqlite:///{(_test_root / 'epic-test.db').as_posix()}"
os.environ.setdefault("EPIC_ENV", "test")
