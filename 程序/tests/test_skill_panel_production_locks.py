"""R1483 制作锁控件依赖与窄窗布局。"""
import unittest
from skip_reasons import PLATFORM_TK_DISPLAY


class ProductionLockViewTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.win = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.addCleanup(self.win.destroy)

    def test_controls_dependency_defaults_and_wrapping(self):
        from production_lock_fields import ProductionLockFields
        self.win.geometry('480x700')
        view = ProductionLockFields(self.win)
        view.pack(fill='x')
        self.win.update()
        self.assertEqual(len(view.inputs), 11)
        self.assertEqual(view.inputs['track'].get(), '')
        # 契约变更：必填缺失不再占一行文字提示、也不再染标签警示色，改为悬停卡片「必填」（R2480）。
        self.assertEqual(str(view.fields['track']['label'].cget('foreground')), '')
        self.assertEqual(view.hints['track'].text, '必填')
        self.assertTrue(view.inputs['reference_mode'].instate(['disabled']))
        view.set_values({'video_model_version': 'Seedance 2.5'})
        self.win.update()
        self.assertFalse(view.inputs['reference_mode'].instate(['disabled']))
        self.assertEqual(view.inputs['reference_mode'].get(), '全能参考模式')
        ys = {child.winfo_y() for child in view.winfo_children()}
        self.assertGreater(len(ys), 1)
        for child in view.winfo_children():
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), view.winfo_width())
        view.set_values({'video_model_version': 'Seedance 2.0'})
        self.assertTrue(view.inputs['reference_mode'].instate(['disabled']))
        self.assertEqual(view.hints['reference_mode'].text, '仅 Seedance 2.5')
