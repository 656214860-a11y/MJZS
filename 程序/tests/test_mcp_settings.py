# -*- coding: utf-8 -*-
"""第 45 期：MCP 设置页里「文本模型服务商」那一栏。

用户要求：最后那一档原来叫「自定义接口」，改成「新增接口」——填完点保存就多出一条接口
（「用户保存后可以新增接口」）；下次打开这一页，保存过的接口直接能在下拉里选到，选回来
三格（地址／模型／密钥）连同它自己的密钥一起回填。运行：python test_mcp_settings.py
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import api_models
from agent import prompt_optimizer as optimizer

PRESET_NAMES = ["智谱 GLM-4.7-Flash", "OpenAI GPT", "DeepSeek"]


class FakeApp:
    """设置窗真正用到的那几样：一扇主窗、一个忙标志、一条日志口。"""

    def __init__(self, window):
        self.window = window
        self.optimizer_busy = False
        self.optimizer_settings = None
        self.log = []

    def write(self, text):
        self.log.append(str(text))


class SettingsCase(unittest.TestCase):
    """每个用例一份临时配置：绝不碰真安装目录里那份 prompt_optimizer.json。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / "prompt_optimizer.json"
        original = optimizer.CONFIG
        optimizer.CONFIG = self.config
        self.addCleanup(setattr, optimizer, "CONFIG", original)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.app = FakeApp(self.win)
        self.addCleanup(self.sweep)

    def sweep(self):
        """用例自己没关掉的设置窗，收尾时关掉，别留给下一例。"""
        sheet = getattr(self.app, "optimizer_settings", None)
        if sheet is not None:
            try:
                if sheet.winfo_exists():
                    sheet.destroy()
            except Exception:
                pass
        self.app.optimizer_settings = None

    def seed(self, values):
        self.config.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        return self.config

    def open_settings(self):
        optimizer.settings(self.app)
        sheet = self.app.optimizer_settings
        self.assertIsNotNone(sheet, "设置窗应当开得出来")
        self.win.update_idletasks()
        return sheet

    def selector(self, sheet):
        """第 0 行右边那只下拉＝文本模型服务商。"""
        return sheet.grid_slaves(row=0, column=1)[0]

    def field(self, sheet, row):
        """1 地址／2 模型／3 密钥／4 优化服务 Python／5 MCP 服务文件。"""
        return sheet.grid_slaves(row=row, column=1)[0]

    def values(self, sheet):
        return [str(item) for item in self.selector(sheet).cget("values")]

    def choose(self, sheet, name):
        selector = self.selector(sheet)
        selector.set(name)
        selector.event_generate("<<ComboboxSelected>>")
        self.win.update_idletasks()

    def fill(self, sheet, base_url, model, key):
        for row, text in ((1, base_url), (2, model), (3, key)):
            entry = self.field(sheet, row)
            entry.delete(0, "end")
            entry.insert(0, text)

    def walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def button(self, sheet, text):
        from tkinter import ttk
        for widget in self.walk(sheet, ttk.Button):
            if str(widget.cget("text")) == text:
                return widget
        raise AssertionError("设置窗里没有这颗按钮：" + text)

    def save(self, sheet):
        self.button(sheet, "保存设置").invoke()
        self.win.update_idletasks()

    def labels(self):
        """落盘那份配置里认得的模型（与「已保存模型」那一栏同一套写法）。"""
        data = json.loads(self.config.read_text(encoding="utf-8"))
        return [api_models.label(record) for record in api_models.records(data)]


