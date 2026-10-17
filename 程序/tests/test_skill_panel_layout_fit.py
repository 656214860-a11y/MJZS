"""R1684 阶段配置页：制作锁下拉自适应宽度、总控＋制作锁区域布局与厂商显示名回归。"""
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
        # 每个可编辑锁（state='normal'）宽度 = 选项最长项显示宽度（CJK 按 2 计），封顶。
        for key, entry in view.inputs.items():
            self.assertLessEqual(int(entry.cget('width')), COMBOBOX_MAX_WIDTH, key)
            self.assertEqual(int(entry.cget('width')),
                             SelectBox._fit_width(tuple(entry.cget('values')), entry.get()), key)
        # 交付形态最长项「只要 markdown 文档」显示宽 18，超出旧固定宽 12 也能完整自适应。
        delivery = view.inputs['delivery_format']
        self.assertEqual(int(delivery.cget('width')),
                         SelectBox._fit_width(tuple(delivery.cget('values'))))
        # set_values 注入超过选项的最长当前值后，宽度按当前值重算。
        view.set_values({'material_source': '自定义素材来源名称比选项都长'})
        self.win.update_idletasks()
        source = view.inputs['material_source']
        self.assertEqual(int(source.cget('width')),
                         SelectBox._fit_width(tuple(source.cget('values')), source.get()))

    def _build_panel(self):
        import skill_panel
        import stage_config
        import workflow_settings
        name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.desktop.root, {'name': name,
            'lock': {name: {'aspect_ratio': '9:16'}}})
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        panel.pack(fill='x')
        panel.toggle_optional_locks()          # 展开选填锁，覆盖完整区域
        return panel

    def test_coordinator_region_does_not_overflow_at_two_widths(self):
        for width in (900, 560):
            with self.subTest(width=width):
                self.win.deiconify()
                self.win.geometry('%dx800' % width)
                panel = self._build_panel()
                self.win.update()
                coordinator = panel.new_lock_row.master
                self.assertIs(coordinator, panel.optional_lock_row.master)
                right = coordinator.winfo_rootx() + coordinator.winfo_width()
                for widget in _descendants(coordinator):
                    if widget.winfo_width() <= 1:
                        continue
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         right + 1,
                                         '子控件越出面板：%s' % widget)
                for row in (panel.lock_row, panel.new_lock_row, panel.optional_lock_row):
                    self._assert_no_overlap_in_row(row)
                panel.destroy()
                self.win.withdraw()

    def _assert_no_overlap_in_row(self, row):
        children = [c for c in row.winfo_children() if c.winfo_width() > 1]
        by_row = {}
        for child in children:
            by_row.setdefault(child.winfo_rooty(), []).append(child)
        for _y, group in by_row.items():
            spans = sorted((c.winfo_rootx(), c.winfo_rootx() + c.winfo_width())
                           for c in group)
            for (l0, r0), (l1, _r1) in zip(spans, spans[1:]):
                self.assertLessEqual(r0, l1 + 1, '同一行相邻控件 x 范围重叠：%r' % spans)


class ProviderLabelTests(unittest.TestCase):
    def test_openai_compatible_label_and_id_round_trip(self):
        import model_pool
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
