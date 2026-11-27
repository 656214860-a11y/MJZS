# -*- coding: utf-8 -*-
"""宠物贴片自检（云朵对话框、弹窗、置顶/前景与尺寸/关闭）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import os
import sys
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if PROGRAM not in sys.path:
    sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from pet_ui_test_support import (
    _Event,
    _Wheel,
    FakeDesktop,
    PetTestCase,
)
import pet_agent
from ui import pet_ask
from ui import pet_cloud
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class CloudTests(PetTestCase):
    """第 14／16 期：贴着三虎脑袋、朝左上铺开的漫画对话框浮窗——既播报也能对话。"""

    def cloud(self):
        widget = self.pet.open_chat()
        self.assertIsNotNone(widget, '云朵框应当能开出来')
        return self.pet.cloud()

    def answer(self, cloud, text, timeout=5.0):
        """走完整链路：回复框 → 后台线程 → 队列 → 心跳把回复贴回云里。

        第 35 期第 2 条起这一行是回复框：三虎问什么、空着回车就发什么——这里用 propose 把那句话摆好。
        """
        cloud.propose(text)
        self.assertEqual(cloud.submit(), text)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.pet.chat_drain():
                return cloud.transcript()
            time.sleep(0.01)
        self.fail('云朵框 %.0f 秒内没有收到回复' % timeout)

    def test_the_cloud_is_a_floating_bubble_of_its_own(self):
        """第 16 期：云朵要伸到界面外，所以它自带一扇无边框置顶浮窗，而不是界面里的浮层。"""
        cloud = self.cloud()
        self.assertIsNotNone(cloud.win, '云朵框该有自己的浮窗')
        self.assertIs(cloud.win.winfo_toplevel(), cloud.win)
        self.assertTrue(cloud.win.overrideredirect(), '无边框：它就是一朵云')
        self.assertTrue(cloud.win.attributes('-topmost'), '置顶：不然会被主界面盖住')
        self.assertTrue(getattr(cloud.win, '_positioned_once', False),
                        '建窗后立刻标 _positioned_once：别让 ui_theme 按对话框接管')

    def test_chat_reuses_window_and_dismisses_on_main_window_click(self):
        cloud = self.cloud()
        win = cloud.win
        self.assertIs(self.pet.open_chat(), cloud.canvas)
        cloud.show(focus=False, shape=pet_cloud.SHAPE_PUFF)
        self.assertIs(cloud.win, win)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        for level in ('hint', 'semi', 'auto'):
            self.pet.agent.set_level(level)
            self.assertEqual(cloud.edge(), pet_cloud.PET_PALETTE['level_' + level + '_outline'])
        self.win.deiconify()
        self.win.update()
        self.win.event_generate('<ButtonPress-1>')
        self.assertFalse(cloud.visible)
        self.assertIsNone(self.pet.chat)

    def test_the_cloud_never_keeps_the_keyboard_grab(self):
        self.cloud()
        self.win.update()
        self.assertIsNone(self.win.grab_current(), '云朵框抓了键盘，主窗口就点不动了')

    def test_a_destroyed_window_takes_the_pending_timer_with_it(self):
        """父窗口被销毁时，待触发的播报定时器必须一起收回。

        不收的话 Tcl 到点会打一句「invalid command name ..._expire」，因为 after 的 Tcl 命令
        已经随控件被删了（第 14 期跑全量自检时真的见过这条 stderr）。
        """
        win = self.tk.Tk()
        win.withdraw()
        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = self.fake.root
            pet = pet_ui.attach(fake, autostart=False)
            cloud = pet.cloud()
            cloud.show(pinned=False, hold=200)
            self.assertIsNotNone(cloud._hold, '播报形态该有一个到点自收的定时器')
            win.destroy()
            self.assertIsNone(cloud._hold)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def placed_cloud(self, anchor=(1200.0, 320.0), bottom=384.0):
        """按给定的锚点（三虎嘴边）／下沿摆一朵云：几何用例都从这里出发。

        第 22 期：整朵云与尾巴共用一个锚点（_anchor），钉住它就等于钉住了「贴片在屏幕上的哪」。
        """
        cloud = self.cloud()
        cloud._anchor = lambda: anchor
        cloud._bottom = lambda: bottom
        cloud._render()
        return cloud

    def test_the_cloud_stands_left_of_the_pet_with_its_bottom_lined_up(self):
        """第 18 期：云身整个站在三虎左边，浮窗下沿与贴片下沿对齐；第 22 期尾巴尖指向嘴边。"""
        mouth = (1200.0, 320.0)
        cloud = self.placed_cloud(anchor=mouth, bottom=384.0)
        cloud._work_right = lambda: 1920          # 钉死屏幕右界：否则几何结果随本机（含隐藏桌面）的显示器宽度变
        left, top = cloud._origin()
        self.assertEqual(left + cloud.total_width(), mouth[0] + pet_cloud.TIP_IN,
                         '整朵云站在三虎左边（尾巴尖往云身里缩 TIP_IN）')
        self.assertEqual(top + cloud._body + pet_cloud.TAIL, 384.0,
                         '下沿与三虎对齐（用户要的「底部和三虎对齐」）')
        tip_x, tip_y = cloud._tip()
        self.assertEqual(tip_x, int(mouth[0] - left), '尾巴尖落在嘴边那一列')
        self.assertGreaterEqual(tip_y, 8)
        self.assertLessEqual(tip_y, cloud._body + pet_cloud.TAIL)

    def test_the_cloud_never_runs_off_the_screen(self):
        """第 18 期：三虎贴着屏幕右边时，云身整个让回屏幕里（原来会顶出去一半）。"""
        cloud = self.cloud()
        cloud._anchor = lambda: (1900.0, 320.0)
        cloud._bottom = lambda: 384.0
        cloud._work_right = lambda: 1920
        cloud._render()
        left, _top = cloud._origin()
        self.assertGreaterEqual(left, pet_cloud.MARGIN)
        self.assertLessEqual(left + cloud.total_width(), 1920 - pet_cloud.MARGIN)

    def test_the_cloud_flips_below_when_there_is_no_room_above(self):
        """第 18 期：全屏时三虎贴着屏幕顶，上方放不下就翻到它下面（这就是「全屏显示不正常」）。

        第 29 期第 3 条：翻下去之后，尾巴带改挂在云身**上方**，带子的尖头正落在脸颊上——
        从前尾巴还在画布下边，尖头顶多顶到画布上沿，离脸差一整条云身（用户报的「箭头没碰到脸」）。
        """
        cloud = self.cloud()
        cloud._anchor = lambda: (1200.0, 120.0)
        cloud._bottom = lambda: 84.0
        cloud._screen_height = lambda: 1080
        cloud._patch_rect = lambda: (1100.0, 0.0, 64.0, 84.0)     # 三虎就贴在屏幕顶
        cloud._render()
        self.assertTrue(cloud._flipped(), '上方连最小云身都放不下，就该翻下去')
        _left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        self.assertGreaterEqual(top, 84.0, '翻下去：云身整个在三虎下沿之外，不许压住猫')
        self.assertLess(tip_y, pet_cloud.TAIL, '带子在上：尖头落在画布最上面那一条带子里')
        self.assertAlmostEqual(top + tip_y, 120.0, delta=2, msg='尖头要顶在脸颊上')
        kind, points = cloud._tail_polygon()
        self.assertEqual(kind, 'poly')
        self.assertAlmostEqual(min(spot[1] for spot in points), float(tip_y), delta=2,
                               msg='多边形的上端就是那个尖头')

    def test_the_tail_is_a_curved_spike_pointing_at_the_cheek(self):
        """第 24 期第 2 条：尖角的两条边带弧度，尖头指三虎的脸颊（不再是嘴边）。"""
        cloud = self.placed_cloud()
        kind, points = cloud._tail_polygon()
        self.assertEqual(kind, 'poly')
        self.assertGreater(len(points), 3, '两条边是折线拟合出来的弧，不再是三点的直三角')
        tip_x, tip_y = cloud._tip()
        nearest = min(points, key=lambda spot: (spot[0] - tip_x) ** 2 + (spot[1] - tip_y) ** 2)
        self.assertAlmostEqual(nearest[0], tip_x, delta=2, msg='尖角指向三虎的脸颊')
        self.assertAlmostEqual(nearest[1], tip_y, delta=2)
        self.assertLess(points[0][0], nearest[0], '底边留在云身这一侧，尖角朝三虎指')

        def off_line(spot, start, end):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            return abs((spot[0] - start[0]) * dy - (spot[1] - start[1]) * dx) / length

        self.assertGreater(off_line(points[3], points[0], nearest), 1.5,
                           '边往外鼓——「尖锐有弧度」看的就是这个')
        for x, y in points:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x, cloud.total_width())
            self.assertLessEqual(y, cloud._body + pet_cloud.TAIL)

    def test_the_tail_base_hides_inside_the_body(self):
        """第 21 期：底边长在云身里（被云身盖住），接缝才看不出来——四种形状都得成立。

        第 31 期：这条原先在「没摆放」的云上算几何——尾巴朝上还是朝下由当时的屏幕空间
        （_flipped）决定，同一份代码会随机红。这里用 placed_cloud 把锚点钉住，再把朝向也钉死，
        两种朝向各测一遍。

        尾巴多边形用的是画布坐标（翻转时云身整体下移一条尾巴带，见 _shift），而 inside_shape
        量的是云身自己的局部坐标——所以先减掉那一条偏移，两者的口径才对得上。
        """
        cloud = self.placed_cloud()
        for shape in pet_cloud.SHAPES:
            for up in (False, True):
                with self.subTest(shape=shape, up=up):
                    cloud.shape = shape
                    cloud._flipped = lambda up=up: up
                    cloud._render()
                    _kind, points = cloud._tail_polygon()
                    shift = cloud._shift()
                    for x, y in (points[0], points[-1]):
                        self.assertTrue(pet_cloud.inside_shape(shape, cloud.width(), cloud._body, x, y - shift),
                                        '底边两点都要落在云身里：%s (%.1f, %.1f)' % (shape, x, y))

    def test_the_record_is_numbered_one_line_at_a_time(self):
        """第 24 期第 7 条：编号和正文写在同一行，条与条之间不空行（每行放满再自动换行）。"""
        cloud = self.cloud()
        cloud.append(pet_cloud.SPEAKER + '：二号')
        body = cloud._body_text()
        lines = body.split('\n')
        self.assertEqual(len(lines), len(cloud.lines), '一条记录一行')
        gap = pet_cloud.NUMBER_GAP
        self.assertTrue(lines[0].startswith('1.' + gap + pet_cloud.WELCOME))
        self.assertIn('二号', lines[-1])
        for index, line in enumerate(lines, 1):
            self.assertTrue(line.startswith('%d.' % index + gap), '编号与正文同一行：' + line)
        self.assertNotIn('\n\n', body, '不再空行间隔，地方都要用来放字')

    def test_the_newest_line_is_always_in_view(self):
        """操作对话框只露最近五步，长记录不再把页面操作区挡住。"""
        cloud = self.cloud()
        for index in range(30):
            cloud.append(pet_cloud.SPEAKER + '：第 %d 行' % index)
        rows = cloud._body_text().split('\n')
        self.assertEqual(len(rows), pet_cloud.CHAT_VISIBLE_STEPS)
        self.assertIn('第 29 行', rows[-1], '最新步骤必须保留')
        self.assertNotIn('第 0 行', cloud._body_text(), '过期步骤不显示')
        self.assertEqual(cloud._scroll, cloud._scroll_limit(), '有单步长文本时默认仍停在最新位置')

    def test_the_wheel_does_not_scroll_the_main_page(self):
        """云框仍接住滚轮；五步上限下不会改变主界面或云框位置。"""
        cloud = self.cloud()
        for index in range(30):
            cloud.append(pet_cloud.SPEAKER + '：第 %d 行' % index)
        bottom = cloud._scroll
        self.assertEqual(cloud.wheel(_Wheel(120)), 'break', '云朵框先接住滚轮')
        self.assertLessEqual(cloud._scroll, bottom, '滚轮不应展开旧步骤或带动主界面')

    def test_the_bubble_emerges_with_a_fade(self):
        """第 16 期：交互时云朵框以浮出的形式出现（淡入），收起时把定时器一起收回来。"""
        cloud = self.cloud()
        self.assertIsNotNone(cloud._fade, '露面的那一下该有一段淡入')
        self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA)
        cloud.close()
        self.assertFalse(cloud.visible, '收起＝立刻不再算「露着」')
        self.assertIsNotNone(cloud._fade, '淡入那串定时器换成渐隐那一串（同一个槽位）')
        self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA, '收场先淡下去')

    def test_a_reply_that_needs_a_nod_rings_the_notification_bubble(self):
        """第 16 期：三虎要用户点头时，除了写进记录，还要弹一块通知气泡。"""
        cloud = self.cloud()
        seen = []
        original = self.pet.confirm
        self.pet.confirm = lambda text, title=None: seen.append((text, title))
        self.addCleanup(setattr, self.pet, 'confirm', original)
        cloud.queue.put({'text': '开始批量生成',
                         'lines': [pet_cloud.SPEAKER + '：开始批量生成。',
                                   pet_cloud.SPEAKER + '：' + pet_cloud.CONFIRM_PREFIX + '半自动：付费步骤需你确认'],
                         'result': None})
        self.assertEqual(cloud.drain(), 1)
        self.assertEqual(len(seen), 1, '要用户点头的事不能悄没声息')
        self.assertIn('付费步骤需你确认', seen[0][0])

    def test_every_line_in_the_record_is_signed_by_the_pet_name(self):
        """第 15 期：猫咪叫三虎——记录里每句话都挂在它名下，名字只有一处定义。"""
        self.assertEqual(pet_cloud.SPEAKER, pet_agent.PET_NAME)
        self.assertEqual(pet_cloud.SPEAKER, '三虎')
        self.assertTrue(pet_cloud.WELCOME.startswith(pet_agent.PET_NAME + '：'))
        for line in pet_cloud.reply_lines({'reply': '开始批量生成。', 'decision': {'run': True}}):
            self.assertTrue(line.startswith(pet_agent.PET_NAME + '：'), line)

    def test_double_clicking_the_pet_opens_the_chat(self):
        """第 19 期：双击＝直接和三虎说话（开关交给单击）。"""
        self.assertTrue(self.pet.canvas.bind('<Double-Button-1>'), '双击贴片应当接了入口')
        self.assertIsNotNone(self.pet.double_click())
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible)
        self.assertTrue(cloud.pinned, '双击是对话形态：带输入行')

    def test_a_line_gets_an_answer_back_in_the_record(self):
        cloud = self.cloud()
        self.pet.agent.set_level('semi')      # 第 22 期默认档是「只提醒」，说「我来做」要走半自动
        text = self.answer(cloud, '查一下进度')
        self.assertIn('您：查一下进度', text)
        self.assertIn(pet_cloud.SPEAKER + '：好，把进度面板打开。', text)
        self.assertIn(pet_cloud.SPEAKER + '：', text)

    def test_the_question_is_recorded_as_a_cloud_command(self):
        cloud = self.cloud()
        self.answer(cloud, '查一下进度')
        self.pet.pump()
        self.assertIn(('intent.command', 'cloud'),
                      [(item['kind'], item.get('source')) for item in self.pet.bus.history])

    def test_a_confirm_without_a_pending_task_does_the_page_task(self):
        """第 31 期第 6 条：提示框上那颗「确认」按下去不能没反应（用户报的哑键）。

        第 29 期遇到「只是播报、没有待办」时只把状态写成 EMPTY 那句小字——字太小，
        用户看到的就是一颗死键。现在的口径：按钮就照「这一页该做的事」办。
        """
        cloud = self.cloud()
        cloud.propose('')                     # 这一趟只是播报，没有要用户点的事
        lines = cloud.transcript().split('\n')
        self.assertEqual(lines[0], pet_cloud.WELCOME, '记录还是从开场那一句起')
        self.assertIn(pet_cloud.SPEAKER + '：', lines[-1],
                        '第 29 期第 5 条：一打开三虎先问这一页该做的事')
        self.assertIn(pet_ui.PAGE_ASKS[0][0], lines[-1])
        command = pet_ui.PAGE_ASKS[0][1]
        self.addCleanup(self.wait_for_the_reply, cloud)
        self.assertEqual(cloud.page_ask(), command, '现场问出这一页该做的事')
        self.assertEqual(cloud.submit(), command)
        self.assertIn('您：' + command, cloud.transcript(), '确认这件事要记进记录')
        self.assertNotEqual(cloud.status.cget('text'), pet_cloud.EMPTY)

    def test_a_busy_cloud_does_not_start_a_second_question(self):
        cloud = self.cloud()
        cloud.busy = True
        cloud.propose('查一下进度')
        self.assertEqual(cloud.submit(), '查一下进度')
        self.assertEqual(cloud.status.cget('text'), pet_cloud.BUSY)
        self.assertNotIn('您：查一下进度', cloud.transcript(), '上一问还没回来，不该又发一问')

    def test_a_broken_answer_still_says_something(self):
        cloud = self.cloud()
        agent = self.pet.agent

        def boom(text, at=None):
            raise RuntimeError('台账坏了')

        original = agent.dispatch
        agent.dispatch = boom
        self.addCleanup(setattr, agent, 'dispatch', original)
        lines = cloud.ask('查一下进度')
        self.assertEqual(len(lines), 1)
        self.assertIn('台账坏了', lines[0])

    def test_a_broadcast_opens_the_cloud_by_itself_and_then_hides_it(self):
        """第 15 期：宠物一说话，云朵框自己冒出来（不用用户手动打开），到点自己收。"""
        self.assertEqual(self.pet.broadcast('播报一句'), self.pet._prefix_output('播报一句'))
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible, '说话就该看见云，不必先双击贴片')
        self.assertTrue(cloud.pinned, '自动冒出来的云带输入行，用户可以马上接一句')
        self.assertIsNotNone(cloud._hold, '冒出来的时候就定好了什么时候收')
        self.assertIn('播报一句', cloud.transcript())
        self.assertTrue(cloud._expire(), '到点应当自己收起来')
        self.assertFalse(cloud.visible)

    def test_an_open_cloud_is_kept_by_a_broadcast_and_the_timer_moves_back(self):
        cloud = self.cloud()
        cloud._pointer_inside = lambda: False
        cloud.show(pinned=True, hold=50)
        self.pet.broadcast('插播一句')
        self.assertTrue(cloud.visible, '开着的时候插一句话不该把云收掉')
        self.assertTrue(cloud.pinned)
        self.assertIn('插播一句', cloud.transcript())
        cloud.busy = True
        self.assertFalse(cloud._expire(), '还在等回复时先别收，答案回来要有地方贴')
        cloud.busy = False
        self.assertTrue(cloud._expire(), '交互结束了就到点自己收')

    def test_the_cloud_stays_open_while_the_pointer_rests_on_it(self):
        """第 27 期第 2 条：用户正把鼠标停在云里读，到点也不许收——挪开之后下一次到点才收。"""
        cloud = self.cloud()
        cloud._pointer_inside = lambda: True
        self.assertFalse(cloud._expire(), '指针还在云上就别收')
        self.assertTrue(cloud.visible, '云还开着')
        self.assertIsNotNone(cloud._hold, '每隔 WATCH_RECHECK_MS 回头看一次指针走了没')
        cloud._pointer_inside = lambda: False
        self.assertTrue(cloud._expire(), '指针挪开了，下一次到点就真收')
        self.assertFalse(cloud.visible)

    def test_the_pointer_check_asks_the_window_for_real_coordinates(self):
        """指针在不在云上直接按窗口的屏幕坐标算——<Enter>／<Leave> 会被子控件吃掉。"""
        cloud = self.cloud()
        self.win.update_idletasks()
        x, y = cloud.win.winfo_rootx(), cloud.win.winfo_rooty()
        cloud.win.winfo_pointerxy = lambda: (x + 5, y + 5)
        self.assertTrue(cloud._pointer_inside(), '落在窗里就是在看这一条')
        cloud.win.winfo_pointerxy = lambda: (x - 40, y - 40)
        self.assertFalse(cloud._pointer_inside(), '飘到窗外就不算')
        self.assertEqual(cloud.win.bind('<Enter>'), '', '第 27 期第 2 条：不再靠 <Enter> 判断')

    def test_the_record_text_uses_the_shared_font(self):
        # 三虎对话框正文必须从设计系统取字体；Tk 的最终字号可能受系统 DPI 缩放影响。
        from tkinter import font as tkfont
        from ui_tokens import FONTS
        cloud = self.cloud()
        cloud.show(pinned=True)
        spec = tkfont.Font(root=self.win, font=cloud.label.cget('font'))
        self.assertEqual(pet_cloud.FONT, FONTS['pet_body'], '正文只从设计系统 pet_body token 取值')
        self.assertGreater(spec.cget('size'), 0, 'Tk 控件必须收到有效正文尺寸')
        self.assertEqual(pet_cloud.STICKER_FONTS[0], 13, '贴纸框也从 13 号起试')

    def test_the_cloud_does_not_steal_the_keyboard_when_it_opens_itself(self):
        self.pet.broadcast('播报一句')
        self.win.update()
        self.assertIsNone(self.win.grab_current(), '自动冒出来的云不抓键盘')
        self.assertEqual(self.pet.cloud().pinned, True)

    def test_typing_and_answering_push_the_auto_close_back(self):
        """交互没结束就不收：发出问题、答案贴回来，两处都把「什么时候收」往后推。"""
        cloud = self.cloud()
        first = cloud._hold
        self.assertIsNotNone(first)
        # 连「这一页该做的事」都问不出来＝这一下真的没有可办的事，才不该重排定时。
        original_task = self.pet.chat_task
        self.pet.chat_task = lambda index=None: ('', '')
        self.addCleanup(setattr, self.pet, 'chat_task', original_task)
        cloud.propose('')
        self.addCleanup(self.wait_for_the_reply, cloud)
        cloud.submit()
        self.assertEqual(cloud._hold, first)
        cloud.queue.put({'text': '查一下进度',
                         'lines': [pet_cloud.SPEAKER + '：好，把进度面板打开。'], 'result': None})
        cloud.busy = True
        self.assertEqual(cloud.drain(), 1)
        self.assertNotEqual(cloud._hold, first, '答案贴回来之后重新计时，留一段读完的时间再收')
        self.assertFalse(cloud.busy)
        second = cloud._hold
        cloud.propose('查一下进度')
        self.assertTrue(cloud.submit().startswith('查一下进度'))
        self.assertNotEqual(cloud._hold, second, '问题发出去之后也要重新计时')

    def test_the_same_sentence_is_not_said_twice_in_a_row(self):
        expected = self.pet._prefix_output('同一句')
        self.assertEqual(self.pet.broadcast('同一句'), expected)
        self.assertEqual(self.pet.broadcast('同一句'), '', '同一句话不该连着说两遍')
        self.assertEqual(self.pet.cloud().lines.count('同一句'), 1)

    def test_the_record_survives_closing_and_reopening(self):
        cloud = self.cloud()
        self.answer(cloud, '查一下进度')
        self.assertIsNone(self.pet.toggle_chat(), '开着的时候再点一次应当收起')
        self.assertIsNotNone(self.pet.toggle_chat())
        self.assertIs(self.pet.cloud(), cloud, '云朵框实例只建一次，记录才留得住')
        self.assertIn('您：查一下进度', cloud.transcript())

    def test_closing_is_idempotent(self):
        cloud = self.cloud()
        self.assertIsNone(cloud.close())
        self.assertIsNone(cloud.close())
        self.assertFalse(cloud.visible)
        self.assertEqual(cloud.errors, [])

    def test_the_record_keeps_only_the_last_lines(self):
        cloud = pet_cloud.Cloud(self.pet, self.win)
        for index in range(pet_cloud.LINE_LIMIT + 20):
            cloud.append('第 %d 行' % index)
        self.assertEqual(len(cloud.lines), pet_cloud.LINE_LIMIT)
        self.assertEqual(cloud.lines[-1], '第 %d 行' % (pet_cloud.LINE_LIMIT + 19))

    def test_a_long_record_does_not_make_the_cloud_grow_forever(self):
        cloud = self.cloud()
        for index in range(60):
            cloud.append('第 %d 行' % index)
        cloud._render()
        self.assertLessEqual(int(cloud.canvas.cget('height')), pet_cloud.TAIL + pet_cloud.MAX_BODY)

    def test_reply_lines_says_why_the_pet_will_not_act(self):
        lines = pet_cloud.reply_lines({'reply': '开始批量生成。',
                                       'decision': {'run': False, 'reason': '半自动：付费步骤需你点一下确认'}})
        self.assertEqual(lines[0], pet_cloud.SPEAKER + '：开始批量生成。')
        self.assertIn('暂时不动手——半自动', lines[1])

    def test_reply_lines_never_comes_back_empty(self):
        lines = pet_cloud.reply_lines(None)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(pet_cloud.SPEAKER + '：'))
        # 第 23 期：放行的那一条不再补「我可以接着做」这类空话——真的做了什么由
        # Pet.run_plan 的结果跟在后面说（见 CloudTests 里那条「说了就真的做」）。
        self.assertEqual(len(pet_cloud.reply_lines({'decision': {'run': True}})), 1)
        lines = pet_cloud.reply_lines({'reply': '开始批量生成首帧。', 'decision': {'run': False,
                                                                        'reason': '只提醒模式：不自动执行'}})
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith(pet_cloud.SPEAKER + '：' + pet_cloud.CONFIRM_PREFIX))

    def test_a_cloud_that_cannot_build_is_recorded_not_raised(self):
        original = pet_cloud.Cloud.build

        def boom(self):
            raise RuntimeError('画不出来')

        pet_cloud.Cloud.build = boom
        self.addCleanup(setattr, pet_cloud.Cloud, 'build', original)
        self.pet._cloud = None                     # 别用上一条用例建好的云：这里要的是「建不出来」
        self.assertIsNone(self.pet.open_chat(), '建不出来就别交出半个控件')
        names = [name for name, _text in self.pet.errors]
        self.assertTrue(any(name.startswith('chat') for name in names), '建不起来要留记录')
        self.assertTrue(self.pet.notice, '点了「和宠物说话」必须说一句，不能没反应')

    def test_closing_the_main_window_takes_the_cloud_with_it(self):
        win = self.tk.Tk()
        win.withdraw()
        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = self.fake.root
            pet = pet_ui.attach(fake, autostart=False)
            self.assertIsNotNone(pet.open_chat())
            win.destroy()
            self.assertIsNone(pet.chat)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def test_the_bubble_points_at_the_cloud(self):
        self.assertIn(pet_ui.CHAT_HINT, self.pet.text())
        self.assertIn('云朵框', pet_ui.CHAT_HINT)


class SingleDialogTests(PetTestCase):
    """第 21 期：用户要的「每次三虎只能启动一个聊天框」——同一时刻只留一个框。"""

    def test_the_progress_bubble_waits_until_the_chat_closes(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        self.assertTrue(self.pet.cloud_visible(), '云朵框正开着')
        self.assertFalse(self.pet.cloud_visible(sticker_only=True),
                         '云朵这一形态不算贴纸——只按贴纸判就会漏掉这一类，又冒一个框出来')
        self.assertEqual(self.pet.progress_voice(force=True), '', '已经有一个框了，就不再冒新的')
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD, '还是那一个框，没被顶掉')
        cloud.close()
        self.assertFalse(self.pet.cloud_visible())

    def test_opening_the_chat_twice_keeps_the_same_window(self):
        cloud = self.pet.cloud()
        self.assertIs(cloud, self.pet.cloud(), '云朵框只建一次')
        self.pet.open_chat()
        self.assertIs(self.pet.chat, cloud)
        self.pet.open_chat()
        self.assertIs(self.pet.chat, cloud, '再打开还是同一朵云，不会冒出第二个框')


class FollowTests(PetTestCase):
    """第 21 期：助手界面一动（挪位、缩放），云朵框跟着重新摆位。"""

    def test_the_patch_and_the_paws_are_watched(self):
        watched = self.pet.cloud()._watchers()
        self.assertIn(self.pet.canvas, watched, '三虎动了云就要跟着动')
        self.assertIn(self.pet.paws, watched)

    def test_a_configure_of_the_patch_moves_the_cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        moved = []
        cloud._place_window = lambda: moved.append('moved') or (0, 0)
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(moved, ['moved'], '贴片自己动一下也要重摆')
        cloud.follow(_Event(widget=self.fake.header_status))
        self.assertEqual(moved, ['moved'], '别的控件冒泡上来的不认领')

    def test_nothing_is_moved_while_the_cloud_is_hidden(self):
        cloud = self.pet.cloud()
        moved = []
        cloud._place_window = lambda: moved.append('moved') or (0, 0)
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(moved, [], '收着的时候不用摆')

    def test_the_drawn_tail_follows_the_pet_when_the_ui_shrinks(self):
        """第 25 期第 7 条：界面一缩（贴片跟着挪），尾巴要当场重画着指回三虎。

        只把浮窗挪个位置是不够的——那根尖角画在画布上，不重画就停在旧坐标上了。
        所以这里量的是**画布上真画出来的那个尖角**（最后一个多边形图元），不是算式里的 _tip()。
        """
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        spot = [1200.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE)]
        cloud._patch_rect = lambda: tuple(spot)
        cloud._work_right = lambda: 1920
        cloud._screen_height = lambda: 1080
        cloud._bottom = lambda: spot[1] + spot[3] + pet_cloud.ANCHOR_DROP

        def drawn_tip():
            coords = cloud.canvas.coords(cloud.canvas.find_withtag('cloud')[-1])
            return list(zip(coords[0::2], coords[1::2]))

        def tip_offset():
            cheek = cloud._cheek()
            left, top = cloud._origin()
            points = drawn_tip()
            return min(((x + left - cheek[0]) ** 2 + (y + top - cheek[1]) ** 2) ** 0.5
                       for x, y in points)

        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertLess(tip_offset(), 2.0, '尾巴要指在脸颊上')
        spot[0], spot[1] = 640.0, 320.0                  # 主界面缩小／贴片挪位
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertLess(tip_offset(), 2.0, '界面一动，画出来的尾巴就要当场跟上')


class ViewportTests(PetTestCase):
    """第 22 期第 5b 条：文字外面套一层取景框——记录再长也滚不到输入行与「发送」上面。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.canvas.update_idletasks()
        return cloud

    def fill(self, cloud, count=14):
        for index in range(count):
            cloud.append('三虎：第 %d 条记录，用来把这一朵云撑得比取景框还高。' % index)
        cloud.canvas.update_idletasks()
        return cloud

    def test_the_label_hangs_inside_a_viewport(self):
        cloud = self.cloud()
        self.assertIsNotNone(cloud.clip, '文字外面要有取景框')
        self.assertEqual(str(cloud.label.winfo_parent()), str(cloud.clip), '标签得挂在框里才裁得住')

    def test_the_viewport_stops_above_the_input_row(self):
        cloud = self.fill(self.cloud())
        room = float(cloud.clip.winfo_height())
        self.assertGreater(room, 20, '取景框要有真实高度，这条才盯得住')
        top = float(cloud.clip.place_info()['y'])
        row_y = float(cloud.chat_row.place_info()['y'])
        self.assertLessEqual(top + room, row_y, '取景框下沿不能压到输入行')

    def test_a_long_record_scrolls_instead_of_overflowing(self):
        cloud = self.fill(self.cloud())
        limit = cloud._scroll_limit()
        self.assertGreater(limit, 0, '记录比取景框高就该能滚')
        cloud.scroll_by(10 ** 6)
        self.assertEqual(cloud._scroll, limit)
        self.assertEqual(float(cloud.label.place_info()['y']), float(-limit), '滚到底＝整条标签往上挪出框')


