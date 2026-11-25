"""阶段执行窗与手动制作精简窗（L4 呈现器）：从 ui_widgets 拆出，导入本模块即向 stage_exec 登记。"""
import tkinter as tk
from tkinter import ttk

import contract.service_contract as service_contract
import infra.app_logging as app_logging
from orchestrator import stage_models
from ui_tokens import BUTTON_GAP, SPACING, TEXT_ROWS, WRAPLENGTH
from ui_widgets import BaseDialog, PrimaryButton, SecondaryButton, TextArea, ask_confirmation


def _release_stage_popup_jobs(window, event=None):
    if event is not None and event.widget is not window:
        return
    for job in tuple(getattr(window, '_stage_popup_jobs', ())):
        try:
            window.after_cancel(job)
        except tk.TclError:
            pass
    window._stage_popup_jobs = set()


def _schedule_stage_popup_job(window, delay, callback):
    jobs = getattr(window, '_stage_popup_jobs', None)
    if jobs is None:
        jobs = set()
        window._stage_popup_jobs = jobs
        window.bind('<Destroy>', lambda event, owner=window: _release_stage_popup_jobs(owner, event), add='+')
    job = None

    def run():
        jobs.discard(job)
        callback()

    job = window.after(delay, run)
    jobs.add(job)
    return job


def _activate_stage_popup(window):
    try:
        window.attributes('-topmost', True)
        window.lift()
        window.focus_force()
        _schedule_stage_popup_job(window, 1200,
                                  lambda: window.winfo_exists() and window.attributes('-topmost', False))
    except tk.TclError:
        pass


def _show_stage_execution(desktop, stage, *, parent, title, names, runner, failed_rows, progress, on_back):
    """L4 承载执行页控件；L3 通过显式回调提供执行和结果解释。"""
    host = parent if parent is not None else getattr(desktop, 'win', None)
    standalone = host is None
    window = tk.Tk() if standalone else BaseDialog(host, '', modal=False, chrome=False)
    window.title(title)
    if not standalone:
        window.transient(host)
    window.resizable(True, True)
    window.minsize(520, 360)
    body = ttk.Frame(window, padding=10)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=title,
              font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
    ttk.Label(body, text='本阶段 SKILL：' + ('、'.join(names) if names else '（还没勾上）'),
              style='Muted.TLabel', wraplength=WRAPLENGTH['sm'], justify='left').pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    progress_label = ttk.Label(body, text='还没开始', style='Muted.TLabel')
    progress_label.pack(anchor='w', pady=(SPACING['sm'], SPACING['none']))
    log = TextArea(body, height=TEXT_ROWS['xl'], wrap='word')
    log.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['none']))
    row = ttk.Frame(body)
    row.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    handle = {'window': window, 'stage': stage, 'run': None, 'log': log, 'names': names,
              'failures': [], 'progress': progress_label}

    def start(only=None):
        try:
            result = runner(desktop, stage, only=only)
        except Exception as exc:
            result = {'results': [], 'text': str(exc), 'failed': []}
        handle['run'] = result
        handle['failures'] = [item.get('skill') for item in failed_rows(result)]
        try:
            log.delete('1.0', 'end')
            log.insert('end', str(result.get('text') or result.get('errors') or ''))
        except tk.TclError:
            pass
        progress_label.configure(text=progress(result))
        retry.configure(state='normal' if handle['failures'] else 'disabled')
        waiting = any(item.get('status') == service_contract.TOOL_PAGE
                      for item in list(result.get('results') or []))
        open_page.configure(state='normal' if waiting else 'disabled')
        return result

    def open_waiting_page():
        rows = list((handle['run'] or {}).get('results') or [])
        row = next((item for item in rows if item.get('status') == service_contract.TOOL_PAGE), None)
        if row is None:
            return False
        try:
            import ui.skill_tools as skill_tools
            return bool(skill_tools.open_page(desktop, row))
        except Exception:
            app_logging.swallowed()
            return False

    def go_back():
        try:
            on_back()
        except Exception:
            app_logging.swallowed()
        window.destroy()

    retry = SecondaryButton(row, text='重试失败项', command=lambda: start(only=handle['failures']))
    retry.pack(side='left')
    retry.configure(state='disabled')
    open_page = SecondaryButton(row, text='打开待办页面', command=open_waiting_page)
    open_page.pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
    open_page.configure(state='disabled')
    SecondaryButton(row, text='返回阶段页面', command=go_back).pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
    SecondaryButton(row, text='关闭', command=window.destroy).pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
    handle['retry'] = lambda: start(only=handle['failures'])
    handle['start'] = start
    handle['back'] = go_back
    handle['open_page'] = open_waiting_page
    start()
    if standalone:
        window.mainloop()
    return handle


def _show_manual_plan(host, title, lines, blocked):
    """L4 承载手动制作精简窗；L3 已在调用前完成业务判定。"""
    choice = []
    window = BaseDialog(host, '', modal=False, chrome=False)
    window.title(title)
    window.transient(host)
    window.resizable(False, False)
    body = ttk.Frame(window, padding=12)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=title, font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
    for line in lines:
        ttk.Label(body, text=line, style='Muted.TLabel').pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    buttons = ttk.Frame(body)
    buttons.pack(fill='x', pady=(SPACING['md'], SPACING['none']))

    def pick(value):
        choice.append(value)
        window.destroy()

    SecondaryButton(buttons, text='修改配置', command=lambda: pick('configure')).pack(side='left')
    run_button = PrimaryButton(buttons, text='直接执行', command=lambda: pick('run'))
    run_button.pack(side='right')
    if blocked:
        run_button.configure(state='disabled')
    SecondaryButton(buttons, text='取消', command=lambda: pick(None)).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
    window.protocol('WM_DELETE_WINDOW', lambda: pick(None))
    window.bind('<Escape>', lambda event: pick(None))
    try:
        window.update_idletasks()
        window.geometry('+%d+%d' % (max(0, host.winfo_rootx() + (host.winfo_width() - window.winfo_width()) // 2),
                                    max(0, host.winfo_rooty() + (host.winfo_height() - window.winfo_height()) // 2)))
        window.grab_set()
        window.lift()
        window.focus_force()
        _schedule_stage_popup_job(window, 60, lambda: _activate_stage_popup(window))
    except tk.TclError:
        pass
    try:
        window.wait_window()
    except tk.TclError:
        pass
    return choice[0] if choice else None


def _show_stage_config(desktop, stage):
    from infra.ui_plugin_registry import module
    return module('skill_panel').show(desktop, stage)


def install_stage_presenters():
    """在 L4 组合根登记阶段 UI 呈现器与工具执行器；依赖方向始终是 UI → 阶段。"""
    from infra.ui_plugin_registry import module
    import ui.skill_tools as skill_tools
    skill_tools.install_executor()
    module('stage_exec').install_ui_presenters(_show_stage_execution, _show_manual_plan, ask_confirmation)
    stage_models.set_config_presenter(_show_stage_config)


install_stage_presenters()
