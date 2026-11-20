# -*- coding: utf-8 -*-
"""自检的调度：跨树 PID/GUI 令牌与等待队列、Tk 沉底保护、并行/串行工作池与单元超时回收。"""

import infra.app_logging as app_logging
import importlib
import io
import json
import os
import sys
import tempfile
import time
import unittest

import selftest_env as env
import selftest_discovery as discovery
import selftest_reporting as reporting


_GUI_LOCK_DEPTH = {}


_FULL_LOCK_DEPTH = {}


def acquire_pid_lock(name, common_dir=None, round_number=None, reentrant=False):
    """跨树令牌：心跳 3 分钟内视为占用；没有心跳的旧锁仍按 PID。原子发布，避免半写锁。"""
    common = common_dir or env.git_common_dir()
    if not common:
        raise RuntimeError('无法定位 Git common-dir，拒绝无令牌执行')
    path = os.path.join(common, name)
    payload = env.lock_lease.payload(os.getpid(), round=round_number)
    while True:
        descriptor, temporary = tempfile.mkstemp(prefix=name + '.', suffix='.tmp', dir=common)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False)
            try:
                os.link(temporary, path)
            except FileExistsError:
                state, holder, _snapshot = env.inspect_lock(path)
                if state == 'missing':
                    continue
                ours = (reentrant and holder.get('pid') == os.getpid()
                        and not env._record_is_reused(holder.get('pid'), holder.get('started_at')))
                if state == 'live' and ours:
                    env.arm_lock(path)
                    return path
                if state in ('live', 'unknown'):
                    raise RuntimeError('%s 已由 PID %s（R%s）持有' %
                                       (name, holder.get('pid'), holder.get('round', '?')))
                if not env.reclaim_stale_lock(path) and os.path.exists(path):
                    raise RuntimeError('%s 已由 PID %s（R%s）持有' %
                                       (name, holder.get('pid'), holder.get('round', '?')))
                continue
            env.arm_lock(path)
            return path
        finally:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def acquire_full_safe_lock(common_dir=None, round_number=None):
    """同一时刻只跑一份全量。锁文件不拦提交：十几分钟的全量不再卡住车道和合并。"""
    path = acquire_pid_lock(env.FULL_SAFE_RUNNER_LOCK_NAME, common_dir, round_number, reentrant=True)
    _FULL_LOCK_DEPTH[path] = _FULL_LOCK_DEPTH.get(path, 0) + 1
    return path


def release_full_safe_lock(path):
    depth = _FULL_LOCK_DEPTH.get(path, 1) - 1
    if depth:
        _FULL_LOCK_DEPTH[path] = depth
        return
    _FULL_LOCK_DEPTH.pop(path, None)
    release_pid_lock(path)


def release_pid_lock(path):
    if env.lock_holder(path).get('pid') != os.getpid():
        return
    env.disarm_lock(path)
    try:
        os.unlink(path)
    except OSError:
        pass


def _gui_queue_dir(common_dir):
    queue = os.path.abspath(os.path.join(common_dir, env.GUI_QUEUE_NAME))
    os.makedirs(queue, exist_ok=True)
    return queue


def _gui_queue_tickets(queue):
    try:
        return sorted(name for name in os.listdir(queue) if name.endswith(env.GUI_QUEUE_SUFFIX))
    except OSError:
        return []


def _drop_dead_gui_tickets(queue):
    """等待者进程已经没了，它留下的号不能永久占住队首。"""
    for name in _gui_queue_tickets(queue):
        path = os.path.join(queue, name)
        holder = env.lock_holder(path)
        pid = holder.get('pid')
        started_at = holder.get('started_at')
        if not env._record_is_reused(pid, started_at) and pid in (None, os.getpid()):
            continue
        if not env._pid_is_alive(pid, started_at):
            try:
                os.unlink(path)
            except OSError:
                pass