class InsideWindowTests(PetTestCase):
    """第 22 期第 9 条：整朵云在屏幕外摆不下时，自动挪进助手界面里。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._window_rect = lambda: (100, 100, 900, 700)      # 助手界面在屏幕上的位置（固定，不随本机变）
        cloud._work_right = lambda: 1920
        cloud._screen_height = lambda: 1080
        return cloud

    def test_a_cloud_that_fits_is_left_alone(self):
        cloud = self.cloud()
        self.assertIsNone(cloud._inside_window(200, 200), '摆得下就照原来的落点，界面上看不出变化')

    def test_a_cloud_past_the_right_edge_is_pulled_back(self):
        cloud = self.cloud()
        spot = cloud._inside_window(1900, 200)
        self.assertIsNotNone(spot, '顶出屏幕右边就该挪回界面里')
        self.assertLessEqual(spot[0] + cloud.total_width(), 1920)
        self.assertGreaterEqual(spot[0], 0)

    def test_a_cloud_above_the_screen_comes_down(self):
        cloud = self.cloud()
        spot = cloud._inside_window(200, -40)
        self.assertIsNotNone(spot, '顶出屏幕上边就该挪回界面里')
        self.assertGreaterEqual(spot[1], 0)


class FadeAndReadTests(PetTestCase):
    """第 24 期第 8 条：四种对话框都留够读完的时间，然后延时淡出去。"""

    def test_every_shape_fades_out_instead_of_vanishing(self):
        cloud = self.pet.cloud()
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                cloud.show(pinned=False, hold=1, shape=shape)
                cloud.close()
                self.assertFalse(cloud.visible, shape)
                self.assertIsNotNone(cloud._fade, shape + '：收场该有一段渐隐')
                self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA)

    def test_the_fade_out_walks_all_the_way_to_hidden(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, hold=1)
        queued = []
        original = cloud.win.after          # 浮窗是自己一个 Toplevel，定时器排在它身上
        cloud.win.after = lambda ms, fn=None, *a: queued.append(fn) or 'job'
        self.addCleanup(setattr, cloud.win, 'after', original)
        cloud.close()
        self.assertTrue(queued, '渐隐要一档一档排下去')
        for _tick in range(len(pet_cloud.FADE_OUT_STEPS) + 2):
            if not queued:
                break
            queued.pop(0)()                   # 走一档：下一档又排进 queued 里
        self.assertIsNone(cloud._fade, '走到最后一档要收干净，别留定时器')
        self.assertFalse(cloud.visible)

    def test_a_longer_line_stays_longer(self):
        cloud = self.pet.cloud()
        short = cloud.read_hold('三虎：好。')
        long = cloud.read_hold('三虎：' + '这句话很长，' * 40)
        self.assertEqual(short, pet_cloud.HOLD_MS, '短句子有底线保底')
        self.assertGreater(long, short, '话越长停得越久')
        self.assertLessEqual(long, pet_cloud.READ_MAX_MS, '再长也不超过上限')

    def test_the_armed_hold_matches_the_reading_time(self):
        cloud = self.pet.cloud()
        text = '三虎：' + '把今天该做的都做完了，镜头、首帧、资产一项都不缺。' * 3
        seen = []
        original = self.win.after
        self.win.after = lambda ms, fn=None, *a: seen.append((ms, fn)) or 'job'
        self.addCleanup(setattr, self.win, 'after', original)
        # R1948：停留随用户操作疏密伸缩；先记一笔动作，落在「正常操作」这一档（十秒）。
        self.pet.note_activity()
        cloud.broadcast(text)
        self.assertTrue(seen, '说完要排一个「什么时候收」的定时器')
        self.assertEqual(seen[-1][0], pet_cloud.PET_CLOUD_AUTO_CLOSE_MS, '排的毫秒数＝统一十秒配置')
        self.assertGreaterEqual(seen[-1][0], pet_cloud.HOLD_MS)


class ForegroundTests(PetTestCase):
    """第 30 期第 3 条：用户切到别的应用上时，三虎不再把聊天框／气泡顶出来。

    「切到别的应用」＝前台窗口不是本进程的窗口（pet_ui.our_process_in_front）。只拦三虎自己
    冒出来的那几路（心跳播报、进度气泡、主动询问、失败提醒），用户自己点开的对话框一条都不拦。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.counts = {"storyboards": 3, "adopted": 0, "shots": 0, "frames": 0}
        self.pet.counts = lambda: dict(self.counts)

    def away(self):
        self.pet.front = lambda: False

    def here(self):
        self.pet.front = lambda: True

    def lines(self):
        return self.pet.cloud().transcript()

    # ── 判据本身 ────────────────────────────────────────────────────────────
    def test_without_a_judge_nothing_is_blocked(self):
        self.assertIsNone(self.pet.front, "自检与假宿主走的就是「不设这道闸」")
        self.assertTrue(self.pet.attending())

    def test_attach_carries_the_judge(self):
        handle = lambda: True
        quiet = pet_ui.attach(self.fake, autostart=False, front=handle)
        self.assertIs(quiet.front, handle)

    def test_a_broken_judge_keeps_talking_and_records_it(self):
        def boom():
            raise RuntimeError("问不到前台窗口")

        self.pet.front = boom
        self.assertTrue(self.pet.attending(), "拦错一边就是把播报全吞了，宁可多说一句")
        self.assertTrue(any(name == "front" for name, _text in self.pet.errors))

    def test_the_windows_api_answers_a_yes_or_no(self):
        self.assertIn(pet_ui.our_process_in_front(), (True, False), "问不出来一律当 True，绝不抛")

    # ── 自动播报 ────────────────────────────────────────────────────────────
    def test_the_heartbeat_keeps_quiet_in_another_app(self):
        self.pet.tick_broadcast()                     # 第一拍只对表
        self.away()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "", "用户在别的应用里：这一拍不许冒泡")
        self.assertNotIn("分镜 JSON", self.lines())
        self.assertFalse(self.pet.cloud().visible)

    def test_coming_back_hears_the_news(self):
        self.pet.tick_broadcast()
        self.away()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "")
        self.here()
        self.assertIn("分镜 JSON", self.pet.tick_broadcast(), "回到软件里再说不迟")

    def test_the_progress_bubble_waits_too(self):
        self.away()
        self.assertEqual(self.pet.progress_voice(force=True), "", "进度气泡也不许冒")
        self.assertNotIn("进度", self.lines())

    def test_nothing_pops_while_the_user_is_in_a_sub_window(self):
        """人在阶段配置等子窗口里（本进程在前台，但不在主界面）：自动冒泡一律不弹。"""
        self.here()
        self.pet.main_view = lambda: False
        self.assertFalse(self.pet.can_pop())
        self.assertEqual(self.pet.progress_voice(force=True), "", "进度气泡不许压在子窗口上")
        self.assertEqual(self.pet.whisper("顺手夸一句"), "")
        self.pet.main_view = lambda: True
        self.pet.tick_broadcast()                     # 第一拍只对表
        self.pet.main_view = lambda: False
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "", "心跳播报也不冒")
        self.assertFalse(self.pet.cloud().visible)
        self.pet.main_view = lambda: True
        self.assertTrue(self.pet.can_pop(), "回到主界面照常")
        self.assertIn("分镜 JSON", self.pet.tick_broadcast())

    def test_a_sub_window_does_not_pause_the_auto_run(self):
        """子窗口不是「离开软件」：watch_focus 仍只看 attending，不因打开配置页把自动执行暂停。"""
        self.here()
        self.pet.main_view = lambda: False
        self.assertTrue(self.pet.attending())
        self.assertTrue(self.pet.watch_focus(at=self.now + 10 ** 6), "人还在软件里")
        self.assertFalse(self.pet.agent.paused)

    def test_the_main_view_judge_follows_the_focus_toplevel(self):
        class Top:
            def __init__(self, top):
                self.top = top

            def winfo_toplevel(self):
                return self.top

        main, other = type("Win", (), {})(), object()
        self.addCleanup(setattr, self.pet, "win", self.pet.win)
        self.pet.win = main
        main.focus_get = lambda: Top(other)
        self.assertFalse(self.pet.in_main_view(), "焦点在子窗口里")
        main.focus_get = lambda: Top(main)
        self.assertTrue(self.pet.in_main_view())
        main.focus_get = lambda: None
        self.assertTrue(self.pet.in_main_view(), "没有焦点时问不出来，当 True")

        def boom():
            raise KeyError("popdown")

        main.focus_get = boom
        self.assertTrue(self.pet.in_main_view(), "Tk 抛错也当 True，绝不抛")

    def test_a_line_said_while_away_goes_into_the_record_only(self):
        """第 49 期第 1 条：人切到别的应用时，这句话只进云朵记录、不把框顶出来。

        原来照顶——那一刻贴片量出来的坐标是假的（主窗口没映射），框就落到屏幕另一头，
        正是用户报的「从右边跳到左边」。
        """
        self.away()
        self.assertEqual(self.pet.broadcast('这一句只说给记录听'),
                         self.pet._prefix_output('这一句只说给记录听'))
        cloud = self.pet.cloud()
        self.assertFalse(cloud.visible, '人在别的应用里，不弹框')
        self.assertIn('这一句只说给记录听', cloud.transcript(), '话不许丢：记在记录里')
        self.here()
        self.pet.broadcast('回来了就冒')
        self.assertTrue(cloud.visible, '人在界面里：照常冒')


    def test_the_oneclick_offer_waits_too(self):
        self.away()
        self.pet.offer_oneclick()                     # 第一拍只对表
        self.now += pet_ui.OFFER_SECONDS + 1
        self.assertEqual(self.pet.offer_oneclick(), "")
        self.assertNotIn("一键执行", self.lines())

    def test_the_failure_notice_waits_too(self):
        self.away()
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertEqual(self.pet.announce_failures(), "", "失败提醒先记着，不弹")
        self.assertNotIn("超时", self.lines())
        self.here()
        self.assertTrue(self.pet.announce_failures(), "回来之后再提醒")

    def test_the_users_own_chat_still_opens(self):
        """自己点开的对话框不是「打扰」：切到别的应用时也不拦。"""
        self.away()
        self.assertIsNotNone(self.pet.open_chat())
        self.assertTrue(self.pet.cloud().visible)

    # ── 第 60 期第 4 条：对话框只能在助手界面上面，不许穿到别的应用上 ─────────
    def showing(self, value=True):
        """自检里主窗口是 withdraw 的：招呼只在主窗口露着时才冒，这里按用例需要钉住它。"""
        self.pet.window_visible = lambda: value

    def test_the_cloud_is_not_topmost_while_the_user_is_away(self):
        self.pet.open_chat()
        cloud = self.pet.cloud()
        self.assertTrue(cloud.win.attributes('-topmost'), '人在界面里：照旧置顶')
        self.away()
        self.assertFalse(cloud.sync_topmost(), '人切走了：不许再压着别的应用')
        self.assertFalse(bool(cloud.win.attributes('-topmost')))

    def test_a_cloud_left_open_is_put_away_when_the_user_leaves(self):
        self.pet.open_chat()
        cloud = self.pet.cloud()
        self.away()
        self.assertTrue(self.pet.guard_cloud_away(), '这一拍真的收了一朵')
        self.assertFalse(cloud.visible)
        self.assertIsNone(self.pet.chat)

    def test_the_heartbeat_keeps_the_cloud_off_other_apps(self):
        self.pet.open_chat()
        self.away()
        self.pet.pump()
        self.assertFalse(self.pet.cloud_visible(), '心跳一到就把露着的云收起来')

    def test_while_here_the_cloud_stays(self):
        self.pet.open_chat()
        self.assertFalse(self.pet.guard_cloud_away())
        self.assertTrue(self.pet.cloud_visible(), '人在界面里就别动它')

    def test_the_greeting_and_the_whisper_wait_for_the_user(self):
        self.showing()
        self.away()
        self.assertEqual(self.pet.greet(), '', '招呼不许穿到别的应用上')
        self.assertEqual(self.pet.whisper('随口一句'), '')
        self.assertEqual(self.pet.banner('一张便签'), '')
        self.assertFalse(self.pet.cloud_visible(), '一句都没冒出去')

    def test_the_greeting_still_comes_while_here(self):
        self.showing()
        self.here()
        self.assertEqual(self.pet.greet(), self.pet._prefix_output(pet_cloud.GREETING))

    # ── 第 35 期第 1 条：切出去＝三虎进入暂停状态（不再只是「各自闭嘴」） ───────
    def test_leaving_the_window_pauses_the_pet_after_a_grace(self):
        self.assertTrue(self.pet.watch_focus(), "第一拍人还在界面里")
        self.away()
        self.assertFalse(self.pet.watch_focus(), "人不在界面里：这一拍起算离开时间")
        self.now += pet_ui.AWAY_PAUSE_SECONDS - 1
        self.assertFalse(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "刚切出去那一下不暂停：alt-tab 一闪不折腾")
        self.now += 1
        self.assertFalse(self.pet.watch_focus())
        self.assertTrue(self.pet.agent.paused, "离开界面满 AWAY_PAUSE_SECONDS 就真的停下来")
        self.assertIn('您切去了别的应用', self.pet.agent.paused_reason)

    def test_an_alt_tab_and_back_never_pauses(self):
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS - 2
        self.pet.watch_focus()
        self.here()
        self.pet.watch_focus()
        self.assertFalse(self.pet.agent.paused, "闪一下就回来：一次都没暂停过")
        self.assertEqual(self.pet.notice, '')

    def test_coming_back_resumes_without_a_word(self):
        """第 37 期第 6 条：切回助手界面时不用弹聊天框——只把自动执行接上，一个字都不说。"""
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.assertTrue(self.pet.agent.paused)
        self.here()
        before = self.lines()
        self.assertTrue(self.pet.watch_focus(), "人回来了")
        self.assertFalse(self.pet.agent.paused, "回来就自动接着跑")
        self.assertNotIn('已回到助手界面', self.pet.notice)
        self.assertEqual(self.lines(), before, "回来说一个字都不冒")
        self.assertFalse(self.pet.cloud_visible(), "也没冒一朵框")

    def test_a_manual_pause_is_left_alone(self):
        self.pet.agent.pause('你自己按的暂停')
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.here()
        self.pet.watch_focus()
        self.assertTrue(self.pet.agent.paused, "手动按的暂停不替我恢复")
        self.assertEqual(self.pet.agent.paused_reason, '你自己按的暂停')
        self.assertNotIn('已回到助手界面', self.pet.notice)

    def test_a_resume_while_away_is_not_announced(self):
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.pet.click('resume')                       # 人不在界面里，自己从菜单按了「继续」
        self.here()
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused)
        self.assertNotIn('已回到助手界面', self.pet.notice, "不是我的暂停，就别替我说话")

    def test_without_a_judge_nothing_is_paused(self):
        self.pet.front = None
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "没有判据的假宿主什么都不做")

    def test_a_broken_judge_is_recorded_and_keeps_the_pet_running(self):
        def boom():
            raise RuntimeError('问不到前台窗口')

        self.pet.front = boom
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "问不出来宁可什么都不做，也不能替用户停")
        self.assertTrue(any(name == 'front' for name, _text in self.pet.errors),
                        "判据出错照旧记一笔（attending 那道闸自己收的）")


