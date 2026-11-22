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
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from contract import api_models
from agent import prompt_optimizer as optimizer
import infra.model_secrets as model_secrets

PRESET_NAMES = ["智谱 GLM-4.7-Flash", "OpenAI GPT", "DeepSeek"]


def use_fake_protector(case):
    """换掉 Windows 加密：用例只看密钥去了哪儿，不依赖执行进程的用户配置文件。"""
    original = model_secrets.PROTECTOR
    case.addCleanup(setattr, model_secrets, "PROTECTOR", original)
    model_secrets.PROTECTOR = lambda data, decrypt=False, label="": (
        bytes(data)[len(b"enc:"):] if decrypt else b"enc:" + bytes(data))


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
        use_fake_protector(self)
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
        return self.form_body(sheet).grid_slaves(row=0, column=1)[0]

    def field(self, sheet, row):
        """1 地址／2 模型／3 密钥／4 优化服务 Python／5 MCP 服务文件。"""
        return self.form_body(sheet).grid_slaves(row=row, column=1)[0]

    def form_body(self, sheet):
        """设置项可放在统一 Card 内，测试只依赖其行列语义。"""
        return next(child for child in sheet.winfo_children()
                    if child.grid_slaves(row=0, column=1))

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
        original = optimizer.ask_confirmation
        optimizer.ask_confirmation = lambda *args, **kwargs: True
        self.addCleanup(setattr, optimizer, "ask_confirmation", original)
        self.button(sheet, "删除模型").invoke()
        self.win.update_idletasks()
        self.assertNotIn(label, self.values(sheet), "删掉的接口不该还留在服务商下拉里")
        self.assertEqual(self.selector(sheet).get(), optimizer.NEW_INTERFACE, "下拉回到「新增接口」")
        self.assertEqual(self.labels(), [])
        again = self.open_settings()
        self.assertNotIn(label, self.values(again))