def _join_gui_queue(queue):
    """按到达顺序取号：文件名前缀是纳秒时间，天然按先来后到排序。"""
    descriptor, path = tempfile.mkstemp(
        prefix='%020d-%d-' % (time.time_ns(), os.getpid()), suffix=env.GUI_QUEUE_SUFFIX, dir=queue)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'pid': os.getpid(), 'started_at': time.time()}, handle, ensure_ascii=False)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _leave_gui_queue(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _gui_queue_position(queue, ticket):
    _drop_dead_gui_tickets(queue)
    tickets = _gui_queue_tickets(queue)
    for index, name in enumerate(tickets):
        if os.path.join(queue, name) == ticket:
            return index + 1
    return len(tickets) + 1


def _gui_queue_is_first(queue, ticket):
    _drop_dead_gui_tickets(queue)
    tickets = _gui_queue_tickets(queue)
    return bool(tickets) and os.path.join(queue, tickets[0]) == ticket


def _gui_wait_report(common, waited, queue, ticket):
    """每 30 秒左右告诉等待者：谁占着、占了多久、自己等了多久。"""
    holder = env.lock_holder(os.path.join(common, env.GUI_LOCK_NAME))
    pid = holder.get('pid', '?')
    try:
        started_at = float(holder.get('started_at'))
    except (TypeError, ValueError):
        started_at = None
    if started_at is None:
        started_text, held_text = '未知', '未知'
    else:
        started_text = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started_at))
        held_text = '%.0f 秒' % max(0.0, time.time() - started_at)
    print('[GUI_WAIT] 等待跨树 GUI 令牌：占用者 PID %s，自 %s 起（已占 %s），'
          '本进程已等 %.0f 秒（队列第 %d 位）' %
          (pid, started_text, held_text, waited, _gui_queue_position(queue, ticket)), flush=True)


def foreign_full_suite(common):
    """别的进程正在跑全量。本进程和它的 worker 不算。"""
    if not common:
        return False
    holder = env.lock_holder(os.path.join(common, env.FULL_SAFE_RUNNER_LOCK_NAME))
    pid = holder.get('pid')
    if pid in (None, os.getpid(), os.getppid()):
        return False
    return env.holder_is_live(holder)


def _gui_deferred(reason, capped):
    if capped:
        print('[GUI_DEFERRED] 全量测试正在占用 GUI，本会话不再等待：%s' % reason)
    else:
        print('[GUI_DEFERRED] GUI 令牌等待超时：%s' % reason)


def acquire_gui_lock(common_dir=None, wait=env.GUI_WAIT_SECONDS):
    if wait < 0:
        raise ValueError('--gui-wait 必须非负')
    common = common_dir or env.git_common_dir()
    if not common:
        raise RuntimeError('无法定位 Git common-dir，拒绝无令牌执行')
    try:
        path = acquire_pid_lock(env.GUI_LOCK_NAME, common, reentrant=True)
        _GUI_LOCK_DEPTH[path] = _GUI_LOCK_DEPTH.get(path, 0) + 1
        return path
    except RuntimeError as exc:
        holder_error = exc
    capped = False
    if foreign_full_suite(common):
        wait = min(wait, env.GUI_FULL_SUITE_WAIT_SECONDS)
        capped = True
        print('[GUI_WAIT] 全量测试正在占用 GUI，本会话最多再等 %.0f 秒' % wait, flush=True)
    deadline = time.monotonic() + wait
    if time.monotonic() >= deadline:
        _gui_deferred(holder_error, capped)
        return None
    queue = _gui_queue_dir(common)
    ticket = _join_gui_queue(queue)
    entered = time.monotonic()
    last_report = None
    try:
        while True:
            # 只有队首可以尝试拿锁：后到的不许每 0.1 秒插一次队。
            if _gui_queue_is_first(queue, ticket):
                try:
                    path = acquire_pid_lock(env.GUI_LOCK_NAME, common, reentrant=True)
                    _GUI_LOCK_DEPTH[path] = _GUI_LOCK_DEPTH.get(path, 0) + 1
                    return path
                except RuntimeError as exc:
                    holder_error = exc
            waited = time.monotonic() - entered
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _gui_deferred(holder_error, capped)
                return None
            if last_report is None or waited - last_report >= env.GUI_WAIT_NOTICE_SECONDS:
                _gui_wait_report(common, waited, queue, ticket)
                last_report = waited
            time.sleep(min(env.GUI_LOCK_POLL_SECONDS, remaining))
    finally:
        _leave_gui_queue(ticket)


def release_gui_lock(path):
    if not path:
        return
    depth = _GUI_LOCK_DEPTH.get(path, 1) - 1
    if depth:
        _GUI_LOCK_DEPTH[path] = depth
    else:
        _GUI_LOCK_DEPTH.pop(path, None)
        release_pid_lock(path)


