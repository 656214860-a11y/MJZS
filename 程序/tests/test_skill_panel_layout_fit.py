"""R1684/R2862 阶段配置页：制作锁下拉自适应宽度、制作锁弹窗布局与厂商显示名回归。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

from ui_tokens import COMBOBOX_MAX_WIDTH
from ui_widgets import SelectBox


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


class LockFitTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'project'
        app = Path(self.tmp.name) / 'program'
        root.mkdir()
        app.mkdir()
        self.desktop = SimpleNamespace(win=self.win, root=root, app=app,
                                       status=tk.StringVar(master=self.win, value=''))

    def test_editable_lock_width_fits_options_and_refits_on_change(self):
        from production_lock_fields import ProductionLockFields
        view = ProductionLockFields(self.win)
        view.pack(fill='x')
        self.win.update_idletasks()
        # 契约变更（统一下拉框尺寸）：所有锁下拉框同一固定宽度，选项长度由弹出列表自适应。
        from ui_tokens import STAGE_PANEL_LAYOUT
        for key, entry in view.inputs.items():
            self.assertEqual(int(entry.cget('width')), STAGE_PANEL_LAYOUT['select_width'], key)
        # set_values 注入超长当前值后，宽度仍保持统一，不被撑开。
        view.set_values({'material_source': '自定义素材来源名称比选项都长'})
        self.win.update_idletasks()
        source = view.inputs['material_source']
        self.assertEqual(int(source.cget('width')), STAGE_PANEL_LAYOUT['select_width'])

    def _open_dialog(self):
        import skill_panel
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        panel.pack(fill='x')
        window = panel.open_lock_dialog()
        self.assertIsNotNone(window)
        self.win.update()
        return panel, window

    def test_lock_dialog_region_does_not_overflow_at_two_widths(self):
        # R2862：内联制作锁协调器已删，锁编辑移入弹窗；几何契约改为弹窗内不越界。
        for width in (900, 560):
            with self.subTest(width=width):
                self.win.deiconify()
                self.win.geometry('%dx800' % width)
                panel, window = self._open_dialog()
                right = window.winfo_rootx() + window.winfo_width()
                for widget in _descendants(window):
                    if widget.winfo_width() <= 1:
                        continue
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         right + 1,
                                         '子控件越出弹窗：%s' % widget)
                window.destroy()
                panel.destroy()
                self.win.withdraw()

class ProviderLabelTests(unittest.TestCase):
    def test_openai_compatible_label_and_id_round_trip(self):
        import infra.model_pool as model_pool
        self.assertEqual(model_pool.PROVIDER_LABELS['openai-compatible'], 'OpenAI 兼容接口')
        self.assertIn('openai-compatible', model_pool.PROVIDER_IDS)
        # 显示名 → id：写盘的是 id，不是中文 label。
        self.assertEqual(model_pool.id_of_label('OpenAI 兼容接口', model_pool.PROVIDERS),
                         'openai-compatible')
        # id → 兜底显示名：provider_name 兜底仍给出中文 label，而不是旧协议标签。
        self.assertEqual(model_pool.provider_name('some-model', {'provider': 'openai-compatible'}),
                         'OpenAI 兼容接口')


if __name__ == '__main__':
    unittest.main()
