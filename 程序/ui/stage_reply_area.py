# -*- coding: utf-8 -*-
"""第 2–13 页共用的「过程与回话区」（08 册 §8 / DOC-D8-1，UX-REPLY-AREA）。

单实例 ``StageReplyArea`` 挂在 ``Desktop.input_dock`` 内共享输入框正上方：

- ``sync_stage`` 由 ``desktop_page_nav._sync_shared_input`` 驱动；script 页
  （自带对话区）与非阶段页 ``pack_forget``，12 个制作阶段页按阶段换档；
- 默认收起：单行显示最新一条摘要＋展开/收起钮，把高度让给页面表格与预览；
  展开体高 ≤ 可用内容区 40%，窗口矮时钳制不把输入框挤出视口；
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
from ui_tokens import COLORS, FONTS, SPACING
from ui_widgets import SecondaryButton, TextArea

EXPAND_RATIO = 0.40
SUMMARY_CHARS = 60

_KIND_LABEL = {
    'user': '你', 'reply': '助手', 'progress': '进度', 'approval': '审批',
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


class StageReplyArea(ttk.Frame):
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
        self.body = ttk.Frame(self, style='ReplyArea.TFrame')
        self.body.pack_propagate(False)
        self.text = TextArea(self.body, wrap='word', state='disabled',
                             bg=COLORS['background_card'], fg=COLORS['text_primary'],
                             highlightthickness=0,
                             selectbackground=COLORS['selection_bg'],
                             selectforeground=COLORS['selection_text'],
                             font=FONTS['body'], cursor='xterm', height=1,
                             padx=SPACING['sm'], pady=SPACING['xs'])
        scroll = ttk.Scrollbar(self.body, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)
        self.text.bind('<MouseWheel>', self._on_wheel, add='+')
        self.bind('<Map>', lambda _event: self._fit(), add='+')
        self.winfo_toplevel().bind('<Configure>', self._on_top_configure, add='+')

    # ------------------------------------------------------------------ 切页与挂载

    def sync_stage(self, stage):
        """``_sync_shared_input`` 切页联动：script/非阶段隐藏，制作阶段页换档加载。"""
        stage = str(stage or '')
        if stage not in pet_bus.STAGES or stage == 'script':
            self.stage = ''
            self._loaded_key = None
            self.pack_forget()
            return
        key = (self._project_key(), stage)
        self.stage = stage
        if key != self._loaded_key:
            self._loaded_key = key
            self._load_tail()
        self._remap()

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

    # ------------------------------------------------------------------ 收起/展开

    def toggle(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        if expanded == self.expanded:
            return
        self.expanded = expanded
        if expanded:
            self.body.pack(side='top', fill='x')
            self._render_body()
            self._fit()
            self._schedule_fit()      # pack 几何结算后再校一次，防止首轮估算偏大
        else:
            self.body.pack_forget()
        self.toggle_button.configure(text='收起' if expanded else '展开')

    def _fit(self):
        """展开态体高：min(可用内容区 40%, 窗口剩余, dock 内剩余)。

        最后一项是硬约束：画布在 ``pack`` 序列里排前、先取走请求高，dock 只分到
        ``窗口高 − 画布请求高``；体高超过 ``dock 分配 − 头部行 − 共享输入框`` 时
        pack 会把输入框整体挤出 dock 视口（``winfo_ismapped`` 变 0）。
        """
        if not self.expanded:
            return
        try:
            top_h = self.winfo_toplevel().winfo_height()
            head_h = self.head.winfo_reqheight()
            shared = getattr(self.desktop, 'shared_input', None)
            shared_h = shared.winfo_reqheight() if shared is not None else 0
            status = getattr(self.desktop, 'status_bar', None)
            status_h = status.winfo_reqheight() if status is not None else 0
            canvas = getattr(self.desktop, 'canvas', None)
            canvas_h = canvas.winfo_height() if canvas is not None else 0
            canvas_req = canvas.winfo_reqheight() if canvas is not None else 0
            body_h = self.body.winfo_height() if self.body.winfo_manager() else 0
            dock = self.master
            dock_h = dock.winfo_height() if dock.winfo_ismapped() else 0
        except tk.TclError:
            return
        if canvas_req <= 0:
            canvas_req = canvas_h
        avail = canvas_h + body_h if canvas_h + body_h > 1 else top_h
        cap = int(avail * self.EXPAND_RATIO)
        room = top_h - (head_h + shared_h + status_h + SPACING['xl'])
        # dock 内还能剩多少给 body：估算（窗口高−画布请求高）与实测分配高取小。
        inner = min(top_h - canvas_req, dock_h if dock_h > 1 else top_h) - head_h - shared_h
        self.body.configure(height=max(0, min(cap, room, inner)))

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

    # ------------------------------------------------------------------ 记录与加载

    def note(self, kind, stage, text='', **fields):
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
                if self.expanded:
                    self._render_record(len(self.records) - 1, stored)
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

    def _on_wheel(self, event):
        """向上滚到顶时自动加载更早一页（同「更早」钮）。"""
        try:
            if getattr(event, 'delta', 0) > 0 and self.has_more and \
                    self.text.yview()[0] <= 0.0:
                self.load_earlier()
        except tk.TclError:
            pass