def other_gui_holder():
    common = env.git_common_dir()
    holder = env.lock_holder(os.path.join(common, env.GUI_LOCK_NAME)) if common else {}
    pid = holder.get('pid')
    # 工作池子进程使用父进程的令牌，不是竞争工作流。
    # 心跳仍在就视为占用，打不开对方进程不算对方已经退出。
    if pid in (os.getpid(), os.getppid(), None):
        return None
    return pid if env.holder_is_live(holder) else None


def concurrency_warning():
    pid = other_gui_holder()
    return ('[SUSPECT_CONCURRENCY] 失败时 GUI 令牌由 PID %s 持有；建议串行复跑' % pid) if pid else ''


class ConcurrencyResult(unittest.TextTestResult):
    def _observe(self):
        warning = concurrency_warning()
        if warning:
            self.stream.writeln(warning)

    def addFailure(self, test, err):
        self._observe()
        super().addFailure(test, err)

    def addError(self, test, err):
        self._observe()
        super().addError(test, err)


def sink_test_windows():
    """自检期间建的窗口一律沉到桌面最底层，别影响用户操作。

    第 31 期第 3 条：整跑要开几十个 Tk 窗口（主界面、云朵框、各种弹窗，三虎那朵云还是
    置顶无边框窗），跑一遍一百秒里用户在自己机器上干活会被反复盖住。这里把「置顶」和
    「抬到最前面」两个动作都拦下来：置顶请求一律改写成 False，抬窗／显示之后立刻压回去。
    只对 Tk／Toplevel 这种真窗口生效，画布之类的子控件不碰（lower 对它们是改同层叠放）。
    """
    import tkinter as tk
    import weakref
    if getattr(tk, '_drama_sunk_windows', False):
        return
    tk._drama_sunk_windows = True
    original_attrs = tk.Wm.wm_attributes
    tk._drama_real_wm_attributes = original_attrs
    wanted = tk._drama_wanted_topmost = weakref.WeakKeyDictionary()

    def wm_attributes(self, *args):
        if len(args) == 2 and args[0] == '-topmost':
            # 真窗口一律不置顶（不然盖住用户），但把「代码想要什么」记下来：用例读 attributes
            # 读到的仍是它请求的值，置顶这件事照旧被盯着；真实状态用 real_topmost 看。
            wanted[self] = str(args[1]) not in ('0', 'False', 'false')
            original_attrs(self, '-topmost', False)
            return ''
        if len(args) == 1 and args[0] == '-topmost' and self in wanted:
            return wanted[self]
        return original_attrs(self, *args)

    tk.Wm.wm_attributes = wm_attributes
    tk.Wm.attributes = wm_attributes

    def sink(widget):
        if not isinstance(widget, (tk.Tk, tk.Toplevel)):
            return
        try:
            tk.Misc.lower(widget)
        except Exception:
            app_logging.swallowed('测试窗口下沉')

    def wrap(cls, name):
        original = getattr(cls, name, None)
        if original is None:
            return

        def wrapper(self, *args, **kwargs):
            outcome = original(self, *args, **kwargs)
            sink(self)
            return outcome

        wrapper.__name__ = name
        setattr(cls, name, wrapper)

    for name in ('lift', 'tkraise'):
        wrap(tk.Misc, name)
    for name in ('deiconify', 'focus_force'):
        wrap(tk.Wm if hasattr(tk.Wm, name) else tk.Misc, name)


def real_topmost(widget):
    """窗口在系统里真实的置顶状态。

    sink_test_windows 会把 attributes('-topmost') 的读值换成「代码请求的值」（用例要盯住
    「云朵框有没有要求置顶」），所以真实状态得走这里看：自检期间它一定是 False。
    """
    import tkinter as tk
    getter = getattr(tk, '_drama_real_wm_attributes', None)
    if getter is None:
        return bool(widget.wm_attributes('-topmost'))
    return bool(getter(widget, '-topmost'))


