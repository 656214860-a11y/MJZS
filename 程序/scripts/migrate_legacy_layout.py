# -*- coding: utf-8 -*-
"""Transactional legacy migration. Exit: 0 success, 1 blocked/failed, 2 bad arguments.

--map SOURCE=TARGET resolves an ambiguous registered source explicitly.
--rollback BATCH recovers a durable transaction; --dry-run never writes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

from orchestrator import legacy_migration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--map', action='append', default=[], metavar='SOURCE=TARGET')
    parser.add_argument('--rollback', metavar='BATCH')
    args = parser.parse_args(argv)
    root = Path(args.project)
    if not root.is_dir():
        print('项目目录不存在：' + str(root), file=sys.stderr)
        return 2
    try:
        if args.rollback:
            if args.dry_run or args.map:
                raise legacy_migration.MigrationError('回滚不能与 --dry-run/--map 同用')
            legacy_migration.rollback(root, args.rollback)
            print('已回滚：' + args.rollback)
            return 0
        explicit = {}
        for item in args.map:
            source, separator, target = item.partition('=')
            if not separator or not source or not target or source in explicit:
                raise legacy_migration.MigrationError('无效或重复 --map：' + item)
            explicit[source] = target
        ops = legacy_migration.plan(root, explicit)
        done, stamp = legacy_migration.apply(root, ops, dry_run=args.dry_run)
        for op in done:
            print('[%s] %s -> %s' % (op['action'], op['source'], op['target']))
        print('只读预检通过' if args.dry_run else ('迁移批次：' + stamp if stamp else '无待迁移项'))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('迁移阻止/失败：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
