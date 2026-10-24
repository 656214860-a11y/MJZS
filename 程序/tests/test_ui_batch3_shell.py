# -*- coding: utf-8 -*-
"""UI 批次 3：主壳在四档窗口下的侧栏滚动、键盘翻页与状态栏分色。"""
import tempfile
import time
import unittest
from tkinter import font, ttk
import tkinter as tk
import sys
from pathlib import Path

HERE=str(Path(__file__).resolve().parents[1])
sys.path.insert(0,HERE)
sys.path.insert(0,str(Path(__file__).resolve().parent))

from desktop import Desktop, PAGES, status_kind
from skip_reasons import PLATFORM_TK_DISPLAY
import test_desktop_startup_perf as startup_fixtures
from ui_tokens import COLORS, FONTS


class ShellScrollAndStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:cls.win=tk.Tk()
        except tk.TclError as exc:raise unittest.SkipTest(PLATFORM_TK_DISPLAY+': '+str(exc))
        cls.temp=tempfile.TemporaryDirectory(prefix='ui-batch3-')
        app,_project=startup_fixtures.DesktopStartupPerfTests._startup_app(cls.temp.name,remembered=False)
        original=Desktop.choose_project
        Desktop.choose_project=lambda self:None
        try:cls.desktop=Desktop(cls.win,root=app)
        finally:Desktop.choose_project=original
        cls.desktop.startup_controller.cancel()
        cls.desktop._startup_project_choice=False
        cls.desktop.root=None
        cls.pump(1.0)

    @classmethod
    def pump(cls,seconds=.3):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            # 并行分片里窗口可能拿不到系统焦点；几何先收敛，再跑事件。
            cls.win.update_idletasks();cls.win.update();time.sleep(.005)

    @classmethod
    def tearDownClass(cls):
        cls.desktop.cancel_timers()
        cls.win.destroy()
        cls.temp.cleanup()

    def resize(self,width,height):
        self.win.geometry(f'{width}x{height}');self.pump()
        self.assertEqual((self.win.winfo_width(),self.win.winfo_height()),(width,height))

    def sidebar_visible(self):
        canvas=self.desktop.sidebar_canvas;last=self.desktop.nav[-1]
        return (last.winfo_ismapped()
                and last.winfo_rooty()>=canvas.winfo_rooty()
                and last.winfo_rooty()+last.winfo_height()<=canvas.winfo_rooty()+canvas.winfo_height()+1)

    def press(self,widget,keysym):
        """显式指定接收控件，避免合成按键被 Tk 改投到当时的焦点窗口。"""
        event=type('KeyEvent',(),{'widget':widget,'keysym':keysym})()
        return self.desktop.scroll_page_key(event)

    def test_last_sidebar_stage_is_reachable_at_four_window_sizes(self):
        d=self.desktop
        self.assertEqual(d.nav[-1].cget('text'),PAGES[-1])
        for width,height in ((800,600),(1080,740),(1280,800),(1360,900)):
            with self.subTest(size=(width,height)):
                self.resize(width,height)
                d.sidebar_canvas.yview_moveto(0);self.pump(.1)
                top=d.sidebar_canvas.yview()
                d.sidebar_canvas.yview_moveto(1);self.pump(.1)
                bottom=d.sidebar_canvas.yview()
                self.assertTrue(self.sidebar_visible(),'最后一项滚到底后必须在侧栏视口内')
                if height==600:
                    self.assertLess(top[1],1.0,'800x600 侧栏应出现可滚动溢出')
                    self.assertGreater(bottom[0],0.0)
                    self.assertAlmostEqual(bottom[1],1.0,places=3)

    def test_sidebar_mouse_wheel_and_page_keys_scroll(self):
        self.resize(800,600);d=self.desktop
        for key in ('<Prior>','<Next>','<Home>','<End>'):self.assertTrue(self.win.bind(key))
        d.sidebar_canvas.yview_moveto(0);self.pump(.1)
        top=d.sidebar_canvas.yview()[0]
        title_y=d.app_title.winfo_rooty();gear_y=d.pet.gear.canvas.winfo_rooty()
        d.nav[0].event_generate('<MouseWheel>',delta=-120);self.pump(.15)
        self.assertGreater(d.sidebar_canvas.yview()[0],top)
        self.assertEqual(d.app_title.winfo_rooty(),title_y,'滚动侧栏时应用名固定不动')
        self.assertEqual(d.pet.gear.canvas.winfo_rooty(),gear_y,'滚动侧栏时齿轮固定不动')
        d.nav[0].event_generate('<MouseWheel>',delta=120);self.pump(.15)
        self.assertAlmostEqual(d.sidebar_canvas.yview()[0],top,places=3)
        self.press(d.sidebar_canvas,'End');self.pump(.1)
        self.assertAlmostEqual(d.sidebar_canvas.yview()[1],1.0,places=3)
        self.assertEqual(d.app_title.winfo_rooty(),title_y,'滚到底时应用名仍固定')
        self.press(d.sidebar_canvas,'Home');self.pump(.1)
        self.assertAlmostEqual(d.sidebar_canvas.yview()[0],0.0,places=3)

    def test_main_content_page_keys_change_scroll_and_text_keeps_its_keys(self):
        self.resize(800,600);d=self.desktop
        d.show(0);self.pump()
        self.assertLess(d.canvas.yview()[1],1.0,'项目首页在 800x600 应高于主内容视口')
        d.canvas.yview_moveto(0);self.pump(.05)
        start=d.canvas.yview()[0]
        self.press(d.canvas,'Next');self.pump(.1)
        after_next=d.canvas.yview()[0]
        self.assertGreater(after_next,start)
        self.press(d.canvas,'Prior');self.pump(.1)
        self.assertAlmostEqual(d.canvas.yview()[0],start,places=3)
        self.press(d.canvas,'End');self.pump(.1)
        self.assertAlmostEqual(d.canvas.yview()[1],1.0,places=3)
        self.press(d.canvas,'Home');self.pump(.1)
        self.assertAlmostEqual(d.canvas.yview()[0],0.0,places=3)
        text=tk.Text(d.content,height=8);text.pack();text.insert('1.0','\n'.join(str(i) for i in range(120)))
        self.pump(.1);d.canvas.yview_moveto(0);self.pump(.05)
        before=d.canvas.yview()[0]
        self.assertIsNone(self.press(text,'Next'))
        self.pump(.1)
        self.assertAlmostEqual(d.canvas.yview()[0],before,places=3,msg='文本框获得焦点时主内容不得抢 PageDown')
        text.destroy()

    def test_three_status_messages_use_three_distinct_styles(self):
        d=self.desktop
        expected={'就绪 · 所有项目共用一份程序':'PaleGreenHint.TLabel',
                  '已保存 3 张参考图':'PaleGreenHint.TLabel',
                  '正在生成首帧…':'Tokens.Status.Running.TLabel',
                  '生成失败：模型未配置':'Tokens.Status.Error.TLabel'}
        seen={}
        for message,style in expected.items():
            with self.subTest(message=message):
                d.status.set(message);self.pump(.03)
                self.assertEqual(d.status_label.cget('style'),style)
                seen[status_kind(message)]=style
        self.assertEqual(len(set(seen.values())),3)
        ttk_style=ttk.Style(self.win)
        self.assertNotEqual(ttk_style.lookup(seen['running'],'background'),
                            ttk_style.lookup(seen['error'],'background'))
        self.assertEqual(ttk_style.lookup(seen['running'],'background'),COLORS['primary_subtle'])
        self.assertEqual(ttk_style.lookup(seen['error'],'background'),COLORS['danger_subtle'])

    def test_shell_fonts_come_from_tokens(self):
        d=self.desktop
        def actual(widget):return font.Font(root=self.win,font=widget.cget('font')).actual()
        heading=actual(d.app_title);self.assertEqual((heading['family'],heading['size'],heading['weight']),
                                                       (FONTS['heading_1'][0],FONTS['heading_1'][1],'bold'))
        self.assertEqual(actual(d.title)['size'],FONTS['heading_1'][1])
        for widget in (d.header_model,d.header_status):
            self.assertEqual(actual(widget)['size'],FONTS['pet_hint'][1])

    def test_project_home_last_action_is_fully_visible_at_1280(self):
        self.resize(1280,800);d=self.desktop
        d.show(0);self.pump()
        found=[]
        def walk(widget):
            if isinstance(widget,ttk.Button) and str(widget.cget('text'))=='重建项目索引':
                found.append(widget)
            for child in widget.winfo_children():walk(child)
        walk(d.content)
        self.assertTrue(found,'项目首页应保留「重建项目索引」动作')
        button=found[0]
        self.assertGreaterEqual(button.winfo_rooty(),d.canvas.winfo_rooty())
        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                             d.canvas.winfo_rooty()+d.canvas.winfo_height()+1)


class StatusKindZeroCountTests(unittest.TestCase):
    """状态栏分色：数量为零的失败不计为错误，普通失败仍按错误上色。"""

    def test_zero_failure_counts_are_not_errors(self):
        for message in ('完成 12 个，失败 0 个','0 个失败','失败：0'):
            with self.subTest(message=message):
                self.assertEqual(status_kind(message),'ready')

    def test_nonzero_and_plain_failures_stay_errors(self):
        for message in ('失败 2 个','生成失败'):
            with self.subTest(message=message):
                self.assertEqual(status_kind(message),'error')


if __name__=='__main__':unittest.main()
