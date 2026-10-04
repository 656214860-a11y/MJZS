"""兼容旧队列命令；实际队列唯一权威为 Git common-dir。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROUND_CLAIM = Path(__file__).with_name("基准脚本") / "round_claim.py"


def _load_round_claim():
    """按文件加载权威 CLI，避免工作树快照再拥有独立写入逻辑。"""
    spec = importlib.util.spec_from_file_location("legacy_claim_queue_round_claim", ROUND_CLAIM)
    if spec is None or spec.loader is None:  # pragma: no cover - 安装损坏的明确报错
        raise RuntimeError("无法加载共享队列入口：%s" % ROUND_CLAIM)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    """转发旧 ``claim_queue.py`` 调用到 common-dir 的 ``round_claim``。"""
    return _load_round_claim().main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
