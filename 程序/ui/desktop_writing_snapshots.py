# -*- coding: utf-8 -*-
"""剧本准备页「历史快照／对比」与「按段落采用」弹窗（从 ``desktop_writing_page._WritingPage`` 迁出）。

迁出原因：``_WritingPage`` 超出类行数棘轮上限（703 > 600）。REQ-S01-87 快照
历史／diff 查看与 REQ-S01-88 段落级部分采用同属「定稿审阅」一簇，与 Tk 控件和
``self.page`` 状态紧耦合，整块搬出后方法体未改、``self`` 语义不变；
``_WritingPage`` 通过继承 ``WritingSnapshotsMixin`` 获得这些方法，同属 L4。
"""
import tkinter as tk
from tkinter import ttk

from ui_tokens import COLORS, FONTS, SCRIPT_FILE_FONT, SPACING
from ui_widgets import BaseDialog, TextArea


class WritingSnapshotsMixin:
    """定稿审阅弹窗：快照列表／快照 diff 查看／按段落勾选采用。"""

    def preparation_snapshots(self, stage):
        """REQ-S01-87：该阶段已登记的确认快照（台账倒序，新→旧）。"""
        from infra.file_cache import read_json
        from contract.stage_path_service import write_dir
        folder = write_dir(self.page.root, 'script')
        try:
            state = read_json(folder / 'preparation_state.json') or {}
        except OSError:
            state = {}
        return [item for item in reversed(state.get('snapshots') or [])
                if isinstance(item, dict) and item.get('stage') == stage]

    def show_preparation_snapshots(self, stage):
        """「历史快照／对比」：列出该阶段快照，可查看全文或与当前文件 diff。"""
        snaps = self.preparation_snapshots(stage)
        if not snaps:
            self.page.status.set('「' + stage + '」还没有确认快照，先设为定稿一次')
            return
        dialog = BaseDialog(self.page.win, '「' + stage + '」确认快照', geometry='560x360')
        listbox = tk.Listbox(dialog.content, font=FONTS['body'],
                             activestyle='none', exportselection=False)
        scroll = ttk.Scrollbar(dialog.content, orient='vertical', command=listbox.yview)
        listbox.configure(yscrollcommand=scroll.set)
        listbox.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        for item in snaps:
            listbox.insert('end', '%s  %s' % (item.get('confirmed_at', ''), item.get('path', '')))
        listbox.selection_set(0)

        def chosen():
            selection = listbox.curselection()
            return snaps[selection[0]] if selection else None

        def view():
            record = chosen()
            if record is not None:
                self._show_snapshot_text(stage, record, diff=False)

        def diff():
            record = chosen()
            if record is not None:
                self._show_snapshot_text(stage, record, diff=True)

        dialog.add_action('关闭', dialog.close)
        dialog.add_action('与当前文件对比', diff)
        dialog.add_action('查看全文', view, primary=True)

    def _show_snapshot_text(self, stage, record, *, diff):
        """快照查看或快照→当前文件 unified diff 弹窗；正文差异一目了然。"""
        from contract.stage_path_service import write_dir
        folder = write_dir(self.page.root, 'script')
        snapshot = folder / str(record.get('snapshot') or '')
        try:
            old = snapshot.read_text(encoding='utf-8') if snapshot.is_file() else ''
        except OSError:
            old = ''
        if not diff:
            title, body = ('「%s」确认快照 · %s' % (stage, record.get('path', ''))), old
        else:
            path = self.selected_script()
            current = path.read_text(encoding='utf-8') if path.is_file() else ''
            import difflib
            lines = list(difflib.unified_diff(
                old.splitlines(), current.splitlines(),
                fromfile='定稿快照 %s' % record.get('confirmed_at', ''),
                tofile='当前文件 ' + path.name, lineterm=''))
            title = '与当前文件对比 · 「%s」' % stage
            body = '\n'.join(lines) if lines else '与定稿快照一致，没有改动。'
        viewer = BaseDialog(self.page.win, title, geometry='720x520')
        area = TextArea(viewer.content, bg=COLORS['background_card'], fg=COLORS['text_primary'],
                        font=SCRIPT_FILE_FONT, wrap='none')
        bar = ttk.Scrollbar(viewer.content, orient='vertical', command=area.yview)
        area.configure(yscrollcommand=bar.set)
        area.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        area.insert('1.0', body)
        area.configure(state='disabled')
        viewer.add_action('关闭', viewer.close)

    def show_partial_adoption(self, stage):
        """REQ-S01-88：按段落采用——勾选保留的段落，截写文件并登记标记。"""
        try:
            path = self.selected_script()
        except ValueError as error:
            self.page.status.set(str(error))
            return
        from orchestrator.writing_unconfirm import adoption_sections
        try:
            sections = adoption_sections(path.read_text(encoding='utf-8'))
        except OSError:
            sections = []
        if len(sections) < 2:
            self.page.status.set('稿件不足两段，无需按段落采用')
            return
        dialog = BaseDialog(self.page.win, '按段落采用 · 「' + stage + '」', geometry='560x420')
        bar = ttk.Scrollbar(dialog.content, orient='vertical')
        canvas = tk.Canvas(dialog.content, yscrollcommand=bar.set,
                           bg=COLORS['background_card'], highlightthickness=0)
        bar.configure(command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(inner_id, width=e.width))
        canvas.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        checks = []
        for section in sections:
            var = tk.IntVar(value=1)
            ttk.Checkbutton(inner, variable=var,
                            text=section['title'][:60]).pack(anchor='w',
                            padx=SPACING['xs'], pady=SPACING['xs'] // 2)
            checks.append(var)

        def apply():
            keep = tuple(index for index, var in enumerate(checks) if var.get())
            if not keep:
                self.page.status.set('请至少勾选一段')
                return
            from stage_execution_service import apply_partial_adoption
            try:
                apply_partial_adoption(self.page.root, stage, path, keep)
            except ValueError as error:
                self.page.status.set(str(error))
                return
            dialog.close()
            self.fill_script_list()
            self.page.status.set('已按所选段落截写「' + stage + '」，请审阅后设为定稿')

        dialog.add_action('取消', dialog.close)
        dialog.add_action('采用所选', apply, primary=True)
