# -*- coding: utf-8 -*-
"""运行全部自检：导入所有模块 ＋ unittest 用例。

第 25 期：整跑改成**按工作单元并行**（本机 24 核，实测 204 秒 → 87 秒）。
大文件（用例多的那两个）会按 TestCase 类再切成几路——原来一个文件只能占一个进程，
test_pet_ui／test_ui_edges_* 各自几十秒，整跑就被它们顶住了。
剩下的长尾是 Tk 界面那几条：每例都要建一整套 11 页的界面，单例 3～6 秒，切得再细也下不去；
并行度也是实测出来的——16 路时 GUI 互相争用，单例成本翻三倍，整跑反而 114 秒，所以默认封顶 8 路。
  python run_selftests.py                  # 并行整跑（默认，取 min(8, 核数) 个进程，约 85 秒）
  python run_selftests.py --serial         # 老样子串行（怀疑并行互相干扰时用它对照）
  python run_selftests.py --jobs 4         # 指定并行度
  python run_selftests.py --whole          # 不拆大文件（一个文件一路，出问题时对照用）
  python run_selftests.py --safe           # 无 Tk 并行、Tk 最多 4 路受控并行，性能用例独占串行
  python run_selftests.py --all --safe --force # 忽略同内容树绿凭据，强制再跑一轮全量复核
  python run_selftests.py --all --safe --allow-dirty-diagnostic # 脏树仅诊断，不记账
  python run_selftests.py -k pet keyframe  # 只跑文件名含这些片段的用例（改哪儿跑哪儿）
  python run_selftests.py --list           # 只列会跑哪些文件
  python run_selftests.py --all            # 不管改没改过，全部重跑一遍，并刷新增量台账
  python run_selftests.py --layer architecture --all  # 只跑架构契约层，并记录分层基线
  python run_selftests.py --layer service --all       # 只跑不依赖 Tk 的服务层
  python run_selftests.py --layer gui-short --safe --all # 短生命周期 Tk 用例（最多 4 路）
  python run_selftests.py --layer gui-e2e --safe --all   # 端到端桌面冒烟（最多 4 路）

第 36 期第 14 条：整跑一次两分钟，而一轮改动通常只碰两三个模块——用户要「不检查没改过的
功能、缩短时间」。所以默认走**增量**：上一次跑绿之后，谁（测试文件自己／它 import 的本项目
模块／skills 里的说明文件）一个字节都没动，这一趟就跳过它，只在结尾报一句跳了多少。
台账优先落在仓库共同 Git 目录的 selftest-incremental.json；非 Git 目录才降级到
维护记录/自检增量.json。--all 会忽略台账全跑，跑绿之后重写台账。
怀疑漏检时用 --all 或 --serial 对照，两条路都在。
"""

import atexit
import importlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(HERE, 'tests')
sys.path.insert(0, HERE)
if os.path.isdir(TESTS_DIR):
    sys.path.insert(0, TESTS_DIR)

import selftest_env as env
import selftest_discovery as discovery
import selftest_receipts as receipts
import selftest_scheduling as scheduling
import selftest_reporting as reporting

