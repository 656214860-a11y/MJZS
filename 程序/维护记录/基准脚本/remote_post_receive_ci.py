#!/usr/bin/env python3
"""私有服务器 post-receive 远端 CI：推送落库后在 Linux 侧跑非 Tk 静态＋架构门禁。

部署：复制本文件到 ``<bare>.git/hooks/post-receive`` 并 ``chmod +x``；
参照副本放 ``/srv/git/ci/remote_post_receive_ci.py``。只用 python3 标准库，
不依赖 Tk 与项目解释器，与推送方环境无关（与 ``remote_pre_receive.py`` 同约定）。

stdin 协议同 pre-receive：每行 ``<old> <new> <ref>``；``new`` 全零＝删分支，跳过。
只对 ``refs/heads/master``、``refs/heads/main``、``refs/heads/codex/*`` 跑 CI，
其它 ref 直接放行。post-receive 无法拒绝推送：CI 结果写
``/srv/git/ci/results/<UTC 时间戳>-<ref>.log`` 与
``/srv/git/ci/last_ci_status.json``（``{ref, sha, ok, steps, log, at}``），
另有 ``<ref>.status.json`` 按 ref 留档；失败只记录状态并回显 stderr，不影响推送。

每个 ref 的检出方式（``/srv/git/ci/work/<ref 去掉 refs/heads/、/ 换 ->``）：

1. ``git clone --shared --no-checkout <bare> <workdir>`` ＋ ``checkout -f <sha>``：
   必须是完整克隆而非 ``git archive``——架构用例要 ``git ls-files`` 看 gitlink、
   要在临时目录建仓库跑 move guard，archive 解包没有 ``.git`` 会整片误红。
2. 按 ``程序/维护记录/外部技能包哈希.json`` 把登记的技能包从各自 source 克隆到
   固定提交（缓存裸仓在 ``/srv/git/ci/pkg-cache/``，克隆失败只告警不阻断，
   对应用例会如实报红）。``reference/`` 下的 gitlink 不在登记表内，不检出。
3. ``程序/维护记录/基准历史.json`` 被 gitignore、本地基准历史只在开发机上：
   干净检出补 ``[]``（无历史记录），与 ``auto_full_safe.IGNORED_INPUTS`` 同口径。

在 ``<workdir>/程序`` 下跑两步（``PYTHONPATH=<程序>:<程序>/tests``、
``PYTHONIOENCODING=utf-8``、``DRAMA_SUPPRESS_*=1``，同 ``local_ci.py``）：

1. 静态门禁：``python3 -B -m unittest`` 跑 ``local_ci.py`` 的 ``STATIC_GATE_TESTS``
   同一组模块。
2. 架构门禁：``python3 -B -m unittest`` 跑 ``tests/architecture`` 全部模块，
   但按 ``SKIP_MODULES``／``PARTIAL_TARGETS`` 排除一组**如实登记的平台边界用例**
   （理由写在常量注释里）；排除是显式清单不是静默放行，用例改名后旧条目失效、
   该用例会重新跑并如实报红。

覆盖差异（T1 文档要求写明）：Linux 远端覆盖「静态门禁＋架构门禁（去掉下列
平台边界用例）」；默认冒烟（Tk）、增量门禁、安全全量自检
``run_selftests.py --all --safe`` 与定向复跑仍在 Windows 本机
（``scripts/local_ci.py exit``／auto_full_safe 凭据）。服务器 python3 与本机
随附解释器存在版本差，远端绿不等于本机绿——合入 master 仍以本机 CI 出口为准。

并发：多路推送经 ``fcntl.flock`` 在 ``/srv/git/ci/ci.lock`` 上串行（非 POSIX
平台无 fcntl 时跳过加锁）；单步超时 ``CI_STEP_TIMEOUT``（默认 1800 秒），
``CI_WORK_ROOT``／``CI_RESULT_DIR``／``CI_PKG_CACHE`` 可用环境变量改。
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CI_WORK_ROOT = Path(os.environ.get('CI_WORK_ROOT', '/srv/git/ci/work'))
CI_RESULT_DIR = Path(os.environ.get('CI_RESULT_DIR', '/srv/git/ci/results'))
CI_PKG_CACHE = Path(os.environ.get('CI_PKG_CACHE', '/srv/git/ci/pkg-cache'))
CI_LOCK = os.environ.get('CI_LOCK', '/srv/git/ci/ci.lock')
CI_STEP_TIMEOUT = int(os.environ.get('CI_STEP_TIMEOUT', '1800'))
PKG_TIMEOUT = int(os.environ.get('CI_PKG_TIMEOUT', '600'))
ZERO = '0' * 40
CI_REFS = ('refs/heads/master', 'refs/heads/main')
CODEX_PREFIX = 'refs/heads/codex/'

# 与 scripts/local_ci.py 的 STATIC_GATE_TESTS 保持同一组模块。
STATIC_GATE_TESTS = (
    'tests.architecture.test_static_hygiene',
    'tests.test_static_names',
    'tests.architecture.test_print_ratchet',
    'tests.architecture.test_module_size_ratchet',
    'tests.architecture.test_function_size_ratchet',
    'tests.architecture.test_silent_exception_ratchet',
    'tests.architecture.test_todo_comment_snapshot',
    'tests.architecture.test_skip_hygiene',
    'tests.test_copy_rules',
)

# ---- 平台边界排除清单（unittest 目标；模块名＝整模块跳过）----
# 1) test_rule_guard_map：setUp 经 scripts/rule_guard_map.py → file_cache.read_json
#    → agent/publication.access() 的 msvcrt 字节锁只支持 Windows（产品只跑 Windows，
#    该锁是发布事务完整性的 Windows 实现，Linux 上没有等价语义，不是缺陷）。
#    test_skill_package_pins 同因：PINS.load_registry 走同一 file_cache 公共读路径。
# 2) test_source_text_contracts.DesktopSourceContracts：每条用例 import desktop，
#    desktop.py 模块级 import tkinter；服务器 python3 无 tkinter，属「依赖 Tk」
#    口径外。同模块 SelftestRunnerContracts 不碰 Tk，保留。
# 3) test_service_return_contract 两条：走 file_cache 公共读路径，同 1)。
# 4) test_unification_ratchet.test_bare_json_load_debt…：台账锚点是
#    sha256(ast.dump(Call))，dump 形态随解释器版本变；基线在随附 3.15 上生成，
#    服务器 python3.11 全部锚点失配。解释器版本敏感，非平台缺陷。
SKIP_MODULES = ('tests.architecture.test_rule_guard_map',
                'tests.architecture.test_skill_package_pins')
PARTIAL_TARGETS = {
    'tests.architecture.test_source_text_contracts': (
        'tests.architecture.test_source_text_contracts.SelftestRunnerContracts',
    ),
    'tests.architecture.test_service_return_contract': (
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_audited_readonly_scope_has_reasons_and_fixed_entrypoints',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_submission_decision_preserves_input_and_project_files',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_every_registered_l2_module_has_a_scope_record',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_only_approved_l2_adopters_import_service_contract',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_delivery_import_is_registered_l2_and_uses_result_contract',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_keyframe_lifecycle_is_registered_l2_and_uses_result_contract',
        'tests.architecture.test_service_return_contract.ServiceReturnContractBoundaryTests'
        '.test_service_result_contract_is_l0',
    ),
    'tests.architecture.test_unification_ratchet': (
        'tests.architecture.test_unification_ratchet.UnificationRatchetTests'
        '.test_l2_formal_publish_debt_is_a_nonincreasing_subset',
        'tests.architecture.test_unification_ratchet.UnificationRatchetTests'
        '.test_formal_path_reads_outside_l2_are_a_nonincreasing_subset',
        'tests.architecture.test_unification_ratchet.UnificationRatchetTests'
        '.test_migrated_projects_cannot_bypass_its_injected_gateway',
    ),
}
ARCH_DIR = 'tests/architecture'


def ci_ref(ref):
    """只对 master/main 与 codex/* 分支跑 CI。"""
    return ref in CI_REFS or ref.startswith(CODEX_PREFIX)


def ref_slug(ref):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', ref.removeprefix('refs/heads/'))


def _clean_env(extra=None):
    """子进程环境：剔除 hook 带进来的 GIT_*（GIT_DIR 会让用例里的临时仓库
    误操作 bare 仓库），再叠加 CI 自己的变量。"""
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update({
        'PYTHONIOENCODING': 'utf-8',
        'DRAMA_SUPPRESS_MODAL': '1',
        'DRAMA_SUPPRESS_NETWORK': '1',
    })
    if extra:
        env.update(extra)
    return env


def git(*args, cwd=None, timeout=CI_STEP_TIMEOUT):
    command = ['git', '-c', 'core.quotepath=false']
    if cwd:
        command += ['-C', str(cwd)]
    command += list(args)
    return subprocess.run(command, capture_output=True, timeout=timeout,
                          env=_clean_env())


def checkout_ref(git_dir, sha, workdir):
    """克隆 bare 仓库并检出 sha；返回错误描述或 None。"""
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    done = git('clone', '--quiet', '--shared', '--no-checkout', str(git_dir), str(workdir))
    if done.returncode:
        return 'git clone 失败：%s' % done.stderr.decode('utf-8', 'replace').strip()[:300]
    done = git('checkout', '-f', '--detach', sha, cwd=workdir)
    if done.returncode:
        return 'git checkout 失败：%s' % done.stderr.decode('utf-8', 'replace').strip()[:300]
    return None


def _pkg_cache(source):
    """按 source URL 派生缓存裸仓路径。"""
    name = re.sub(r'[^A-Za-z0-9_.-]+', '-', source.rstrip('/').rsplit('/', 1)[-1].removesuffix('.git'))
    return CI_PKG_CACHE / (name + '.git')


def provision_packages(program):
    """按登记表把技能包克隆到固定提交；返回告警列表（不阻断）。"""
    warnings = []
    registry_path = program / '维护记录' / '外部技能包哈希.json'
    if not registry_path.is_file():
        return warnings
    try:
        packages = json.loads(registry_path.read_text(encoding='utf-8')).get('packages', {})
    except ValueError as exc:
        return ['登记表解析失败：%s' % exc]
    for rel, entry in sorted(packages.items()):
        source, commit = entry.get('source'), entry.get('commit')
        target = program / rel
        if not source or not commit:
            warnings.append('%s：登记缺 source/commit' % rel)
            continue
        try:
            cache = _pkg_cache(source)
            if not (cache / 'HEAD').exists():
                CI_PKG_CACHE.mkdir(parents=True, exist_ok=True)
                done = git('clone', '--quiet', '--bare', source, str(cache), timeout=PKG_TIMEOUT)
                if done.returncode:
                    warnings.append('%s：缓存克隆失败 %s' % (rel, done.stderr.decode('utf-8', 'replace').strip()[:200]))
                    continue
            else:
                git('fetch', '--quiet', 'origin', '--prune', cwd=cache, timeout=PKG_TIMEOUT)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            done = git('clone', '--quiet', str(cache), str(target), timeout=PKG_TIMEOUT)
            if done.returncode:
                warnings.append('%s：检出克隆失败' % rel)
                continue
            done = git('remote', 'set-url', 'origin', source, cwd=target)
            done = git('checkout', '-f', '--detach', commit, cwd=target)
            if done.returncode:
                warnings.append('%s：固定提交 %s 不可检出' % (rel, str(commit)[:12]))
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append('%s：%s' % (rel, exc))
    return warnings


def provision_ignored_inputs(program):
    """gitignore 的本地输入：干净检出天然没有，补最小合法内容（同 auto_full_safe 口径）。"""
    history = program / '维护记录' / '基准历史.json'
    if not history.exists():
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text('[]\n', encoding='utf-8')


def arch_targets(program):
    """枚举 tests/architecture 全部测试模块，减去平台边界排除项。"""
    arch = program / ARCH_DIR
    targets = []
    for path in sorted(arch.glob('test_*.py')):
        module = 'tests.architecture.' + path.stem
        if module in SKIP_MODULES:
            continue
        targets.extend(PARTIAL_TARGETS.get(module, (module,)))
    return targets


def run_step(name, command, cwd, log):
    """跑一步门禁，输出追加进 log，返回 (退出码, 用时秒)。"""
    log.write('\n[CI] === %s ===\n' % name)
    log.write('[CI] $ %s\n' % ' '.join(command))
    log.flush()
    env = _clean_env({
        'PYTHONPATH': os.pathsep.join(filter(None, (str(cwd), str(cwd / 'tests'),
                                                  os.environ.get('PYTHONPATH', '')))),
    })
    started = time.perf_counter()
    try:
        done = subprocess.run(command, cwd=str(cwd), env=env, stdout=log,
                              stderr=subprocess.STDOUT, timeout=CI_STEP_TIMEOUT)
        code = done.returncode
    except subprocess.TimeoutExpired:
        code = 'timeout>%ds' % CI_STEP_TIMEOUT
    seconds = time.perf_counter() - started
    log.write('[CI] %s 退出码 %s，用时 %.1f 秒\n' % (name, code, seconds))
    log.flush()
    return code, seconds


def _steps(program):
    arch = arch_targets(program)
    return (
        ('静态门禁', [sys.executable, '-B', '-m', 'unittest', *STATIC_GATE_TESTS]),
        ('架构门禁', [sys.executable, '-B', '-m', 'unittest', *arch]),
    )


def run_ci(git_dir, ref, sha):
    """对单个 ref 跑 CI，返回状态 dict；永不抛异常。"""
    slug = ref_slug(ref)
    workdir = CI_WORK_ROOT / slug
    program = workdir / '程序'
    status = {'ref': ref, 'sha': sha, 'ok': False, 'steps': [], 'at': None}
    started = time.perf_counter()
    CI_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log_path = CI_RESULT_DIR / ('%s-%s.log' % (stamp, slug))
    status['log'] = str(log_path)
    try:
        problem = checkout_ref(git_dir, sha, workdir)
        if problem:
            status['error'] = problem
        elif not program.is_dir():
            status['error'] = '检出的树缺少 程序/ 目录'
        else:
            pkg_warnings = provision_packages(program)
            provision_ignored_inputs(program)
            with log_path.open('w', encoding='utf-8') as log:
                log.write('[CI] ref=%s sha=%s at=%s\n'
                          % (ref, sha, datetime.now(timezone.utc).isoformat(timespec='seconds')))
                if pkg_warnings:
                    log.write('[CI] 技能包检出告警：%s\n' % '；'.join(pkg_warnings))
                    status['package_warnings'] = pkg_warnings
                for name, command in _steps(program):
                    code, seconds = run_step(name, command, program, log)
                    status['steps'].append({'name': name, 'exit': code, 'seconds': round(seconds, 1)})
                    if code != 0:
                        break
                status['ok'] = all(step['exit'] == 0 for step in status['steps']) \
                    and len(status['steps']) == len(_steps(program))
        if not log_path.exists():
            with log_path.open('w', encoding='utf-8') as log:
                log.write('[CI] ref=%s sha=%s error=%s\n' % (ref, sha, status.get('error', '?')))
    except Exception as exc:  # post-receive 不能让推送失败，但要留下痕迹
        status['error'] = '%s: %s' % (type(exc).__name__, exc)
    finally:
        status['seconds'] = round(time.perf_counter() - started, 1)
        status['at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        try:
            CI_RESULT_DIR.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(status, ensure_ascii=False, indent=2) + '\n'
            (CI_RESULT_DIR / 'last_ci_status.json').write_text(payload, encoding='utf-8')
            (CI_RESULT_DIR / (slug + '.status.json')).write_text(payload, encoding='utf-8')
        except OSError:
            pass
    return status


def _locked():
    """拿到 ci.lock 的排他锁；拿不到 fcntl（非 POSIX）时退化为空上下文。"""
    try:
        import fcntl
    except ImportError:
        return contextlib.nullcontext()

    class _Lock:
        def __enter__(self):
            CI_RESULT_DIR.mkdir(parents=True, exist_ok=True)
            self._fd = os.open(CI_LOCK, os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX)
            return self

        def __exit__(self, *exc):
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)

    return _Lock()


def main() -> int:
    updates = [line.split() for line in sys.stdin if line.strip()]
    git_dir = os.environ.get('GIT_DIR') or '.'
    ran = 0
    with _locked():
        for old, new, ref in updates:
            if set(new) == {'0'} or not ci_ref(ref):
                continue
            ran += 1
            status = run_ci(git_dir, ref, new)
            mark = 'PASS' if status['ok'] else 'FAIL'
            sys.stderr.write('[post-receive CI] %s %s %s（%.1fs，日志 %s）\n'
                             % (mark, ref, new[:10], status['seconds'], status['log']))
    sys.stderr.write('[post-receive CI] 本次推送触发 %d 个 ref 的远端 CI\n' % ran)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