def protect_tk():
    """自测也要给 Tk 解释器上同一层保护。

    自测进程每例都建 Tk 窗口、还留着常驻 worker 线程：worker 里的一次 GC 就可能把主线程建的窗口
    对象环连同 Tcl 解释器一起回收，Tcl 会直接中止进程（Tcl_AsyncDelete），表现为整跑崩掉、
    一条用例结果都不打印。主程序在 Desktop 启动时装这层保护，自测在发现用例之前装。
    """
    sink_test_windows()          # 第 31 期第 3 条：自检的窗口一律沉到桌面最底层，不打扰用户
    # 第 47 期第 3 条：点「手动XX」时那句「先去阶段配置挑模型」的提醒框，整跑里一律换成
    # 「先不配，照旧开始」——用例点到那颗按钮时不该弹个模态框把整跑卡死。要盯这句话的用例
    # 自己换回来（见 test_manual_gate.py），它验的就是这里的默认值被换掉以后的行为。
    try:
        import stage_models
        stage_models.ASKER = lambda *a, **k: False
        # 第 54 期附件三那扇「手动制作XX」精简窗同理：整跑里一律按「直接执行」，
        # 用例点到那颗按钮时不该冒出一个模态窗把整跑卡死。要盯这一窗的用例自己换回来
        # （见 test_manual_plan.py 与 test_manual_gate.py）。
        stage_models.PLANNER = lambda *a, **k: 'run'
    except Exception as exc:
        print('「先挑模型」提醒未改写成假函数：' + str(exc))
    try:
        from desktop import protect_tk_gc
        protect_tk_gc()
    except Exception as exc:
        print('Tk 保护未安装：' + str(exc))


def _run_unit(payload):
    """子进程里跑一个工作单元；返回 (标签, 文件名, 条数, 坏例, 细节, 秒数, 输出)。"""
    label, module, classes = payload
    os.chdir(env.HERE)
    if env.HERE not in sys.path:
        sys.path.insert(0, env.HERE)
    env.install_temp_sandbox()
    protect_tk()
    stdio_save = sys.stdout, sys.stderr
    buf = io.StringIO()
    sys.stdout = sys.stderr = buf
    started = time.time()
    try:
        loader = unittest.TestLoader()
        if classes:
            mod = importlib.import_module(module)
            suite = unittest.TestSuite()
            for class_name, methods in classes:
                wanted = set(methods)
                for case in discovery._flat_cases(loader.loadTestsFromTestCase(getattr(mod, class_name))):
                    if case._testMethodName in wanted:
                        suite.addTest(case)
        else:
            suite = loader.loadTestsFromName(module)
        result = unittest.TextTestRunner(stream=buf, verbosity=1, resultclass=ConcurrencyResult).run(suite)
        bad = [str(case) for case, _tb in list(result.failures) + list(result.errors)]
        detail = ''
        for case, tb in list(result.failures) + list(result.errors):
            detail += "\n===== %s =====\n%s" % (case, tb)
        skipped = [(str(case), str(reason).splitlines()[0] if str(reason) else '')
                   for case, reason in result.skipped]
        return (label, module, result.testsRun, bad, detail, time.time() - started, buf.getvalue(), skipped)
    except Exception as exc:                     # 这一路起不来（导入期就炸）
        return (label, module, 0, [label], "\n===== %s 起不来 =====\n%s" % (label, exc),
                time.time() - started, buf.getvalue() + concurrency_warning(), [])
    finally:
        # 一路测试可能通过 Desktop → asset_thumbs 启动后台 Tk 解码器；测试进程退出
        # 不会替它收尾，导致全量并行后积累几十个 Python 进程并让 smoke 卡住。
        cleanup_unit_helpers()
        sys.stdout, sys.stderr = stdio_save


def _worker(payload):
    return _run_unit(payload)


def _serial_worker(payload, result_sender):
    """隔离安全串行的单元，使失控的 Tk 模态窗能被父进程超时回收。"""
    try:
        result_sender.send(_run_unit(payload))
    finally:
        result_sender.close()


def cleanup_unit_helpers():
    """回收测试单元启动的后台助手，避免 Windows 留下缩略图孤儿进程。"""
    try:
        import asset_thumbs
        asset_thumbs.forget()
        asset_thumbs.reset_worker()
    except Exception:
        app_logging.swallowed('清理缩略图工作单元')  # 清理失败不能覆盖原测试的报错


