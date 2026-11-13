"""Detached server launcher used by ``scripts/start.ps1``.

Why this file exists:
    ``Start-Process`` inherits handles from the parent shell; when the parent is a
    capturing console/CI pipe, the long-running server keeps the pipe open and the
    launching shell never appears to finish. Launching through WMI
    (``Win32_Process.Create``) detaches completely, so the script exits immediately.

It also redirects stdout/stderr to ``data/logs/server.{out,err}.log`` because a
detached process has no console.

Usage (called by the PowerShell script, not by humans):
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
