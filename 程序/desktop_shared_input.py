"""共享底部输入框（R2893，任务书轮 3）：13 个阶段页共用同一实例。

布局（任务书 §4＋语音输入离线化轮 3）：``[skill 图标][附件图标][麦克风] | [TextArea 输入框] | [模型图标][发送]``；
视觉 token 走 ``ui_tokens``，快捷键登记走宿主 ``ShortcutRegistry``（``/`` 补全与
``Esc`` 关闭）。命令解析在无 Tk 的 ``skill_command``；发送门禁复用
``stage_parallel`` 上游判定与 ``stage_completion_service.completion_evidence``。

宿主契约（轮 4 由 Desktop／页面接线）：``desktop.root`` 为项目根、
``desktop.status`` 为状态栏 StringVar；``options`` 携带 ``on_send(text,
parsed)``（返回真值表示已受理，假值＝本组件恢复可用态）与 ``on_skill_config``／
``on_attachment``／``on_model`` 三个入口回调、``status``、``skills``、``engines``，
缺省给出可用兜底。
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import app_logging
import skill_command
import ui_plugin_registry
from contract import pet_bus
from ui_shortcuts import ShortcutRegistry
from ui_tokens import FONTS, ICON_MICROPHONE, SPACING, TEXT_ROWS
from ui_widgets import SecondaryButton, TextArea, PrimaryButton, Tooltip

SHORTCUT_SCOPE = 'shared_input'


def project_root(desktop):
    root = getattr(desktop, 'root', None) if desktop is not None else None
    return Path(root) if root else None


def _status_of(desktop, status=None):
    return status if status is not None else getattr(desktop, 'status', None)


def _say(status, text):
    if status is not None:
        try:
            status.set(str(text))
        except Exception:
            app_logging.swallowed()


def upstream_send_error(project, stage):
    """发送门禁（任务书轮 3）：当前阶段上游空白 → 拒绝并提示；放行返回 ``''``。

    有 ``stage_parallel`` 门禁的阶段走 ``evaluate``（UPSTREAM_BLANK／BLOCKED 都拦）；
    没有门禁行的非 script 阶段看紧邻上游阶段的 ``completion_evidence``，上游被显式
    跳过（skipped）时豁免；``script`` 与无项目一律放行（简报门禁由宿主发送路径负责）。
    """
    stage = str(stage or '')
    if not stage or stage == 'script' or stage not in pet_bus.STAGES:
        return ''
    try:
        import stage_parallel
        row = stage_parallel.gate_for(stage)
    except Exception:
        return ''
    if row is not None:
        try:
            result = stage_parallel.evaluate(project, stage)
        except Exception:
            return ''
        if result.get('verdict') == stage_parallel.UPSTREAM_BLANK:
            return '请先完成/确认「%s」阶段' % stage_parallel.label(result.get('from'))
        if not result.get('ok'):
            return stage_parallel.blocked_text(result) or '上游阶段未完成，请先处理'
        return ''
    index = pet_bus.STAGES.index(stage)
    if index <= 0:
        return ''
    upstream = pet_bus.STAGES[index - 1]
    try:
        import stage_parallel as _sp
        if _sp.stage_state(project, upstream) in _sp.EXEMPT_STATES:
            return ''
    except Exception:
        app_logging.swallowed()
    try:
        from stage_completion_service import completion_evidence
        ok, detail = completion_evidence(project, upstream)
    except Exception:
        return ''
    if ok:
        return ''
    return '请先完成/确认「%s」阶段（%s）' % (pet_bus.stage_name(upstream), detail or '上游成果未完成')


class SharedStageInput(ttk.Frame):
    """底部固定共享输入框：单实例跨页复用，``stage`` 只换补全与门禁上下文。"""

    def __init__(self, master, *, desktop=None, stage='script', shortcuts=None, options=None):
        super().__init__(master)
        options = dict(options or {})
        self.desktop = desktop
        self.stage = str(stage or 'script')
        self.status = options.get('status') or _status_of(desktop)
        self.shortcuts = shortcuts if shortcuts is not None else ShortcutRegistry()
        self.on_send = options.get('on_send')
        self.on_skill_config = options.get('on_skill_config')
        self.on_attachment = options.get('on_attachment')
        self.on_model = options.get('on_model')
        self._skills = list(options.get('skills') or ())
        self._engines = options.get('engines')
        self.in_flight = False
        self.request_model = None
        self._completion_open = False
        self.mic_button = None
        self.voice_input = None
        self._build()

    # ── 构建 ────────────────────────────────────────────────────────────
    def _build(self):
        left = ttk.Frame(self)
        left.pack(side='left', fill='y', padx=(SPACING['sm'], SPACING['xs']))
        self.skill_button = SecondaryButton(left, text='技能', width=0,
                                            command=self.open_skill_config)
        self.skill_button.pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        self.attachment_button = SecondaryButton(left, text='附件', width=0,
                                                 command=self.open_attachments)
        self.attachment_button.pack(side='left')
        # 语音输入离线化任务书轮 3：麦克风入口只此一处（非 Windows 不显示，REQ-S01-71
        # 原口径）；听写会话绑定本栏共享 Text，13 页切页只换 set_stage 上下文不重建。
        if os.name == 'nt':
            self.mic_button = SecondaryButton(left, text=ICON_MICROPHONE, width=0,
                                              command=self._toggle_voice)
            self.mic_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
            Tooltip(self.mic_button, '语音输入：点一下开始录音，再点一下结束并转成文字')

        self.input = TextArea(self, height=TEXT_ROWS['sm'], wrap='word')
        self.input.pack(side='left', fill='both', expand=True,
                        padx=(SPACING['xs'], SPACING['sm']))

        right = ttk.Frame(self)
        right.pack(side='right', fill='y', padx=(SPACING['xs'], SPACING['sm']))
        self.model_button = SecondaryButton(right, text='模型', width=0,
                                            command=self.open_model_picker)
        self.model_button.pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        self.send_button = PrimaryButton(right, text='发送', width=0,
                                         command=self.send)
        self.send_button.pack(side='left')

        self._completion = ttk.Frame(self)
        self._list = tk.Listbox(self._completion, exportselection=False,
                                height=TEXT_ROWS['md'], font=FONTS['hint'])
        self._list.pack(fill='x')
        self._list.bind('<<ListboxSelect>>', self._choose_completion)
        self._list.bind('<Escape>', lambda _e: self.close_completion())
        self.input.bind('<KeyRelease>', self._on_key_release, add='+')
        self.input.bind('<Return>', self._on_return, add='+')
        # ``/`` 触发与 ``Esc`` 关闭都走宿主 ShortcutRegistry 登记（任务书轮 3 验收）。
        self.shortcuts.bind(self.input, ('/',), self._on_slash_key,
                            scope=SHORTCUT_SCOPE, name='slash_completion')
        self.shortcuts.bind(self.input, ('<Escape>',),
                            lambda _e: self.close_completion(),
                            scope=SHORTCUT_SCOPE, name='dismiss_completion')
        self.shortcuts.bind(self.input, ('<KP_Enter>',), self._on_return,
                            scope=SHORTCUT_SCOPE, name='send_on_enter')
        if self.mic_button is not None:
            self.voice_input = self._make_voice_input()
        self._sync_model_label()

    def _make_voice_input(self):
        """共享栏唯一一份听写会话：跟随 ``self.input``（跨页同一 Text 实例）。"""
        import desktop_voice_input
        return desktop_voice_input.VoiceInput(
            self.input, self.mic_button, status=self.status,
            listening_style='Tokens.Primary.TButton', idle_style='Tokens.Secondary.TButton',
            project=self.project)

    def _toggle_voice(self):
        voice = self.voice_input
        if voice is None:
            return
        try:
            voice.toggle()
        except Exception as exc:
            _say(self.status, '语音输入未能启动（%s）。' % exc)

    # ── 上下文 ──────────────────────────────────────────────────────────
    @property
    def project(self):
        return project_root(self.desktop)

    def set_stage(self, stage):
        """切页只换上下文：不重建实例，只刷新补全候选、模型标签与发送键默认态。"""
        self.stage = str(stage or 'script')
        self._reset_send_button()
        self._sync_model_label()
        if self._completion_open:
            self._refresh_completion()

    def _reset_send_button(self):
        """页面级对发送键的改写（剧本页运行中＝终止图标）随切页复位，回到默认「发送」。"""
        try:
            self.send_button.configure(text='发送', command=self.send)
            self.send_button.state(['!disabled'])
        except tk.TclError:
            app_logging.swallowed()

    def skill_items(self):
        if self._skills:
            return list(self._skills)
        try:
            import skill_registry
            return list(skill_registry.default_registry().getAll())
        except Exception:
            return []

    def engine_names(self):
        if self._engines is not None:
            return tuple(self._engines)
        try:
            return skill_command.sub_engine_names()
        except Exception:
            return ()

    # ── 入口回调 ────────────────────────────────────────────────────────
    def open_skill_config(self):
        if callable(self.on_skill_config):
            return self.on_skill_config()
        try:
            return ui_plugin_registry.module('skill_panel').show(self.desktop, self.stage)
        except Exception as exc:
            _say(self.status, '阶段配置打开失败：%s' % exc)
            return None

    def open_attachments(self):
        if callable(self.on_attachment):
            return self.on_attachment()
        _say(self.status, '附件入口由当前页面提供')
        return None

    def open_model_picker(self):
        if callable(self.on_model):
            return self.on_model()
        _say(self.status, '模型选择由当前页面提供')
        return None

    def _sync_model_label(self):
        """模型按钮显示当前请求模型名（只读标签；选择逻辑在宿主回调里）。"""
        label = ''
        try:
            import writing_api
            label = str(writing_api.capture_request_model(self.project)['label'] or '')
        except Exception:
            label = ''
        self.model_button.configure(text=('模型·' + label) if label else '模型')

    # ── ``/`` 补全 ───────────────────────────────────────────────────────
    def _on_slash_key(self, _event):
        """``/`` 键按下时补全：等默认插入完成后再取文本刷新候选。"""
        try:
            self.after_idle(self._refresh_completion)
        except Exception:
            app_logging.swallowed()
        return None

    def _on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab', 'ISO_Left_Tab'):
            return
        token = skill_command.command_token(self.text())
        if token:
            self._refresh_completion()
        elif self._completion_open:
            self.close_completion()

    def _on_return(self, event):
        """Enter 发送（Shift+Enter 换行）；补全候选优先——有选中先补全不发送。

        返回 ``'break'`` 拦截同组件上后绑的页面级 Enter 绑定（如剧本页 send_on_enter），
        保证 13 页共用同一条发送路径；Shift+Enter 返回 None 放行默认换行。
        """
        if getattr(event, 'state', 0) & 0x1:
            return None
        if self._completion_open and self._list.size():
            selection = self._list.curselection()
            if selection:
                self._apply_completion(self._list.get(selection[0]))
                return 'break'
        self.send()
        return 'break'

    def _refresh_completion(self):
        options = skill_command.completions(self.text(), stage=self.stage,
                                            skills=self.skill_items(),
                                            engines=self.engine_names())
        self._list.delete(0, 'end')
        for item in options[:12]:
            self._list.insert('end', item)
        if self._list.size():
            self._completion.pack(fill='x', padx=SPACING['sm'],
                                  pady=(SPACING['none'], SPACING['xs']))
            self._completion_open = True
        else:
            self.close_completion()

    def _choose_completion(self, _event=None):
        selection = self._list.curselection()
        if selection:
            self._apply_completion(self._list.get(selection[0]))

    def _apply_completion(self, option):
        name = str(option).lstrip('/')
        current = self.text()
        body = current[1:].lstrip() if current.startswith('/') else current
        rest = body.split(' ', 1)[1] if ' ' in body else ''
        self.input.delete('1.0', 'end')
        self.input.insert('1.0', '/' + name + (' ' + rest if rest else ''))
        self.close_completion()

    def close_completion(self):
        """关闭补全层；只在确实关掉了候选时 ``'break'``，否则放行 Esc 的其他宿主绑定
        （如剧本页输入框的「 Esc 中断任务」）。"""
        if self._completion_open:
            self._completion.pack_forget()
            self._completion_open = False
            return 'break'
        return None

    # ── 发送 ────────────────────────────────────────────────────────────
    def text(self):
        try:
            return str(self.input.get('1.0', 'end-1c') or '').strip()
        except Exception:
            return ''

    def clear(self):
        try:
            self.input.delete('1.0', 'end')
        except Exception:
            app_logging.swallowed()

    def set_text(self, value):
        self.clear()
        self.input.insert('1.0', str(value or ''))

    def request_snapshot(self):
        """请求在途的模型快照：发送瞬间捕获，之后切换模型只影响下一次请求。"""
        try:
            import writing_api
            return writing_api.capture_request(self.project)
        except Exception:
            return None

    def send(self):
        """发送门禁 → 命令解析 → 快照捕获 → 宿主 ``on_send``；返回是否受理。"""
        value = self.text()
        if not value:
            return False
        error = upstream_send_error(self.project, self.stage)
        if error:
            _say(self.status, error)
            return False
        parsed = skill_command.parse_command(
            value, stage=self.stage, skills=self.skill_items(),
            engines=self.engine_names())
        if self.request_model is None:
            self.request_model = self.request_snapshot()
        self.in_flight = True
        try:
            if callable(self.on_send):
                accepted = self.on_send(value, parsed)
            else:
                accepted = True
        except Exception:
            self.in_flight = False
            raise
        if accepted is False:
            self.in_flight = False
            return False
        self.clear()
        return True

    def end_request(self):
        """宿主请求结束后调用：释放在途标记（模型快照保留供下次比对）。"""
        self.in_flight = False
        self.request_model = None
        self._sync_model_label()
