"""副屏回归：软件放在副屏时，悬停卡片与三虎聊天框不得被主屏尺寸拽回主屏。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pet_cloud as pc
from ui_widgets import Tooltip

SECOND = (1920, 0, 3840, 1080)      # 副屏在主屏右侧


class _Tip:
    def overrideredirect(self, value): pass
    def configure(self, **kwargs): pass
    def geometry(self, value): self.geometry_value = value
    def unbind(self, *_args): pass
    def attributes(self, *_args): pass
    def update_idletasks(self): pass
    def winfo_reqwidth(self): return 300
    def winfo_reqheight(self): return 100
    def winfo_screenwidth(self): return 1920      # 主屏尺寸：副屏上绝不能拿它当边界
    def winfo_screenheight(self): return 1080
    def winfo_exists(self): return True
    def withdraw(self): pass
    def destroy(self): pass


class _Label:
    def __init__(self, *_a, **_k): pass
    def pack(self, **_k): pass


class _Widget:
    def bind(self, *_a, **_k): pass
    def after(self, *_a): return "job"
    def winfo_exists(self): return True
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0


class TooltipSecondMonitorTests(unittest.TestCase):
    def show_at(self, x, y):
        tooltip = Tooltip(_Widget(), "完整文件名")
        tooltip._position = (x, y)
        tip = _Tip()
        with patch("ui_widgets.tk.Toplevel", return_value=tip), patch("ui_widgets.tk.Label", _Label), \
             patch("ui_tooltip.monitor_bounds", return_value=SECOND):
            tooltip.show()
        return tip.geometry_value

    def test_card_stays_on_second_monitor(self):
        self.assertEqual(self.show_at(3000, 200), "+3000+200")

    def test_card_clamps_to_second_monitor_right_edge(self):
        self.assertEqual(self.show_at(3800, 200), "+3540+200")

    def test_card_flips_up_at_second_monitor_bottom(self):
        x, y = self.show_at(3000, 1050).lstrip("+").split("+")
        self.assertEqual(x, "3000")
        self.assertLess(int(y), 1050)


class CloudSecondMonitorTests(unittest.TestCase):
    def cloud(self, patch_rect):
        c = pc.Cloud.__new__(pc.Cloud)
        c.parent = SimpleNamespace(winfo_rootx=lambda: 2000, winfo_rooty=lambda: 100,
                                   winfo_width=lambda: 1700, winfo_height=lambda: 900)
        c.win = SimpleNamespace()
        c.shape = pc.SHAPE_CLOUD
        c._body = 120
        c._down = False
        c.width = lambda: 300
        c.total_width = lambda: 346
        c._patch_rect = lambda: patch_rect
        c._anchor = lambda: (patch_rect[0] + 20.0, patch_rect[1] + 40.0)
        c._bottom = lambda: patch_rect[1] + patch_rect[3] + pc.ANCHOR_DROP
        return c

    def test_cloud_origin_stays_on_second_monitor(self):
        c = self.cloud((3600, 700, 64, 64))
        with patch("pet_cloud_place.monitor_bounds", return_value=SECOND):
            left, _top = c._origin()
        self.assertGreaterEqual(left, SECOND[0])
        self.assertLessEqual(left + c.total_width(), SECOND[2])
        self.assertLess(left, 3600)           # 仍在三虎左边

    def test_cloud_not_clamped_to_primary_width(self):
        c = self.cloud((3000, 700, 64, 64))
        with patch("pet_cloud_place.monitor_bounds", return_value=SECOND):
            left, _top = c._origin()
        self.assertGreater(left, 1920)        # 旧行为：按主屏宽度钳到 ≤1920

    def test_cloud_respects_second_monitor_left_edge(self):
        c = self.cloud((2100, 700, 64, 64))
        with patch("pet_cloud_place.monitor_bounds", return_value=SECOND):
            left, _top = c._origin()
        self.assertGreaterEqual(left, SECOND[0] + pc.MARGIN)


if __name__ == "__main__":
    unittest.main()
