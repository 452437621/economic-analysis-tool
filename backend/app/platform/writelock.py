"""Process-wide write lock for SQLite.

SQLite 是单写者数据库。两个采集任务同时写时，后一个通常能靠 ``busy_timeout``
等到锁；但如果它的连接已经开着一个**读**事务、再想把锁升级成写锁，SQLite 为了
避免死锁会立刻返回 ``database is locked``，完全不看 busy_timeout——表现就是
整轮采集（比如日线、持仓）直接失败、日志里刷 "database is locked"。

所以所有会写库的后台任务都先拿这把进程内锁：宁可让后面的任务排队，也不让
任何一轮采集因为并发写而整轮丢掉。
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from collections.abc import Iterator

WRITE_LOCK = threading.RLock()
DEFAULT_TIMEOUT = 240.0


@contextmanager
def write_lock(timeout: float = DEFAULT_TIMEOUT) -> Iterator[None]:
    if not WRITE_LOCK.acquire(timeout=timeout):
        raise TimeoutError(f"等待数据库写锁超过 {timeout:.0f}s")
    try:
        yield
    finally:
        WRITE_LOCK.release()
