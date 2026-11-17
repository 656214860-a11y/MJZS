# -*- coding: utf-8 -*-
"""一次性迁移旧英文目录到当前阶段目录（任务书 P4，Q19）。

用法（工作目录＝仓库根或程序目录均可，用随附解释器）：
  python -B scripts/migrate_legacy_layout.py --project <项目路径> --dry-run
  python -B scripts/migrate_legacy_layout.py --project <项目路径>

退出码：0＝完成（含无待迁移项）；2＝参数或项目路径不可用。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))


def main(argv=None):
    parser = argparse.ArgumentParser(description='把旧英文目录的存量文件迁到当前阶段目录')
    parser.add_argument('--project', required=True, help='项目根目录')
    parser.add_argument('--dry-run', action='store_true', help='只列出待迁移项，不写盘')
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser()
    if not root.is_dir():
        print('项目目录不可用：' + str(root))
        return 2
    from orchestrator import legacy_migration
    ops = legacy_migration.plan(root)
    if args.dry_run:
        moved = [op for op in ops if op['action'] == 'move']
        print('待迁移 %d 项（冲突 %d、跳过 %d）：' % (
            len(moved), sum(1 for op in ops if op['action'] == 'conflict'),
            sum(1 for op in ops if op['action'] == 'skip')))
        for op in ops:
            print('  [%s] %s -> %s %s' % (op['action'], op['source'], op['target'], op['reason']))
        return 0
    done, stamp = legacy_migration.apply(root, ops)
    moves = legacy_migration.mapping_of(done)
    saved = legacy_migration.repoint_manifests(root, moves)
    rewritten = legacy_migration.rewrite_absolute_manifests(root, moves)
    report = legacy_migration.report(root, done, stamp)
    failed = [op for op in done if op['action'] == 'failed']
    print('迁移批次 %s：搬动 %d、失败 %d、清单重指向 %d、绝对路径改写 %d' % (
        stamp, len(moves), len(failed), len(saved), len(rewritten)))
    print('报告：' + str(report))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
