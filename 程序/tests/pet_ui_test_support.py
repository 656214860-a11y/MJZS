# -*- coding: utf-8 -*-
"""test_pet_ui 拆分出的共享测试夹具与替身（C09 结构治理：内容自 tests/test_pet_ui.py 原样迁入）。"""
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if PROGRAM not in sys.path:
    sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from skip_reasons import PLATFORM_TKINTER
import pet_bus
import stage_flow
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)


def make_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": []},
                                                               ensure_ascii=False), encoding="utf-8")
    return proj


class _Event:
    """最小事件替身：只带一个 widget，用来验证别认领子组件冒泡上来的事件。"""

    def __init__(self, widget):
        self.widget = widget


class _Point:
    """只带 y 的点击替身：猫爪按钮按 y 落在第几只爪上来选档（竖向排列）。"""

    def __init__(self, y):
        self.y = y


class _Wheel:
    """最小滚轮事件替身：只带一个 delta（往下滚是负）。"""

    def __init__(self, delta):
        self.delta = delta


class SequenceRand:
    """按给定序列出数的假随机源：用例要的是可复现，不是真随机（第 17 期猫样用）。"""

    def __init__(self, values=(0.0,)):
        self.values = [float(value) for value in values] or [0.0]
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class _Registry:
    """最小项目登记表替身：只有一个 .info（与 projects.Projects 那一份同形）。"""

    def __init__(self, active, projects):
        self.info = {'active': active, 'projects': list(projects)}


class FakeDesktop:
    """最小宿主：只提供贴片真正用到的几个容器与开关，避免为了画宠物去建整个应用。"""

    def __init__(self, tk, ttk, win):
        self.win = win
        self.root = None
        self.shutting_down = False
        self.kicks = []
        self.pages = []          # pet_goto 切过哪几步
        self.advances = []       # pet_advance 叫醒过哪几步
        self.deaf = ()           # 放进这里的阶段：pet_advance 一律说「没有这条路」
        self.title_row = ttk.Frame(win)
        self.title_row.pack(fill="x")
        self.body = ttk.Frame(win)
        self.body.pack(fill="both", expand=True)
        # 第 R2933 期：三虎簇的真实宿主是侧栏底栏 pet_dock（pet_layer 指向它）；
        # 假宿主给同一对属性，让用例走和真 Desktop 一样的承载路径。
        # settings_gear_layer 也要有：没有它齿轮会退回 pet_dock，把猫爪命中区挤掉。
        self.settings_gear_layer = ttk.Frame(win)
        self.settings_gear_layer.pack(side="bottom", fill="x")
        self.pet_dock = ttk.Frame(win, height=pet_ui.DOCK_ROOM)
        self.pet_dock.pack(side="bottom", fill="x")
        self.pet_dock.pack_propagate(False)
        self.pet_layer = self.pet_dock
        self.header_status = ttk.Label(self.title_row, text="就绪")
        self.header_status.pack(side="right")
        self.header_model = ttk.Label(self.title_row, text="模型")
        self.header_model.pack(side="right")
        self.status = tk.StringVar(master=win, value="就绪")

    def kick_unattended(self, source):
        self.kicks.append(source)

    def pet_goto(self, stage):
        """第 23 期接缝：切页。记下切到哪一步，回一句页面名。"""
        self.pages.append(stage)
        return pet_bus.STAGE_NAMES.get(stage, '')

    def pet_advance(self, stage):
        """第 23 期接缝：把某一步提前叫醒一轮；deaf 里的阶段一律答「没有这条路」。"""
        if stage in self.deaf:
            return ''
        self.advances.append(stage)
        return '已把「%s」这一步提前叫醒一轮' % pet_bus.STAGE_NAMES.get(stage, stage)

    def asset_base(self):
        return self.root / "episode"


class PetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        # 分片 worker 会复用进程；前一个用例的自动链阻塞不属于新项目。
        previous_auto = stage_flow.AUTO
        stage_flow.AUTO = stage_flow.Auto()
        self.addCleanup(setattr, stage_flow, 'AUTO', previous_auto)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeDesktop(self.tk, self.ttk, self.win)
        self.fake.root = make_project(self.tmp.name)
        # window／tray／toast=False：这些都默认开（第 16 期起），自检一律显式关掉，
        # 免得用例去碰真托盘图标、真浮窗，跑起来还得看本机配置。
        self.pet = pet_ui.attach(self.fake, autostart=False)
        # 一键执行前会弹确认框：用例里换成「一律点头」的假函数，不弹真窗也不卡住用例。
        self.pet.asker = lambda title, text: True
        # 第 43 期：模型池／三虎设置都落在这个临时目录里，自检绝不碰真安装目录的配置。
        self.pet.program = Path(self.tmp.name)
        # 真实退出先由宿主停止宠物、再销毁 Tk 根窗；用例也保持相同顺序，
        # 否则根窗抢先清 Tcl 命令会把仍在队列里的定位重试误报成 Tcl 生命周期错误。
        self.addCleanup(self.pet.stop)
        self.addCleanup(self.win.destroy)

    def wait_for_the_reply(self, cloud, timeout=5.0):
        """等后台那句回完再收工（用 `addCleanup` 挂在 submit 的用例上）。

        `cloud.submit()` 只是把这句话交给后台线程去想；那句话没命中规则表时会真的问一次
        模型，并把诊断事件写进 `<项目>/model_diagnostics/`。线程不许抢在
        `TemporaryDirectory.cleanup` 前面动那个目录，否则清理会撞上
        `OSError [WinError 145]`／`PermissionError [WinError 32]`。
        `addCleanup` 后进先出，用例里注册的这条排在 `setUp` 里那条 `tmp.cleanup` 之后，
        所以会先执行。超时不静默吞：没回完就直接让用例失败，说明后台还在写。
        """
        if cloud is None:
            return
        deadline = time.time() + timeout
        while time.time() < deadline and cloud.busy:
            cloud.drain()
            time.sleep(0.01)
        if cloud.busy:
            self.fail('后台那句 %.0f 秒内没回完：临时目录还在被它写，不能就这样收工' % timeout)

    def pad_of(self, widget):
        return [int(float(item)) for item in re.findall(r"-?\d+\.?\d*", str(widget.cget("padding")))]


class FakeWinreg:
    """假注册表：只实现 Autostart 用到的那几个名字与函数，真注册表一行都不碰。"""

    HKEY_CURRENT_USER = 'HKCU'
    KEY_READ, KEY_SET_VALUE, REG_SZ = 1, 2, 3

    def __init__(self, fail_read=False, fail_write=False):
        self.values = {}
        self.fail_read = fail_read
        self.fail_write = fail_write

    def OpenKey(self, root, key, reserved, access):
        if self.fail_read:
            raise OSError('读不回来')
        return _Handle(self)

    def CreateKeyEx(self, root, key, reserved, access):
        if self.fail_write:
            raise OSError('写不进去')
        return _Handle(self)

    def QueryValueEx(self, handle, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, handle, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, handle, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        self.values.pop(name)


class _Handle:
    """注册表句柄：Autostart 用 with 打开，这里只负责进出。"""

    def __init__(self, api):
        self.api = api

    def __enter__(self):
        return self.api

    def __exit__(self, *exc):
        return False
