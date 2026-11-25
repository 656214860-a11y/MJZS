# -*- coding: utf-8 -*-
"""三虎的「是/否、列表选一个」小窗与半自动付费步骤放行（SANHU-FIX-2：S-03/S-05/S-10）。

``ask_yes`` 复用 ``ui_widgets.ask_confirmation``：主线程同步弹；非界面线程先经
``win.after(0, ...)`` 切回主线程再弹——本机 Tcl 拒收后台线程的 ``after`` 时
（``main thread is not in main loop``，与 desktop_async_tasks 同一口径）改投
``_PENDING``，由主线程心跳 ``pump_asks()`` 领走弹出；``wait`` 秒内没人答就返回
``None``（弹不了也按没答处理）。``ask_choice`` 是 Toplevel 列表＋「确定/取消」
（照 ``ui/version_picker.py`` 的风格但不复用它）：确定返回所选序号，
取消／关窗／没有选项返回 ``None``。

``approve_stage``／``confirm_paid`` 是 S-05 半自动付费步骤的放行裁决：用户没点头的阶段
记进宿主的 ``_paid_declined`` 集合，本档不再自动追问——用户说「继续」或切档才清
（清的两处在 ``pet_ui_stages``）。
"""
import threading
import tkinter as tk

import contract.pet_bus as pet_bus
from ui.pet_ui_support import CONFIRM_TITLE
from ui_tokens import SPACING
from ui_widgets import BaseDialog, DataTable, DescriptionBlock, ask_confirmation


def _on_main_thread():
    try:
        return threading.current_thread() is threading.main_thread()
    except Exception:
        return True


_PENDING = []                    # worker 攒下的「是/否」回切，主线程 pump_asks() 领走
_PENDING_LOCK = threading.Lock()


def pump_asks():
    """主线程心跳（Pet.pump → poll_test_mode）里领走 worker 攒下的回切；过期只标完成。"""
    while True:
        with _PENDING_LOCK:
            if not _PENDING:
                return
            ask = _PENDING.pop(0)
        ask()


def ask_yes(win, title, text, wait=None):
    """「是/否」小窗：True 点头；False 按「否」／取消／关窗／弹不了；None 超时没等到。

    主线程同步弹；非界面线程先把弹窗动作经 ``win.after(0, ...)`` 递回主线程，Tcl 拒收
    时投进 ``_PENDING`` 等心跳领走，再阻塞等到答出或 ``wait`` 秒到点。超时后迟到的
    回切只标记完成，不再把窗弹出来。
    """
    if _on_main_thread():
        try:
            return bool(ask_confirmation(win, title, text))
        except Exception:
            return False
    box = {'answer': False, 'expired': False, 'done': threading.Event()}

    def ask():
        if box['expired']:
            box['done'].set()
            return
        try:
            box['answer'] = bool(ask_confirmation(win, title, text))
        except Exception:
            box['answer'] = False
        box['done'].set()
    try:
        win.after(0, ask)
    except Exception:
        with _PENDING_LOCK:
            _PENDING.append(ask)
    if not box['done'].wait(wait):
        box['expired'] = True
        return None
    return box['answer']


def ask_choice(win, title, text, options):
    """列表选一个：确定返回所选序号；取消／关窗／没有选项返回 None。"""
    items = [str(item) for item in (options or ())]
    if win is None or not items:
        return None
    box = {'picked': None}
    dialog = BaseDialog(win, str(title or ''))
    DescriptionBlock(dialog.content, text=str(text or '')).pack(fill='x')
    table = DataTable(dialog.content, columns=(('item', '可选', 40),),
                      height=min(len(items), 8), horizontal=False)
    for index, item in enumerate(items):
        table.tree.insert('', 'end', iid=str(index), values=(item,))
    table.tree.selection_set('0')
    table.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['none']))

    def ok():
        chosen = table.tree.selection()
        box['picked'] = int(chosen[0]) if chosen else None
        dialog.close()

    dialog.add_action('确定', ok, primary=True)
    dialog.add_action('取消', dialog.close)
    try:
        dialog.wait_window()
    except tk.TclError:
        return None
    return box['picked']


def declined_set(host):
    """宿主上「本档内被拒过的付费阶段」集合：懒初始化、不落盘，切档随授权一起清。"""
    return host.__dict__.setdefault('_paid_declined', set())


def confirm_paid(host, stage):
    """半自动付费步骤的点头裁决（S-05）。

    True＝用户点头：先把这一阶段授权记进 ``grant_paid``，再以 ``confirmed=True`` 重审；
    False＝用户没点头或没等到：阶段记进被拒集合；
    None＝这一阶段本档已被拒过，不再自动追问。
    """
    if stage in declined_set(host):
        return None
    name = pet_bus.STAGE_NAMES.get(stage, stage)
    if ask_yes(getattr(host, 'win', None), CONFIRM_TITLE,
               '「%s」这一步要花钱，现在做吗？' % name) is not True:
        declined_set(host).add(stage)
        return False
    try:
        host.grant_paid(stage)
        return bool(host.agent.approve('stage.run', paid=True, confirmed=True).get('run'))
    except Exception as exc:
        errors = getattr(host, 'errors', None)
        if errors is not None:
            errors.append(('paid.confirm', str(exc)))
        return False


def approve_stage(host, stage, *, paid=False):
    """``start_stage`` 的放行裁决：返回 ``(allowed, declined_text)``。

    审批放行 → ``(True, '')``；不在询问口径（不需要确认／已拒过）→ ``(False, '')``，
    照旧只把轮询提前叫醒；付费步骤刚被用户拒绝 → ``(False, 回话)``，调用方照旧叫醒
    轮询后把这句回出去。
    """
    try:
        decision = host.agent.approve('stage.run', paid=paid)
    except Exception as exc:
        host.errors.append(('start', str(exc)))
        return False, ''
    if not decision.get('confirm'):
        return bool(decision.get('run')), ''
    verdict = confirm_paid(host, stage)
    if verdict is False:
        return False, '「%s」要花钱，等您点头再开始' % pet_bus.STAGE_NAMES.get(stage, stage)
    return bool(verdict), ''
