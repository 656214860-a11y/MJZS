# -*- coding: utf-8 -*-
"""「设置」窗口与齿轮入口的自检（第 44 期）。

用户这一轮的要求落在这几条上：
- 「三虎设置」改名「设置」，入口做成齿轮摆到窗口左上角标题（V0.7）旁边，醒目；
- 点开分五格：基础功能／三虎模型配置／自动化等级／预算／开发信息（附件里的 SKILL 管理不做）；
  第 47 期第 8 条：预算右边补上「开发信息」（版本、开发者 Bill Lai 与邮箱）；
- 「基础」这一格叫「基础功能」，「模型」那一格叫「三虎模型配置」（第 46 期第 6 条改名）；
- 预算新增一页：Token 日／生图 每项目／视频 每项目这类硬限制，改完落盘并立刻生效。

这里只建最小的假桌面（贴片真正用到的那几个容器），另加一条真 Desktop 的接缝用例验齿轮真的
挂在左上角那一行上。运行：python test_pet_settings.py
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
import threading
import unittest
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

import desktop
import model_secrets
import infra.model_pool as model_pool
import infra.project_settings as project_settings
import pet_agent
import pet_models_ui
import pet_settings_ui
import ui.pet_ui as pet_ui
# 第 45 期：这些用例读的（并会写的）是全局配置目录里那一份三虎设置。原来 program 指向本机真
# 安装目录，于是「出厂默认档是半自动」这类断言会被用户机上那份配置左右（那里存过 hint 就红）。
# 指到沙盒目录：读不到真配置，也写不脏真安装目录（见 selftest_sandbox 的说明）。
import selftest_sandbox
selftest_sandbox.isolate(pet_ui)
from orchestrator import skill_budget
from ui_tokens import CHAR_WIDTH


def make_project(td):
    """一个最小项目目录：贴片与预算账本都用得到的那几个文件。"""
    proj = Path(td) / "p"
    (proj / "episode").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    return proj


class _Event:
    def __init__(self, widget):
        self.widget = widget


class _Registry:
    """假注册表：只记一个 Run 项，够验开机自启开／关。"""

    def __init__(self, values=None):
        self.values = dict(values or {})

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 1
    KEY_READ = 1
    REG_SZ = 1

    def OpenKey(self, root, key, reserved, access):
        if self.values:
            return self
        raise FileNotFoundError(key)

    def CreateKeyEx(self, root, key, reserved, access):
        return self

    def QueryValueEx(self, handle, name):
        if name in self.values:
            return self.values[name], self.REG_SZ
        raise FileNotFoundError(name)

    def SetValueEx(self, handle, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, handle, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        self.values.pop(name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeDesktop:
    """最小宿主：贴片真正用到的容器与开关；另给一行左上角的标题行（齿轮挂在那儿）。"""

    def __init__(self, tk, ttk, win):
        self.win = win
        self.root = None
        self.shutting_down = False
        self.kicks = []
        self.closed = 0
        self.title_row = ttk.Frame(win)
        self.title_row.pack(fill='x')
        self.body = ttk.Frame(win)
        self.body.pack(fill='both', expand=True)
        self.header_status = ttk.Label(self.title_row, text='就绪')
        self.header_status.pack(side='right')
        self.header_model = ttk.Label(self.title_row, text='模型')
        self.header_model.pack(side='right')
        self.sidebar_head = ttk.Frame(win)
        self.sidebar_head.pack(fill='x')
        self.status = tk.StringVar(master=win, value='就绪')

    def kick_unattended(self, source):
        self.kicks.append(source)

    def asset_base(self):
        return self.root / 'episode'

    def close(self):
        self.closed += 1
        return True


class SettingsCase(unittest.TestCase):
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
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # 每例在 attach 读取设置前就隔离 program；复用 worker 的进程沙盒可能已有旧档位。
        program_patch = mock.patch.object(pet_ui, 'PROGRAM', Path(self.tmp.name))
        program_patch.start()
        self.addCleanup(program_patch.stop)
        self.fake = FakeDesktop(self.tk, self.ttk, self.win)
        self.fake.root = make_project(self.tmp.name)
        self.pet = pet_ui.attach(self.fake, autostart=False)
        self.pet.asker = lambda title, text: True
        self.pet.program = Path(self.tmp.name)
        self.addCleanup(self.win.destroy)

    def hub(self, tab=None):
        win = self.pet.open_settings(tab)
        self.addCleanup(win.destroy)
        return win

    def selected(self, win):
        """第 48 期第 1 条：分页头换成按钮行，亮着哪一格读 win._pet_tab。"""
        key = pet_settings_ui.current(win)
        return dict(pet_settings_ui.TABS)[key] if key else ''

    def walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found


class ManagerGeometryTests(unittest.TestCase):
    """第 52 期第 1 条：模型管理窗比主界面小一圈、落在主界面正中。

    第 65 期任务 5：用户要「模型池内容框优先显示全部内容」，比例 80% → 90%、
    上限长高到 1180x860，下面的数字跟着改。R2405 方案 B：比例统一为
    ui_tokens.OVERLAY_RATIO，去掉绝对上限（cap=None），下限先被主界面封顶，弹窗永不
    超界。R2411：比例调至 1.0，弹窗尺寸＝主界面（视觉上像切换页面，用户拍板）。
    """

    class Parent(object):
        """够 fit_to_main 用的假主界面：位置与大小都给死。"""

        def __init__(self, width, height, left=100, top=50):
            self.size = (width, height); self.at = (left, top)

        def update_idletasks(self): pass

        def winfo_width(self): return self.size[0]

        def winfo_height(self): return self.size[1]

        def winfo_rootx(self): return self.at[0]

        def winfo_rooty(self): return self.at[1]

    class Window(object):
        """假窗口：只记下 fit_to_main 最后摆的那个 geometry。"""

        def __init__(self): self.geometry_value = ''

        def geometry(self, value=None):
            if value is not None: self.geometry_value = str(value)
            return self.geometry_value

    def fit(self, parent):
        win = self.Window()
        pet_models_ui.fit_to_main(win, parent, pet_models_ui.MANAGER_GEOMETRY)
        return win.geometry_value

    def test_the_window_covers_the_main_one_exactly_and_centred(self):
        said = self.fit(self.Parent(1200, 700))
        self.assertEqual(said, '1200x700+100+50', '主界面的 100%，完全覆盖主界面')
        self.assertEqual(1200, 1200); self.assertEqual(700, 700)

    def test_a_big_main_window_stays_a_fixed_ratio_not_an_absolute_cap(self):
        self.assertEqual(self.fit(self.Parent(1600, 1000, left=0, top=0)), '1600x1000+0+0',
                         '去掉绝对上限后，超大屏也严格等于主界面，不再被 1180 封顶')

    def test_a_main_window_that_is_too_small_keeps_the_floor(self):
        self.assertEqual(self.fit(self.Parent(940, 640)), '940x640+100+50',
                         '弹窗恒等于主界面，不超界不骤缩')

    def test_a_main_window_that_cannot_be_measured_falls_back(self):
        self.assertEqual(self.fit(self.Parent(1, 1)), pet_models_ui.MANAGER_GEOMETRY)
        self.assertEqual(self.fit(None), pet_models_ui.MANAGER_GEOMETRY)


class GearTests(SettingsCase):
    """齿轮入口（第 R2933 期：Fluent settings 图标，与导航同套字形；PNG 缺失退回手绘齿轮）。"""

    def test_the_gear_hangs_on_the_hosts_fallback_row(self):
        """假宿主没有 settings_gear_layer／pet_dock 时，齿轮退回 sidebar_head 那一行。"""
        gear = self.pet.gear
        self.assertIsNotNone(gear, '贴片一起来的那颗齿轮')
        self.assertEqual(str(gear.canvas.winfo_parent()), str(self.fake.sidebar_head),
                         '缺底栏承载层时挂在宿主给的兜底行上')
        self.assertEqual(gear.tip_text, pet_ui.GEAR_TIP)

    def test_no_caption_sits_beside_the_gear(self):
        """第 45 期：齿轮旁边那句「设置」删掉了（侧栏里放不下，整句被裁得只剩半截）。"""
        gear = self.pet.gear
        self.assertFalse(hasattr(gear, "tip"), "齿轮不再自带那颗文字标签")
        texts = [str(child.cget("text")) for child in self.fake.sidebar_head.winfo_children()
                 if "text" in child.keys()]
        self.assertNotIn(pet_ui.GEAR_TIP, texts, "那一句不再挂在齿轮旁边")
        self.assertEqual(gear.tip_text, pet_ui.GEAR_TIP, "那句话只留在提示文本里")

    def test_the_gear_is_really_drawn_like_a_gear(self):
        """PNG 在时画 Fluent settings 图标；强制无图时手绘齿轮三件套仍要在。"""
        gear = self.pet.gear
        gear.draw()
        if gear._gear_image() is not None:
            self.assertTrue(gear.canvas.find_withtag('gear-icon'),
                            'settings.png 在时画的是图标字形')
        original = gear._gear_image
        gear._gear_image = lambda: None
        try:
            gear.draw()
            tags = gear.canvas.find_withtag('gear')
            self.assertEqual(len(tags), 3)
            self.assertTrue(gear.canvas.find_withtag('gear-teeth'), '有齿')
            self.assertTrue(gear.canvas.find_withtag('gear-hole'), '中间挖了孔')
            body = gear.canvas.find_withtag('gear-body')[0]
            self.assertEqual(gear.canvas.itemcget(body, 'fill'), pet_ui.GEAR_COLOR[0])
        finally:
            gear._gear_image = original
            gear.draw()
        self.assertNotEqual(pet_ui.GEAR_COLOR[0], pet_ui.PAW_IDLE[0], '与没选中的灰爪不是同一个颜色')

    def test_a_gear_shape_has_eight_teeth_around_the_body(self):
        shape = pet_ui.gear_parts(pet_ui.GEAR_SIZE)
        self.assertEqual(len(shape['teeth']) // 2, 16, '八颗齿＝十六个顶点')
        self.assertLess(shape['body'][2], pet_ui.GEAR_SIZE * 0.5)
        self.assertGreater(shape['teeth'][0], 0)

    def body_fill(self):
        """齿身的填色（每画一次都是新的图元，所以每次都重新找一遍）。"""
        canvas = self.pet.gear.canvas
        return canvas.itemcget(canvas.find_withtag('gear-body')[0], 'fill')

    def test_hovering_the_gear_brightens_it(self):
        """悬停加深只在手绘兜底路径有意义；PNG 图标路径垫一层浅灰底衬。"""
        gear = self.pet.gear
        original = gear._gear_image
        gear._gear_image = lambda: None
        gear.draw()
        try:
            self.assertEqual(self.body_fill(), pet_ui.GEAR_COLOR[0])
            gear.hover_on()
            self.assertEqual(self.body_fill(), pet_ui.GEAR_HOVER[0])
            gear.hover_off()
            self.assertEqual(self.body_fill(), pet_ui.GEAR_COLOR[0])
        finally:
            gear._gear_image = original
            gear.draw()

    def test_clicking_the_gear_opens_the_settings_window(self):
        opened = []
        original = self.pet.open_settings
        self.pet.open_settings = lambda tab=None: opened.append(tab) or 'ok'
        self.addCleanup(setattr, self.pet, 'open_settings', original)
        self.assertEqual(self.pet.gear.click(), 'ok')
        self.assertEqual(opened, [None], '点一下就把「设置」打开')

    def test_a_broken_command_does_not_blow_up_the_event_loop(self):
        self.pet.gear.command = None
        self.assertIsNone(self.pet.gear.click())


class SettingsWindowTests(SettingsCase):
    """「设置」窗口：七格、名字、以及每一格真的接在宠物身上。"""

    def test_the_window_offers_the_settings_pages(self):
        win = self.hub()
        labels = [str(win._pet_tabs[key].cget('text')) for key, _title in pet_settings_ui.TABS]
        self.assertEqual(labels, [title for _key, title in pet_settings_ui.TABS])
        self.assertEqual(labels[:2], ['基础功能', '三虎模型配置'])
        self.assertIn('预算', labels)
        # R3089（生命周期任务书 T7）：「SKILL 管理」格落地，排在预算与开发信息之间；
        # 开发信息仍是分页里的最后一格。
        self.assertEqual(labels[-3:], ['预算', 'SKILL 管理', pet_settings_ui.DEV_TITLE])

    def test_a_page_can_be_picked_when_opening(self):
        win = self.hub('budget')
        self.assertEqual(self.selected(win), '预算')
        self.assertIsNotNone(pet_settings_ui.select(win, 'level'))
        self.assertEqual(self.selected(win), '自动化等级')
        self.assertEqual(self.selected(pet_settings_ui.open_hub(self.pet, 'dev')), '开发信息')
        self.assertIsNone(pet_settings_ui.select(win, '不存在'), '认不出的名字停着不切')

    def test_the_model_page_is_the_old_four_dimension_page(self):
        win = self.hub('model')
        model_frame = getattr(win, '_pet_pages', {}).get('model', win)
        combos = self.walk(model_frame, self.ttk.Combobox)
        self.assertEqual(len(combos), 4, '默认／对话／升级／降级四个下拉框')
        self.assertEqual(combos[0].get(), '自动')

    def test_the_model_page_keeps_its_buttons(self):
        win = self.hub('model')
        texts = [str(button.cget('text')) for button in self.walk(win, self.ttk.Button)]
        # 第 46 期第 6 条：「打开模型管理」改名「API统一配置」并挪到抬头行右侧；
        # 用户要求这颗键再改名为「模型配置」（pet_models_ui.MANAGER_BUTTON）。
        for label in ('测试连接', '模型配置', '保存', '重置'):
            self.assertIn(label, texts)
        self.assertNotIn('打开模型管理', texts)

    def test_the_api_button_sits_next_to_the_model_tab(self):
        """第 48 期第 1 条：那颗键往上挪一级——长在分页按钮那一行上，就在「三虎模型配置」右边。"""
        win = self.hub('model')
        button = win._pet_seams['model']['manager']
        self.assertEqual(str(button.cget('text')), pet_models_ui.MANAGER_BUTTON)
        self.assertIs(button.master, win._pet_tabs['model'].master, '与分页按钮同一行')
        order = [str(w.cget('text')) for w in button.master.winfo_children()]
        self.assertEqual(order[order.index('三虎模型配置') + 1], pet_models_ui.MANAGER_BUTTON,
                         '紧挨着「三虎模型配置」的右边')
        self.assertEqual(str(button.cget('style')), 'Tokens.Secondary.TButton',
                         '第 51 期第 1 条：它原来用 Highlight（琥珀底／粗体／大内边距），'
                         '在一排 Compact 按钮里格式不统一，现在与同排的键一个样')
        labels = [str(w.cget('text')) for w in self.walk(win._pet_pages['model'], self.ttk.Label)
                  if 'text' in w.keys()]
        self.assertIn(pet_models_ui.NOTE_ABOUT, labels)
        self.assertNotIn(pet_models_ui.SETTINGS_TITLE, labels,
                         '分页按钮上已经写着「三虎模型配置」，页里不再重复')

    def test_only_the_picked_page_is_shown_and_it_is_marked(self):
        """按钮行要能看出现在在哪一格：选中的那颗用 Selected 样式，页面栈里也只摆那一格。"""
        win = self.hub('budget')
        shown = [key for key, frame in win._pet_pages.items() if frame.winfo_manager()]
        self.assertEqual(shown, ['budget'])
        for key, button in win._pet_tabs.items():
            self.assertEqual(str(button.cget('style')),
                             'Selected.Nav.TButton' if key == 'budget' else 'Nav.TButton')

    def test_left_categories_reuse_the_main_nav_icons_and_keep_text_accessible(self):
        """左栏沿用主界面 Fluent PNG 图标轨；文字仍保留，键盘与读屏不依赖猜图标。"""
        win = self.hub('basic')
        for key, button in win._pet_tabs.items():
            self.assertEqual(button._nav_icon_name, pet_settings_ui.TAB_ICONS[key])
            self.assertEqual(str(button.cget('text')), dict(pet_settings_ui.TABS)[key])
            self.assertEqual(str(button.cget('compound')), 'left')
            self.assertTrue(str(button.cget('image')), '%s 应拿到主导航图标位图' % key)

    def test_opening_and_arrow_keys_keep_focus_on_the_selected_category(self):
        """设置窗是 chrome=False 的旧外壳，不会自动聚焦；这里钉住左栏键盘入口。"""
        self.win.deiconify()
        self.win.update()
        win = self.hub('basic')
        win.deiconify()
        win.update()
        win.focus_force()
        pet_settings_ui.select(win, 'basic')
        win.update()
        basic = win._pet_tabs['basic']
        self.assertEqual(str(win.focus_get()), str(basic), '打开后焦点落在当前分类')
        basic.event_generate('<Down>')
        win.update()
        self.assertEqual(pet_settings_ui.current(win), 'model')
        self.assertEqual(str(win.focus_get()), str(win._pet_tabs['model']),
                         '方向键切页后焦点不丢，也不需要鼠标重新点')
        win._pet_tabs['model'].event_generate('<Up>')
        win.update()
        self.assertEqual(pet_settings_ui.current(win), 'basic')
        self.assertEqual(str(win.focus_get()), str(basic))

    def test_pages_build_lazily_and_are_reused_without_reloading(self):
        """设置窗首帧只建落到的页；切走再切回复用同一页，不重读配置、不重启后台加载。"""
        win = self.hub('basic')
        self.assertIn('basic', win._pet_seams)
        self.assertNotIn('model', win._pet_seams)
        self.assertNotIn('skills', win._pet_seams)
        pet_settings_ui.select(win, 'model')
        model_seam = win._pet_seams['model']
        self.assertNotIn('skills', win._pet_seams, '没打开过的 SKILL 页不得提前扫描')
        pet_settings_ui.select(win, 'basic')
        pet_settings_ui.select(win, 'model')
        self.assertIs(win._pet_seams['model'], model_seam, '切回已建页必须复用，不能重复加载')
        combos = self.walk(win._pet_pages['model'], self.ttk.Combobox)
        self.assertEqual(len(combos), 4, '复用后的模型页四档下拉仍在')

    def test_token_controls_use_widths_chosen_by_value_kind(self):
        """枚举用短固定宽；数字短一些，模型名长一些，并行数很短；输入框不再被输入列拉满。"""
        win = self.hub('token')
        widgets = win._pet_seams['token']['field_widgets']
        for key in ('model_reasoning_effort', 'model_reasoning_summary', 'model_verbosity'):
            self.assertEqual(int(widgets[key].cget('width')), CHAR_WIDTH['md'], key)
            self.assertNotIn('e', str(widgets[key].grid_info()['sticky']), key)
        for key in ('model_context_window', 'model_auto_compact_token_limit', 'max_thinking_tokens'):
            self.assertEqual(int(widgets[key].cget('width')), CHAR_WIDTH['lg'], key)
            self.assertNotIn('e', str(widgets[key].grid_info()['sticky']), key)
        self.assertEqual(int(widgets['subagent_model'].cget('width')), CHAR_WIDTH['3xl'])
        self.assertEqual(int(widgets['subagent_limit'].cget('width')), CHAR_WIDTH['xs'])

    def test_the_standalone_window_still_offers_the_api_button(self):
        """它自己单独开一扇窗时（没有上一级）那颗键照旧在这一页里。"""
        win = pet_models_ui.open_settings(self.pet)
        self.addCleanup(win.destroy)
        buttons = {str(button.cget('text')): button for button in self.walk(win, self.ttk.Button)}
        self.assertIn(pet_models_ui.MANAGER_BUTTON, buttons)
        self.assertEqual(str(buttons[pet_models_ui.MANAGER_BUTTON].cget('style')), 'Tokens.Secondary.TButton',
                         '第 51 期第 1 条：这扇窗里那一颗也改用与「关闭」一样的格式')


class ManagerKeyAutoSaveTests(SettingsCase):
    """第 65 期任务 5：密钥框里敲进去就自动存——用户报「密钥输入后没有自动保存」。"""

    def setUp(self):
        super().setUp()
        self._protector = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', self._protector)

    def manager(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        return win

    def fill_record(self, win, key_env='MINE_KEY'):
        entries = win._pet_entries
        for field, value in (('label', '我的本地模型'), ('model', 'llama-3-8b'),
                             ('base_url', 'http://127.0.0.1:8000/v1'), ('key_env', key_env)):
            entries[field].delete(0, 'end')
            entries[field].insert(0, value)
        return entries

    def test_a_typed_key_is_saved_without_pressing_the_button(self):
        win = self.manager()
        self.fill_record(win)
        entry = win._pet_key_entry
        entry.insert(0, 'sk-auto-1')
        win._pet_save_typed()                       # 等价于回车，或点到别处
        self.assertEqual(entry.get(), '', '存好就把框清空，界面上不长期留着明文')
        pool = model_pool.pool(program=self.pet.program)
        self.assertIn('llama-3-8b', pool, '记录也进了池子')
        self.assertEqual(model_pool.local_key_of(pool['llama-3-8b'], self.pet.program), 'sk-auto-1')
        env = model_pool.env_file(self.pet.program)
        self.assertFalse(env.exists(), '模型管理不得重新创建明文 .env')
        encrypted = model_secrets.path('MINE_KEY', self.pet.program)
        self.assertNotIn(b'sk-auto-1', encrypted.read_bytes())

    def test_an_empty_box_saves_nothing(self):
        win = self.manager()
        self.fill_record(win)
        self.assertIsNone(win._pet_save_typed(), '框里没字就什么都不做')
        self.assertFalse(model_pool.env_file(self.pet.program).is_file())


class ManagerProviderTests(SettingsCase):
    """自定义厂商随模型池记录保存，并回填到模型管理的 Provider 下拉。"""

    def test_a_saved_custom_provider_becomes_a_dropdown_option(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        entries = win._pet_entries
        for field, value in (('label', '月光测试模型'), ('model', 'moonshot-test'),
                             ('base_url', 'https://api.example.test/v1'), ('key_env', 'MOON_KEY')):
            entries[field].delete(0, 'end')
            entries[field].insert(0, value)
        win._pet_provider.set('Moonshot')
        button = next(button for button in self.walk(win, self.ttk.Button)
                      if str(button.cget('text')) == '保存这条')
        button.invoke()
        self.assertIn('Moonshot', tuple(str(item) for item in win._pet_provider_box.cget('values')))

    def test_the_manager_groups_gpt_entries_and_sorts_rows_by_label(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        tree = win._pet_tree

        def group_rows():
            rows = [tree.item(row, 'values') for row in tree.get_children()]
            # 列顺序：功能／Provider／调用方式／模型 ID／显示名…；同一 Provider 只在分组首行写名字。
            providers, last = {}, ''
            for row in rows:
                last = str(row[1]) or last
                providers[str(row[4])] = last
            heads = [str(row[1]) for row in rows if str(row[1])]
            return rows, providers, heads

        # 页签化（R2398）后列表只显示当前调用方式；GPT 厂商的条目分散在 API／Desktop 两页签，
        # 分别验证：同一 Provider 首行写名＋按名排序、GPT 条目按显示名归组排序。
        rows, providers, heads = group_rows()
        self.assertEqual(heads, sorted(set(heads), key=str.casefold), '每个 Provider 只出现一次且按名排序')
        self.assertEqual(providers['GPT-4o'], 'GPT')
        gpt = [str(row[4]) for row in rows if providers[str(row[4])] == 'GPT']
        self.assertEqual(gpt, sorted(gpt, key=str.casefold))
        win._pet_mode.set('Desktop')
        rows, providers, heads = group_rows()
        self.assertEqual(heads, sorted(set(heads), key=str.casefold), '每个 Provider 只出现一次且按名排序')
        self.assertEqual(providers['ChatGPT Desktop · Codex'], 'GPT')
        gpt = [str(row[4]) for row in rows if providers[str(row[4])] == 'GPT']
        self.assertEqual(gpt, sorted(gpt, key=str.casefold))
        self.assertEqual(str(win._pet_manager_hint_label.cget('style')), 'PaleGreenHint.TLabel')

    def test_the_list_shows_the_call_mode_and_leaves_api_details_to_the_form(self):
        """R2174：列表加一列「调用方式」；根地址／协议／密钥名只在下面表单里看，状态不再重复模型 ID。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        tree = win._pet_tree
        self.assertEqual([str(tree.heading(key, 'text')) for key in tree['columns']],
                         ['功能', 'Provider', '调用方式', '模型 ID', '显示名', '能力标签', '状态'])
        # 页签化（R2398）后列表只显示当前调用方式，分别切页签验证各类调用方式与状态。
        def by_label():
            return {str(values[4]): [str(value) for value in values]
                    for values in (tree.item(row, 'values') for row in tree.get_children())}
        self.assertEqual(by_label()['GPT-4o'][2], 'API')
        win._pet_mode.set('Desktop')
        rows = by_label()
        self.assertEqual(rows['ChatGPT Desktop · Codex'][2], 'Desktop')
        self.assertEqual(rows['ChatGPT Desktop · Codex'][6], '可用', '模型 ID 已有自己一列，状态不再带上')
        win._pet_mode.set('CLI')
        self.assertEqual(by_label()['Claude Code'][2], 'CLI')
        # 表单切到 Desktop 时列表不跟着藏列：每行的调用方式已经说明哪些信息适用。
        win._pet_mode.set('Desktop')
        shown = tuple(str(key) for key in tree['displaycolumns'])
        self.assertIn(shown, (('#all',), tuple(str(key) for key in tree['columns'])))

    def test_only_the_provider_heading_sorts_and_it_flips_the_group_order(self):
        """列头只有 Provider 可点：其余列头没有排序命令；点 Provider 翻转分组顺序，再点翻回。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        tree = win._pet_tree
        for key in tree['columns']:
            command = str(tree.heading(key, 'command'))
            self.assertEqual(bool(command), key == 'provider', key)

        def heads():
            return [str(tree.item(row, 'values')[1]) for row in tree.get_children()
                    if str(tree.item(row, 'values')[1])]
        before = heads()
        tree.tk.call(tree.heading('provider', 'command'))
        self.assertEqual(heads(), sorted(set(before), key=str.casefold, reverse=True))
        tree.tk.call(tree.heading('provider', 'command'))
        self.assertEqual(heads(), before)

    def test_the_form_pairs_fields_on_one_row_with_short_boxes(self):
        """表单：调用方式｜Provider、模型 ID｜显示名、上下文长度｜备注各占一行，下拉框与输入框定宽不拉长。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        win.update_idletasks()
        form = win._pet_provider_box.master
        entries, labels = win._pet_entries, win._pet_labels

        def row_of(widget):
            return int(widget.grid_info()['row'])
        self.assertEqual(row_of(win._pet_provider_box), 0)
        self.assertEqual(row_of(entries['model']), row_of(entries['label']))
        self.assertEqual(row_of(entries['context_length']), row_of(entries['note']))
        self.assertLess(row_of(win._pet_provider_box), row_of(entries['model']))
        self.assertLess(row_of(entries['model']), row_of(entries['base_url']))
        self.assertEqual(row_of(labels['context_length']), row_of(entries['context_length']))
        for widget in (win._pet_provider_box, entries['model'], entries['label'],
                       entries['context_length'], entries['note']):
            self.assertLess(widget.winfo_reqwidth(), form.winfo_reqwidth() // 2, widget)


class CodexDesktopEntryTests(SettingsCase):
    """桌面模型是模型池的选项，不在 API 统一配置额外放启动按钮。"""

    def test_the_manager_does_not_restore_the_removed_codex_launch_button(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        buttons = {str(button.cget('text')): button for button in self.walk(win, self.ttk.Button)}
        self.assertNotIn('打开 ChatGPT 桌面', buttons,
                         '阶段配置选择桌面模型后由工作流启动，不在 API 配置重复提供入口')


class BasicPageTests(SettingsCase):
    """基础功能：名字、贴片动画、免打扰、开机自启。"""

    def page(self, tab='basic'):
        win = self.hub(tab)
        return win, win._pet_seams[tab]

    def test_the_name_is_the_one_the_spec_pins(self):
        """规格：名字就是「三虎」，所有 UI／通知／日志／气泡都用它——这一格只显示，不给改。"""
        win, seams = self.page()
        labels = [str(widget.cget('text')) for widget in self.walk(win, self.ttk.Label)
                  if 'text' in widget.keys()]
        self.assertEqual(self.pet.pet_settings()['name'], '三虎')
        self.assertIn('三虎', labels)
        name = next(widget for widget in self.walk(win, self.ttk.Label) if widget.cget('text') == '三虎')
        self.assertIn('一律用「三虎」', name.tooltip.text)
        self.assertEqual(seams['anim'].get(), self.pet.animation_enabled())

    def test_basic_inputs_keep_widths_matched_to_their_values(self):
        """两位小时用短框；主题是固定枚举，宽度按最长选项测出，不借输入列拉满。"""
        _win, seams = self.page()
        self.assertEqual(int(seams['start_box'].cget('width')), CHAR_WIDTH['xs'])
        self.assertEqual(int(seams['end_box'].cget('width')), CHAR_WIDTH['xs'])
        self.assertLessEqual(int(seams['theme_box'].cget('width')), CHAR_WIDTH['xl'])
        self.assertGreaterEqual(int(seams['theme_box'].cget('width')), CHAR_WIDTH['xs'])

    def test_the_animation_switch_is_written_down_and_takes_effect_at_once(self):
        _win, seams = self.page()
        self.assertTrue(self.pet.animation_enabled(), '出厂是动的')
        self.assertTrue(seams['anim'].get(), '勾选框开局就照着当前状态画')
        seams['anim'].set(False)
        seams['apply_anim']()
        self.assertFalse(self.pet.animation_enabled())
        self.assertIn('关掉', seams['hint'].get())
        saved = json.loads((Path(self.tmp.name) / '配置' / '宠物' / '配置.json').read_text('utf-8'))
        self.assertIs(saved['anim'], False, '写进全局配置，下次开机照旧')
        self.assertTrue(seams['anim'].get() is False)

    def test_a_stopped_animation_freezes_the_frame(self):
        self.pet.set_anim(False)
        before = self.pet.frame
        self.pet.step()
        self.assertEqual(self.pet.frame, before, '关掉动画就不再推帧')
        self.pet.set_anim(True)
        self.pet.step()
        self.assertEqual(self.pet.frame, before + 1)

    def test_the_dnd_window_is_saved_and_applied(self):
        _win, seams = self.page()
        self.assertEqual(self.pet.dnd_window(), pet_agent.DND)
        seams['start'].set('22')
        seams['end'].set('6')
        self.assertEqual(seams['save_dnd'](), (22, 6))
        self.assertEqual(self.pet.dnd_window(), (22, 6))
        self.assertEqual(self.pet.agent.notifier.window, (22, 6), '正在用的那一份通知立刻照新窗口算')
        self.assertIn('22:00 - 06:00', seams['hint'].get())

    def test_a_silly_dnd_window_is_refused(self):
        _win, seams = self.page()
        seams['start'].set('23')
        seams['end'].set('23')
        self.assertIsNone(seams['save_dnd'](), '首尾对得一样＝一整天不打扰，不是用户想说的')
        self.assertIn('没改成', seams['hint'].get())
        seams['start'].set('25')
        self.assertIsNone(seams['save_dnd']())
        self.assertEqual(self.pet.dnd_window(), pet_agent.DND)

    def test_the_quiet_button_follows_the_countdown(self):
        """那一颗按钮就是功能栏里的「免打扰」：按一下安静，再按一下恢复。"""
        _win, seams = self.page()
        self.assertEqual(seams['snooze'].get(), self.pet.snooze_label())
        self.pet.snooze(600)
        self.pet.toggle_snooze()
        self.assertFalse(self.pet.snoozing())
        self.assertIn('免打扰', self.pet.snooze_label())

    def test_the_autostart_box_drives_the_registry(self):
        self.pet._autostart = pet_ui.Autostart(api=_Registry())
        _win, seams = self.page()
        self.assertFalse(seams['autostart'].get(), '假注册表里还没有这一项')
        seams['autostart'].set(True)
        self.assertTrue(seams['apply_autostart']())
        self.assertTrue(self.pet.autostart().enabled())
        self.assertIn('已开启', self.pet.notice)
        seams['autostart'].set(False)
        self.assertFalse(seams['apply_autostart']())
        self.assertFalse(self.pet.autostart().enabled())


class LevelPageTests(SettingsCase):
    """自动化等级那一格：三档、点哪一档就切到哪一档、并且写进配置。"""

    def test_the_page_lists_the_three_levels(self):
        win = self.hub('level')
        radios = self.walk(win, self.ttk.Radiobutton)
        self.assertEqual(len(radios), 3)
        for level, radio in zip(pet_agent.LEVELS, radios):
            self.assertIn(pet_agent.LEVEL_NAMES[level], str(radio.cget('text')))
            self.assertIn(pet_ui.LEVEL_NOTES[level], str(radio.cget('text')))
        self.assertEqual(win._pet_seams['level']['picked'].get(), pet_agent.DEFAULT_LEVEL)

    def test_picking_a_level_switches_and_writes_it_down(self):
        win = self.hub('level')
        seams = win._pet_seams['level']
        seams['picked'].set('auto')
        seams['apply']()
        self.assertEqual(self.pet.agent.level, 'auto')
        self.assertIn('全自动', seams['hint'].get())
        saved = json.loads((Path(self.tmp.name) / '配置' / '宠物' / '配置.json').read_text('utf-8'))
        self.assertEqual(saved['level'], 'auto', '写进全局配置，下次开机照这一档来')

    def test_the_restore_button_goes_back_to_the_factory_level(self):
        win = self.hub('level')
        seams = win._pet_seams['level']
        self.pet.set_level('auto')
        seams['restore']()
        self.assertEqual(self.pet.agent.level, pet_agent.DEFAULT_LEVEL)

    def test_switching_the_level_persists_even_without_the_page(self):
        """猫爪／聊天切档也要落盘——不然设置页只是个装饰。"""
        self.pet.set_level('hint')
        saved = json.loads((Path(self.tmp.name) / '配置' / '宠物' / '配置.json').read_text('utf-8'))
        self.assertEqual(saved['level'], 'hint')

    def test_picking_levels_only_reaches_the_three_legal_combinations(self):
        """设置页与猫爪同一入口：三档各落一种组合——手动+只提醒+开关全关、
        手动+半自动+开关全关、自动+全自动+开关全开；切回去同样收干净。"""
        win = self.hub('level')
        seams = win._pet_seams['level']
        seen = []
        for level in pet_agent.LEVELS + pet_agent.LEVELS[::-1]:
            seams['picked'].set(level)
            seams['apply']()
            opened = all(project_settings.get(self.fake.root, key) is True
                         for key in project_settings.DEFAULTS)
            self.assertTrue(all(self.pet.auto_variable(name).get() is opened
                                for name in pet_ui.AUTO_VARIABLE_NAMES), level)
            seen.append((self.pet.mode, self.pet.agent.level, opened))
        self.assertEqual(seen, [('manual', 'hint', False), ('manual', 'semi', False),
                                ('auto', 'auto', True), ('auto', 'auto', True),
                                ('manual', 'semi', False), ('manual', 'hint', False)])


class BudgetPageTests(SettingsCase):
    def test_cost_reconciliation_dialog_saves_receipt_and_reports_validation(self):
        from infra.pet_llm import RequestLedger
        with tempfile.TemporaryDirectory() as folder:
            ledger = RequestLedger(folder)
            ledger.reserve('unknown-api', 'images', 1)
            ledger.mark_unknown('unknown-api'); ledger.save()
            receipt = Path(folder) / 'invoice.txt'; receipt.write_text('test invoice')
            hub = self.hub('budget')._pet_seams['budget']
            with mock.patch('pet_settings_ui.token_project', return_value=None):
                self.assertIsNone(hub['reconcile_usage']())
            with mock.patch('pet_settings_ui.token_project', return_value=Path(folder)):
                seams = hub['reconcile_usage']()
            try:
                self.assertIsNone(seams['save']())
                seams['selected'].current(0); seams['pick']()
                values = {'amount': '0.3', 'currency': 'CNY', 'reviewer': 'test reviewer', 'evidence': str(receipt)}
                for key, value in values.items(): seams['fields'][key].set(value)
                result = seams['save']()
                self.assertEqual(result['budget_cost'], '0.3')
                self.assertIn('已核对', seams['hint'].get())
                self.assertEqual(RequestLedger(folder).load()._find('unknown-api')['money_state'], 'reconciled')
                seams['fields']['amount'].set('-1')
                self.assertIsNone(seams['save']())
                old = RequestLedger(Path(folder) / 'cloud_video/old')
                old.settle('video:s1:v1:seconds', kind='seconds', amount=5); old.save()
                self.assertEqual(seams['import_legacy'](), 1)
                self.assertEqual(seams['selected'].current(), -1)
                self.assertEqual(len(seams['selected']['values']), 2)
                seams['selected'].current(1); seams['pick']()
                seams['fields']['amount'].set('0.1')
                seams['fields']['currency'].set('CNY')
                self.assertEqual(seams['save']()['money_state'], 'reconciled')
                self.assertEqual(seams['import_legacy'](), 0)
            finally:
                seams['window'].destroy()

    """预算那一格：五类硬限制、落盘、立刻生效、坏值拦下来。"""

    def test_the_page_shows_the_five_limits(self):
        win = self.hub('budget')
        fields = win._pet_seams['budget']['fields']
        self.assertEqual(sorted(fields), sorted(pet_agent.BUDGET_KINDS))
        self.assertEqual(fields['tokens'].get(), str(pet_agent.DEFAULT_BUDGET['tokens']))
        self.assertIn('2000000', fields['tokens'].get())

    def test_budget_number_fields_do_not_stretch_across_the_form(self):
        """额度是数字：给可预期字符宽并左对齐，输入列仍可把剩余空间留给单位与用量说明。"""
        win = self.hub('budget')
        widgets = win._pet_seams['budget']['field_widgets']
        for kind in pet_agent.BUDGET_KINDS:
            self.assertEqual(int(widgets[kind].cget('width')), CHAR_WIDTH['lg'], kind)
            self.assertIn('w', str(widgets[kind].grid_info()['sticky']), kind)
            self.assertNotIn('e', str(widgets[kind].grid_info()['sticky']), kind)

    def test_saving_writes_the_limits_and_applies_them(self):
        win = self.hub('budget')
        seams = win._pet_seams['budget']
        seams['fields']['tokens'].set('1500000')
        seams['fields']['image'].set('120')
        saved = seams['save']()
        self.assertEqual(saved['tokens'], 1500000)
        self.assertEqual(self.pet.agent.budget.limits['image'], 120, '正在用的账本立刻按新额度算')
        stored = json.loads((Path(self.tmp.name) / '配置' / '宠物' / '配置.json').read_text('utf-8'))
        self.assertEqual(stored['budget_limits']['tokens'], 1500000)
        self.assertEqual(stored['budget_limits']['image'], 120)
        self.assertEqual(sorted(stored['budget_limits']), sorted(pet_agent.BUDGET_KINDS),
                         '五类一起写全——面板那一行「x/y」两边都要有数')
        self.assertIn('已保存预算', seams['hint'].get())
        self.assertIn('Token 1500000', seams['hint'].get())
        self.assertIn('生图 120', seams['hint'].get())

    def test_a_bad_number_is_refused_with_a_sentence(self):
        win = self.hub('budget')
        seams = win._pet_seams['budget']
        seams['fields']['video'].set('0')
        self.assertIsNone(seams['save']())
        self.assertIn('正整数', seams['hint'].get())
        self.assertEqual(self.pet.budget_limits()['video'], pet_agent.DEFAULT_BUDGET['video'],
                         '坏值一个都不许写进去')
        seams['fields']['video'].set('不是数')
        self.assertIsNone(seams['save']())

    def test_restoring_fills_the_factory_numbers_back(self):
        win = self.hub('budget')
        seams = win._pet_seams['budget']
        seams['fields']['image'].set('7')
        seams['save']()
        seams['restore']()
        self.assertEqual(seams['fields']['image'].get(), str(pet_agent.DEFAULT_BUDGET['image']))
        self.assertIn('点「保存」', seams['hint'].get())

    def test_an_empty_box_keeps_the_factory_number(self):
        win = self.hub('budget')
        seams = win._pet_seams['budget']
        seams['fields']['voice'].set('')
        saved = seams['save']()
        self.assertEqual(saved['voice'], pet_agent.DEFAULT_BUDGET['voice'])


class DevPageTests(SettingsCase):
    """开发信息那一格（第 47 期第 8 条）：版本、开发者、邮箱，外加一颗复制邮箱。"""

    def test_the_page_is_labelled_and_the_version_has_one_source(self):
        win = self.hub('dev')
        seams = win._pet_seams['dev']
        self.assertEqual(seams['version'], desktop.VERSION, '版本号只有 desktop.VERSION 这一份')
        self.assertEqual(pet_settings_ui.app_version(), desktop.VERSION)

    def test_the_page_carries_developer_and_mail(self):
        win = self.hub('dev')
        texts = [str(w.cget('text')) for w in self.walk(win._pet_pages['dev'], self.ttk.Label)]
        for value in (pet_settings_ui.APP_TITLE, pet_settings_ui.DEVELOPER_NAME,
                      pet_settings_ui.DEVELOPER_MAIL, desktop.VERSION):
            self.assertIn(value, texts)
        self.assertIn('开发者', texts)
        self.assertIn('联系方式', texts)

    def test_the_copy_button_writes_the_mail_to_the_clipboard(self):
        win = self.hub('dev')
        seams = win._pet_seams['dev']
        # 系统剪贴板在无交互 Windows 会话中可能没有 STRING selection；这里验证本页把
        # 唯一剪贴板出口调用为目标邮箱，实际写入行为由 prompt_window 的专用用例覆盖。
        with mock.patch('prompt_window.copy_text', return_value='') as copy_text:
            self.assertEqual(seams['copy_mail'](), pet_settings_ui.DEVELOPER_MAIL)
        copy_text.assert_called_once_with(self.pet.win, pet_settings_ui.DEVELOPER_MAIL)
        self.assertIn(pet_settings_ui.DEVELOPER_MAIL, seams['hint'].get())


    def test_environment_check_button_shows_report_without_changing_settings(self):
        win = self.hub('dev')
        seams = win._pet_seams['dev']
        with mock.patch('ui_widgets.notify') as shown:
            text = seams['check_environment']()
        shown.assert_called_once()
        self.assertEqual(shown.call_args.kwargs.get('title'), '环境自检')
        self.assertIn('FFmpeg', text)
        self.assertIn('共', seams['hint'].get())


    def test_usage_button_reports_without_a_project_and_shows_when_open(self):
        win = self.hub('budget')
        seams = win._pet_seams['budget']
        with mock.patch('pet_settings_ui.token_project', return_value=None):
            self.assertIsNone(seams['show_usage']())
        self.assertIn('还没打开项目', seams['hint'].get())
        with tempfile.TemporaryDirectory() as folder, mock.patch('pet_settings_ui.token_project', return_value=Path(folder)), \
                mock.patch('ui_widgets.notify') as shown:
            text = seams['show_usage']()
        shown.assert_called_once()
        self.assertEqual(shown.call_args.kwargs.get('title'), '用量总览')
        self.assertIn('合计：0 次', text)
        self.assertIn('Token（每天）', text)


class BudgetWiringTests(unittest.TestCase):
    """预算落盘之后，SKILL 编排那本账读的是同一份设置（一份设置、两处都认）。"""

    def test_the_skill_budget_reads_the_pet_config(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(skill_budget.pet_limits(td), {})
            self.assertEqual(skill_budget.configured(td),
                             {'tokens_per_day': 2000000, 'images_per_project': 200,
                              'videos_per_project': 100})
            pet_agent.save_settings({'budget_limits': {'tokens': 500000, 'image': 30, 'video': 12}},
                                    program=td)
            self.assertEqual(skill_budget.configured(td),
                             {'tokens_per_day': 500000, 'images_per_project': 30,
                              'videos_per_project': 12})

    def test_for_project_builds_the_ledger_from_the_settings(self):
        with tempfile.TemporaryDirectory() as td:
            pet_agent.save_settings({'budget_limits': {'image': 3}}, program=td)
            budget = skill_budget.for_project(td, program=td)
            self.assertEqual(budget.limit('images'), 3)
            self.assertEqual(budget.limit('videos'), 100, '没写的那几档照旧用出厂值')

    def test_the_orchestrator_takes_the_same_numbers(self):
        from orchestrator import skill_orchestrator
        with tempfile.TemporaryDirectory() as td:
            pet_agent.save_settings({'budget_limits': {'image': 4}}, program=td)
            orchestrator = skill_orchestrator.default_orchestrator(program=td, project=td)
            self.assertEqual(orchestrator.budget.limit('images'), 4)
            self.assertEqual(orchestrator.budget.limit('tokens'), 2000000, '没改的那档照旧')


class QuitMenuTests(SettingsCase):
    """附件功能栏最后那一行「退出程序」：先问一句，宿主没有退出通道就老实说。"""

    def test_the_menu_keeps_quit_as_the_last_entry(self):
        labels = [self.pet.menu.entrycget(index, 'label')
                  for index in range(self.pet.menu.index('end') + 1)
                  if self.pet.menu.type(index) == 'command']
        self.assertEqual(labels[-1], pet_ui.QUIT_LABEL)
        self.assertIn('quit', self.pet.menu_index)

    def test_answering_no_keeps_the_program_open(self):
        self.pet.asker = lambda title, text: False
        self.assertFalse(self.pet.quit_app())
        self.assertEqual(self.fake.closed, 0)
        self.assertIn('已取消退出', self.pet.notice)

    def test_answering_yes_calls_the_hosts_close(self):
        asked = []
        self.pet.asker = lambda title, text: asked.append((title, text)) or True
        self.assertTrue(self.pet.quit_app())
        self.assertEqual(self.fake.closed, 1)
        self.assertEqual(asked[0][0], '退出程序')
        self.assertIn('没跑完的活留在原地', asked[0][1])

    def test_a_host_without_a_close_channel_says_so(self):
        class Deaf(FakeDesktop):
            pass

        deaf = Deaf(self.tk, self.ttk, self.win)
        deaf.close = None
        self.pet.desktop = deaf
        self.assertFalse(self.pet.quit_app())
        self.assertIn('没有退出通道', self.pet.notice)


class DesktopGearSeamTests(unittest.TestCase):
    """真接缝：第 R2946 期设置入口并入图标轨末尾（settings_rail_button），三虎簇在 pet_dock，点得到、开得出设置。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk()
        win.withdraw()
        # 显式给尺寸：withdrawn 窗口不映射，winfo_ismapped 恒假，但几何（rooty）仍按给定尺寸结算。
        win.geometry('1280x800')
        from desktop import Desktop
        return win, Desktop(win, root=PROGRAM)

    def test_the_gear_sits_in_the_sidebar_dock_without_a_sidebar_version_label(self):
        win, desktop = self.build()
        try:
            self.assertEqual(win.title(), __import__('contract.app_metadata', fromlist=['APP_NAME']).APP_NAME + ' · V0.7')
            # 第 R2933 期：侧栏顶部浮层（应用名）与标题行标语都删了；项目名只留窗口标题。
            self.assertFalse(hasattr(desktop, 'app_title'), '侧栏不再有应用名浮层')
            self.assertFalse(hasattr(desktop, 'sidebar_head'), '侧栏不再有顶部浮层行')
            self.assertFalse(hasattr(desktop, 'header_slogan'), '页头不再有标语')
            # 第 R2946 期：齿轮不再进底栏——设置入口是图标轨末尾的轨钮，三虎簇独占 pet_dock。
            self.assertIsNone(desktop.pet.gear, '真桌面不再建底栏齿轮')
            rail = desktop.settings_rail_button
            self.assertIsNotNone(rail, '图标轨末尾有设置钮')
            self.assertEqual(str(rail.winfo_parent()), str(desktop.sidebar),
                             '设置钮与 00–14 阶段钮同在侧栏滚动区')
            self.assertEqual(rail.cget('style'), 'RailIcon.TButton')
            self.assertEqual(rail.winfo_manager(), 'pack', '设置钮已 pack 进图标轨')
            win.update_idletasks()
            self.assertGreater(rail.winfo_rooty(), desktop.nav[-1].winfo_rooty(),
                               '设置钮排在最后一个阶段钮下面')
            self.assertEqual(rail._nav_tooltip.text, '设置')
            # 三虎簇在 pet_dock：头像／小字／猫爪都归它管。
            self.assertEqual(str(desktop.pet.canvas.winfo_parent()), str(desktop.pet_dock))
            self.assertEqual(str(desktop.pet_dock.winfo_parent()), str(desktop.sidebar_dock))
            self.assertFalse(hasattr(desktop, 'settings_gear_layer'), '齿轮行已随齿轮一起撤掉')
        finally:
            win.destroy()

    def test_the_gear_opens_the_settings_window(self):
        win, desktop = self.build()
        try:
            opened = []
            original = desktop.pet.open_settings
            desktop.pet.open_settings = lambda tab=None: opened.append(tab) or 'ok'
            try:
                desktop.settings_rail_button.invoke()
            finally:
                desktop.pet.open_settings = original
            self.assertEqual(opened, [None])
            hub = desktop.pet.open_settings('basic')
            try:
                self.assertEqual(hub.title(), pet_settings_ui.HUB_TITLE)
                # 第 47 期第 8 条：分页数不再钉死（这次多了「开发信息」一格），跟着 TABS 走。
                # 第 48 期第 1 条：分页头换成了按钮行，数一数 buttons。
                self.assertEqual(len(hub._pet_tabs), len(pet_settings_ui.TABS))
            finally:
                hub.destroy()
        finally:
            win.destroy()


class StartupSettingsTests(SettingsCase):
    """写下去的设置，下一次启动要认得（不然设置页就是个哑键）。"""

    def test_the_saved_settings_come_back_on_the_next_start(self):
        self.pet.set_level('auto')
        self.pet.set_anim(False)
        self.pet.set_dnd(22, 6)
        self.pet.save_budget_limits({'tokens': 900000, 'image': 60, 'video': 40})
        settings = pet_agent.load_settings(program=Path(self.tmp.name))
        self.assertEqual(settings['level'], 'auto')
        self.assertIs(settings['anim'], False)
        self.assertEqual(settings['dnd'], (22, 6))
        self.assertEqual(settings['budget_limits']['tokens'], 900000)
        self.assertEqual(settings['budget_limits']['image'], 60)
        closed = pet_agent.Agent(settings=settings, persist=False)
        self.assertEqual(closed.level, 'auto')
        self.assertEqual(closed.budget.limits['image'], 60)
        self.assertEqual(closed.notifier.window, (22, 6))


class SaveSettingsLockTests(unittest.TestCase):
    """审查 AUD-MODEL D2：save_settings 的读—改—写要在 agent.publication.access() 锁内。

    宠物设置与模型池共用 配置/宠物/配置.json；model_pool.record_health 的读—改—写在发布锁内。
    save_settings 若在锁外先读后写，record_health 整段插进它的读与写之间时，对方刚写下的键
    会被这份旧快照静默盖掉。复现手法：把 pet_agent.save 换成「喊一声、等放行再写真 save」，
    让 record_health 的读—改—写确定性落在 save_settings 读盘之后、写盘之前。
    """

    def test_concurrent_record_health_loses_no_keys(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            config = model_pool.config_file(program)
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps({'models': {'m1': {'model': 'gpt-x'}},
                                          'agent': {'name': '三虎'}}, ensure_ascii=False),
                              encoding='utf-8')

            about_to_write = threading.Event()
            proceed = threading.Event()
            health_done = threading.Event()
            real_save = pet_agent.save

            def gated_save(path, data):
                about_to_write.set()
                proceed.wait(15)
                return real_save(path, data)

            def save_settings():
                pet_agent.save_settings({'level': 'auto'}, program=program)

            def record_health():
                try:
                    model_pool.record_health('m1', {'ok': True, 'at': 't', 'config_version': 'v'},
                                             program=program)
                finally:
                    health_done.set()

            writer = threading.Thread(target=save_settings, daemon=True)
            health = threading.Thread(target=record_health, daemon=True)
            with mock.patch.object(pet_agent, 'save', gated_save):
                writer.start()
                try:
                    self.assertTrue(about_to_write.wait(15), 'save_settings 没走到写盘那一步')
                    health.start()
                    # 修复前：record_health 不拿锁，毫秒级写完，等它落盘再放行，竞态才确定。
                    # 修复后：它堵在发布锁上直到放行，超时只是白等一会儿，不影响正确性。
                    health_done.wait(10)
                finally:
                    proceed.set()
                writer.join(15)
                health.join(15)
            self.assertFalse(writer.is_alive(), 'save_settings 线程没收尾')
            self.assertFalse(health.is_alive(), 'record_health 线程没收尾')
            data = json.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(data.get('level'), 'auto', '宠物设置键要落盘')
            self.assertIn('m1', data.get('models', {}), '模型池记录不能被设置写丢')
            self.assertTrue(data.get(model_pool.HEALTH_KEY, {}).get('m1', {}).get('ok'),
                            'record_health 写下的键不能被设置写丢')


class HubLayoutTests(SettingsCase):
    """REQ-UI-L5-1：设置弹窗——左侧分类列＋右侧内容；保存即关闭、关闭不保存、
    有未保存改动时关闭先确认。"""

    def _hub(self, tab=None):
        win = pet_settings_ui.open_hub(self.pet, tab)
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        return win

    def test_left_categories_and_right_content(self):
        win = self._hub('budget')
        nav = getattr(win, '_pet_nav', None)
        self.assertIsNotNone(nav, 'REQ-UI-L5-1：分类列收进左侧一列')
        self.assertEqual(nav.pack_info()['side'], 'left', '分类列在内容区左边')
        for key, _title in pet_settings_ui.TABS:
            self.assertIs(win._pet_tabs[key].master, nav, '分类按钮都在左侧那一列')
            self.assertEqual(win._pet_tabs[key].pack_info()['fill'], 'x', '分类按钮整列排')
        separators = [w for w in self.walk(nav.master, self.ttk.Separator)
                      if str(w.cget('orient')) == 'vertical']
        self.assertTrue(separators, '分类列与内容区之间要有竖分隔线')

    def test_save_writes_and_closes_the_window(self):
        win = self._hub('budget')
        win._pet_seams['budget']['fields']['tokens'].set('1500000')
        win._pet_save.invoke()
        self.assertFalse(win.winfo_exists(), 'REQ-UI-L5-1：保存＝写入并关闭')
        stored = json.loads((Path(self.tmp.name) / '配置' / '宠物' / '配置.json').read_text('utf-8'))
        self.assertEqual(stored['budget_limits']['tokens'], 1500000)

    def test_failed_save_keeps_the_window(self):
        win = self._hub('budget')
        win._pet_seams['budget']['fields']['video'].set('0')
        win._pet_save.invoke()
        self.assertTrue(win.winfo_exists(), '保存失败留在窗内')
        self.assertIn('正整数', win._pet_seams['budget']['hint'].get())

    def test_close_without_changes_does_not_ask(self):
        win = self._hub('budget')
        with mock.patch('pet_settings_ui.ask_confirmation') as ask:
            win._pet_close.invoke()
        self.assertFalse(ask.called, '没改动时关闭不再问')
        self.assertFalse(win.winfo_exists())
        self.assertEqual(self.pet.budget_limits()['tokens'], pet_agent.DEFAULT_BUDGET['tokens'],
                         '关闭不保存')

    def test_close_with_unsaved_changes_asks_first(self):
        win = self._hub('budget')
        win._pet_seams['budget']['fields']['tokens'].set('1500000')
        with mock.patch('pet_settings_ui.ask_confirmation', return_value=False) as ask:
            win._pet_close.invoke()
            self.assertTrue(ask.called, '有未保存改动要先确认')
            self.assertTrue(win.winfo_exists(), '拒绝确认就留在设置窗')
        with mock.patch('pet_settings_ui.ask_confirmation', return_value=True):
            win._pet_close.invoke()
            self.assertFalse(win.winfo_exists(), '确认后才关窗')
        self.assertEqual(self.pet.budget_limits()['tokens'], pet_agent.DEFAULT_BUDGET['tokens'],
                         '关闭不保存')
