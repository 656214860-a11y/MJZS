"""剧本结构页编辑器会话：右键菜单「编辑／退出编辑」、防抖自动保存、撤销快捷键。

R2724 从 ``desktop_script_pages`` 拆出（单模块行数棘轮）：会话只依赖注入的
``page``／``box`` 鸭子类型与 ui_tokens，不反向 import 页面模块；
``desktop_script_pages`` 再导入 ``_install_script_edit_controls``／``_reset_preview_text``。
REQ-S02-37 起页面上不再有「编辑／删除」按钮：编辑入口移到文本框右键菜单首项
（REQ-S02-39 的先行落点），删除收进右侧文件面板的右键菜单。
"""
import logging
import time
import tkinter as tk
from pathlib import Path

import orchestrator.edit_habits as edit_habits
import ui.script_view_style as script_view_style
from ui_tokens import SCRIPT_EDIT_SAVE_DEBOUNCE_MS

LOGGER = logging.getLogger('desktop_script_edit_session')


def _reset_preview_text(preview, text, kind):
    """清空预览并整段刷入文本、按需加样式；返回后留在 normal 态由调用方决定下一步。"""
    preview.configure(state='normal')
    preview.delete('1.0', 'end')
    preview.insert('1.0', text)
    if script_view_style.should_style(text):
        script_view_style.apply_tags(preview, text, kind)
    preview.edit_reset()
    # apply_tags 会把全部 tag 字体重置回基础值；缩放状态经 _reading_sync 回调重放。
    sync = getattr(preview, '_reading_sync', None)
    if callable(sync):
        sync()


def _record_natural_edit(page, before, after, name):
    """REQ-S01-58：记下这次修改供「修改习惯」归纳；记录失败不影响已完成的保存。"""
    if not getattr(page, 'root', None):
        return
    try:
        edit_habits.record_edit(page.root, 'script', before, after, name)
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning('修改记录未保存：%s', exc)


