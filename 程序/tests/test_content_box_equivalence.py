"""desktop_script_pages._ScriptStructurePage.content_box 改写成类：HEAD 旧方法原样内嵌，替换到同一页上，
打开剧本结构页后对两个内容框逐个点“编辑／后退／恢复”（R1842 起；旧实现已并入 R1842 的编辑控件），对照每步控件树、状态栏与落盘正文。"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_script_pages as module
import pet_state
from catalog_page_test_support import show_catalog_page_ready
from page_diff_support import freeze_times
from page_diff_support import buttons, pump, safe_call, snapshot, _clean
from skip_reasons import PLATFORM_TKINTER
from test_script_structure_page_equivalence import _open_app
from window_diff_support import legacy

LEGACY = 'def content_box(self, parent, title, file_heading, documents, active_path, empty, attribute,\n                editable=True, kind=\'natural\'):\n    # 剧本文件选择改为正文上方的横向下拉框，与操作按钮同一行；正文独占整行宽度。\n    box = ttk.Frame(parent, padding=(SPACING["xs"], SPACING["none"]))\n    available = tuple(path for path in documents if path and path.is_file())\n    preview_area = ttk.Frame(box); preview_area.pack(fill=\'both\', expand=True)\n    preview_header = ttk.Frame(preview_area)\n    preview_header.pack(fill=\'x\')\n    # 编辑操作贴着标题行右侧，下拉框占用其余宽度。\n    controls = ttk.Frame(preview_header)\n    controls.pack(side=\'right\', padx=(SPACING["sm"], SPACING["none"]))\n    file_list = _DocumentPicker(preview_header, available, active_path)\n    file_list.pack(side=\'left\', fill=\'x\', expand=True)\n    active = {\'path\': active_path if active_path in available else (available[0] if available else None)}\n    text_area = ttk.Frame(preview_area); text_area.pack(fill=\'both\', expand=True)\n    preview, horizontal = _build_script_preview(text_area)\n    preview_ticket = {\'value\': 0}\n    loaded = {\'raw\': \'\'}\n    def set_preview(value, ticket=None):\n        """小文本立即显示；大文本在 Tk 空闲时分块插入，避免一次性重排。"""\n        loaded[\'raw\'] = str(value or \'\')\n        shown = script_view_style.compact_display(loaded[\'raw\'])\n        styled = script_view_style.should_style(shown)\n        _set_script_wrap(preview, horizontal, styled)\n        preview.configure(state=\'normal\')\n        preview.delete(\'1.0\', \'end\')\n        preview.configure(state=\'disabled\')\n        chunks = iter(self.preview_chunks(shown))\n        def append_chunk():\n            if ticket is not None and ticket != preview_ticket[\'value\']:\n                return\n            try:\n                chunk = next(chunks)\n            except StopIteration:\n                try:\n                    preview.configure(state=\'normal\')\n                    if styled:\n                        script_view_style.apply_tags(preview, shown, kind)\n                    # 初始预览不能成为“恢复删除”的一条历史记录；只恢复用户本次编辑中的动作。\n                    preview.edit_reset()\n                    preview.configure(state=\'disabled\')\n                except tk.TclError:\n                    pass\n                return\n            try:\n                preview.configure(state=\'normal\')\n                preview.insert(\'end\', chunk)\n                preview.configure(state=\'disabled\')\n                self.page.win.after_idle(append_chunk)\n            except tk.TclError:\n                pass\n        if ticket is None:\n            _reset_preview_text(preview, shown, kind)\n            preview.configure(state=\'disabled\')\n        else:\n            _safe_after_idle(self.page.win, append_chunk)\n    def load_preview(path):\n        """大文本在后台读取；选中项变化或进入编辑态时丢弃旧结果。"""\n        preview_ticket[\'value\'] += 1\n        ticket = preview_ticket[\'value\']\n        if not self.should_load_async(path):\n            set_preview(self.read_preview(path, empty))\n            return\n        set_preview(self.LOADING_PREVIEW)\n        expected = Path(path) if path else None\n        # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。\n        # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。\n        preview_results = queue.Queue(maxsize=1)\n        threading.Thread(\n            target=lambda: preview_results.put((ticket, expected, self.read_preview(expected, empty))),\n            daemon=True,\n        ).start()\n        def await_preview():\n            try:\n                result_ticket, result_path, value = preview_results.get_nowait()\n            except queue.Empty:\n                try:\n                    self.page.win.after(50, await_preview)\n                except tk.TclError:\n                    pass\n                return\n            if (result_ticket != preview_ticket[\'value\'] or active[\'path\'] != result_path or\n                    str(preview.cget(\'state\')) != \'disabled\'):\n                return\n            try:\n                if preview.winfo_exists():\n                    set_preview(value, ticket=ticket)\n            except tk.TclError:\n                pass\n        _safe_after(self.page.win, 20, await_preview)\n    load_preview(active[\'path\'])\n    def select_document(_event=None):\n        selected = file_list.selection()\n        if not selected or not available:\n            return\n        if str(preview.cget(\'state\')) == \'normal\':\n            file_list.selection_set(str(active[\'path\']))\n            self.page.status.set(\'请先保存或完成当前修改，再切换剧本。\')\n            return\n        chosen = Path(selected[0])\n        if chosen == active[\'path\']:\n            return\n        active[\'path\'] = chosen\n        load_preview(chosen)\n    file_list.bind(\'<<ComboboxSelected>>\', select_document)\n    def delete_document():\n        """目录右键删除只移入项目回收站；来源稿删除后刷新会隐藏关联结构稿。"""\n        selected = file_list.selection()\n        from script_workspace_service import selected_workspace_document\n        destination = selected_workspace_document(available, selected[0] if selected else None)\n        from storage_maintenance import recycle_paths\n        records = recycle_paths(self.page.root, [destination], \'删除\' + title)\n        if not records:\n            raise ValueError(\'未能安全移入项目回收站，原文件未删除。\')\n        self.page.show(PAGE[\'script_structure\'])\n        self.page.status.set(\'已将\' + destination.name + \'移入回收站；关联的结构剧本已按来源刷新。\')\n    def open_document_menu(event):\n        if not available:\n            return None\n        menu = self.page.script_page_services.context_menu(file_list).command(\'删除（移入回收站）\', lambda:self.page.safe(delete_document))\n        self.page._script_structure_file_menu = menu\n        return menu.popup(event)\n    file_list.bind(\'<Button-3>\', open_document_menu)\n    # 合并 R1842：编辑控件改由 _install_script_edit_controls 装配（编辑／后退／恢复＋自动保存），与 master aa3e2efe 一致。\n    _install_script_edit_controls(self.page, controls, __import__(\'types\').SimpleNamespace(preview=preview, loaded=loaded, active=active, kind=kind, title=title, editable=editable, attribute=attribute))\n    setattr(self.page, attribute, preview)\n    setattr(self.page, attribute + \'_files\', file_list)\n    return box\n'

def texts(widget):
    out = [widget] if widget.winfo_class() == 'Text' else []
    for child in widget.winfo_children():
        out.extend(texts(child))
    return out


ACTIONS = ('编辑', '后退', '恢复')   # R1842：按钮改为编辑／后退／恢复，保存改为自动


def _texts(root):
    return sorted((str(p.relative_to(root)), p.read_text(encoding='utf-8', errors='replace'))
                  for p in Path(root).rglob('*.md') if p.is_file())


class ContentBoxEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)

    def _session(self, impl):
        td = Path(tempfile.gettempdir()) / ('drama_content_box_diff_%d' % os.getpid())
        shutil.rmtree(td, ignore_errors=True)
        td.mkdir(parents=True)
        try:
            win, desktop = _open_app(self.tk, td)
            from stage_path_service import write_dir
            scripts = write_dir(desktop.root, 'script'); scripts.mkdir(parents=True, exist_ok=True)
            for name, body in (('第一集剧本.md', '第一场 日 内\n林夏推门进来。\n'), ('第二集剧本.md', '第二场 夜 外\n雨很大。\n')):
                (scripts / name).write_text(body, encoding='utf-8')
            from stage_execution_service import adopt_natural_script
            adopt_natural_script(desktop.root, scripts / '第一集剧本.md')   # 采用后来源框才可编辑
            freeze_times(desktop.root)   # 新写的文件也钉死修改时间，下拉框排序才跨次一致
            roots = sorted({str(td), td.as_posix(), str(td.resolve()), td.resolve().as_posix()}, key=len, reverse=True)
            steps = []
            try:
                said = []
                real_set = desktop.status.set
                # 状态栏会被页面刷新随即覆盖，逐条记下每次写入才能对照保存／恢复的提示文字。
                with mock.patch.object(module._ScriptStructurePage, 'content_box', impl),                         mock.patch.object(desktop.status, 'set', lambda value: (said.append(_clean(value, roots)), real_set(value))):
                    show_catalog_page_ready(desktop, pet_state.PAGE_OF['script_structure'])
                    pump(win, 0.2)
                    content = desktop.content
                    steps.append(('initial', snapshot(content, roots), _clean(desktop.status.get(), roots)))
                    for round_ in range(2):
                        for text in ACTIONS:
                            for index, button in enumerate(b for b in buttons(content) if str(b.cget('text')) == text):
                                if str(button.cget('state')) == 'disabled':
                                    steps.append((round_, text, index, 'disabled'))
                                    continue
                                outcome = safe_call(button.invoke)
                                if text == '编辑':
                                    for widget in texts(content):
                                        if str(widget.cget('state')) == 'normal':
                                            widget.insert('end', '补一句%d' % round_)
                                pump(win, 0.1)
                                steps.append((round_, text, index, outcome, snapshot(content, roots),
                                              _clean(desktop.status.get(), roots)))
                    steps.append(('files', _texts(desktop.root)))
                    steps.append(('status', said))
            finally:
                desktop.cancel_timers()
                win.destroy()
            return steps
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_matches_legacy(self):
        old = legacy(module, LEGACY, 'content_box')
        self._session(old)   # 预热：进程里第一次建窗的布局与之后不同
        expected = self._session(old)
        actual = self._session(module._ScriptStructurePage.content_box)
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertEqual(a, b, a[:3])
        self.assertTrue(any(len(step) > 4 for step in actual))   # 至少真的点到了一个按钮


if __name__ == '__main__':
    unittest.main()
