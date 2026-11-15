"""标准库自实现行覆盖率度量（零第三方依赖），供「先记基线、后设阈值」使用。

本项目不安装 coverage.py；本脚本用 ``sys.settrace`` 只对**生产模块**采集行事件，
足以对定向用例给出真实行覆盖。全量套件用它跑会非常慢，因此只建议对核心模块的
定向用例测量并沉淀基线到 ``维护记录/覆盖率基线.json``。

注：随附解释器 Python 3.15.0a2 未随附标准库 ``trace`` 模块，故这里不依赖它。
口径：生产模块集合与 ``tests/architecture/_scan.production_runtime_files()`` 一致，
由 ``tests/architecture/test_coverage_baseline.py`` 断言两侧相等，防止口径漂移。

用法（工作目录＝程序，随附解释器）：
  python -B scripts/coverage_report.py tests.test_money_invariants tests.test_request_ledger \
      --json 维护记录/覆盖率基线.json

退出码：0＝测量完成且目标用例全通过；1＝目标用例存在失败／错误（此时覆盖率不可信）；
2＝参数错误。用例失败不写入 ``--json``，避免把退化后的基线当真。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import threading
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
# 与 tests/architecture/_scan.py 同口径：测试、轮次记录、维护记录与字节码缓存不参与；
# `.wt` 是仓库的干净检出区（后台全量在 `.wt/ci` 上跑），副本不能算第二批生产模块；
# `.selftmp` 是自检临时区，探针脚本不是产品模块。
EXCLUDED_PARTS = frozenset({'tests', 'tasks_round', '维护记录', '.git', '.wt', '.selftmp', '__pycache__'})
# 非产品目录：技能随附脚本、开发维护脚本、参考资料、构建产物、外部附加工具。
NON_PRODUCT_PARTS = frozenset({'skills', 'scripts', 'reference', 'outputs', '附加工具'})
SKIP_STEMS = frozenset({'smoke_test', 'run_selftests', 'selftest_sandbox',
                        'selftest_env', 'selftest_discovery', 'selftest_receipts',
                        'selftest_scheduling', 'selftest_reporting'})


def production_modules():
    """产品运行时生产模块（递归口径，排除非产品目录与自检器）。"""
    out = []
    for path in PROGRAM.rglob('*.py'):
        parts = path.relative_to(PROGRAM).parts
        if EXCLUDED_PARTS.intersection(parts) or NON_PRODUCT_PARTS.intersection(parts):
            continue
        if path.stem in SKIP_STEMS or path.stem.startswith('test'):
            continue
        out.append(path)
    return tuple(sorted(out))


def executable_lines(path):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return set()
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)}


def measure(targets):
    tracked = {}
    for path in production_modules():
        tracked[path.resolve()] = path.relative_to(PROGRAM).as_posix()
    hit = {key: set() for key in tracked}
    resolve_cache = {}

    def resolve(filename):
        if filename not in resolve_cache:
            try:
                resolve_cache[filename] = Path(filename).resolve()
            except (OSError, ValueError):
                resolve_cache[filename] = None
        return resolve_cache[filename]

    def local_tracer(frame, event, arg):
        recorded = hit.get(resolve(frame.f_code.co_filename))
        if recorded is not None and event == 'line':
            recorded.add(frame.f_lineno)
        return local_tracer

    def global_tracer(frame, event, arg):
        if event == 'call' and resolve(frame.f_code.co_filename) in tracked:
            return local_tracer
        return None

    sys.path[:0] = [str(PROGRAM), str(PROGRAM / 'tests')]
    previous = sys.gettrace()
    sys.settrace(global_tracer)
    threading.settrace(global_tracer)
    try:
        # 采集范围含目标用例的导入期执行：import 生产模块的模块级语句确实被执行，
        # 与 coverage.py 的 --source 口径一致。故套件加载必须在 tracer 生效之后。
        suite = unittest.TestLoader().loadTestsFromNames(list(targets))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        sys.settrace(previous)
        threading.settrace(None)
    rows = []
    for path in production_modules():
        total = executable_lines(path)
        if not total:
            continue
        covered = len(hit.get(path.resolve(), set()) & total)
        rows.append({'module': path.relative_to(PROGRAM).as_posix(), 'covered': covered,
                     'total': len(total),
                     'percent': round(100.0 * covered / len(total), 1)})
    rows.sort(key=lambda row: (row['percent'], row['module']))
    return {'targets': list(targets), 'tests_ok': result.wasSuccessful(),
            'modules': rows,
            'modules_covered': sum(1 for row in rows if row['covered']),
            'modules_total': len(rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='+', help='unittest 目标名，如 tests.test_money_invariants')
    parser.add_argument('--json', type=Path, default=None, help='把结果写入该 JSON 路径')
    parser.add_argument('--quiet', action='store_true', help='只打印被覆盖到的模块')
    args = parser.parse_args(argv)
    report = measure(args.targets)
    for row in report['modules']:
        if row['covered'] or not args.quiet:
            print('%-46s %5.1f%%  %4d/%4d' % (row['module'], row['percent'], row['covered'], row['total']))
    print('模块被覆盖：%d/%d；目标用例：%s'
          % (report['modules_covered'], report['modules_total'],
             '全通过' if report['tests_ok'] else '存在失败／错误'))
    if not report['tests_ok']:
        print('目标用例未全通过，覆盖率不可信，未写入基线。')
        return 1
    if args.json is not None:
        target = args.json if args.json.is_absolute() else PROGRAM / args.json
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print('已写入 %s' % target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())