class _ScriptEditSession:
    """剧本编辑器的编辑会话：右键菜单「编辑／退出编辑」、防抖自动保存、撤销快捷键。

    「编辑／退出编辑／后退一步／前进一步／复原全文／立即保存」都在文本框右键菜单
    （REQ-S02-37/39）。落盘统一走 ``controller.save``（内容未变化不写盘），实际写盘
    由 ``save_text`` 回调分流 natural／structured 并做空内容校验。页面重建时整个会话
    随之重建，``ShortcutRegistry`` 按 scope/name 幂等替换旧绑定。
    """

    _MENU_LABELS = ('后退一步', '前进一步', '复原全文', '立即保存')

    def __init__(self, page, box):
        # box 是 _ContentBox：预览框、已读原文、当前文档与内容框配置都从它取。
        from domain.script_structure_edit_controller import ScriptStructureEditController
        self.page = page
        self.box = box
        self.preview = box.preview
        self.loaded = box.loaded
        self.active = box.active
        self.title = box.title
        self.kind = box.kind
        self.editable = box.editable
        self.editing = False
        self.suppress = False
        self.pending = None
        self.last_menu = None
        self.controller = ScriptStructureEditController(save=self.save_text)
        box.edit_session = self
        self.preview.bind('<<Modified>>', self.on_modified, add=True)
        self.preview.bind('<Button-3>', self.on_context_menu, add=True)
        self.preview.bind('<Destroy>', self._on_destroy, add=True)
        self._bind_undo_shortcuts()

    # ── 编辑生命周期 ────────────────────────────────────────────────────
    def toggle_edit(self):
        if self.editing:
            self.exit_edit()
        else:
            self.begin_edit()

    def begin_edit(self):
        if not self.editable or self.active['path'] is None:
            raise ValueError('当前没有可修改的剧本文档。')
        if self.loaded['raw'] == getattr(self.box.owner, 'LOADING_PREVIEW', None):
            raise ValueError('剧本仍在读取，请稍候再编辑。')
        self.cancel_pending()
        _reset_preview_text(self.preview, self.loaded['raw'], self.kind)
        self.preview.edit_modified(False)
        self.controller.begin_edit(self.loaded['raw'])
        self.editing = True
        self.preview.focus_set()

    def exit_edit(self):
        """退出编辑：先把未落盘内容写回（自动保存契约），落盘失败则留在编辑态。"""
        if not self.editing:
            return
        self.cancel_pending()
        self.flush_save(self.preview.get('1.0', 'end-1c'))
        self.editing = False
        self.suppress = True
        try:
            self.box.set_preview(self.loaded['raw'])
        finally:
            self.suppress = False
        self.page.status.set('已退出' + self.title + '编辑。')

    # ── 落盘 ────────────────────────────────────────────────────────────
    def save_text(self, value):
        """自动保存／立即保存／复原全文共用的落盘口：原文直写，不做 strip 隐藏变换。"""
        value = str(value or '')
        if not value:
            raise ValueError('剧本内容不能为空。')
        destination = Path(self.active['path'])
        before = self.loaded['raw']
        if self.kind == 'natural':
            from script_contract import save_natural_script
            save_natural_script(destination, value)
        else:
            from agent.core import save_text as write_text
            write_text(destination, value + '\n')
        self.loaded['raw'] = value
        if self.kind == 'natural':
            _record_natural_edit(self.page, before, value, destination.name)

    def flush_save(self, text, *, auto=False):
        """把文本框当前内容落盘；与上次落盘相同则不写盘。返回是否实际写盘。"""
        wrote = self.controller.save(text)
        if wrote:
            hint = '；如要据此制作结构剧本，请重新采用。' if self.kind == 'natural' else ''
            stamp = time.strftime('%H:%M:%S')
            label = '已自动保存' if auto else '已保存'
            self.page.status.set('%s%s（%s）：%s%s' % (label, self.title, stamp,
                                                   Path(self.active['path']).name, hint))
        return wrote

    # ── 防抖自动保存 ────────────────────────────────────────────────────
    def on_modified(self, _event=None):
        if self.suppress or not self.editing or str(self.preview.cget('state')) != 'normal':
            return
        if not self.preview.edit_modified():
            return
        self.preview.edit_modified(False)
        self.schedule_autosave()

    def schedule_autosave(self):
        self.cancel_pending()
        try:
            self.pending = self.preview.after(SCRIPT_EDIT_SAVE_DEBOUNCE_MS, self.autosave)
        except tk.TclError:
            self.pending = None

    def _on_destroy(self, _event=None):
        """预览销毁（页面重建／窗口关闭）时撤掉待触发的防抖回调。"""
        self.cancel_pending()
        self.editing = False

    def cancel_pending(self):
        if self.pending is not None:
            try:
                self.preview.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None

    def autosave(self):
        self.pending = None
        try:
            if (not self.editing or not self.preview.winfo_exists()
                    or str(self.preview.cget('state')) != 'normal'):
                return
            self.flush_save(self.preview.get('1.0', 'end-1c'), auto=True)
        except tk.TclError:
            return  # 控件或窗口已销毁：丢弃这次回调
        except Exception as exc:
            try:
                self.page.status.set('自动保存失败：' + str(exc))
            except tk.TclError:
                pass

    # ── 右键菜单动作（经 page.safe 调用）─────────────────────────────────
    def undo_step(self):
        """「后退一步」：Tk 原生撤销一步，随后照常防抖自动保存。"""
        if not self.editing or str(self.preview.cget('state')) != 'normal':
            return
        try:
            self.preview.edit_undo()
        except tk.TclError:
            return
        self.schedule_autosave()

    def redo_step(self):
        """「前进一步」：Tk 原生重做一步，随后照常防抖自动保存。"""
        if not self.editing or str(self.preview.cget('state')) != 'normal':
            return
        try:
            self.preview.edit_redo()
        except tk.TclError:
            return
        self.schedule_autosave()

    def restore_full(self):
        """「复原全文」：确认后把进入编辑时的原文写回文本框并立即落盘。"""
        if not self.editing or str(self.preview.cget('state')) != 'normal':
            return
        initial = self.controller.initial
        if initial is None or self.preview.get('1.0', 'end-1c') == initial:
            return
        if not self.page.script_page_services.confirm(
                self.page.win, '复原全文',
                '将放弃本次编辑的全部修改并恢复到进入编辑时的内容，确定吗？', dangerous=True):
            return
        self.suppress = True
        try:
            _reset_preview_text(self.preview, initial, self.kind)
            self.preview.edit_modified(False)
        finally:
            self.suppress = False
        self.flush_save(initial)
        self.page.status.set('已复原' + self.title + '全文：' + Path(self.active['path']).name)

    def save_now(self):
        """「立即保存」：取消待触发的防抖，直接把文本框当前内容落盘（幂等）。"""
        if not self.editing or self.active['path'] is None:
            raise ValueError('请先经右键菜单进入“编辑”，修改后再保存。')
        self.cancel_pending()
        if not self.flush_save(self.preview.get('1.0', 'end-1c')):
            self.page.status.set('内容没有变化，无需保存。')

    def on_context_menu(self, event):
        """文本框右键：首项「编辑／退出编辑」，其后四项按编辑态与改动启用。"""
        menu = self.page.script_page_services.context_menu(self.preview)
        editing = self.editing and str(self.preview.cget('state')) == 'normal'
        if editing:
            menu.command('退出编辑', lambda: self.page.safe(self.exit_edit))
            menu.command('后退一步', lambda: self.page.safe(self.undo_step))
            menu.command('前进一步', lambda: self.page.safe(self.redo_step))
            initial = self.controller.initial
            if initial is not None and self.preview.get('1.0', 'end-1c') != initial:
                menu.command('复原全文', lambda: self.page.safe(self.restore_full))
            else:
                menu.disabled('复原全文')
            menu.command('立即保存', lambda: self.page.safe(self.save_now))
        else:
            if self.editable and self.active['path'] is not None:
                menu.command('编辑', lambda: self.page.safe(self.begin_edit))
            else:
                menu.disabled('编辑')
            for label in self._MENU_LABELS:
                menu.disabled(label)
        self.last_menu = menu
        return menu.popup(event)

    # ── 快捷键（经 ShortcutRegistry 登记，不直绑）─────────────────────────
    def _bind_undo_shortcuts(self):
        shortcuts = getattr(self.page, 'shortcuts', None)
        if shortcuts is None:
            return
        scope = '剧本结构页·' + str(self.box.attribute)
        shortcuts.bind(self.preview, ('<Control-z>', '<Control-Z>'),
                       self._shortcut_undo, scope=scope, name='后退一步')
        shortcuts.bind(self.preview,
                       ('<Control-y>', '<Control-Y>', '<Control-Shift-z>', '<Control-Shift-Z>'),
                       self._shortcut_redo, scope=scope, name='前进一步')

    def _shortcut_undo(self, _event=None):
        if self.editing and str(self.preview.cget('state')) == 'normal':
            self.undo_step()
        return 'break'

    def _shortcut_redo(self, _event=None):
        if self.editing and str(self.preview.cget('state')) == 'normal':
            self.redo_step()
        return 'break'


def _install_script_edit_controls(page, box):
    """给剧本编辑器装上自动保存编辑会话（REQ-S02-37 起页面上不再有编辑按钮）。

    会话与控制器以 ``attribute + '_edit_session'``／``'_controller'`` 名登记到
    页面实例上，供测试与页面逻辑读取。
    """
    session = _ScriptEditSession(page, box)
    setattr(page, box.attribute + '_controller', session.controller)
    setattr(page, box.attribute + '_edit_session', session)