# 兼容面：既有消费者与测试仍从 run_selftests 读取全部公开名。
from selftest_env import (
    SKIP,
    SPLIT_OVER,
    CHUNK_TESTS,
    JOBS_CAP,
    SAFE_GUI_JOBS,
    SAFE_UNIT_TIMEOUT,
    HEARTBEAT_SECONDS,
    SLOW_UNITS_LIMIT,
    SKIP_REPORT_LIMIT,
    PID_REUSE_TOLERANCE_SECONDS,
    CACHE_NAME,
    INCREMENTAL_RULES,
    FULL_SAFE_LOCK_NAME,
    GUI_LOCK_NAME,
    GUI_QUEUE_NAME,
    GUI_QUEUE_SUFFIX,
    GUI_WAIT_SECONDS,
    GUI_WAIT_NOTICE_SECONDS,
    GUI_LOCK_POLL_SECONDS,
    LAYER_BASELINE_NAME,
    FULL_SAFE_TREE_TTL,
    FULL_SAFE_ROUND_INTERVAL,
    FULL_SAFE_AUTO_LEAD,
    FULL_SAFE_RISK_GRACE,
    AUTO_FULL_LOCK_NAME,
    AUTO_FULL_STALE_SECONDS,
    NON_SOURCE_DIRS,
    _ROUND_SUBJECT,
    DATA_GLOBS,
    TEST_LAYERS,
    GUI_E2E_MODULES,
    PERFORMANCE_MODULES,
    HERE,
    TESTS_DIR,
    _digest,
    _git_text,
    git_common_dir,
    _process_created_at,
    _record_is_reused,
    _pid_is_alive,
    lock_holder,
)
from selftest_discovery import (
    project_modules,
    imports_of,
    dependency_closure,
    data_files,
    import_all,
    test_modules,
    test_path,
    gui_test_module,
    modules_for_layer,
    _flat_cases,
    split_classes,
    chunks_of,
    units,
    split_performance_units,
    safe_full_options,
    safe_gui_jobs,
    split_safe_units,
)
from selftest_receipts import (
    cache_path,
    load_cache,
    save_cache,
    record_elapsed,
    incremental,
    layer_baseline_path,
    content_tree,
    checkout_dirty_entries,
    full_safe_preflight,
    is_master_checkout,
    is_source_change,
    count_source_rounds,
    _round_commits,
    source_rounds_since,
    risk_paths,
    has_risk_change,
    risk_overdue,
    risk_overdue_since,
    auto_full_running,
    risk_changed_since,
    receipt_checkout_allowed,
    full_safe_required,
    full_safe_auto_due,
    participating_full_safe_run,
    measurement_unchanged,
    verified_tree_record,
    load_layer_document,
    full_safe_receipts_path,
    record_verified_tree,
    invalidate_verified_tree,
    latest_completed_round,
    save_layer_baseline,
    save_full_safe_verification,
)
from selftest_scheduling import (
    _GUI_LOCK_DEPTH,
    _FULL_LOCK_DEPTH,
    acquire_pid_lock,
    acquire_full_safe_lock,
    release_full_safe_lock,
    release_pid_lock,
    _gui_queue_dir,
    _gui_queue_tickets,
    _drop_dead_gui_tickets,
    _join_gui_queue,
    _leave_gui_queue,
    _gui_queue_position,
    _gui_queue_is_first,
    _gui_wait_report,
    acquire_gui_lock,
    release_gui_lock,
    other_gui_holder,
    concurrency_warning,
    ConcurrencyResult,
    sink_test_windows,
    real_topmost,
    protect_tk,
    _run_unit,
    _worker,
    _serial_worker,
    cleanup_unit_helpers,
    run_units,
    run_serial,
    run_safe_serial,
    prioritize_gui_units,
)
from selftest_reporting import (
    slowest_units,
    skip_summary,
    print_unit_result,
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    keys, jobs, serial, listing, whole = [], 0, False, False, False
    everything, safe, force, layer = False, False, False, ''
    allow_dirty_diagnostic = False
    gui_override = None
    gui_wait = GUI_WAIT_SECONDS
    gui_lock = None
    lock = None
    deferred = []
    while argv:
        arg = argv.pop(0)
        if arg == '--serial':
            serial = True
        elif arg == '--list':
            listing = True
        elif arg == '--whole':
            whole = True
        elif arg == '--safe':
            safe = True
        elif arg == '--force':
            force = True
        elif arg == '--allow-dirty-diagnostic':
            allow_dirty_diagnostic = True
        elif arg == '--all':
            everything = True
        elif arg == '--incremental':
            # 默认就是增量模式；保留显式开关给三虎测试模式与脚本调用，不能把它当成 -k 关键字。
            pass
        elif arg == '--layer':
            layer = argv.pop(0).strip().lower()
        elif arg == '--jobs':
            jobs = int(argv.pop(0))
        elif arg == '--gui-jobs':
            gui_override = int(argv.pop(0))
            safe_gui_jobs(JOBS_CAP, gui_override)
        elif arg == '--gui-wait':
            gui_wait = float(argv.pop(0))
            if gui_wait < 0:
                raise ValueError('--gui-wait 必须非负')
        elif arg == '-k':
            keys.extend(argv.pop(0).split())
        else:
            keys.append(arg)
    everything, serial, whole, jobs = safe_full_options(everything, serial, whole, jobs, safe)
    all_names = test_modules()
    names = test_modules(keys)
    try:
        all_names = modules_for_layer(all_names, layer)
        names = modules_for_layer(names, layer)
    except ValueError as exc:
        print(str(exc))
        return 2
    if layer:
        print('测试层：%s（%d 个测试文件）' % (layer, len(names)))
    if listing:
        for name in names:
            print(name)
        return 0
    full_safe = everything and safe and not keys and not layer
    no_receipt = full_safe and allow_dirty_diagnostic
    start_head = ''
    tree = content_tree() if full_safe else ''
    verified = verified_tree_record(load_layer_document().get('full_safe_verified_trees', []), tree)
    if (full_safe and not force and not os.environ.get('AUTO_FULL_SAFE_HEAD') and auto_full_running()):
        print('后台自动全量正在运行（scripts/auto_full_safe.py），请勿再手动跑全量：同时跑两份会争抢 GUI 令牌且互相拖慢。')
        print('进度见 程序/logs/auto_full_safe.log；确需手动执行加 --force。')
        return 3
    if full_safe and verified and not force:
        print('内容树同 R%s 已验证(3,698 条/%.3f秒/0 红)' %
              (verified['round'], float(verified['seconds'])))
        return 0
    if full_safe:
        try:
            lock = acquire_full_safe_lock(round_number=latest_completed_round())
        except RuntimeError as exc:
            print(str(exc))
            return 2
        atexit.register(release_full_safe_lock, lock)
        permitted, tree = full_safe_preflight(allow_dirty_diagnostic)
        if not permitted:
            atexit.unregister(release_full_safe_lock)
            release_full_safe_lock(lock)
            lock = None
            return 2
        start_head = _git_text('rev-parse', 'HEAD') if tree else ''
        if tree:
            print('验收起点：HEAD=%s，工作树干净' % start_head)
    if not serial and not jobs:
        jobs = max(2, min(JOBS_CAP, (os.cpu_count() or 4)))
    try:
        protect_tk()
        fails = import_all()
        if fails:
            print("IMPORT FAILURES:")
            for m, e in fails:
                print(f"  {m}: {e}")
        else:
            print("IMPORT OK: all modules imported")
        cache = {} if everything else load_cache()
        todo_names, skipped, state = incremental(names, cache)
        if keys:
            # -k 是显式门禁，不应被增量台账跳过；同时不能因只跑一个用例而抹掉其他用例的缓存。
            old_tests = cache.get('tests') if isinstance(cache.get('tests'), dict) else {}
            selected_tests = state['tests']
            state['tests'] = {name: entry for name, entry in old_tests.items() if name in all_names}
            state['tests'].update(selected_tests)
            todo_names, skipped = list(names), []
            print('定向：忽略增量台账，执行 %d 个匹配测试文件' % len(names))
        elif everything:
            todo_names, skipped = list(names), []
            print('%s：忽略增量台账，%d 个测试文件全跑一遍' %
                  ('--safe（全量受控分池）' if safe else '--all', len(names)))
        elif skipped:
            print('增量：跳过 %d 个没改过的测试文件（--all 全跑）：%s' % (len(skipped), ' '.join(skipped)))
        keep = set(todo_names)
        todo = [unit for unit in units(names, whole=whole) if unit[1] in keep]
        # 性能用例不与别的用例挤并行池：它们量的是墙上时间，而「建 Tk 控件＋
        # 字体量宽」是全机共享的资源，被别的用例抢慢好几倍时，会把自己的抖动判成性能退化
        # （第 72 期实测：并行时资产页打开 3.9～6.8 s，单独跑 0.3～0.5 s）。挑出来等池子空了自己跑。
        todo, perf = split_performance_units(todo)
        non_gui, gui = split_safe_units(todo)
        perf_non_gui, perf_gui = split_safe_units(perf)
        print('跑 %d 个测试文件 / %d 路工作单元（%s）' % (len(todo_names), len(todo),
                                                      '串行' if serial else '%d 路并行' % jobs))
        if perf:
            print('另有 %d 个工作单元是性能用例，排在并行池之后单独串行跑' % len(perf))
        gui_jobs = safe_gui_jobs(jobs, gui_override) if safe else jobs
        started = time.time()
        if safe and (non_gui or gui):
            print('安全分池：%d 路无 Tk 并行（%d workers），%d 路 Tk 受控并行（%d workers）' %
                  (len(non_gui), jobs, len(gui), gui_jobs))
        # 非 GUI 用例先跑完，再申请令牌：GUI 令牌只在真正执行 Tk 用例期间持有。
        if non_gui:
            got = run_serial(non_gui) if serial else run_units(non_gui, jobs)
        else:
            got = []
        if gui or perf_gui:
            print('申请跨树 GUI 令牌（最多等待 %.1f 秒）' % gui_wait, flush=True)
            gui_lock = acquire_gui_lock(wait=gui_wait)
            if gui_lock:
                atexit.register(release_gui_lock, gui_lock)
            else:
                deferred = []
                for unit in gui + perf_gui:
                    if unit[1] not in deferred:
                        deferred.append(unit[1])
                gui, perf_gui = [], []
            try:
                if gui:
                    if safe:
                        got += run_units(prioritize_gui_units(gui), gui_jobs)
                    elif serial:
                        got += run_serial(gui)
                    else:
                        got += run_units(gui, jobs)
                if perf_gui:
                    got += run_safe_serial(perf_gui) if safe else run_serial(perf_gui)
            finally:
                # 跑完 GUI 用例立刻还牌，不等汇总、台账或进程退出。
                if gui_lock:
                    atexit.unregister(release_gui_lock)
                    release_gui_lock(gui_lock)
                    gui_lock = None
        if perf_non_gui:
            got += run_safe_serial(perf_non_gui) if safe else run_serial(perf_non_gui)
        elapsed = time.time() - started
        total = sum(item[2] for item in got)
        reds = [(item[1], item[3], item[4]) for item in got if item[3]]
        print('\n共 %d 条用例，%.1f 秒；%d 个文件有红' % (total, elapsed, len(reds)))
        slow = slowest_units(got)
        if slow:
            print('最慢 %d 路工作单元：' % len(slow))
            for item in slow:
                print('  %-26s %6.1f 秒 / %d 条' % (item[0], item[5], item[2]))
        skips = skip_summary(got)
        if skips:
            print('实际跳过 %d 条用例（登记位不等于已跳过）：' % len(skips))
            for module, test, reason in skips[:SKIP_REPORT_LIMIT]:
                print('  %-24s %s ← %s' % (module, test, reason))
            if len(skips) > SKIP_REPORT_LIMIT:
                print('  …还有 %d 条未打印' % (len(skips) - SKIP_REPORT_LIMIT))
        else:
            print('实际跳过 0 条用例：本机没有任何登记位被跳过')
        for name, bad, detail in reds:
            print('\n### %s（%d 条红）' % (name, len(bad)))
            print(detail)
        if any('[SUSPECT_CONCURRENCY]' in item[6] for item in got if item[3]):
            print('[SUSPECT_CONCURRENCY] 红项发生时有其他 PID 持有 GUI 令牌；建议串行复跑。')
        if deferred:
            print('[GUI_DEFERRED] 未执行、不计通过：' + ' '.join(deferred))
            print('GUI 测试 %d 个未运行（等待令牌超时，未执行、未计入通过）：%s' %
                  (len(deferred), ' '.join(deferred)))
        if full_safe and not no_receipt and not measurement_unchanged(start_head, tree):
            print('验收无效：测量期间 HEAD 或工作树变化，不写入绿凭据。')
            raise SystemExit(2)
        if no_receipt:
            print('[NO_RECEIPT] 本次仅诊断：不写入绿凭据、分层基线或增量台账。')
        baseline = '' if (deferred or no_receipt) else save_layer_baseline(layer, got, elapsed)
        if baseline:
            print('分层基线已刷新：' + baseline)
        if fails or reds:
            failed_tree = content_tree()
            if failed_tree and invalidate_verified_tree(load_layer_document(), failed_tree):
                print('当前内容树的全量绿凭据已失效：本轮存在红项')
            raise SystemExit(1)
        if deferred:
            return 2
        if full_safe and not no_receipt and tree and receipt_checkout_allowed():
            saved = save_full_safe_verification(tree, latest_completed_round(), elapsed)
            if saved:
                print('内容树全量凭据已刷新：' + saved)
        timings = record_elapsed(cache, state, elapsed) if not no_receipt else None
        written = save_cache(state) if not no_receipt else ''
        if written:
            print('增量台账已刷新：' + written)
            print('最近 %d 轮自检中位基线：%.1f 秒' % (len(timings['recent_seconds']), timings['median_seconds']))
        print("\nALL TESTS PASSED")
        return 0
    finally:
        if gui_lock:
            atexit.unregister(release_gui_lock)
            release_gui_lock(gui_lock)
        if lock:
            atexit.unregister(release_full_safe_lock)
            release_full_safe_lock(lock)



if __name__ == "__main__":
    sys.exit(main())
