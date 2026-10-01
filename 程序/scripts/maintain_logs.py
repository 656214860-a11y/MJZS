r"""Manual entry point for the bounded program-log maintenance policy.

Run with the bundled interpreter:
``D:\漫剧制作助手\运行环境\Python\python.exe -B scripts\maintain_logs.py --dry-run``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from log_maintenance import main


if __name__ == "__main__":
    raise SystemExit(main())
