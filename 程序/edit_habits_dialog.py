"""「修改习惯」弹窗：查看、归纳、采用／停用／改写／删除用户修改习惯（REQ-S01-59/60）。

只负责 Tk 控件与事件；记录与规则的读写都经 ``edit_habits``。归纳要调用模型，放在后台线程，
结果经 ``after`` 回到 Tk 线程；弹窗已关闭时丢弃结果。
"""
import logging
import queue
import threading

import tkinter as tk
from tkinter import ttk

import orchestrator.edit_habits as edit_habits
from skill_panel_support import desktop_project
from ui_tokens import CHAR_WIDTH, SPACING, TEXT_ROWS
from ui_widgets import (BaseDialog, DataTable, DescriptionBlock, PrimaryButton, SecondaryButton,
                        ask_confirmation, ask_string, notify)

LOGGER = logging.getLogger(__name__)
TITLE = '修改习惯'
POLL_MS = 100
COLUMNS = [('status', '状态', 80), ('text', '规则', 460), ('evidence', '次数', 60)]


def entry_button(row, panel):
    """在剧本准备面板的「风格」行放入口按钮。"""
    button = SecondaryButton(row, text=TITLE, width=CHAR_WIDTH['xl'], command=lambda: open_dialog(panel))
    button.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    return button


def open_dialog(panel, program=None):
    project = desktop_project(panel.desktop)
    if not project:
        notify(panel.winfo_toplevel(), '请先选择项目。', title=TITLE,
               status=getattr(panel.desktop, 'status', None), modal=False)
        return None
    return HabitsDialog(panel.winfo_toplevel(), project, program)


class HabitsDialog(BaseDialog):
    def __init__(self, parent, project, program=None):
        super().__init__(parent, TITLE, minsize=(720, 460), modal=False, chrome=False)
        self.project, self.program = project, program
        self.rows = {}
        body = ttk.Frame(self, padding=SPACING['md'])
        body.pack(fill='both', expand=True)
        DescriptionBlock(body, text='在剧本结构页编辑并保存自然剧本时，程序会记下您的修改。攒够 %d 次后点「归纳最近修改」，'
                                    '模型会把反复出现的改法归纳成规则；您采用的规则会用于所有项目之后的剧本创作。'
                         % edit_habits.MIN_RECORDS).pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        self.pending = DescriptionBlock(body, text='')
        self.pending.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        self.table = DataTable(body, columns=COLUMNS, height=TEXT_ROWS['lg'], horizontal=False,
                               empty_text='还没有修改习惯', on_select=lambda _items: self.show_example())
        self.table.pack(fill='both', expand=True)
        self.example = DescriptionBlock(body, text='')
        self.example.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        actions = ttk.Frame(body)
        actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        self.learn_button = PrimaryButton(actions, text='归纳最近修改', width=CHAR_WIDTH['xl'], command=self.learn)
        self.learn_button.pack(side='left')
        for text, action in (('采用', 'adopt'), ('停用', 'disable'), ('改写', 'rewrite'), ('删除', 'delete')):
            SecondaryButton(actions, text=text, width=CHAR_WIDTH['md'],
                            command=lambda value=action: self.apply(value)).pack(
                side='left', padx=(SPACING['sm'], SPACING['none']))
        SecondaryButton(actions, text='关闭', width=CHAR_WIDTH['md'], command=self.close).pack(side='right')
        self.status = DescriptionBlock(body, text='')
        self.status.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
        self.refresh()

    def refresh(self):
        count = len(edit_habits.pending(self.project, program=self.program))
        self.pending.configure(text='本项目还有 %d 次修改未归纳。' % count)
        tree = self.table.tree
        tree.delete(*tree.get_children())
        self.rows = {}
        for rule in edit_habits.load_rules(self.program):
            self.rows[rule['id']] = rule
            tree.insert('', 'end', iid=rule['id'], values=(
                edit_habits.STATUS_LABELS[rule['status']], rule['text'], rule.get('evidence', '')))
        self.table.refresh_empty_state()
        self.show_example()

    def selected(self):
        items = self.table.selected_items()
        return self.rows.get(items[0]) if items else None

    def show_example(self):
        rule = self.selected()
        example = (rule or {}).get('example') or {}
        if not example.get('before') and not example.get('after'):
            self.example.configure(text='')
            return
        self.example.configure(text='例子 · 改前：' + str(example.get('before') or '（空）')
                               + '\n例子 · 改后：' + str(example.get('after') or '（删去）'))

    def apply(self, action):
        rule = self.selected()
        if rule is None:
            self.status.configure(text='请先在表格里选中一条规则。')
            return
        text = None
        if action == 'rewrite':
            text = ask_string(self, '改写规则', '改写后的规则（%d 字以内）：' % edit_habits.MAX_RULE_CHARS,
                              initialvalue=rule['text'])
            if text is None:
                return
        if action == 'delete' and not ask_confirmation(self, '删除规则', '删除「' + rule['text'] + '」吗？', dangerous=True):
            return
        try:
            edit_habits.decide(rule['id'], action, text, self.program)
        except (OSError, ValueError) as exc:
            self.status.configure(text=str(exc) if isinstance(exc, ValueError) else '规则暂时无法保存，请检查目录写入权限。')
            return
        self.status.configure(text={'adopt': '已采用，之后的剧本创作会遵守这条规则。', 'disable': '已停用。',
                                    'rewrite': '已改写。', 'delete': '已删除。'}[action])
        self.refresh()

    def learn(self):
        self.learn_button.state(['disabled'])
        self.status.configure(text='正在归纳最近的修改…')
        results = queue.Queue(maxsize=1)
        threading.Thread(target=self._summarize, args=(results,), daemon=True).start()
        self._await(results)

    def _summarize(self, results):
        try:
            result = edit_habits.summarize(self.project, program=self.program)
        except Exception as exc:  # 线程边界：任何异常都要回到界面，否则按钮一直灰着
            LOGGER.warning('归纳修改习惯失败：%s', type(exc).__name__)
            result = {'ok': False, 'count': 0, 'message': '归纳修改习惯暂未完成，请稍后重试。'}
        results.put(result)

    def _await(self, results):
        if self._closed:
            return
        try:
            result = results.get_nowait()
        except queue.Empty:
            try:
                self.after(POLL_MS, lambda: self._await(results))
            except tk.TclError:
                pass
            return
        self.learn_button.state(['!disabled'])
        self.status.configure(text=result['message'])
        self.refresh()