class ProviderListTests(SettingsCase):
    """下拉里那几档叫什么、排在哪。"""

    def test_the_last_slot_is_named_add_interface(self):
        sheet = self.open_settings()
        self.assertEqual(optimizer.NEW_INTERFACE, "新增接口")
        self.assertNotIn("自定义接口", self.values(sheet), "老名字不再出现")
        self.assertEqual(self.values(sheet)[-1], "新增接口", "新加那一档排在最后")

    def test_the_three_official_presets_stay_in_front(self):
        sheet = self.open_settings()
        self.assertEqual(self.values(sheet)[:3], PRESET_NAMES)

    def test_a_fresh_page_starts_on_the_new_interface_slot(self):
        sheet = self.open_settings()
        self.assertEqual(self.selector(sheet).get(), optimizer.NEW_INTERFACE,
                         "没存过东西时，下拉指的就是「新增接口」")

    def test_an_official_address_keeps_its_preset_name(self):
        self.seed({"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                   "api_key": "sk-test"})
        sheet = self.open_settings()
        self.assertEqual(self.selector(sheet).get(), "DeepSeek", "官方那一档不因为存过就改名")
        self.assertNotIn("deepseek-chat · https://api.deepseek.com/v1", self.values(sheet),
                         "官方地址不算「新增接口」")


class NewInterfaceSaveTests(SettingsCase):
    """「用户保存后可以新增接口」：存一条、再存一条，都在下拉里。"""

    def test_saving_a_new_interface_puts_it_in_the_list(self):
        sheet = self.open_settings()
        self.choose(sheet, optimizer.NEW_INTERFACE)      # 三格清空＝从零填一条新接口
        self.assertEqual([self.field(sheet, row).get() for row in (1, 2, 3)], ["", "", ""])
        self.fill(sheet, "https://api.example.com/v1", "example-chat", "sk-test")
        self.save(sheet)
        self.assertEqual(self.labels(), ["example-chat · https://api.example.com/v1"],
                         "保存后这条接口进了「已保存模型」")
        again = self.open_settings()
        self.assertEqual(self.selector(again).get(), "example-chat · https://api.example.com/v1",
                         "下次打开就能选到它")

    def test_a_second_new_interface_lands_beside_the_first(self):
        first = self.open_settings()
        self.choose(first, optimizer.NEW_INTERFACE)
        self.fill(first, "https://api.example.com/v1", "example-chat", "sk-test")
        self.save(first)
        second = self.open_settings()
        self.choose(second, optimizer.NEW_INTERFACE)
        self.fill(second, "https://api.mine.example/v2", "mine-chat", "sk-mine")
        self.save(second)
        self.assertEqual(self.labels(), ["example-chat · https://api.example.com/v1",
                                         "mine-chat · https://api.mine.example/v2"])
        again = self.open_settings()
        self.assertIn("example-chat · https://api.example.com/v1", self.values(again))
        self.assertIn("mine-chat · https://api.mine.example/v2", self.values(again))

    def test_picking_a_saved_interface_brings_its_own_key_back(self):
        self.seed({"base_url": "https://api.example.com/v1", "model": "example-chat",
                   "api_key": "sk-test"})
        sheet = self.open_settings()
        label = "example-chat · https://api.example.com/v1"
        self.assertEqual(self.selector(sheet).get(), label, "打开就认得出这是保存过的接口")
        self.choose(sheet, PRESET_NAMES[0])
        self.assertEqual(self.field(sheet, 1).get(), "https://open.bigmodel.cn/api/paas/v4/")
        self.choose(sheet, label)
        self.assertEqual([self.field(sheet, row).get() for row in (1, 2, 3)],
                         ["https://api.example.com/v1", "example-chat", "sk-test"],
                         "选回来的是整条记录，密钥不串到别家去")

    def test_deleting_a_model_takes_it_out_of_the_provider_list(self):
        self.seed({"base_url": "https://api.example.com/v1", "model": "example-chat",
                   "api_key": "sk-test"})
        sheet = self.open_settings()
        label = "example-chat · https://api.example.com/v1"
        self.assertIn(label, self.values(sheet))
        original = optimizer.messagebox.askyesno
        optimizer.messagebox.askyesno = lambda *args, **kwargs: True
        self.addCleanup(setattr, optimizer.messagebox, "askyesno", original)
        self.button(sheet, "删除模型").invoke()
        self.win.update_idletasks()
        self.assertNotIn(label, self.values(sheet), "删掉的接口不该还留在服务商下拉里")
        self.assertEqual(self.selector(sheet).get(), optimizer.NEW_INTERFACE, "下拉回到「新增接口」")
        self.assertEqual(self.labels(), [])
        again = self.open_settings()
        self.assertNotIn(label, self.values(again))


if __name__ == "__main__":
    unittest.main(verbosity=2)
