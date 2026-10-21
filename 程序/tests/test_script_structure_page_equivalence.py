"""desktop_script_pages.ScriptPagesMixin.script_structure（剧本结构页）由闭包改写成类：旧方法原样内嵌，用同一份脚本驱动两个真 Desktop，逐步对照整棵控件树。"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_script_pages as module
import pet_state
from page_diff_support import freeze_times, poke, pump, snapshot
from catalog_page_test_support import show_catalog_page_ready
from skip_reasons import PLATFORM_TKINTER

LEGACY_SCRIPT_STRUCTURE = r'''def _legacy_script_structure(self):
    """上看剧本准备原稿、下看结构化正稿；两框独立滚动并可分别编辑保存。"""
    import script_contract
    from script_workspace_service import script_structure_documents
    structure = script_structure_documents(self.root)
    source_directory = structure.source_directory
    structure_directory = structure.output_directory
    source = structure.source
    target = structure.target
    # 将两份剧本放入同一个等分网格。动作栏与说明文字不参与分配，窗口缩放时
    # 上、下内容框始终各占剩余阅读区域的一半。
    split_area = ttk.Frame(self.content)
    split_area.pack(fill='both', expand=True)
    split_area.columnconfigure(0, weight=1)
    split_area.rowconfigure(0, weight=1, uniform='script_structure_preview')
    split_area.rowconfigure(1, weight=1, uniform='script_structure_preview')
    structure_note = '本地规则整理，不调用模型；不切镜头、不改自然语言原稿。'
    from script_preview_service import LOADING_PREVIEW, preview_chunks, read_preview, should_load_async
    def content_box(parent, title, file_heading, documents, active_path, empty, attribute,
                    editable=True, kind='natural'):
        # 剧本文件选择改为正文上方的横向下拉框，与操作按钮同一行；正文独占整行宽度。
        box = ttk.Frame(parent, padding=(SPACING["xs"], SPACING["none"]))
        available = tuple(path for path in documents if path and path.is_file())
        preview_area = ttk.Frame(box); preview_area.pack(fill='both', expand=True)
        preview_header = ttk.Frame(preview_area)
        preview_header.pack(fill='x')
        # 编辑操作贴着标题行右侧，下拉框占用其余宽度。
        controls = ttk.Frame(preview_header)
        controls.pack(side='right', padx=(SPACING["sm"], SPACING["none"]))
        file_list = _DocumentPicker(preview_header, available, active_path)
        file_list.pack(side='left', fill='x', expand=True)
        active = {'path': active_path if active_path in available else (available[0] if available else None)}
        text_area = ttk.Frame(preview_area); text_area.pack(fill='both', expand=True)
        preview, horizontal = _build_script_preview(text_area)
        preview_ticket = {'value': 0}
        loaded = {'raw': ''}
        def set_preview(value, ticket=None):
            """小文本立即显示；大文本在 Tk 空闲时分块插入，避免一次性重排。"""
            loaded['raw'] = str(value or '')
            shown = script_view_style.compact_display(loaded['raw'])
            styled = script_view_style.should_style(shown)
            _set_script_wrap(preview, horizontal, styled)
            preview.configure(state='normal')
            preview.delete('1.0', 'end')
            preview.configure(state='disabled')
            chunks = iter(preview_chunks(shown))
            def append_chunk():
                if ticket is not None and ticket != preview_ticket['value']:
                    return
                try:
                    chunk = next(chunks)
                except StopIteration:
                    try:
                        preview.configure(state='normal')
                        if styled:
                            script_view_style.apply_tags(preview, shown, kind)
                        # 初始预览不能成为“恢复删除”的一条历史记录；只恢复用户本次编辑中的动作。
                        preview.edit_reset()
                        preview.configure(state='disabled')
                    except tk.TclError:
                        pass
                    return
                try:
                    preview.configure(state='normal')
                    preview.insert('end', chunk)
                    preview.configure(state='disabled')
                    self.win.after_idle(append_chunk)
                except tk.TclError:
                    pass
            if ticket is None:
                _reset_preview_text(preview, shown, kind)
                preview.configure(state='disabled')
            else:
                _safe_after_idle(self.win, append_chunk)
        def load_preview(path):
            """大文本在后台读取；选中项变化或进入编辑态时丢弃旧结果。"""
            preview_ticket['value'] += 1
            ticket = preview_ticket['value']
            if not should_load_async(path):
                set_preview(read_preview(path, empty))
                return
            set_preview(LOADING_PREVIEW)
            expected = Path(path) if path else None
            # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。
            # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。
            preview_results = queue.Queue(maxsize=1)
            threading.Thread(
                target=lambda: preview_results.put((ticket, expected, read_preview(expected, empty))),
                daemon=True,
            ).start()
            def await_preview():
                try:
                    result_ticket, result_path, value = preview_results.get_nowait()
                except queue.Empty:
                    try:
                        self.win.after(50, await_preview)
                    except tk.TclError:
                        pass
                    return
                if (result_ticket != preview_ticket['value'] or active['path'] != result_path or
                        str(preview.cget('state')) != 'disabled'):
                    return
                try:
                    if preview.winfo_exists():
                        set_preview(value, ticket=ticket)
                except tk.TclError:
                    pass
            _safe_after(self.win, 20, await_preview)
        load_preview(active['path'])
        def select_document(_event=None):
            selected = file_list.selection()
            if not selected or not available:
                return
            if str(preview.cget('state')) == 'normal':
                file_list.selection_set(str(active['path']))
                self.status.set('请先保存或完成当前修改，再切换剧本。')
                return
            chosen = Path(selected[0])
            if chosen == active['path']:
                return
            active['path'] = chosen
            load_preview(chosen)
        file_list.bind('<<ComboboxSelected>>', select_document)
        def delete_document():
            """目录右键删除只移入项目回收站；来源稿删除后刷新会隐藏关联结构稿。"""
            selected = file_list.selection()
            from script_workspace_service import selected_workspace_document
            destination = selected_workspace_document(available, selected[0] if selected else None)
            from storage_maintenance import recycle_paths
            records = recycle_paths(self.root, [destination], '删除' + title)
            if not records:
                raise ValueError('未能安全移入项目回收站，原文件未删除。')
            self.show(PAGE['script_structure'])
            self.status.set('已将' + destination.name + '移入回收站；关联的结构剧本已按来源刷新。')
        def open_document_menu(event):
            if not available:
                return None
            menu = self.script_page_services.context_menu(file_list).command('删除（移入回收站）', lambda:self.safe(delete_document))
            self._script_structure_file_menu = menu
            return menu.popup(event)
        file_list.bind('<Button-3>', open_document_menu)
        def begin_edit():
            if not editable or active['path'] is None:
                raise ValueError('当前没有可修改的剧本文档。')
            _reset_preview_text(preview, loaded['raw'], kind)
            preview.edit_modified(False)
            edit.state(['disabled']); restore.state(['!disabled']); save.state(['!disabled'])
            preview.focus_set()
        def save_edit():
            if not editable or active['path'] is None:
                raise ValueError('当前没有可保存的剧本文档。')
            value = preview.get('1.0', 'end-1c').strip()
            if not value:
                raise ValueError('剧本内容不能为空。')
            destination = Path(active['path'])
            if preview.edit_modified():
                from script_contract import save_natural_script
                save_natural_script(destination, value)
                set_preview(value + '\n')
            else:
                set_preview(loaded['raw'])
            edit.state(['!disabled']); restore.state(['disabled']); save.state(['disabled'])
            self.status.set('已保存'+title+'：'+destination.name)
            if destination == source:
                self.status.set('已保存剧本准备阶段剧本；如需更新下方结构化剧本，请重新执行“手动制作结构剧本”。')
        def restore_deleted():
            if str(preview.cget('state')) == 'disabled':
                raise ValueError('请先点击“修改内容”，再恢复刚删除的文字。')
            try:
                preview.edit_undo()
            except tk.TclError as exc:
                raise ValueError('没有可恢复的删除内容。') from exc
        edit = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='修改内容', command=lambda:self.safe(begin_edit))
        edit.pack(side='left')
        restore = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='恢复删除', command=lambda:self.safe(restore_deleted))
        restore.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); restore.state(['disabled'])
        save = PrimaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='保存修改', command=lambda:self.safe(save_edit))
        save.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); save.state(['disabled'])
        setattr(self, attribute, preview)
        setattr(self, attribute + '_edit_button', edit)
        setattr(self, attribute + '_restore_button', restore)
        setattr(self, attribute + '_save_button', save)
        setattr(self, attribute + '_files', file_list)
        return box
    self.script_structure_source_box = content_box(
        split_area,
        '自然剧本（采用：'+source.name+'）' if source else '自然剧本（待选择采用版本）',
        '自然剧本', structure.source_documents, source,
        '尚未找到剧本准备阶段的剧本。请先生成、下载或导入剧本。',
        'script_structure_source_preview', editable=source is not None, kind='natural')
    self.script_structure_source_box.grid(row=0, column=0, sticky='nsew', pady=(SPACING["xs"], SPACING["none"]))
    self.script_structure_output_box = content_box(
        split_area,
        '结构剧本', '结构剧本', structure.output_documents, target,
        '尚未生成结构化剧本。点击上方“手动制作结构剧本”，或由三虎全自动模式执行。',
        'script_structure_output_preview', editable=True, kind='structured')
    self.script_structure_output_box.grid(row=1, column=0, sticky='nsew')
    actions = FlowBar(split_area); actions.grid(row=2, column=0, sticky='ew', pady=(SPACING["xs"], SPACING["none"]))
    def start_structure():
        if script_contract.resolve_script_source(self.root) is None:
            raise ValueError('请先选择自然剧本并点击“采用选中剧本”；已采用文件被修改或删除后须重新采用。')
        started = self.pet_script_structure_batch(trigger='manual', refresh_page=True)
        if not started:
            raise ValueError('剧本结构正在执行，或三虎自动化暂不可用。')
        self.status.set(started)
    from stage_models import manual_command
    action_group = ttk.Frame(actions)
    action_group.pack(anchor='center', pady=SPACING["xs"])
    def adopt_source():
        from stage_execution_service import adopt_natural_script
        selected = self.script_structure_source_preview_files.selection()
        if not selected:raise ValueError('请先选择一份自然剧本。')
        adopted = adopt_natural_script(self.root, selected[0])
        self.status.set('已采用自然剧本：'+adopted.name)
        self.show(self.page_index)
    SecondaryButton(action_group, text='采用选中剧本', command=lambda:self.safe(adopt_source)).pack(
        side='left', padx=(SPACING['none'], SPACING['xs']))
    manual = PrimaryButton(action_group, text='手动制作结构剧本', width=STAGE_ACTION_WIDTH,
                           command=lambda:self.safe(manual_command(self, 'script_structure', start_structure, self.win)))
    manual.pack(side='left', padx=(SPACING["none"], SPACING["xs"])); self.script_structure_manual_button = manual
    ui_plugin_registry.module('stage_flow').follow(manual, 'script_structure')
    self.stage_button = ui_plugin_registry.module('skill_panel').stage_button(action_group, self, PAGE['script_structure'])
    self.stage_button.pack(side='left', padx=(SPACING["sm"], SPACING["xs"]))
    # 流程说明留在两块内容之后的右下角，避免占用顶部阅读空间。
    info = ttk.Label(self.content, text=structure_note, style='Muted.TLabel', justify='left')
    info.pack(anchor='center', pady=(SPACING["xs"], SPACING["none"]))
    self.script_structure_info_label = info
    self.script_structure_source_directory = source_directory
    self.script_structure_output_directory = structure_directory
'''

PAGES = {'script_structure': 'script_structure'}
OWNER = 'ScriptPagesMixin'



TARGET = getattr(module, OWNER) if OWNER else module


def _open_app(tk, td):
    import test_ui_edges
    from desktop import Desktop
    from local_video import open_studio
    win = tk.Tk()
    win.withdraw()
    app = Path(td) / 'app'
    app.mkdir()
    desktop = Desktop(win, root=app)
    desktop.startup_controller.cancel()
    desktop.root = test_ui_edges.make_populated_project(td)
    desktop.studio = open_studio(desktop.root)
    freeze_times(desktop.root)
    return win, desktop


class ScriptStructurePageEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            root = tkinter.Tk()
            root.destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.namespace = dict(vars(module))
        exec(compile(LEGACY_SCRIPT_STRUCTURE, 'legacy_script_structure', 'exec'), self.namespace)

    def _session(self, name, impl):
        page = pet_state.PAGE_OF[PAGES[name]]
        # 路径要在两次运行里逐字相同（请求宽度随字形变化），所以用按进程号固定的目录，而不是随机临时目录
        td = Path(tempfile.gettempdir()) / ('drama_page_diff_%d' % os.getpid())
        shutil.rmtree(td, ignore_errors=True)
        td.mkdir(parents=True)
        try:
            win, desktop = _open_app(self.tk, td)
            roots = sorted({str(td), Path(td).as_posix(), str(Path(td).resolve()), Path(td).resolve().as_posix()},
                           key=len, reverse=True)
            steps = []
            try:
                with mock.patch.object(TARGET, name, impl):
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#1', steps, roots)
                    desktop.go_page(pet_state.PAGE_OF['assets'])
                    pump(win, 0.1)
                    steps.append(('left', snapshot(desktop.content, roots)))
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#2', steps, roots)
            finally:
                desktop.cancel_timers()
                win.destroy()
            return steps
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_script_structure_is_identical(self):
        self._session('script_structure', self.namespace['_legacy_script_structure'])   # 预热：进程里第一次建窗的布局与之后不同，先跑一遍丢掉
        old = self._session('script_structure', self.namespace['_legacy_script_structure'])
        new = self._session('script_structure', getattr(TARGET, 'script_structure'))
        self.assertEqual(len(new), len(old))
        for a, b in zip(new, old):
            self.assertEqual(a, b, a[0])
        widgets = max(len(step[1]) if isinstance(step[1], list) else 0 for step in new)
        self.assertGreater(widgets, 15)   # 对照不能是空对空：页面真的建出了一棵控件树


if __name__ == '__main__':
    unittest.main()
