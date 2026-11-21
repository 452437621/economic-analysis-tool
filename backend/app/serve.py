"""Detached server launcher used by ``scripts/epic.py start`` (via the
``start.ps1`` / ``start.cmd`` / ``start.sh`` wrappers).

Why this file exists:
    The cross-platform runner (``scripts/epic.py``) starts this module detached
    (``DETACHED_PROCESS`` on Windows, ``start_new_session`` on POSIX) so the
    launching shell returns immediately even when its output is captured by a
    CI pipe.  This launcher then redirects stdout/stderr to
    ``data/logs/server.{out,err}.log`` and runs uvicorn in-process.

Usage (called by the runner, not by humans):
    python -m app.serve --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="EPIC detached uvicorn launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    log_dir = root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out = open(  # noqa: SIM115 - must stay open for the process lifetime
        log_dir / "server.out.log", "a", encoding="utf-8", errors="replace", buffering=1
    )
    err = open(  # noqa: SIM115
        log_dir / "server.err.log", "a", encoding="utf-8", errors="replace", buffering=1
    )
    sys.stdout = out
    sys.stderr = err
    backend = root / "backend"
    # PYTHONPATH must be set before the interpreter starts, so fix sys.path here too:
    # this launcher is started detached (no shell to export env vars).
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    os.environ.setdefault("PYTHONPATH", str(backend))

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
