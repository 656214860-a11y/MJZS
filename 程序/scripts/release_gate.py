r"""发布门禁聚合：一条命令回答「现在能不能发布」。

默认只读：只检查收据与文件（秒级返回）；``--run`` 才执行耗时命令
（``local_ci.py exit``、``run_selftests.py --all --safe``、``distribution_selfcheck.py --release``
及已落地的升级保留用例）。输出 JSON：逐项给出 通过／未通过／未运行／警告 与原因；
退出码 0 表示全部阻断项通过——「未运行」不算通过。

用法（随附解释器，程序目录下）::

    python -B scripts\release_gate.py          # 只读判定
    python -B scripts\release_gate.py --run    # 实跑耗时项后判定
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
ROOT = PROGRAM.parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import selftest_env as stenv  # noqa: E402
import selftest_receipts  # noqa: E402
from scripts import tools_lock  # noqa: E402

PASS, FAIL, SKIP, WARN = '通过', '未通过', '未运行', '警告'
VERSION_RE = re.compile(r"VERSION\s*=\s*'([^']+)'")
README_VERSION_RE = re.compile(r'V\d+\.\d+')
CI_STARTED_RE = re.compile(r'^\[CI\] 开始 (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', re.M)
CI_PASSED_RE = re.compile(r'^\[CI\] 通过$', re.M)
CI_STEP_RE = re.compile(r'^\[CI\] === (.+?) ===$', re.M)
DIST_EXIT_RE = re.compile(r'^\[CI\] 分发自检 退出码 (\d+)，', re.M)
CI_EXIT_STEPS = ('静态门禁', '架构门禁')
NOTICE_NAMES = ('NOTICE', 'NOTICE.txt', 'THIRD_PARTY_NOTICES.txt')
INSTALL_INFO_REASON = '安装信息.json 是安装残留、不入库、非版本来源（R1460），门禁明确排除不比对'


def _item(item_id, check, status, reason, blocking=True):
    return {'id': item_id, 'check': check, 'status': status, 'reason': reason,
            'blocking': blocking}


def check_bundle_tools(env, ran):
    """(1) 随包工具齐全（REL-01）：ffmpeg/ffprobe 摘要与 ffmpeg/LICENSE 对得上锁文件。"""
    lock = env.get('tools_lock')
    if not isinstance(lock, dict):
        return _item('bundle-tools', '随包工具齐全（REL-01）', FAIL,
                     '缺少 external_tools.lock.json，无法核对随包工具')
    problems = tools_lock.bundle_problems(lock, resolver=env.get('bundle_resolver'))
    if problems:
        return _item('bundle-tools', '随包工具齐全（REL-01）', FAIL, '；'.join(problems[:4]))
    return _item('bundle-tools', '随包工具齐全（REL-01）', PASS,
                 '随包工具齐全 %d 项' % len(tools_lock.BUNDLE_ITEMS))


def _ci_started(text):
    matched = CI_STARTED_RE.search(text)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(1), '%Y-%m-%d %H:%M:%S').astimezone()
    except ValueError:
        return None


def check_ci_exit(env, ran):
    """(2) ci exit 通过：local_ci 收据为 exit/release 口径、结论绿、且不早于当前提交。"""
    if 'ci-exit' in ran and ran['ci-exit'] != 0:
        return _item('ci-exit', '本地 CI exit 通过', FAIL,
                     'local_ci.py exit 实跑退出码 %d' % ran['ci-exit'])
    text = env.get('ci_log')
    if not text:
        return _item('ci-exit', '本地 CI exit 通过', SKIP,
                     '无 local_ci 收据（logs/ci_最近.log）：先跑 本地CI.cmd exit 或 --run')
    steps = set(CI_STEP_RE.findall(text))
    missing = [step for step in CI_EXIT_STEPS if step not in steps]
    if missing:
        return _item('ci-exit', '本地 CI exit 通过', FAIL,
                     'CI 收据缺 %s 步，不是 exit/release 口径' % '、'.join(missing))
    if not CI_PASSED_RE.search(text):
        return _item('ci-exit', '本地 CI exit 通过', FAIL, 'CI 收据未记录「[CI] 通过」')
    started = _ci_started(text)
    head = env.get('head_time')
    if started is None or head is None:
        return _item('ci-exit', '本地 CI exit 通过', FAIL,
                     '收据无法与当前提交绑定（缺 CI 开始时间或 HEAD 提交时间）')
    if started < head:
        return _item('ci-exit', '本地 CI exit 通过', FAIL,
                     'CI 收据 %s 早于当前提交 %s，须对当前提交重跑'
                     % (started.isoformat(timespec='seconds'), head.isoformat(timespec='seconds')))
    return _item('ci-exit', '本地 CI exit 通过', PASS,
                 '本地 CI 于 %s 通过，不早于当前提交' % started.isoformat(timespec='seconds'))


def check_full_safe(env, ran):
    """(3) full --safe 绿收据：绑定当前内容树与时间，旧提交或过期收据不算。"""
    if 'full-safe' in ran and ran['full-safe'] != 0:
        return _item('full-safe', '全量 full --safe 绿收据（当前提交）', FAIL,
                     'run_selftests.py --all --safe 实跑退出码 %d' % ran['full-safe'])
    tree = env.get('content_tree')
    if not tree:
        return _item('full-safe', '全量 full --safe 绿收据（当前提交）', FAIL,
                     '无法确认当前内容树（工作树脏或非 Git 检出），收据无法绑定')
    records = (env.get('receipts') or {}).get('full_safe_verified_trees') or []
    record = selftest_receipts.verified_tree_record(records, tree, env.get('now'))
    if record is None:
        return _item('full-safe', '全量 full --safe 绿收据（当前提交）', FAIL,
                     '当前内容树 %s 无有效全量绿收据（旧提交或过期收据不算）' % tree[:12])
    return _item('full-safe', '全量 full --safe 绿收据（当前提交）', PASS,
                 '内容树 %s 于 %s 全量绿（R%s）'
                 % (tree[:12], record.get('at'), record.get('round')))


def check_dist_release(env, ran):
    """(4) dist --release 通过：必须有 ``--release`` 实跑证据（SBOM release_blockers 为空）。

    ``local_ci release`` 的「分发自检」步跑的是不带 ``--release`` 的
    ``distribution_selfcheck.py``，只证构建／校验／导入绿，不证 release_blockers，
    不能当作本项通过依据；其退出码非 0 仍可判未通过。
    """
    if 'dist-release' in ran:
        code = ran['dist-release']
        if code == 0:
            return _item('dist-release', 'dist --release 通过（SBOM 无阻断）', PASS,
                         'distribution_selfcheck --release 通过'
                         '（release_ready：构建校验绿且 release_blockers 为空）')
        return _item('dist-release', 'dist --release 通过（SBOM 无阻断）', FAIL,
                     'distribution_selfcheck --release 退出码 %d' % code)
    text = env.get('ci_log')
    if text and '分发自检' in set(CI_STEP_RE.findall(text)):
        matched = DIST_EXIT_RE.search(text)
        if matched and matched.group(1) != '0':
            return _item('dist-release', 'dist --release 通过（SBOM 无阻断）', FAIL,
                         'CI 收据中分发自检退出码非 0')
        return _item('dist-release', 'dist --release 通过（SBOM 无阻断）', SKIP,
                     'CI 分发自检未带 --release，不证明 SBOM release_blockers 为空；'
                     '需 --run 实跑 distribution_selfcheck.py --release')
    return _item('dist-release', 'dist --release 通过（SBOM 无阻断）', SKIP,
                 '无 dist --release 收据；需 --run 实跑 distribution_selfcheck.py --release')


def check_version(env, ran):
    """(5) 版本一致：app_metadata.VERSION ↔ CHANGELOG 小节 ↔ README 版本字样。"""
    matched = VERSION_RE.search(env.get('version_text') or '')
    version = matched.group(1) if matched else ''
    if not version:
        return _item('version-consistency', '版本号一致（VERSION/CHANGELOG/README）', FAIL,
                     'contract/app_metadata.py 中无 VERSION')
    problems = []
    changelog = env.get('changelog')
    if not changelog or not re.search(r'(?m)^## %s\s*$' % re.escape(version), changelog):
        problems.append('CHANGELOG.md 缺「## %s」小节' % version)
    tokens = sorted(set(README_VERSION_RE.findall(env.get('readme') or '')))
    if not tokens:
        problems.append('README.md 无 V主.次 版本字样')
    elif tokens != [version]:
        problems.append('README.md 版本字样 %s 与 %s 不一致' % ('、'.join(tokens), version))
    if problems:
        return _item('version-consistency', '版本号一致（VERSION/CHANGELOG/README）', FAIL,
                     '；'.join(problems))
    return _item('version-consistency', '版本号一致（VERSION/CHANGELOG/README）', PASS,
                 'VERSION=%s；CHANGELOG/README 一致；%s' % (version, INSTALL_INFO_REASON))


def check_upgrade_preserve(env, ran):
    """(6) 升级保留数据测试（REL-04）：用例在测试集内，其绿色由全量/CI 凭据覆盖。"""
    stems = env.get('upgrade_modules') or []
    if not stems:
        return _item('upgrade-preserve', '升级保留数据测试通过（REL-04）', SKIP,
                     'REL-04 未落地：tests/ 下未见含 upgrade 的用例；落地前不算通过')
    if 'upgrade-preserve' in ran:
        code = ran['upgrade-preserve']
        if code == 0:
            return _item('upgrade-preserve', '升级保留数据测试通过（REL-04）', PASS,
                         '升级保留用例 %s 实跑绿' % '、'.join(stems))
        return _item('upgrade-preserve', '升级保留数据测试通过（REL-04）', FAIL,
                     '升级保留用例 %s 退出码 %d' % ('、'.join(stems), code))
    return _item('upgrade-preserve', '升级保留数据测试通过（REL-04）', PASS,
                 '用例 %s 在测试集内，其绿色由 ci-exit 与 full-safe 凭据覆盖'
                 % '、'.join(stems))


def check_notice(env, ran):
    """(7) NOTICE 存在且无 NOASSERTION（REL-10）。"""
    files = env.get('notice_files') or []
    if not files:
        return _item('notice', 'NOTICE 存在且无 NOASSERTION（REL-10）', SKIP,
                     'REL-10 未落地：仓库无 NOTICE/THIRD_PARTY_NOTICES.txt'
                     '（现由 scripts/sbom.py 在构建时生成进副本）；落地前不算通过')
    hits = [label for label, text in files if 'NOASSERTION' in text]
    if hits:
        return _item('notice', 'NOTICE 存在且无 NOASSERTION（REL-10）', FAIL,
                     'NOASSERTION 出现在 %s' % '、'.join(hits))
    return _item('notice', 'NOTICE 存在且无 NOASSERTION（REL-10）', PASS,
                 '%s 存在且无 NOASSERTION' % '、'.join(label for label, _ in files))


def _default_cert_status():
    try:
        from domain import account_client
        text = account_client.pinned_cert_warning()
    except (ImportError, OSError, ValueError, AttributeError, RuntimeError) as exc:
        return WARN, '钉死证书到期无法评估：%s' % exc
    return (WARN, text) if text else (PASS, '钉死证书距到期超出 60 天告警窗')


def check_cert(env, ran):
    """(8) 证书到期前 60 天告警：警告项，不阻断。"""
    probe = env.get('cert_status') or _default_cert_status
    status, reason = probe()
    return _item('cert-expiry', '证书到期前 60 天告警', status, reason, blocking=False)


CHECKS = (check_bundle_tools, check_ci_exit, check_full_safe, check_dist_release,
          check_version, check_upgrade_preserve, check_notice, check_cert)


def run_plan(env, python=None):
    """``--run`` 要执行的耗时命令清单（顺序即执行序）；用桩注入时可断言调用内容。"""
    python = python or sys.executable
    plan = [('ci-exit', [python, '-B', 'scripts/local_ci.py', 'exit']),
            ('full-safe', [python, '-B', 'run_selftests.py', '--all', '--safe']),
            ('dist-release', [python, '-B', 'scripts/distribution_selfcheck.py', '--release'])]
    stems = env.get('upgrade_modules') or []
    if stems:
        plan.append(('upgrade-preserve', [python, '-B', 'run_selftests.py', '-k', *stems]))
    return plan


def _default_runner(env):
    def run(command):
        print('[release-gate] --run：' + ' '.join(command), file=sys.stderr)
        return subprocess.call(command, cwd=str(env.get('program') or PROGRAM))
    return run


def _refresh(env):
    """``--run`` 之后重读会变的收据输入（CI 日志、全量凭据、内容树）。"""
    for key in ('ci_log', 'receipts', 'content_tree'):
        loader = env.get(key + '_loader')
        if callable(loader):
            env[key] = loader()


def evaluate(env, run=False, runner=None):
    """逐项判定并给出总退出结论；``env`` 为显式注入的输入快照，可整体伪造。"""
    ran = {}
    if run:
        runner = runner or _default_runner(env)
        for key, command in run_plan(env):
            ran[key] = runner(command)
        _refresh(env)
    items = [check(env, ran) for check in CHECKS]
    releasable = all(item['status'] == PASS for item in items if item['blocking'])
    return {'releasable': releasable, 'commit': env.get('commit') or '', 'items': items}


def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except OSError:
        return None


def _read_json(path):
    """经 `agent.core.read_json` 读 JSON：与产品同一条读取链，不在这里裸 `json.loads`。"""
    try:
        from agent.core import read_json
        return read_json(path, default=None)
    except Exception:
        return None


def _git_line(*args):
    try:
        return stenv._git_text(*args)
    except (OSError, subprocess.SubprocessError):
        return ''


def _head_commit_time():
    try:
        return datetime.fromisoformat(stenv._git_text('show', '-s', '--format=%cI', 'HEAD'))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _notice_files(root, program):
    found = []
    for name in NOTICE_NAMES:
        for base in (root, program):
            path = base / name
            if path.is_file():
                text = _read(path)
                if text is not None:
                    found.append((path.relative_to(root).as_posix(), text))
    return found


UPGRADE_TEST_RE = re.compile(r'def\s+test_\w*upgrade', re.IGNORECASE)


def _upgrade_test_modules(tests_dir):
    """REL-04 用例所在测试模块：文件名含 upgrade 的整文件，加上其它文件里内嵌的 upgrade 用例。"""
    stems = {path.stem for path in tests_dir.glob('test_*upgrade*.py')}
    for path in tests_dir.glob('test_*.py'):
        if path.stem in stems:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        if UPGRADE_TEST_RE.search(text):
            stems.add(path.stem)
    return sorted(stems)


def build_env(program=PROGRAM):
    """真实环境输入快照；测试不经过它，直接注入等价 dict。"""
    root = program.parent
    env = {'program': program, 'now': datetime.now()}
    env['tools_lock'] = _read_json(program / 'external_tools.lock.json')
    env['ci_log'] = _read(program / 'logs' / 'ci_最近.log')
    env['ci_log_loader'] = lambda: _read(program / 'logs' / 'ci_最近.log')
    env['receipts'] = _read_json(Path(selftest_receipts.full_safe_receipts_path()))
    env['receipts_loader'] = lambda: _read_json(Path(selftest_receipts.full_safe_receipts_path()))
    env['content_tree'] = selftest_receipts.content_tree()
    env['content_tree_loader'] = selftest_receipts.content_tree
    env['head_time'] = _head_commit_time()
    env['commit'] = _git_line('rev-parse', '--short', 'HEAD')
    env['version_text'] = _read(program / 'contract' / 'app_metadata.py')
    env['changelog'] = _read(program / 'CHANGELOG.md')
    env['readme'] = _read(program / 'README.md')
    env['notice_files'] = _notice_files(root, program)
    env['upgrade_modules'] = _upgrade_test_modules(program / 'tests')
    return env


def main(argv=None, env=None, runner=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', action='store_true',
                        help='实跑耗时命令（CI exit／安全全量／分发自检等）后再判定')
    args = parser.parse_args(argv)
    env = build_env() if env is None else env
    report = evaluate(env, run=args.run, runner=runner)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['releasable'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