class ChatSizeTests(PetTestCase):
    """第 30 期第 4 条：聊天框尺寸收一档，文字尺寸一动不动。"""

    def test_the_chat_box_is_narrower_than_round_28(self):
        self.assertLess(pet_cloud.WIDTH, 372, "第 28 期那一档是 372，这一轮要更窄")
        self.assertLessEqual(pet_cloud.MAX_BODY, 236, "框身整体也收一档")
        self.assertGreaterEqual(pet_cloud.WIDTH, pet_cloud.MIN_WIDTH, "别收成一条缝：正文还要排得开")

    def test_the_text_size_is_only_one_step_smaller(self):
        """第 49 期第 3 条：这一期只收字号，一档一档连着（15 → 13），别的地方一动不动。"""
        from ui_tokens import FONTS
        self.assertEqual(pet_cloud.FONT, FONTS['pet_body'], "正文使用设计系统 pet_body 令牌")
        self.assertEqual(tuple(pet_cloud.STICKER_FONTS), (13, 12, 11, 10, 9, 8, 7, 6),
                         "贴纸那几档跟着收，仍然连成一串")

    def test_the_chat_still_holds_a_line(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.canvas.update_idletasks()
        box = pet_cloud.text_box(pet_cloud.SHAPE_CLOUD, cloud.width(), cloud._body)
        self.assertGreaterEqual(box[2], 240, "写字框还放得下一行十来个字")


class CloudFitTests(PetTestCase):
    """第 36 期第 11／12 条：回复框摆出三虎听得懂的指令；云朵框跟着文字收窄。

    第 7 条在这里一并盯住：主界面贴着屏幕上沿时，这一条内容上方放不下就整朵往下挪。
    """

    def test_the_commands_roll_inside_the_reply_box(self):
        """第 37 期第 4 条：基本指令放进回复框里、小字、自己往右滚，不再写「三虎听得懂：」。"""
        # UI 批次 2：原断言靠 'white'／'#FFFFFF' 字面差异通过，改为两色真不同时按颜色值比较
        import ui_widgets
        from ui_tokens import COLORS
        # 先装全局样式：open_chat() 建回复框时 LineInput 会调 setup_styles() 整表重写 TEntry，
        # 生产里 ui_theme.apply() 在启动时已做过同一件事；不先装，下面临时改的底色会被它盖回去。
        ui_widgets.setup_styles(self.win)
        style = self.ttk.Style(self.win)
        original_field_bg = style.lookup('TEntry', 'fieldbackground', '')
        style.configure('TEntry', fieldbackground=COLORS['background_primary'])
        self.addCleanup(style.configure, 'TEntry', fieldbackground=original_field_bg)
        cloud = self.pet.cloud()
        self.pet.open_chat()
        self.assertIn(cloud.hint, cloud.chat_row.winfo_children(), '小字就挂在回复框这一行里')
        # 第 39 期第 1 条：贴着左沿、从最左侧起步，底色跟输入框（不再是云身色那块贴片）。
        self.assertEqual(float(cloud.hint.place_info().get('relx')), 0.0, '贴着回复框左沿')
        self.assertEqual(cloud.hint.place_info().get('anchor'), 'w', '左对齐：小字往右长')
        self.assertEqual(str(cloud.hint.cget('bg')), cloud.field_bg(), '底色跟着 ttk.Entry 走')
        self.assertNotEqual(self.win.winfo_rgb(str(cloud.hint.cget('bg'))),
                            self.win.winfo_rgb(cloud.fill()), '不再刷云身色')
        self.assertGreaterEqual(pet_cloud.HINT_MS, 400, '慢慢挪')
        self.assertLess(pet_cloud.HINT_FONT[1], pet_cloud.REPLY_FONT[1], '小字比回复框的字小一档')
        self.assertIn(str(pet_cloud.HINT_FONT[1]), str(cloud.hint.cget('font')), '真的挂在这一档上')
        self.assertTrue(str(cloud.hint.cget('text')).strip(), '开着就露着一条')
        self.assertNotIn('三虎听得懂', pet_cloud.REPLY_HINTS, '那半句前缀删掉了')
        for word in ('右键功能', '进度面板', '设置模型', '自动化等级', '暂停', '重试失败项', '退出程序'):
            self.assertIn(word, pet_cloud.REPLY_HINTS)
        self.assertEqual(cloud.status.cget('text'), '', '这三句不再占提示行')

    def test_the_rolling_line_starts_at_the_left_and_marches_right(self):
        """整句从左往右移动，离场后才重新从左侧开始，不在中段循环拼接。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        first = str(cloud.hint.cget('text'))
        first_x = int(cloud.hint.place_info().get('x'))
        self.assertEqual(first, pet_cloud.REPLY_HINTS, '整句不截断')
        self.assertEqual(first_x, pet_cloud.HINT_X, '一露脸就在最左侧')
        cloud._hint_tick()
        second = str(cloud.hint.cget('text'))
        second_x = int(cloud.hint.place_info().get('x'))
        self.assertEqual(second, first, '移动时正文不从中间截断')
        self.assertEqual(second_x, first_x + pet_cloud.HINT_STEP_PX, '向右移动')
        cloud._hint_stop()
        self.assertEqual(cloud.hint.cget('text'), '', '收起后把字清干净')

    def test_clicking_the_hint_yields_to_the_reply_cursor(self):
        """点到提示层也必须进入输入框，不能把光标挡在灰字后面。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        cloud._focus_reply()
        self.assertEqual(cloud.reply.focus_get(), cloud.reply, '提示层点击后焦点回到输入框')
        self.assertEqual(cloud.hint.cget('text'), '', '用户开始输入时提示让位')
        cloud._restore_hint_after_reply()
        self.assertEqual(cloud.hint.cget('text'), pet_cloud.REPLY_HINTS, '离开空框后恢复说明')

    def test_the_entry_colour_falls_back_when_the_theme_has_none(self):
        """量不到输入框底色时退回常量：写一个空字符串回去，标签会被画成一块默认色。"""
        import tkinter.ttk as ttk_module
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        real = ttk_module.Style.lookup
        ttk_module.Style.lookup = lambda self, *args, **kwargs: ''
        self.addCleanup(setattr, ttk_module.Style, 'lookup', real)
        self.assertEqual(cloud.field_bg(), pet_cloud.HINT_BG)

    def test_every_chat_window_gets_the_rolling_line(self):
        """第 39 期第 1 条：回复框一露出来就有这条小字，不用等提示行那一拍。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud._hint_stop()
        self.assertEqual(cloud.hint.cget('text'), '')
        cloud.pin()                       # 点一下云：转成对话形态
        cloud._render()
        self.assertTrue(str(cloud.hint.cget('text')).strip(), '回复框露出来就滚起来')
        self.assertEqual(cloud.hint_state.x, pet_cloud.HINT_X, '还是从最左侧起步')
        cloud._hint_stop()

    def test_the_rolling_line_gives_way_to_what_the_user_types(self):
        """别遮挡：框里一有字就把这条小字藏起来，清空了再露。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        cloud.reply.insert(0, '查一下进度')
        self.assertEqual(cloud._sync_hint(), '', '有字就藏')
        cloud.reply.delete(0, 'end')
        self.assertTrue(str(cloud._sync_hint()).strip(), '清空了再露出来')
        status = cloud.status.cget('text')
        cloud.set_status(pet_cloud.BUSY)
        self.assertEqual(cloud.hint.cget('text'), '', '三虎在忙着想：小字让位')
        self.assertEqual(cloud.status.cget('text'), pet_cloud.BUSY)
        cloud.set_status(status)

    def test_a_short_line_gets_a_narrow_cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        cloud.lines = ['好']
        cloud._render()
        narrow = cloud.width()
        self.assertGreaterEqual(narrow, pet_cloud.MIN_WIDTH, '再短也有个下限')
        cloud.lines = ['这一句长得多，长到得换一行才排得下，看看框身会不会跟着宽一点。']
        cloud._render()
        self.assertGreater(cloud.width(), narrow, '字多了框就宽一档')
        self.assertLessEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_CLOUD),
                             '再长也封顶在原来的宽度')

    def test_a_docked_top_window_sends_the_cloud_down(self):
        """第 36 期第 7 条：全屏／上移到屏幕边缘时，上方放不下就整朵往下挪。"""
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        room = pet_cloud.shape_min_body(pet_cloud.SHAPE_CLOUD) + 10
        cloud._room_above = lambda: room
        cloud._room_below = lambda: 520
        cloud._docked_top = lambda: True
        self.assertTrue(cloud._wants_down(room + 60), '贴着屏幕上沿、这条内容放不下：往下挪')
        cloud._docked_top = lambda: False
        self.assertFalse(cloud._wants_down(room + 60), '界面不在屏幕顶：落点照旧')
        cloud._docked_top = lambda: True
        self.assertFalse(cloud._wants_down(10), '这一条上方放得下：不动')
        cloud._room_below = lambda: 10
        self.assertFalse(cloud._wants_down(room + 60), '下面更窄：也不挪')

    def test_the_body_decides_the_side_before_measuring(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._room_above = lambda: 60
        cloud._room_below = lambda: 520
        cloud._docked_top = lambda: True
        cloud._fit_body(300)
        self.assertTrue(cloud._down, '量之前先把朝向定下来')
        self.assertTrue(cloud._flipped(), '_down 之后就算翻到下面了')

    def test_the_old_flip_rule_still_works(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._down = False
        cloud._room_above = lambda: 10
        cloud._room_below = lambda: 400
        cloud._docked_top = lambda: False
        self.assertTrue(cloud._flipped(), '上方连最小云身都放不下：照旧翻下去')


    def test_a_window_flush_with_the_screen_top_counts_as_docked(self):
        """第 42 期第 2 条：窗体上沿（含标题栏）贴到屏幕上沿就算「贴着顶」。

        原来按客户区上沿（winfo_rooty）判，窗口拖到屏幕最上面时客户区还在标题栏下面二三十像素，
        判据整个不生效——用户看到的「聊天框只显示一行」就是这么来的。
        """
        cloud = self.pet.cloud()
        win = self.win
        win.deiconify(); win.geometry('520x360+0+0'); win.update()
        self.addCleanup(win.withdraw)
        self.assertTrue(cloud._docked_top(), '拖到屏幕最上面＝贴着顶（客户区还差一条标题栏）')
        win.geometry('520x360+0+260'); win.update()
        self.assertFalse(cloud._docked_top(), '离屏幕顶还有一段：照旧不算')

    def test_the_box_grows_past_the_normal_ceiling_only_when_docked(self):
        """第 42 期第 2 条：贴着顶、整朵翻到三虎下面时上限放宽；内容短还是原来那么小。"""
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._room_above = lambda: 60
        cloud._room_below = lambda: 700
        cloud._docked_top = lambda: True
        self.assertEqual(cloud._body_ceiling(), pet_cloud.MAX_BODY_DOWN)
        body = cloud._fit_body(400)
        self.assertTrue(cloud._flipped(), '贴着顶：整朵往下挪')
        self.assertLess(body, pet_cloud.MAX_BODY, '即使下方空间充足，对话框也保持紧凑')
        cloud.shape = pet_cloud.SHAPE_ROUND
        self.assertGreater(cloud._fit_body(400), pet_cloud.MAX_BODY, '较长的进度报告可以利用下方空间')
        self.assertLessEqual(body, pet_cloud.MAX_BODY_DOWN)
        self.assertLessEqual(cloud._fit_body(120), 120, '内容短就还是原来那么小')
        # 界面不在屏幕顶（哪怕翻下去过）照旧收在 MAX_BODY
        cloud._docked_top = lambda: False
        cloud._room_above = lambda: 10
        self.assertEqual(cloud._body_ceiling(), pet_cloud.MAX_BODY)
        self.assertLessEqual(cloud._fit_body(400), pet_cloud.MAX_BODY)

    def test_a_sticker_never_grows_a_reply_box(self):
        """第 40 期第 1 条：贴纸点一下只把话多留一会儿，不长出回复框。

        用户报「三虎打招呼的云朵框里有个回复框」——点一下那朵云，它原来会顺手转成带输入行的
        样子（pin 一视同仁）。现在只有方框对话框带回复框，三种贴纸都不带。
        """
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                cloud = self.pet.cloud()
                cloud.show(pinned=False, shape=shape)
                cloud.pin()                                  # 点一下这朵贴纸
                self.assertFalse(cloud.pinned, '贴纸不转对话形态')
                self.assertFalse(cloud._replies())
                self.assertEqual(cloud.chat_row.place_info(), {}, '回复框那一行不摆出来')
                self.assertEqual(cloud.status.place_info(), {}, '提示行也不占位')
                self.assertEqual(cloud.hint.place_info(), {}, '滚动小字跟着那一行一起收')
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        cloud.pin()
        self.assertTrue(cloud._replies() and cloud.chat_row.place_info(), '方框对话框照旧带回复框')

    def test_the_greeting_bubble_has_no_reply_row(self):
        """第 40 期第 1 条：开机招呼那一屏没有回复框，点开也长不出来。"""
        cloud = self.pet.cloud()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF, '招呼还是云朵框')
        for name, widget in (('回复框', cloud.reply), ('提示行', cloud.status), ('滚动小字', cloud.hint)):
            self.assertEqual(widget.place_info(), {}, '%s 不该在招呼那一屏里' % name)
        cloud.pin()
        self.assertEqual(cloud.reply.place_info(), {}, '点一下招呼那朵云也不长回复框')
        self.assertEqual(str(cloud.reply.get()), '', '回复框是空的那个（压根没摆出来）')

    def test_the_puff_follows_the_line(self):
        """第 40 期第 3 条：云朵框也跟文字多少收放——短话收窄，长话封顶在原来的宽度。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        cloud.lines = ['喵']
        cloud._render()
        narrow = cloud.width()
        self.assertGreaterEqual(narrow, pet_cloud.PUFF_MIN_WIDTH, '再短也有个下限')
        self.assertLess(narrow, pet_cloud.shape_width(pet_cloud.SHAPE_PUFF), '短话不占满一整条')
        cloud.lines = ['三虎：' + '这一句长得多，长到得换一行才排得下。' * 3]
        cloud._render()
        self.assertEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_PUFF), '长话封顶')
        self.assertGreater(cloud.width(), narrow, '字多了框就宽一档')

    def test_the_progress_frame_follows_the_line(self):
        """第 40 期第 3 条：进度那个框也跟文字多少收放（原来钉在 ROUND_WIDTH）。"""
        cloud = self.pet.cloud()
        cloud.lines = ['进度：20%']
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        short = cloud.width()
        self.assertGreaterEqual(short, pet_cloud.ROUND_MIN_WIDTH, '再短也有个下限')
        self.assertLess(short, pet_cloud.shape_width(pet_cloud.SHAPE_ROUND), '一句短话不占满整条')
        x, y, w, h = cloud._text_box()
        self.assertGreater(w, 0, '收窄之后写字框仍有地方落字')
        cloud.lines = ['进度：剧本准备 20%\n首帧还差 36 个镜头（08 首帧管理 → 手动制作首帧）']
        cloud._render()
        self.assertGreater(cloud.width(), short, '字多了椭圆就宽一档')
        self.assertLessEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_ROUND), '封顶')


class CloudHygieneTests(PetTestCase):
    """第 37 期第 5／6 条：记录里不留空行；对话框收起时及时清理；名字不再被小字抢位。"""

    def test_the_record_has_no_blank_lines(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.append('第一句\n\n   \n第二句  ')
        self.assertEqual(cloud.lines[-1], '第一句\n第二句')
        cloud.lines = ['三虎：上一条', '   ', '三虎：下一条']
        body = cloud._body_text()
        self.assertNotIn('\n\n', body, '每行之间不许有空行')
        self.assertNotIn('   ', body, '行内空白也收干净')

    def test_the_sticker_has_no_blank_lines_either(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        cloud.lines = ['三虎：一句\n\n带空行的话']
        self.assertEqual(cloud._body_text(), '三虎：一句\n带空行的话')

    def test_the_number_gap_survives(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_ROUND
        gap = pet_cloud.NUMBER_GAP
        cloud.lines = ['当前阶段\n\n进度']       # 空行会被丢掉，两行各带一个号
        self.assertEqual(cloud._body_text(), '1.' + gap + '当前阶段\n2.' + gap + '进度')
        cloud.lines = ['甲' + gap + '乙']          # 行里本来就有的不换行空格一个都不动
        self.assertEqual(cloud._body_text(), '1.' + gap + '甲' + gap + '乙',
                         '不换行空格是「编号与正文粘在一起」的关键，一个都不能少')

    def test_trim_keeps_the_newest(self):
        cloud = self.pet.cloud()
        cloud.lines = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self.assertEqual(cloud.trim(3), ['f', 'g', 'h'])

    def test_closing_the_dialog_trims_the_record(self):
        cloud = self.pet.cloud()
        self.pet.open_chat()
        for index in range(pet_cloud.CHAT_KEEP + 6):
            cloud.append('第%d句' % index)
        cloud.close()
        self.assertLessEqual(len(cloud.lines), pet_cloud.CHAT_KEEP)
        self.assertEqual(cloud.lines[-1], '第%d句' % (pet_cloud.CHAT_KEEP + 5), '留的是最新的')


class CloudCloseTests(PetTestCase):
    """第 45 期：三虎的对话框右上角多一颗看得见、点得到的「关闭」。"""

    def dialog(self, shape=None, pinned=True):
        cloud = self.pet.cloud()
        cloud.show(pinned=pinned, shape=shape or pet_cloud.SHAPE_CLOUD)
        cloud.canvas.update_idletasks()
        return cloud

    def test_the_dialog_grows_a_close_button_up_on_the_right(self):
        cloud = self.dialog()
        button = cloud.close_button
        self.assertIsNotNone(button, "对话框右上角要有一颗点得到的关闭")
        self.assertEqual(str(button.cget("text")), pet_cloud.CLOSE_MARK)
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE, "贴着云身右上角")
        self.assertEqual(float(spot["y"]), box_y + 2)
        self.assertEqual((float(spot["width"]), float(spot["height"])),
                         (float(pet_cloud.CLOSE_SIZE), float(pet_cloud.CLOSE_SIZE)))

    def test_the_cloud_wears_no_zoom_buttons_in_its_corner(self):
        """第 8 轮（收口）：弹窗那两颗「最小化／最大化」全程序都删了（见 ui_theme），
        这一朵云自然也没有——第 67 期任务 1 当年是单独把它从这朵云上摘掉的，现在整份接线
        都不在了，弹窗与云朵框都只剩自己那颗 ×。
        """
        import ui_theme
        cloud = self.dialog()
        self.assertIsNone(getattr(cloud.win, "_drama_buttons", None), "云朵框不带那两颗按钮")
        self.assertFalse(hasattr(ui_theme, "window_buttons"), "第 8 轮起没有画键的函数了")

    def test_the_records_start_below_the_close_button(self):
        cloud = self.dialog()
        info = cloud.clip.place_info()
        self.assertEqual(float(info["y"]), cloud._text_box()[1] + pet_cloud.CLOSE_H,
                         "正文从「关闭」那条下面起步，别压在字上")
        self.assertLessEqual(float(info["y"]) + float(info["height"]),
                             float(cloud.chat_row.place_info()["y"]),
                             "记录仍然压不到输入行")

    def test_the_cross_is_placed_again_on_every_render(self):
        cloud = self.dialog()
        cloud.close_button.place_forget()
        cloud._render()
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = cloud.close_button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
        self.assertEqual(float(spot["y"]), box_y + 2)

    def test_clicking_the_cross_shuts_the_dialog(self):
        cloud = self.dialog()
        calls = []
        original = cloud.close
        cloud.close = lambda event=None: calls.append(event)
        self.addCleanup(setattr, cloud, "close", original)
        self.assertEqual(cloud._hit_close(), "break", "点一下就是收起，事件不再往下传")
        self.assertEqual(len(calls), 1)

    def test_the_escape_key_still_works_beside_the_cross(self):
        cloud = self.dialog()
        bound = cloud.win.bind()
        self.assertTrue(any("Escape" in item for item in bound),
                        "看得见的那颗只是多一条路，Esc 照旧要能用：%r" % (bound,))

    def test_the_cross_turns_red_under_the_mouse(self):
        from tkinter import ttk
        cloud = self.dialog()
        button = cloud.close_button
        style = ttk.Style(self.win)
        style_name = str(button.cget("style"))
        self.assertEqual(style_name, "Tokens.Close.TButton")
        self.assertEqual(str(style.lookup(style_name, "fill")).upper(), pet_cloud.CLOSE_BG.upper())
        # 测试根窗口保持 withdraw；未映射控件不会收到 Tk crossing 事件，
        # 因而直接走与 <Enter> 绑定相同的可测状态转换。
        cloud._hover_close_button()
        self.assertTrue(button.instate(["active"]))
        self.assertEqual(str(style.lookup(style_name, "fill", ("active",))).upper(),
                         pet_cloud.CLOSE_HOVER.upper())
        self.assertEqual(str(style.lookup(style_name, "foreground", ("active",))).upper(),
                         pet_cloud.CLOSE_HOVER_FG.upper())
        cloud._unhover_close_button()
        self.assertFalse(button.instate(["active"]))

    def test_the_cross_shouts_where_to_close(self):
        """UX-CLOSE-X：三虎关闭按钮与全应用统一 CloseButton——常态中性、悬停清晰红底白×。"""
        from tkinter import ttk
        from ui_tokens import COLORS
        cloud = self.dialog()
        button = cloud.close_button
        style = ttk.Style(self.win)
        style_name = str(button.cget("style"))
        self.assertEqual(style_name, "Tokens.Close.TButton")
        self.assertEqual(str(style.lookup(style_name, "fill")).upper(), COLORS['background_card'].upper())
        self.assertEqual(str(style.lookup(style_name, "foreground")).upper(), COLORS['text_secondary'].upper())
        self.assertEqual(str(style.lookup(style_name, "fill", ("active",))).upper(), COLORS['danger'].upper())
        self.assertEqual(str(style.lookup(style_name, "foreground", ("active",))).upper(), COLORS['on_accent'].upper())
        self.assertEqual(pet_cloud.CLOSE_BG, COLORS['background_card'])
        self.assertEqual(pet_cloud.CLOSE_FG, COLORS['text_secondary'])
        self.assertEqual(pet_cloud.CLOSE_HOVER, COLORS['danger'])
        self.assertEqual(pet_cloud.CLOSE_HOVER_FG, COLORS['on_accent'])
        self.assertGreaterEqual(pet_cloud.CLOSE_SIZE, 20, "按钮足大，不用提着气去点")
        self.assertGreaterEqual(pet_cloud.CLOSE_H, pet_cloud.CLOSE_SIZE, "云身顶上那一条装得下这颗按钮")
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = button.place_info()
        self.assertEqual((float(spot["width"]), float(spot["height"])),
                         (float(pet_cloud.CLOSE_SIZE), float(pet_cloud.CLOSE_SIZE)))
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE, "还在云身右上角")

    def test_a_sticker_wears_a_close_button_too(self):
        """第 46 期第 4 条：云朵框与圆形框右上角也来一颗「关闭」。

        贴纸原来只靠到点自己收（用户要的「右上角增加关闭按钮」当时只做给了对话框）。
        """
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND):
            with self.subTest(shape=shape):
                cloud = self.dialog(shape=shape, pinned=False)
                self.assertFalse(cloud._replies(), "贴纸本来就没有输入行")
                self.assertTrue(cloud._closable(), "云朵框／圆形框要能随手关掉")
                button = cloud.close_button
                self.assertIsNotNone(button)
                box_x, box_y, box_w, _box_h = cloud._text_box()
                spot = button.place_info()
                self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
                self.assertEqual(float(spot["y"]), box_y + 2)
                self.assertEqual(str(button.cget("text")), pet_cloud.CLOSE_MARK)

    def test_the_sticker_text_starts_below_the_cross(self):
        """顶上那条「关闭」是从框身里量出来的：正文整块往下挪 CLOSE_H，字不压在×上。"""
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND):
            with self.subTest(shape=shape):
                cloud = self.dialog(shape=shape, pinned=False)
                info = cloud.clip.place_info()
                self.assertEqual(float(info["y"]), cloud._text_box()[1] + pet_cloud.CLOSE_H)
                self.assertLessEqual(float(info["y"]) + float(info["height"]),
                                     cloud._text_box()[1] + cloud._text_box()[3],
                                     "正文仍然装在能写字的那块框里")

    def test_clicking_the_sticker_cross_puts_it_away(self):
        cloud = self.dialog(shape=pet_cloud.SHAPE_ROUND, pinned=False)
        calls = []
        original = cloud.close
        cloud.close = lambda event=None: calls.append(event)
        self.addCleanup(setattr, cloud, "close", original)
        self.assertEqual(cloud._hit_close(), "break")
        self.assertEqual(len(calls), 1)

    def test_the_report_tag_wears_a_close_button(self):
        """日报／周报标签框也要有可见且可点击的关闭入口。"""
        cloud = self.dialog(shape=pet_cloud.SHAPE_TAG, pinned=False)
        cloud._render(skip_sync=True)
        self.assertTrue(cloud._closable())
        self.assertIsNotNone(cloud.close_button)
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = cloud.close_button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
        self.assertEqual(float(spot["y"]), box_y + 2)
        self.assertEqual(str(cloud.close_button.cget("text")), pet_cloud.CLOSE_MARK)


class ChatUnderModalTests(PetTestCase):
    """第 59 期第 8 条：弹窗抽着指针时，三虎的聊天框不能留在那儿点不动。

    Tk 的本地 grab 把整个应用的指针事件都送进抓着的那屋窗，聊天框连右上角那颗
    「关闭」都点不动（用户报的就是这个）。所以：一发现有弹窗抓着，聊天框自己先收；
    要说的那一句话压住，弹窗一关心跳再补说。
    """

    def modal(self):
        """造一屋「正抽着指针」的弹窗（真 Toplevel，只把 grab_current 换成它）。"""
        holder = self.tk.Toplevel(self.win)
        self.addCleanup(holder.destroy)
        original = self.win.grab_current
        self.win.grab_current = lambda: holder
        self.addCleanup(setattr, self.win, "grab_current", original)
        return holder

    def test_a_modal_dialog_puts_the_chat_away(self):
        self.pet.open_chat()
        self.assertTrue(self.pet.cloud_visible())
        self.modal()
        self.assertTrue(self.pet.modal_grabbed(), "有弹窗抽着指针")
        self.assertTrue(self.pet.guard_chat_grab(), "这一拍真的收了一朵")
        self.assertFalse(self.pet.cloud_visible(), "关不掉的框不该留着")
        self.assertIsNone(self.pet.chat)

    def test_without_a_modal_the_chat_stays(self):
        self.pet.open_chat()
        self.assertFalse(self.pet.modal_grabbed())
        self.assertFalse(self.pet.guard_chat_grab())
        self.assertTrue(self.pet.cloud_visible(), "没弹窗就别动它")

    def test_the_held_line_is_said_once_the_dialog_closes(self):
        self.pet.open_chat()
        self.modal()
        self.pet.broadcast("弹窗期间的一句话")
        self.assertEqual(self.pet.bstate.held_broadcast, "弹窗期间的一句话", "弹窗期间先压着")
        self.assertTrue(self.pet.guard_chat_grab(), "心跳发现有弹窗：聊天框先自己收起来")
        self.assertFalse(self.pet.cloud_visible(), "关不掉的框不该留着")
        self.assertEqual(self.pet.bstate.held_broadcast, "弹窗期间的一句话", "压着的话不能丢")
        self.win.grab_current = lambda: None   # 弹窗关了
        self.pet.pump()                        # 下一个心跳把它补说
        self.assertFalse(self.pet.bstate.held_broadcast, "压不住太久：弹窗关了这一句就该说出去")
        self.assertIn("弹窗期间的一句话", self.pet.cloud().transcript(),
                      "弹窗一关，那句话还得说出去")


class PetAskTests(PetTestCase):
    """SANHU-FIX-2：三虎的「是/否」小窗与列表小窗——主线程同步弹，子线程切回主线程再弹。"""

    def test_ask_yes_returns_the_answer_on_the_main_thread(self):
        answers = iter((True, False))
        original = pet_ask.ask_confirmation
        pet_ask.ask_confirmation = lambda *args, **kwargs: next(answers)
        self.addCleanup(setattr, pet_ask, 'ask_confirmation', original)
        self.assertIs(pet_ask.ask_yes(self.win, '标题', '问一句'), True)
        self.assertIs(pet_ask.ask_yes(self.win, '标题', '问一句'), False)

    def test_ask_yes_hops_to_the_main_thread_from_a_worker(self):
        """非界面线程经 win.after／心跳队列切回主线程弹完再拿到回答。"""
        original = pet_ask.ask_confirmation
        pet_ask.ask_confirmation = lambda *args, **kwargs: True
        self.addCleanup(setattr, pet_ask, 'ask_confirmation', original)
        box = {}
        worker = threading.Thread(
            target=lambda: box.setdefault('answer', pet_ask.ask_yes(self.win, 't', 'x', wait=5.0)),
            daemon=True)
        worker.start()
        deadline = time.time() + 5.0
        while worker.is_alive() and time.time() < deadline:
            pet_ask.pump_asks()      # 生产里由 Pet.pump 心跳领走；测试里手动领
            self.win.update()
            time.sleep(0.01)
        worker.join(timeout=2.0)
        self.assertIs(box.get('answer'), True)

    def test_ask_yes_times_out_to_none(self):
        """wait 秒内没人答出来就回 None（迟到的回切只标完成、不再弹窗）。"""
        calls = []
        original = pet_ask.ask_confirmation
        pet_ask.ask_confirmation = lambda *args, **kwargs: calls.append(1) or True
        self.addCleanup(setattr, pet_ask, 'ask_confirmation', original)
        box = {}
        worker = threading.Thread(
            target=lambda: box.setdefault('answer', pet_ask.ask_yes(self.win, 't', 'x', wait=0.05)),
            daemon=True)
        worker.start()
        worker.join(timeout=5.0)
        self.assertIsNone(box.get('answer'))
        pet_ask.pump_asks()          # 收掉那条迟到的回切
        self.win.update()
        self.assertEqual(calls, [], '超时之后迟到的回切不再把窗弹出来')

    def test_ask_choice_returns_the_picked_index(self):
        """Toplevel 列表＋确定：选哪一行就回哪一行的序号。"""
        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)
        def drive():
            tops = [w for w in self.win.winfo_children() if w.winfo_class() == 'Toplevel']
            dialog = tops[-1]
            listing = [w for w in walk(dialog) if w.winfo_class() == 'Treeview'][0]
            listing.selection_set('2')
            for button in dialog.winfo_children()[-1].winfo_children():
                if str(button.cget('text')) == '确定':
                    button.invoke()
                    return
        self.win.after(0, drive)
        self.assertEqual(pet_ask.ask_choice(self.win, '标题', '挑一个', ['甲', '乙', '丙']), 2)

    def test_ask_choice_cancel_or_close_returns_none(self):
        """取消／关窗／没有选项都回 None。"""
        def drive():
            tops = [w for w in self.win.winfo_children() if w.winfo_class() == 'Toplevel']
            tops[-1].close()
        self.win.after(0, drive)
        self.assertIsNone(pet_ask.ask_choice(self.win, '标题', '挑一个', ['甲', '乙']))
        self.assertIsNone(pet_ask.ask_choice(self.win, '标题', '挑一个', []), '没有选项直接 None')


if __name__ == '__main__':
    unittest.main()
