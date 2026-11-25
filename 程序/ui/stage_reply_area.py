# -*- coding: utf-8 -*-
"""第 2–13 页共用的「过程与回话区」（08 册 §8 / DOC-D8-1，UX-REPLY-AREA）。

单实例 ``StageReplyArea`` 挂在 ``Desktop.input_dock`` 内共享输入框正上方：

- ``sync_stage`` 由 ``desktop_page_nav._sync_shared_input`` 驱动；script 页
  （自带对话区）与非阶段页 ``pack_forget``，12 个制作阶段页按阶段换档；
- 默认收起：单行显示最新一条摘要＋展开/收起钮，把高度让给页面表格与预览；
  展开后正文以卡片浮层盖在内容区上，页面正文不重排；浮层随窗口与切页重定位，
  支持键盘收起/滚动与拖动调整高度；
- 渲染复用 ``ui/ui_part_renderers.py``（思考折叠、工具步骤、可点开产物行），
  排版与第 1 页一致；支持流式按段追加；上滚到顶或「更早」钮按游标分页；
- 记录经 ``domain.stage_reply_log`` 按阶段落 ``<项目>/对话记录/<阶段键>.jsonl``，
  纯记录：绝不进入任何发给模型的上下文。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import infra.app_logging as app_logging
from agent.core import save_text
from contract import pet_bus
from domain import message_parts, stage_reply_log
from ui import ui_part_renderers
from ui_tokens import COLORS, FONTS, SPACING, TEXT_ROWS
from ui_widgets import Card, SecondaryButton, TextArea, Tooltip

EXPAND_RATIO = 0.40
SUMMARY_CHARS = 60

_KIND_LABEL = {
    'user': '您', 'reply': '助手', 'progress': '进度', 'approval': '审批',
    'artifact': '产物', 'error': '错误', 'tool': '工具', 'notice': '提示',
}
_KIND_COLOR = {
    'user': 'text_primary', 'reply': 'text_primary', 'progress': 'text_secondary',
    'approval': 'warning_text', 'artifact': 'text_primary', 'error': 'danger_text',
    'tool': 'text_secondary', 'notice': 'text_secondary',
}


def _record_parts(record):
    """记录 → message_parts 段表：显式 parts 优先，否则按 kind 构造。"""
    parts = record.get('parts')
    if isinstance(parts, (list, tuple)) and parts:
        return [item for item in parts if isinstance(item, dict)]
    kind = str(record.get('kind') or '')
    text = str(record.get('text') or '')
    if kind == 'artifact':
        identifier = str(record.get('path') or record.get('identifier') or '')
        title = str(record.get('title') or text or identifier)
        artifact_kind = str(record.get('artifact_kind') or
                            ('json' if identifier.lower().endswith('.json')
                             else message_parts.ArtifactKind.TEXT.value))
        return [message_parts.part(message_parts.PartType.ARTIFACT, {
            'kind': artifact_kind, 'identifier': identifier, 'title': title,
            'meta': {'path': identifier}})]
    if kind == 'tool':
        return [message_parts.part(message_parts.PartType.TOOL_CALL, {
            'name': str(record.get('name') or text), 'elapsed': record.get('elapsed')},
            state=record.get('state'))]
    return [message_parts.text_part(text)] if text else []


class _ReplyTranscript:
    """回话记录的正文、摘要、附件和流式显示。"""

    def _summary_of(self, record):
        kind = str(record.get('kind') or 'reply')
        label = _KIND_LABEL.get(kind, '记录')
        text = str(record.get('text') or record.get('title') or '')
        if not text:
            parts = record.get('parts') or ()
            text = message_parts.text_of(parts) or str(record.get('path') or '')
        text = ' '.join(text.split())
        if len(text) > SUMMARY_CHARS:
            text = text[:SUMMARY_CHARS] + '…'
        return '%s · %s' % (label, text) if text else label

    def _refresh_summary(self):
        if self.records:
            self.summary.configure(text=self._summary_of(self.records[-1]))
        else:
            self.summary.configure(text='暂无记录')

    def _sync_earlier_button(self):
        try:
            managed = self.earlier_button.winfo_manager() == 'pack'
            if self.has_more and not managed:
                self.earlier_button.pack(side='right', before=self.toggle_button,
                                         padx=(SPACING['none'], SPACING['xs']),
                                         pady=(SPACING['xs'], SPACING['none']))
            elif not self.has_more and managed:
                self.earlier_button.pack_forget()
        except tk.TclError:
            pass

    def _render_body(self, keep_view_top=False):
        box = self.text
        try:
            box.configure(state='normal')
            box.delete('1.0', 'end')
            for index, record in enumerate(self.records):
                self._render_record(index, record)
            box.configure(state='disabled')
            if keep_view_top:
                box.yview_moveto(0)
            else:
                box.see('end')
        except tk.TclError:
            pass

    def _render_record(self, index, record):
        box = self.text
        try:
            if box.cget('state') != 'normal':
                box.configure(state='normal')
            kind = str(record.get('kind') or 'reply')
            name = 'r%d' % index
            stamp = str(record.get('at') or '')[11:16]
            meta = ' '.join(part for part in (_KIND_LABEL.get(kind, '记录'), stamp) if part)
            tag = name + '_meta'
            box.tag_configure(tag, foreground=COLORS['text_muted'], font=FONTS['hint'],
                              spacing1=SPACING['xs'])
            box.insert('end', meta + '\n', tag)
            color = _KIND_COLOR.get(kind, 'text_primary')
            for pidx, part in enumerate(_record_parts(record)):
                pname = '%s_p%d' % (name, pidx)
                if part.get('type') == message_parts.PartType.TEXT.value:
                    body = str((part.get('payload') or {}).get('text') or '')
                    if not body:
                        continue
                    box.tag_configure(pname + '_t', foreground=COLORS[color],
                                      font=ui_part_renderers.PART_FONT, wrap='word')
                    box.insert('end', body + '\n', pname + '_t')
                else:
                    ui_part_renderers.render_parts(box, pname, [part], self)
            box.configure(state='disabled')
        except tk.TclError:
            pass

    def open_artifact(self, artifact):
        """``ui_part_renderers`` 的产物行回调：经宿主的 ``open_target`` 打开文件。"""
        meta = getattr(artifact, 'meta', None)
        target = str((meta or {}).get('path') or '')
        target = target or str(getattr(artifact, 'identifier', '') or '')
        if not target:
            return
        opener = getattr(self.desktop, 'open_target', None)
        if callable(opener):
            try:
                opener(target)
            except Exception:
                app_logging.swallowed()

    # ------------------------------------------------------------------ 流式与滚顶分页

    def begin_stream(self):
        """一次回话流式输出开始：按段追加显示，``end_stream`` 时才落记录。"""
        self._stream = ''

    def push_stream(self, chunk):
        if self._stream is None:
            self._stream = ''
        self._stream += str(chunk or '')
        if self.expanded:
            box = self.text
            try:
                box.configure(state='normal')
                box.tag_configure('reply_stream', foreground=COLORS['text_secondary'],
                                  font=ui_part_renderers.PART_FONT, wrap='word')
                box.insert('end', str(chunk or ''), 'reply_stream')
                box.configure(state='disabled')
                box.see('end')
            except tk.TclError:
                pass

    def end_stream(self):
        text = self._stream
        self._stream = None
        if text:
            self.note('reply', self.stage, text)
            if self.expanded:
                self._render_body()


class StageReplyArea(_ReplyTranscript, ttk.Frame):
    """共享输入框正上方的分阶段过程与回话区（单实例）。"""

    EXPAND_RATIO = EXPAND_RATIO

    def __init__(self, master, desktop):
        super().__init__(master, style='ReplyArea.TFrame')
        self.desktop = desktop
        self.stage = ''
        self.expanded = False
        self.records = []
        self.has_more = False
        self._cursor = 0
        self._loaded_key = None
        self._stream = None
        self._pending_fit = None
        self._font = tkfont.Font(font=FONTS['body'])
        # desktop_shared_send 等薄接线经此回调写过程记录；无回话区的宿主不受影响。
        desktop.reply_note = self.note

        self.head = ttk.Frame(self, style='ReplyArea.TFrame')
        self.head.pack(side='top', fill='x')
        self.caption = ttk.Label(self.head, text='过程与回话', style='ReplyArea.Title.TLabel')
        self.caption.pack(side='left', padx=(SPACING['sm'], SPACING['xs']),
                          pady=(SPACING['xs'], SPACING['none']))
        self.summary = ttk.Label(self.head, text='暂无记录', style='ReplyArea.Summary.TLabel',
                                 anchor='w')
        self.summary.pack(side='left', fill='x', expand=True,
                          padx=(SPACING['none'], SPACING['xs']),
                          pady=(SPACING['xs'], SPACING['none']))
        self.earlier_button = SecondaryButton(
            self.head, text='更早', width=0, style='Tokens.Composer.Model.TButton',
            command=self.load_earlier)
        self.toggle_button = SecondaryButton(
            self.head, text='展开', width=0, style='Tokens.Composer.Model.TButton',
            command=self.toggle)
        self.toggle_button.pack(side='right', padx=(SPACING['none'], SPACING['sm']),
                                pady=(SPACING['xs'], SPACING['none']))
        Tooltip(self.toggle_button, '展开/收起回话；Esc 收起，Ctrl+↑/↓ 调整高度')
        # 展开正文是盖在内容区上的卡片浮层：它必须挂在画布与 input_dock 的共同
        # 祖先下并用 place 定位；留在 input_dock 里 pack 会把正文挤小（本轮契约变更）。
        canvas = getattr(desktop, 'canvas', None)
        host = getattr(canvas, 'master', None) if canvas is not None else None
        if host is None:
            host = getattr(master, 'master', None) or master
        self._overlay_suppressed = True
        self._user_height = None
        self._resize_bottom = None
        self._restore_focus_widget = None
        self._overlay_focus_suspended = False
        self._nav_settle_job = None
        self._hidden_focus_fallback = None
        self.overlay = Card(host, padding=(SPACING['sm'], SPACING['xs']))
        self.resize_edge = ttk.Frame(self.overlay, height=SPACING['sm'],
                                     cursor='sb_v_double_arrow', style='ReplyArea.TFrame')
        self.resize_edge.pack(side='top', fill='x')
        self.resize_edge.pack_propagate(False)
        self.resize_separator = ttk.Separator(self.resize_edge, orient='horizontal')
        self.resize_separator.pack(side='bottom', fill='x')
        self.body = ttk.Frame(self.overlay, style='ReplyArea.TFrame')
        self.body.pack_propagate(False)
        self.text = TextArea(self.body, wrap='word', state='disabled',
                             bg=COLORS['background_card'], fg=COLORS['text_primary'],
                             highlightthickness=0, takefocus=True,
                             selectbackground=COLORS['selection_bg'],
                             selectforeground=COLORS['selection_text'],
                             font=FONTS['body'], cursor='xterm', height=1,
                             padx=SPACING['sm'], pady=SPACING['xs'])
        scroll = ttk.Scrollbar(self.body, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)
        self.text.bind('<MouseWheel>', self._on_wheel, add='+')
        self.text.bind('<KeyPress>', self._on_text_key, add='+')
        self.text.bind('<Escape>', self._on_escape, add='+')
        self.toggle_button.bind('<Escape>', self._on_escape, add='+')
        for widget in (self.resize_edge, self.resize_separator):
            widget.bind('<Button-1>', self._resize_start, add='+')
            widget.bind('<B1-Motion>', self._resize_drag, add='+')
            widget.bind('<ButtonRelease-1>', self._resize_end, add='+')
        self.bind('<Map>', lambda _event: self._fit(), add='+')
        self.winfo_toplevel().bind('<Configure>', self._on_top_configure, add='+')
        host.bind('<Configure>', self._on_top_configure, add='+')
        if canvas is not None:
            canvas.bind('<Configure>', self._on_top_configure, add='+')

    # ------------------------------------------------------------------ 切页与挂载

    def sync_stage(self, stage):
        """``_sync_shared_input`` 切页联动：script/非阶段隐藏，制作阶段页换档加载。"""
        stage = str(stage or '')
        if stage not in pet_bus.STAGES or stage == 'script':
            self.stage = ''
            self._loaded_key = None
            self._overlay_suppressed = True
            if self.expanded:
                # 非阶段页随后连共享输入框也会隐藏；这种情况把焦点放到正文画布，
                # 不留进不可见控件。script 页共享输入框仍显示，按原路恢复。
                # 应用失焦时 focus_get() 可能是 None，但 Tk 仍会把“恢复焦点到回话文本”
                # 记成待生效；因此展开态隐藏一律重挂焦点，而不只依赖此刻的 focus_get。
                self._overlay_focus_suspended = True
                fallback = getattr(self.desktop, 'canvas', None) if not stage else None
                self._hidden_focus_fallback = fallback
                self._restore_focus(fallback=fallback)
                self._schedule_nav_settle(fallback=fallback)
            self._sync_overlay()
            self.pack_forget()
            return
        key = (self._project_key(), stage)
        self.stage = stage
        self._overlay_suppressed = False
        self._hidden_focus_fallback = None
        if key != self._loaded_key:
            self._loaded_key = key
            self._load_tail()
        self._remap()
        if self._overlay_focus_suspended:
            self._overlay_focus_suspended = False
            if self.expanded:
                self._focus_text()

    def _project_key(self):
        root = getattr(self.desktop, 'root', None)
        return '' if root is None else str(root)

    def _remap(self):
        shared = getattr(self.desktop, 'shared_input', None)
        try:
            managed = shared is not None and shared.winfo_manager() == 'pack'
            if managed:
                self.pack(side='top', fill='x', before=shared)
            else:
                self.pack(side='top', fill='x')
        except tk.TclError:
            pass
        self._sync_overlay()
        self._schedule_nav_settle()

    def _schedule_nav_settle(self, fallback=None):
        """等真实路由把共享输入框显隐落定后，再校正回话区与焦点。

        ``desktop_page_nav`` 先 ``reply.sync_stage(stage)``，随后才按 locked/free/home
        路由决定 ``shared_input`` 是否 ``pack_forget``；同一拍内只看当前 pack 状态会
        把回话区误留在首页/锁定页。这里只延后到 idle 复核，不改写路由本身。
        """
        if fallback is not None:
            self._hidden_focus_fallback = fallback
        if self._nav_settle_job is not None:
            return
        try:
            self._nav_settle_job = self.after_idle(self._nav_settled)
        except tk.TclError:
            self._nav_settle_job = None

    def _nav_settled(self):
        self._nav_settle_job = None
        try:
            if not self.winfo_exists():
                return
            if self.stage:
                shared = getattr(self.desktop, 'shared_input', None)
                try:
                    shared_managed = shared is not None and shared.winfo_manager() == 'pack'
                except tk.TclError:
                    shared_managed = False
                if not shared_managed:
                    # locked/free/home 路由在 sync_stage 之后又收起了共享输入框；
                    # 回话区是它的附件，不能单独留在页面上，浮层也不能残留。
                    self._overlay_suppressed = True
                    if self.expanded:
                        self._overlay_focus_suspended = True
                        self._restore_hidden_focus()
                    self._sync_overlay()
                    self.pack_forget()
                    return
                try:
                    if self.master is shared.master and self.winfo_manager() == 'pack':
                        slaves = shared.master.pack_slaves()
                        if (self in slaves and shared in slaves
                                and slaves.index(self) > slaves.index(shared)):
                            self.pack(side='top', fill='x', before=shared)
                except tk.TclError:
                    pass
            if self._overlay_focus_suspended and not (self.expanded and not self._overlay_suppressed):
                self._restore_hidden_focus(self._hidden_focus_fallback)
            self._hidden_focus_fallback = None
        except tk.TclError:
            pass

    def _restore_hidden_focus(self, fallback=None):
        """浮层撤下后把键盘焦点交给仍可见的输入框/画布；不使用 force 抢外应用焦点。"""
        try:
            focused = self.winfo_toplevel().focus_get()
        except tk.TclError:
            focused = None
        if focused is not None and not self._focus_in_overlay():
            try:
                if focused.winfo_exists() and focused.winfo_ismapped():
                    return
            except tk.TclError:
                pass
        shared = getattr(self.desktop, 'shared_input', None)
        candidates = [fallback, getattr(shared, 'input', None),
                      getattr(self.desktop, 'canvas', None)]
        for target in candidates:
            if target is None:
                continue
            try:
                if target.winfo_exists() and target.winfo_ismapped():
                    target.focus_set()
                    return
            except tk.TclError:
                continue

    # ------------------------------------------------------------------ 收起/展开

    def toggle(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        if expanded == self.expanded:
            return
        self.expanded = expanded
        if expanded:
            self._capture_focus()
            self.body.pack(side='top', fill='both', expand=True)
            self._render_body()
        else:
            self.body.pack_forget()
        self.toggle_button.configure(text='收起' if expanded else '展开')
        self._sync_overlay()
        if expanded:
            if self._overlay_suppressed:
                self._overlay_focus_suspended = True
            else:
                self._focus_text()
            self._schedule_fit()      # place 几何结算后再校一次，窗口首帧也能落定
        else:
            self._restore_focus()

    def _focus_in_overlay(self):
        """当前焦点是否落在浮层子树里；切页隐藏时不能把它留在不可见文本里。"""
        try:
            widget = self.winfo_toplevel().focus_get()
        except tk.TclError:
            return False
        while widget is not None:
            if widget is self.overlay:
                return True
            widget = getattr(widget, 'master', None)
        return False

    def _capture_focus(self):
        """展开前记住焦点；收起时还给输入框/原控件，浮层键盘操作不打断输入流。"""
        try:
            focused = self.winfo_toplevel().focus_get()
        except tk.TclError:
            focused = None
        self._restore_focus_widget = None if focused is self.text else focused

    def _focus_text(self):
        try:
            self.text.focus_set()
        except tk.TclError:
            pass

    def _fallback_focus_target(self):
        shared = getattr(self.desktop, 'shared_input', None)
        for target in (getattr(shared, 'input', None), self.toggle_button):
            if target is None:
                continue
            try:
                if target.winfo_exists() and target.winfo_ismapped():
                    return target
            except tk.TclError:
                continue
        return None

    def _restore_focus(self, fallback=None):
        target = self._restore_focus_widget
        self._restore_focus_widget = None
        try:
            valid = (target is not None and target not in (self.text, self.toggle_button)
                     and target.winfo_exists() and target.winfo_ismapped())
        except tk.TclError:
            valid = False
        if not valid:
            target = fallback if fallback is not None else self._fallback_focus_target()
        if target is None:
            return
        try:
            target.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 浮层几何与调整大小

    def _overlay_metrics(self, preferred_height=None):
        """画布内下边锚定的浮层几何；坐标换算到 ``overlay`` 的父容器。"""
        canvas = getattr(self.desktop, 'canvas', None)
        if canvas is None:
            return None
        try:
            host = self.overlay.master
            canvas_w, canvas_h = canvas.winfo_width(), canvas.winfo_height()
            if canvas_w <= 1 or canvas_h <= 1:
                return None
            margin = SPACING['sm']
            width = max(1, canvas_w - margin * 2)
            available = max(1, canvas_h - margin * 2)
            line_h = max(1, int(self._font.metrics('linespace') or 1))
            minimum = line_h * TEXT_ROWS['xs'] + SPACING['sm'] * 2
            minimum = min(minimum, available)
            if preferred_height is None:
                preferred_height = self._user_height
            if preferred_height is None:
                preferred_height = int(canvas_h * self.EXPAND_RATIO)
            height = max(minimum, min(int(preferred_height), available))
            x = canvas.winfo_rootx() - host.winfo_rootx() + margin
            bottom = canvas.winfo_rooty() - host.winfo_rooty() + canvas_h - margin
            return x, bottom - height, width, height
        except (tk.TclError, TypeError, ValueError):
            return None

    def _place_overlay(self):
        metrics = self._overlay_metrics()
        if metrics is None:
            self.overlay.place_forget()
            return False
        x, y, width, height = metrics
        self.overlay.place(x=x, y=y, width=width, height=height)
        self.overlay.lift()
        return True

    def _sync_overlay(self):
        if self.expanded and not self._overlay_suppressed:
            self._place_overlay()
        else:
            self.overlay.place_forget()

    def resize_to(self, height):
        """把浮层高度调到 ``height``（像素）；窗口变窄/变矮时仍按可用区钳制。"""
        try:
            self._user_height = max(1, int(height))
        except (TypeError, ValueError):
            return
        self._fit()

    def _resize_start(self, event):
        metrics = self._overlay_metrics()
        if metrics is not None:
            self._resize_bottom = metrics[1] + metrics[3]
        return 'break'

    def _resize_drag(self, event):
        if self._resize_bottom is None:
            return 'break'
        try:
            pointer = event.y_root - self.overlay.master.winfo_rooty()
        except tk.TclError:
            return 'break'
        self.resize_to(self._resize_bottom - pointer)
        return 'break'

    def _resize_end(self, _event):
        self._resize_bottom = None
        return 'break'

    def _fit(self):
        """展开态只重排浮层：正文画布不参与 pack，高度变化不再推动页面内容。"""
        if not self.expanded or self._overlay_suppressed:
            return
        self._place_overlay()

    def _schedule_fit(self):
        if self._pending_fit is not None:
            return
        try:
            self._pending_fit = self.after_idle(self._fit_done)
        except tk.TclError:
            self._pending_fit = None

    def _on_top_configure(self, _event=None):
        if not self.expanded:
            return
        self._schedule_fit()

    def _fit_done(self):
        self._pending_fit = None
        try:
            if self.winfo_exists():
                self._fit()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 键盘访问

    def _on_escape(self, _event=None):
        """浮层打开时 Esc 只收浮层；收起态放行给输入框/页面自己的 Esc 语义。"""
        if not self.expanded:
            return None
        self.set_expanded(False)
        return 'break'

    def _on_text_key(self, event):
        """只读回话区的键盘滚动；Ctrl+Up/Down 以行为步进调整浮层高度。"""
        key = getattr(event, 'keysym', '')
        state = int(getattr(event, 'state', 0) or 0)
        ctrl = bool(state & 0x0004)
        if ctrl and key in ('Up', 'Down'):
            line = max(1, int(self._font.metrics('linespace') or 1))
            current = self.overlay.winfo_height()
            if current <= 1:
                metrics = self._overlay_metrics()
                current = metrics[3] if metrics is not None else line * TEXT_ROWS['xs']
            self.resize_to(current + (line if key == 'Up' else -line))
            return 'break'
        if state & 0x0001:      # Shift+方向键保留给文本选择
            return None
        steps = {'Up': (-1, 'units'), 'Down': (1, 'units'),
                 'Prior': (-1, 'pages'), 'Next': (1, 'pages')}
        try:
            if key in steps:
                self.text.yview_scroll(*steps[key])
            elif key in ('Home', 'End'):
                self.text.yview_moveto(0 if key == 'Home' else 1)
            else:
                return None
        except tk.TclError:
            return 'break'
        return 'break'

    # ------------------------------------------------------------------ 记录与加载

    def note(self, kind, stage, text='', *, expand=False, **fields):
        """薄接线的记录入口：落盘＋刷新摘要/正文；任何失败静默返回 ``None``。"""
        try:
            root = getattr(self.desktop, 'root', None)
            if root is None:
                return None
            record = {'kind': str(kind or ''), 'text': str(text or '')}
            record.update(fields)
            if record['kind'] == 'artifact' and not (
                    record.get('path') or record.get('identifier')):
                record['kind'] = 'reply'      # 无路径的产物记录降级为普通回话行
            stored = stage_reply_log.append_record(root, str(stage or ''), record,
                                                   publish=save_text)
            if stored is None:
                return None
            if str(stage or '') == self.stage:
                self.records.append(stored)
                self._refresh_summary()
                if expand and self.stage and not self.expanded:
                    self.set_expanded(True)
                elif self.expanded:
                    self._render_record(len(self.records) - 1, stored)
                if self.expanded:
                    try:
                        self.text.see('end')
                    except tk.TclError:
                        pass
            return stored
        except Exception:
            app_logging.swallowed()
            return None

    def _load_tail(self):
        root = getattr(self.desktop, 'root', None)
        self.records, self._cursor = [], 0
        if root is not None:
            try:
                self.records, self._cursor = stage_reply_log.read_tail(
                    root, self.stage, stage_reply_log.TAIL_LIMIT)
            except Exception:
                app_logging.swallowed()
                self.records, self._cursor = [], 0
        self.has_more = self._cursor > 0
        self._refresh_summary()
        self._sync_earlier_button()
        if self.expanded:
            self._render_body()

    def load_earlier(self):
        """「更早」钮/滚到顶：按字节游标加载前一页，插到现有记录之前。"""
        root = getattr(self.desktop, 'root', None)
        if root is None or not self._cursor:
            self.has_more = False
            self._sync_earlier_button()
            return
        try:
            earlier, self._cursor = stage_reply_log.read_before(
                root, self.stage, self._cursor, stage_reply_log.TAIL_LIMIT)
        except Exception:
            app_logging.swallowed()
            return
        if earlier:
            self.records = list(earlier) + self.records
            if self.expanded:
                self._render_body(keep_view_top=True)
        self.has_more = self._cursor > 0
        self._sync_earlier_button()

    # ------------------------------------------------------------------ 渲染

    def _on_wheel(self, event):
        """向上滚到顶时自动加载更早一页（同「更早」钮）。"""
        try:
            if getattr(event, 'delta', 0) > 0 and self.has_more and \
                    self.text.yview()[0] <= 0.0:
                self.load_earlier()
        except tk.TclError:
            pass

    def destroy(self):
        """浮层挂在共同祖先下，不随内联头自动销毁；这里成对回收。"""
        try:
            if self._pending_fit is not None:
                try:
                    self.after_cancel(self._pending_fit)
                except tk.TclError:
                    pass
                self._pending_fit = None
            if self._nav_settle_job is not None:
                try:
                    self.after_cancel(self._nav_settle_job)
                except tk.TclError:
                    pass
                self._nav_settle_job = None
            overlay = getattr(self, 'overlay', None)
            if overlay is not None and overlay.winfo_exists():
                overlay.destroy()
        finally:
            super().destroy()
