"""写锁：采集任务必须串行写库，否则 SQLite 会以 database is locked 整轮失败。"""

from __future__ import annotations

import threading
import time

import pytest

from app.platform.writelock import WRITE_LOCK, write_lock


def test_write_lock_is_mutually_exclusive():
    order: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with write_lock(timeout=5):
            order.append("holder-in")
            entered.set()
            release.wait(5)
            order.append("holder-out")

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(5)

    # 锁被占用时第二个写者必须等待，而不是和第一个交替进入
    assert not WRITE_LOCK.acquire(blocking=False)
    release.set()
    thread.join(5)
    assert order == ["holder-in", "holder-out"]


def test_write_lock_raises_when_timeout():
    # RLock allows same-thread re-entry (used by nested supervisor/repair jobs);
    # a *different* thread must still time out while the lock is held.
    entered = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with write_lock(timeout=2):
            entered.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(TimeoutError):
            with write_lock(timeout=0.05):
                pass  # pragma: no cover - 不应该进入
    finally:
        release.set()
        thread.join(5)


def test_write_lock_releases_after_exception():
    with pytest.raises(RuntimeError):
        with write_lock(timeout=1):
            raise RuntimeError("boom")
    # 异常路径必须释放锁，否则后续采集永远拿不到写权限
    assert WRITE_LOCK.acquire(timeout=1)
    WRITE_LOCK.release()
    time.sleep(0)