class KeyAtRestTests(SettingsCase):
    """密钥不再明文写进设置文件：保存、搬家、留空沿用、删除后清掉。"""
    URL = "https://api.example.com/v1"
    OTHER = "https://api.other.example/v1"

    def file_text(self):
        return self.config.read_text(encoding="utf-8")

    def stored(self, url):
        return model_secrets.load(optimizer.key_name_for(url), root=self.tmp.name)

    def confirm_deletion(self):
        original = optimizer.ask_confirmation
        optimizer.ask_confirmation = lambda *args, **kwargs: True
        self.addCleanup(setattr, optimizer, "ask_confirmation", original)

    def test_saving_keeps_the_key_out_of_the_settings_file(self):
        sheet = self.open_settings()
        self.choose(sheet, optimizer.NEW_INTERFACE)
        self.fill(sheet, self.URL, "example-chat", "sk-test")
        self.save(sheet)
        self.assertNotIn("sk-test", self.file_text(), "设置文件里不该再有密钥原文")
        self.assertEqual(self.stored(self.URL), "sk-test", "密钥进了本机加密存储")
        self.assertTrue(model_secrets.path(optimizer.key_name_for(self.URL), root=self.tmp.name).is_file(),
                        "加密存储跟着设置文件落在临时目录里")

    def test_opening_settings_moves_an_old_plain_key_into_the_store(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-test"})
        sheet = self.open_settings()
        self.assertNotIn("sk-test", self.file_text(), "一打开设置，老的明文密钥就该搬走")
        self.assertEqual(self.stored(self.URL), "sk-test")
        self.assertEqual(self.field(sheet, 3).get(), "sk-test", "密钥格照旧回填")

    def test_a_blank_key_box_keeps_the_saved_key(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-test"})
        sheet = self.open_settings()
        self.fill(sheet, self.URL, "example-chat-2", "")
        self.save(sheet)
        self.assertEqual(self.stored(self.URL), "sk-test", "留空＝沿用这个地址已保存的密钥")
        self.assertIn("example-chat-2 · " + self.URL, self.labels())
        self.assertNotIn("sk-test", self.file_text())

    def test_a_new_address_without_a_key_is_refused(self):
        sheet = self.open_settings()
        self.choose(sheet, optimizer.NEW_INTERFACE)
        self.fill(sheet, self.OTHER, "other-chat", "")
        shown = []
        original = optimizer.notify
        optimizer.notify = lambda *args, **kwargs: shown.append(args[1])
        self.addCleanup(setattr, optimizer, "notify", original)
        self.save(sheet)
        self.assertEqual(shown, ["新地址需要填写对应密钥，不会复用视频密钥"])
        self.assertFalse(self.config.is_file(), "被拒绝时什么都不落盘")
        self.assertEqual(self.stored(self.OTHER), "")

    def test_deleting_the_last_model_of_an_address_forgets_its_key(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "",
                   "model_profiles": [
                       {"base_url": self.URL, "model": "example-chat", "api_key": "sk-test"},
                       {"base_url": self.OTHER, "model": "other-chat", "api_key": "sk-other"}]})
        sheet = self.open_settings()
        self.assertEqual(self.stored(self.OTHER), "sk-other", "先确认两把密钥都搬进去了")
        self.fill(sheet, self.OTHER, "other-chat", "")
        self.confirm_deletion()
        self.button(sheet, "删除模型").invoke()
        self.win.update_idletasks()
        self.assertEqual(self.stored(self.OTHER), "", "这个地址没有模型在用了，密钥一并删掉")
        self.assertEqual(self.stored(self.URL), "sk-test", "当前在用的地址，密钥留着")

    def test_deleting_the_model_of_the_address_in_use_keeps_its_key(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-test"})
        sheet = self.open_settings()
        self.confirm_deletion()
        self.button(sheet, "删除模型").invoke()
        self.win.update_idletasks()
        self.assertEqual(self.labels(), [])
        self.assertEqual(self.stored(self.URL), "sk-test", "地址还填在当前设置里，密钥不删")


class KeyStoreTests(unittest.TestCase):
    """不用开窗口的那一半：密钥叫什么、老文件怎么搬、开始优化时读到什么、交给子进程的是哪几项。"""
    URL = "https://api.example.com/v1"
    OTHER = "https://api.other.example/v1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / "prompt_optimizer.json"
        original = optimizer.CONFIG
        optimizer.CONFIG = self.config
        self.addCleanup(setattr, optimizer, "CONFIG", original)
        use_fake_protector(self)

    def seed(self, values):
        self.config.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")

    def file_text(self):
        return self.config.read_text(encoding="utf-8")

    def stored(self, url):
        return model_secrets.load(optimizer.key_name_for(url), root=self.tmp.name)

    def test_key_names_are_per_address_and_file_safe(self):
        pattern = r"^OPTIMIZER_[0-9A-Z_]+_[0-9a-f]{8}_KEY$"
        name = optimizer.key_name_for(self.URL)
        self.assertRegex(name, pattern)
        self.assertEqual(name, optimizer.key_name_for(self.URL + "/"), "末尾斜杠不算两个地址")
        self.assertNotEqual(name, optimizer.key_name_for("https://api.example.com/v2"), "路径不同是两个地址")
        self.assertNotEqual(name, optimizer.key_name_for(self.OTHER))
        self.assertRegex(optimizer.key_name_for("不是网址"), pattern, "认不出主机名也给得出能当文件名的名字")
        self.assertEqual(model_secrets.safe_name(name), name)

    def test_migration_moves_every_plain_key_and_blanks_the_file(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-top",
                   "profiles": {self.URL: {"base_url": self.URL, "model": "example-chat",
                                           "api_key": "sk-old"}},
                   "model_profiles": [{"base_url": self.OTHER, "model": "other-chat",
                                       "api_key": "sk-other"}]})
        cfg = optimizer.load_config()
        for plain in ("sk-top", "sk-old", "sk-other"):
            self.assertNotIn(plain, self.file_text())
        self.assertEqual(self.stored(self.URL), "sk-top", "同一个地址有多份时以顶层那一份为准")
        self.assertEqual(self.stored(self.OTHER), "sk-other")
        self.assertEqual(cfg["api_key"], "")
        self.assertEqual(optimizer.load_config(), cfg, "再读一遍不再变")

    def test_migration_keeps_a_key_already_in_the_store(self):
        model_secrets.save(optimizer.key_name_for(self.URL), "sk-new", root=self.tmp.name)
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-stale"})
        optimizer.load_config()
        self.assertEqual(self.stored(self.URL), "sk-new", "加密存储里已有的，不被老文件里的覆盖")
        self.assertNotIn("sk-stale", self.file_text())

    def test_a_key_the_store_refuses_stays_in_the_file(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-test"})
        with patch.object(model_secrets, "PROTECTOR", side_effect=OSError("x")):
            cfg = optimizer.load_config()
        self.assertEqual(cfg["api_key"], "sk-test", "存不进去就原样留着，不丢用户的密钥")
        self.assertIn("sk-test", self.file_text())
        optimizer.load_config()
        self.assertEqual(self.stored(self.URL), "sk-test", "下次能存了再搬")
        self.assertNotIn("sk-test", self.file_text())

    def test_starting_reads_the_key_from_the_store(self):
        self.seed({"base_url": self.URL, "model": "example-chat", "api_key": "sk-test", "server": "s.py"})
        cfg, secret, missing = optimizer.ready_config()
        self.assertEqual((secret, missing), ("sk-test", []))
        self.assertEqual(cfg["api_key"], "", "读出来的设置里不带密钥")
        model_secrets.clear(optimizer.key_name_for(self.URL), root=self.tmp.name)
        self.assertEqual(optimizer.ready_config()[1:], ("", ["api_key"]), "密钥没了要报缺 api_key")

    def test_the_bridge_gets_only_the_fields_it_uses(self):
        cfg = {"base_url": self.URL, "model": "example-chat", "server": "s.py", "python": "p.exe",
               "profiles": {self.OTHER: {"api_key": "sk-elsewhere"}}, "deleted_models": []}
        self.assertEqual(optimizer.bridge_payload(cfg, "sk-test", "原提示词", "要求"),
                         {"base_url": self.URL, "model": "example-chat", "server": "s.py",
                          "api_key": "sk-test", "prompt": "原提示词", "instructions": "要求"})


class OptimizerHomeTests(unittest.TestCase):
    """R3029 P3：优化器工具链根目录跟随全局下载根，不再写死 D: 盘。"""

    def test_home_follows_configured_downloads_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'config.json').write_text(
                json.dumps({'downloads_root': 'E:/我的下载'}), encoding='utf-8')
            with patch.object(optimizer, 'ROOT', root):
                self.assertEqual(optimizer._optimizer_home(),
                                 Path('E:/我的下载') / 'PromptOptimizer')

    def test_home_falls_back_to_default_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(optimizer, 'ROOT', Path(td)):
                self.assertEqual(optimizer._optimizer_home(),
                                 Path('D:/漫剧下载') / 'PromptOptimizer')


if __name__ == "__main__":
    unittest.main(verbosity=2)