def run_units(todo, jobs=8, fresh_children=False):
    """并行跑（Windows 上 spawn：每个子进程自己建 Tk，互不打扰）。

    ``fresh_children`` 让每个工作单元拿到全新子进程（``max_tasks_per_child=1``）：
    隐藏桌面里同一进程的第二个及以后 ``tk.Tk()`` 无法合成按键事件
    （``event_generate('<Control-…>')`` 不投递，见 tests/test_script_zoom.py 卷首），
    复用 worker 会让排在后面的按键用例必然拿不到焦点投递，故 GUI 单元必须逐单元隔离。
    """
    import concurrent.futures as futures
    out = []
    pool = futures.ProcessPoolExecutor(
        max_workers=max(1, jobs),
        max_tasks_per_child=1 if fresh_children else None)
    timed_out = False
    try:
        pending = {pool.submit(_worker, payload): payload for payload in todo}
        last_progress = time.time()
        while pending:
            done, waiting = futures.wait(pending, timeout=env.HEARTBEAT_SECONDS,
                                         return_when=futures.FIRST_COMPLETED)
            if not done:
                print('  … 并行回归仍在执行：%d 路未完成（每 %d 秒心跳）' %
                      (len(waiting), env.HEARTBEAT_SECONDS), flush=True)
                if time.time() - last_progress < env.SAFE_UNIT_TIMEOUT:
                    continue
                stalled = [pending[future] for future in waiting]
                labels = [payload[0] for payload in stalled]
                print('  ! 并行池连续 %d 秒无进展，回收 %d 路卡住单元：%s' %
                      (env.SAFE_UNIT_TIMEOUT, len(labels), ' '.join(labels)), flush=True)
                for process in pool._processes.values():
                    process.terminate()
                now = time.time()
                out.extend((payload[0], payload[1], 0, [payload[0]],
                            '\n===== %s 超时 =====\n并行池连续 %d 秒无进展，已回收。' %
                            (payload[0], env.SAFE_UNIT_TIMEOUT), now - last_progress, concurrency_warning())
                           for payload in stalled)
                pending = {}
                timed_out = True
                break
            for future in done:
                item = future.result()
                out.append(item)
                reporting.print_unit_result(item)
                pending.pop(future)
            last_progress = time.time()
    finally:
        # ``with ProcessPoolExecutor`` always waits in __exit__.  Once a GUI
        # worker is known stuck, that turns the watchdog into another hang.
        pool.shutdown(wait=not timed_out, cancel_futures=timed_out)
    return out


def run_serial(todo, timeout=env.SAFE_UNIT_TIMEOUT):
    """一次只跑一个单元，并为每段 UI 回归设置可回收的超时边界。"""
    import multiprocessing
    out = []
    for payload in todo:
        print('  → 开始 %-26s' % payload[0], flush=True)
        started = time.time()
        result_reader, result_sender = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.Process(target=_serial_worker, args=(payload, result_sender))
        try:
            process.start()
        except OSError as exc:
            # Windows 在长安全串行运行中可能拒绝复制新子进程的管道句柄。
            # 不能把尚未执行的测试误报为通过；退回当前进程直接运行并保留真实结果。
            result_sender.close()
            result_reader.close()
            print('  ! 安全隔离进程未启动，改为同进程执行：' + str(exc), flush=True)
            item = _run_unit(payload)
            out.append(item)
            reporting.print_unit_result(item)
            continue
        result_sender.close()
        try:
            # Pipe.poll 有明确的超时语义；即使 Tk 子进程异常退出而未回传，也不会永久卡在
            # Queue.get。仍须先接收再 join，避免大结果堵住回传管道。
            if not result_reader.poll(timeout):
                raise TimeoutError
            item = result_reader.recv()
        except (EOFError, TimeoutError):
            process.terminate()
            process.join(10)
            item = (payload[0], payload[1], 0, [payload[0]],
                    '\n===== %s 超时 =====\n安全串行单元超过 %d 秒，已回收。' % (payload[0], timeout),
                    time.time() - started, concurrency_warning())
        else:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(10)
        result_reader.close()
        out.append(item)
        reporting.print_unit_result(item)
    return out


def run_safe_serial(todo):
    """安全全量在当前进程逐单元执行，规避 Windows 长运行的 spawn 管道句柄限制。

    ``--serial`` 仍保留子进程隔离与超时回收；``--safe`` 的目标是同一时刻只运行一个
    测试单元，直接调用既能满足该目标，也不会在数百次 Windows spawn 后失去结果汇总。
    """
    out = []
    for payload in todo:
        print('  → 开始 %-26s' % payload[0], flush=True)
        item = _run_unit(payload)
        out.append(item)
        reporting.print_unit_result(item)
    return out


def prioritize_gui_units(units):
    """Submit known long GUI suites first; retain every unit and stable group order."""
    return sorted(units, key=lambda unit: unit[1].rsplit('.', 1)[-1] not in env.GUI_E2E_MODULES)
