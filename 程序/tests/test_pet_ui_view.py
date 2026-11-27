# -*- coding: utf-8 -*-
"""宠物贴片自检（外观、姿态、猫爪、气泡排版与落点几何）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import os
import sys
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
    _Point,
    SequenceRand,
    PetTestCase,
)
import pet_agent
from ui import pet_cloud
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class LevelColorTests(PetTestCase):
    """第 15 期：头像颜色＝自动化等级（全自动红／半自动蓝／只提示黄）。"""

    def test_the_three_levels_have_three_distinct_colours(self):
        self.assertEqual(sorted(pet_ui.LEVEL_COLORS), sorted(pet_agent.LEVELS))
        self.assertEqual(len({pet_ui.LEVEL_COLORS[level][0] for level in pet_agent.LEVELS}), 3)

    def test_the_paw_and_the_cat_share_one_colour_per_level(self):
        """第 20 期用户报「自动化级别显示错误」：同一档不许蓝爪配黄猫——配色只留一份。"""
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.assertEqual(pet_ui.PAW_COLORS[level], pet_ui.LEVEL_COLORS[level][:2])
                self.assertEqual(pet_ui.palette('idle', level)[0], pet_ui.PAW_COLORS[level][0])

    def test_the_palette_prefers_the_level_over_the_mood(self):
        self.assertEqual(pet_ui.palette('worry'), pet_ui.MOODS['worry'])
        self.assertEqual(pet_ui.palette('worry', 'auto'), pet_ui.LEVEL_COLORS['auto'])
        self.assertEqual(pet_ui.palette('busy', '不存在'), pet_ui.MOODS['busy'])

    def test_sanhu_avatar_and_paw_levels_use_three_mode_day_and_night_palettes(self):
        """UX-SANHU-FIX：三模式（只提醒石板蓝灰／半自动暖琥珀橘／全自动翡翠绿）在日夜双主题均有高区分度与清晰对比。"""
        import ui_tokens

        origin = ui_tokens.current_theme()
        self.addCleanup(ui_tokens.set_theme, origin)
        for theme, expected_caption in (('day', '#0F1419'), ('night', '#E8ECF2')):
            ui_tokens.set_theme(theme)
            self.assertEqual(pet_ui.CAPTION_INK, expected_caption)
            bodies = {pet_ui.LEVEL_COLORS[level][0] for level in pet_agent.LEVELS}
            outlines = {pet_ui.LEVEL_COLORS[level][1] for level in pet_agent.LEVELS}
            self.assertEqual(len(bodies), 3, '%s 三模式毛色必须两两不同' % theme)
            self.assertEqual(len(outlines), 3, '%s 三模式描边必须两两不同' % theme)
            for level in pet_agent.LEVELS:
                self.assertEqual(pet_ui.PAW_COLORS[level], pet_ui.LEVEL_COLORS[level][:2])

    def test_switching_the_level_changes_the_avatar_colour_per_mode(self):
        self.pet.agent.set_level('semi')
        self.pet.draw()
        self.assertEqual(self.pet.agent.level, 'semi')
        self.assertEqual(self.body_colour(), pet_ui.LEVEL_COLORS['semi'][0],
                         '半自动头像使用暖琥珀橘色')
        self.pet.click('level')                      # 半自动 → 全自动
        self.assertEqual(self.pet.agent.level, 'auto')
        self.assertEqual(self.body_colour(), pet_ui.LEVEL_COLORS['auto'][0],
                         '全自动头像切换为翡翠运行绿')
        self.pet.click('level')                      # 全自动 → 只提醒
        self.assertEqual(self.pet.agent.level, 'hint')
        self.assertEqual(self.body_colour(), pet_ui.LEVEL_COLORS['hint'][0],
                         '只提醒头像切换为冷静石板蓝灰')

    def body_colour(self):
        fur = self.pet.canvas.find_withtag('fur')
        return self.pet.canvas.itemcget(fur[2], 'fill')

    def test_the_level_comes_from_the_snapshot(self):
        self.assertEqual(self.pet.level({'level': 'auto'}), 'auto')
        self.assertIn(self.pet.level({'level': '不存在'}), pet_agent.LEVELS)

    def test_a_broken_agent_falls_back_to_the_default_level(self):
        class Broken:
            @property
            def level(self):
                raise RuntimeError('读不到')
        original = pet_ui.Pet.agent
        pet_ui.Pet.agent = property(lambda self: Broken())
        self.addCleanup(setattr, pet_ui.Pet, 'agent', original)
        self.assertEqual(self.pet.level({}), pet_agent.DEFAULT_LEVEL)


class OverlayTests(PetTestCase):
    """第 19 期：贴片、猫爪、等级小字永远在最上层，否则被内容框压住，点了等于没点。"""

    class Raiser:
        """假控件：只记 Tcl 调用（Canvas 的 lift 被覆写成了 tag_raise，见 lift_patch 的注释）。"""

        def __init__(self, name):
            self._w = '.' + name
            self.calls = []
            self.tk = self

        def call(self, *args):
            self.calls.append(args)
            return ''

    def test_the_patch_the_paws_and_the_caption_are_raised(self):
        raisers = [self.Raiser(name) for name in ('canvas', 'paws', 'caption')]
        self.pet.canvas, self.pet.paws, self.pet.caption = raisers
        self.assertIs(self.pet.lift_patch(), raisers[0])
        for raiser in raisers:
            self.assertEqual(raiser.calls, [('raise', raiser._w)])

    def test_the_real_widgets_are_raised_without_errors(self):
        self.pet.lift_patch()
        self.assertEqual([item for item in self.pet.errors if item[0] == 'lift'], [])

    def test_a_widget_that_cannot_raise_is_recorded_not_raised(self):
        class Boom:
            def __init__(self):
                self.tk = self
                self._w = '.boom'

            def call(self, *args):
                raise RuntimeError('抬不动')

        self.pet.paws = Boom()
        self.assertIs(self.pet.lift_patch(), self.pet.canvas)
        self.assertTrue(any(name == 'lift' for name, _text in self.pet.errors))


class PoseTests(PetTestCase):
    """第 17 期：猫样——右上角那只猫会自己换动作（爬行／舔爪／打哈欠／摇尾巴／撒娇）。"""

    def paint_pose(self, pose, step=1):
        self.pet.canvas.delete("all")
        pet_ui.paint(self.pet.canvas, step, "idle", 0.0, None, pose)
        return self.pet.canvas

    def test_every_pose_has_its_own_marks_and_only_its_own(self):
        for pose in pet_ui.POSES:
            canvas = self.paint_pose(pose)
            if pose == "sit":
                self.assertEqual(len(canvas.find_withtag("pose-sit")), 0,
                                 "端坐就是那套基础画法，不该另加图元")
                continue
            self.assertTrue(canvas.find_withtag("pose-%s" % pose), "%s 要有自己的图元" % pose)
            for other in pet_ui.POSES:
                if other == pose or other == "sit":
                    continue
                self.assertEqual(len(canvas.find_withtag("pose-%s" % other)), 0,
                                 "%s 这一帧不该画出 %s 的东西" % (pose, other))

    def test_the_yawn_blushes_instead_of_gaping(self):
        """第 24 期第 6 条：打哈欠不再在脸上开一个黑洞（用户嫌丑），改成脸颊泛红。"""
        canvas = self.paint_pose("yawn")
        self.assertEqual(len(canvas.find_withtag("mouth-open")), 0, "脸上不再有那张张开的嘴")
        blushes = canvas.find_withtag("blush")
        self.assertTrue(blushes, "困意靠腮红说")
        for item in blushes:
            self.assertEqual(canvas.itemcget(item, "fill"), pet_ui.SANHU_BLUSH,
                             "基础腮红与打哈欠腮红共用三虎头像配色")
        self.assertTrue(canvas.find_withtag("pose-yawn"), "这一帧仍要认得出是打哈欠")

    def test_the_drawn_frame_follows_the_current_pose(self):
        self.pet.cat.pose = "yawn"
        self.pet.draw()
        self.assertTrue(self.pet.canvas.find_withtag("pose-yawn"))
        self.pet.cat.pose = "wag"
        self.pet.draw()
        self.assertEqual(len(self.pet.canvas.find_withtag("pose-yawn")), 0)
        self.assertTrue(self.pet.canvas.find_withtag("pose-wag"))

    def test_the_cat_changes_its_pose_on_its_own(self):
        start = self.pet.frame
        for _ in range(80):
            self.pet.step()
        self.assertGreater(self.pet.cat.changes, 1, "闲着的时候也该自己换动作")
        self.assertIn(self.pet.cat.pose, pet_ui.POSES)
        self.assertEqual(self.pet.frame, start + 80)

    def test_the_cat_never_repeats_the_same_pose_twice_in_a_row(self):
        cat = pet_ui.Cat(rand=SequenceRand([0.0]))
        seen = [cat.next(frame, force=True) for frame in range(len(pet_ui.POSES) * 3)]
        for before, after in zip(seen, seen[1:]):
            self.assertNotEqual(before, after, "连着两次同一个动作等于没换，看着像卡住了")

    def test_a_pose_lasts_between_the_configured_span(self):
        cat = pet_ui.Cat(rand=SequenceRand([0.0]))
        cat.next(0, force=True)
        self.assertGreaterEqual(cat.until, pet_ui.POSE_MIN)
        self.assertLessEqual(cat.until, pet_ui.POSE_MAX)

    def test_a_broken_random_source_never_raises(self):
        def boom():
            raise RuntimeError("随机源坏了")

        for bad in (boom, lambda: float("nan"), lambda: -1.0, lambda: 9.0, lambda: "不是数"):
            cat = pet_ui.Cat(rand=bad)
            for frame in range(30):
                self.assertIn(cat.next(frame), pet_ui.POSES)
            self.assertIn(cat.describe()["name"], pet_ui.POSE_NAMES.values())

    def test_the_blink_stays_on_the_frame_rhythm(self):
        """动作再换，眨眼仍只按帧走：用例与眼睛相关的断言才稳。"""
        for pose in pet_ui.POSES:
            self.pet.cat.pose = pose
            self.pet.draw(0)
            self.assertEqual(len(self.pet.canvas.find_withtag("eye-dot")), 2, pose)
            self.pet.draw(3)
            self.assertEqual(len(self.pet.canvas.find_withtag("eye-line")), 2, pose)


class CaptionTests(PetTestCase):
    """第 18 期：贴片左边那行小字写着现在是哪一档（用户报「正常／半自动／全自动不显示了」）。"""

    def test_the_caption_sits_below_the_patch(self):
        """第 R2946 期：小字在头像正下方、左沿对齐（坐标由 _cluster_layout 细算）。"""
        caption = self.pet.caption
        self.assertIsNotNone(caption, '三虎图像下方该有一行等级小字')
        info = caption.place_info()
        self.assertEqual(info['anchor'], 'nw')
        layout = self.pet._cluster_layout()
        self.assertAlmostEqual(float(info['x']), layout['avatar_x'], delta=1,
                               msg='小字左沿与头像左沿对齐（同一个 x 锚点）')
        self.assertAlmostEqual(float(info['y']), layout['caption_y'], delta=1)
        self.assertGreater(layout['caption_y'], pet_ui.SIZE,
                           '小字在头像下方（caption_y 比头像边长大）')

    def test_the_caption_clears_the_patch(self):
        """小字落在头像正下方：不出底栏、不压猫脸；标题行文字已不再需要让位。"""
        for width, height in ((942, 1032), (800, 600)):
            with self.subTest(size=(width, height)):
                self.win.geometry(f'{width}x{height}+0+0')
                self.win.deiconify()
                self.win.update_idletasks()
                self.win.update()
                caption, avatar, paws = self.pet.caption, self.pet.canvas, self.pet.paws
                dock = self.fake.pet_dock
                self.assertGreaterEqual(
                    caption.winfo_rooty(),
                    avatar.winfo_rooty() + avatar.winfo_height() - 2,
                    '状态字在头像正下方，不压猫脸')
                self.assertLessEqual(caption.winfo_rootx() + caption.winfo_width(),
                                     dock.winfo_rootx() + dock.winfo_width() + 2,
                                     '状态字完整留在底栏内')
                self.assertGreaterEqual(caption.winfo_width(), caption.winfo_reqwidth(),
                                        '状态字画布必须容纳完整文案')
                # 第 R2933 期：小字在底栏里，标题行的 header_status／header_model 不再与它同层，
                # 「标题文字让开贴片」的旧契约随迁移作废（dock 与标题行不相交）。

    def test_the_caption_is_black_ink(self):
        """小字采用当前主题高对比文字色（日间 #0F1419，夜间 #E8ECF2），不随等级淡化。"""
        import ui_tokens
        origin = ui_tokens.current_theme()
        self.addCleanup(ui_tokens.set_theme, origin)
        ui_tokens.set_theme('day')
        self.assertEqual(pet_ui.CAPTION_INK, '#0F1419')
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.pet.agent.set_level(level)
                self.pet.draw()
                self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK)
        ui_tokens.set_theme('night')
        self.pet.draw()
        self.assertEqual(pet_ui.CAPTION_INK, '#E8ECF2')
        self.assertEqual(str(self.pet.caption.cget('foreground')), '#E8ECF2')

    def test_the_caption_follows_the_level(self):
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.pet.agent.set_level(level)
                self.pet.draw()
                self.assertEqual(self.pet.caption.cget('text'), pet_ui.LEVEL_CAPTIONS[level])

    def test_the_paused_caption_stays_black(self):
        """第 22 期：用户要「已暂停也显示黑色」——小字一律 CAPTION_INK，不跟猫一起变灰。"""
        self.pet.agent.pause('用例')
        self.pet.draw()
        self.assertEqual(self.pet.caption_text(), pet_ui.PAUSED_CAPTION)
        self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK,
                         '暂停时小字仍是黑的')
        self.pet.agent.resume()

    def test_the_caption_says_the_users_words_for_the_hint_level(self):
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['hint'], '只提醒')
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['semi'], '半自动')
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['auto'], '全自动')

    def test_pausing_writes_a_paused_caption_and_greys_the_cat(self):
        self.pet.agent.pause('用例')
        self.pet.draw()
        self.assertEqual(self.pet.caption.cget('text'), pet_ui.PAUSED_CAPTION)
        self.assertEqual(self.body_colour(), pet_ui.MOODS['paused'][0], '暂停时整只置灰')
        self.pet.agent.resume()
        self.pet.draw()
        self.assertNotEqual(self.pet.caption.cget('text'), pet_ui.PAUSED_CAPTION)

    def body_colour(self):
        fur = self.pet.canvas.find_withtag('fur')
        return self.pet.canvas.itemcget(fur[2], 'fill')


class ShapeTests(PetTestCase):
    """第 18 期：四种对话框形状——各自的图元、配色与写字框。

    第 57 期第 1 条：四种外形统一成方框（用户要的「全部改成方形框，保留颜色的区分」），
    这组用例改成验「外形是同一份方框几何 ＋ 颜色各不相同 ＋ 写字框够宽」。
    """

    def test_every_shape_has_parts_colours_and_a_width(self):
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                parts = pet_cloud.shape_parts(shape, 400, 200)
                self.assertTrue(parts, '每个形状都得画得出来')
                for part in parts:
                    self.assertIn(part[0], ('oval', 'ellipse', 'rect', 'poly'))
                self.assertGreater(pet_cloud.shape_width(shape), 0)
                self.assertEqual(len(pet_cloud.shape_colors(shape)), 2)
                self.assertGreater(pet_cloud.shape_min_body(shape), 0)
                self.assertEqual(len(pet_cloud.text_box(shape, 400, 200)), 4)

    def test_an_unknown_shape_falls_back_to_the_cloud(self):
        self.assertEqual(pet_cloud.shape_parts('不存在', 400, 200),
                         pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, 400, 200))

    def test_the_progress_bubble_is_a_square_frame(self):
        """第 57 期第 1 条：进度提示框（原来是宽椭圆）也改成方框，只留「提示蓝」这一档。"""
        width = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND]
        height = pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND]
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_ROUND, width, height)
        self.assertEqual({part[0] for part in parts}, {'rect', 'oval'}, '只有框身与四个圆角')
        widest = max(part[3] - part[1] for part in parts if part[0] == 'rect')
        self.assertGreaterEqual(widest, width * 0.9, '框身要占满整条宽度')
        from ui_tokens import COLORS
        self.assertEqual(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_ROUND],
                         (COLORS['primary_subtle'], COLORS['primary']), '颜色来自提示蓝令牌')

        box = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, width, height)
        self.assertGreaterEqual(box[2], 190, '写字框够宽，一行多放得下几个字')

    def test_the_puff_is_a_square_frame_in_red(self):
        """第 57 期第 1 条：可爱话那一档（原来是一圈鼓包叠出来的云）也是方框，颜色照旧偏红。"""
        width = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF]
        height = pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_PUFF]
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_PUFF, width, height)
        kinds = [part[0] for part in parts]
        self.assertEqual(set(kinds), {'rect', 'oval'}, '只有框身与四个圆角')
        self.assertEqual(parts, pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, width, height),
                         '四种框的外形一模一样')
        self.assertNotEqual(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_PUFF],
                            pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD], '颜色仍分得开')

    def test_the_puff_stays_inside_its_body(self):
        """框身与四角的圆不许顶出云身画布（顶出去会被浮窗裁掉，框就成了切边的）。"""
        for width, height in ((300, 216), (300, 150), (240, 132)):
            with self.subTest(size=(width, height)):
                parts = pet_cloud.shape_parts(pet_cloud.SHAPE_PUFF, width, height)
                for part in parts:
                    if part[0] == 'oval':
                        self.assertGreaterEqual(part[1] - part[3], -0.5)
                        self.assertLessEqual(part[1] + part[3], width + 0.5)
                        self.assertGreaterEqual(part[2] - part[3], -0.5)
                        self.assertLessEqual(part[2] + part[3], height + 0.5)
                    else:
                        self.assertGreaterEqual(part[1], -0.5)
                        self.assertLessEqual(part[3], width + 0.5)
                        self.assertGreaterEqual(part[2], -0.5)
                        self.assertLessEqual(part[4], height + 0.5)

    def test_the_tail_grows_out_of_the_shape(self):
        """尾巴根要落在形状自己身上，不能飘在云身外面（看着像三点贴错了地方）。"""
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                width = pet_cloud.shape_width(shape)
                height = pet_cloud.shape_min_body(shape)
                x, y = pet_cloud.shape_root(shape, width, height)
                self.assertGreaterEqual(x, width * 0.5)
                self.assertLess(x, width)
                self.assertLess(y, height)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)

    def test_the_tag_is_a_rounded_rectangle(self):
        kinds = {part[0] for part in pet_cloud.shape_parts(pet_cloud.SHAPE_TAG, 360, 120)}
        self.assertEqual(kinds, {'rect', 'oval'})

    def test_the_chat_box_is_a_squared_frame(self):
        """第 24 期第 2 条：云朵对话框改成方框（用户要的「正方形」），不再是「一堆圆叠出来的云」。"""
        width, body = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_CLOUD], 200
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, width, body)
        self.assertEqual({part[0] for part in parts}, {'rect', 'oval'}, '只有框身与四个圆角')
        widest = max(part[3] - part[1] for part in parts if part[0] == 'rect')
        self.assertGreaterEqual(widest, width * 0.9, '框身要占满整条宽度')
        self.assertLessEqual(max(part[3] for part in parts if part[0] == 'oval'), width * 0.2,
                             '四角的圆不许大得像云朵的圆弧')

    def test_the_four_frames_share_one_shape_and_keep_their_colours(self):
        """第 57 期第 1 条：四种聊天框的外形完全一样（都是方框），分得开的只剩颜色。"""
        for width, height in ((300, 150), (300, 216), (240, 132)):
            with self.subTest(size=(width, height)):
                boxes = [pet_cloud.shape_parts(shape, width, height) for shape in pet_cloud.SHAPES]
                for parts in boxes[1:]:
                    self.assertEqual(parts, boxes[0], '四种框是同一份方框几何')
        colours = [pet_cloud.SHAPE_COLORS[shape] for shape in pet_cloud.SHAPES]
        self.assertEqual(len(set(colours)), len(colours), '四种颜色各不相同')

    def test_switching_the_shape_repaints_the_bubble(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertTrue(cloud.canvas.find_withtag('cloud'), '换了形状也要重新画出来')
        mode_fill = cloud.fill()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_CLOUD)      # 换回云朵走的是同一扇窗
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertEqual(cloud.fill(), mode_fill)


class PawHoverTests(PetTestCase):
    """第 23 期：鼠标扫过那排猫爪就把那一只提亮——点哪一档变得可预期。"""

    def fill_of(self, index):
        canvas = self.pet.paws
        parts = canvas.find_withtag('paw-' + pet_ui.PAW_LEVELS[index])
        self.assertTrue(parts, '这一只爪应当画出来了')
        return canvas.itemcget(parts[0], 'fill')

    def at(self, index):
        return _Point(index * pet_ui.PAW_STEP + pet_ui.PAW_SIZE // 2)

    def test_hovering_a_paw_brightens_it(self):
        self.pet.set_level('hint')              # 第 44 期：默认档已是半自动，先退到别的档再验悬停
        self.pet.paw_hover(self.at(1))
        self.assertEqual(self.pet._paw_hover, 1)
        self.assertEqual(self.fill_of(1), pet_ui.PAW_HOVER[0])

    def test_leaving_the_row_puts_it_back(self):
        self.pet.set_level('hint')
        self.pet.paw_hover(self.at(1))          # 第 0 只是当前档，提亮只发生在没选中的爪上
        self.assertEqual(self.fill_of(1), pet_ui.PAW_HOVER[0])
        self.pet.paw_leave()
        self.assertIsNone(self.pet._paw_hover)
        self.assertEqual(self.fill_of(1), pet_ui.PAW_IDLE[0])

    def test_the_selected_paw_keeps_its_level_colour_under_the_cursor(self):
        level = self.pet.agent.level
        index = pet_ui.PAW_LEVELS.index(level)
        self.pet.paw_hover(self.at(index))
        self.assertEqual(self.fill_of(index), pet_ui.PAW_COLORS[level][0], '当前档的颜色不被悬停盖掉')

    def test_off_the_row_is_not_a_paw(self):
        self.assertIsNone(self.pet.paw_at(10 * (pet_ui.PAW_SIZE + pet_ui.PAW_GAP)))
        self.assertIsNone(self.pet.paw_at(None))
        self.assertIsNone(self.pet.paw_hover(_Event(widget=self.pet.paws)))   # 这个替身没有 x
        self.assertIsNone(self.pet._paw_hover)

    def test_the_hover_bindings_are_wired(self):
        self.assertTrue(self.pet.paws.bind('<Motion>'), '扫过去要有反应')
        self.assertTrue(self.pet.paws.bind('<Leave>'), '扫出去要恢复')

    def test_the_click_and_the_hover_share_one_hit_test(self):
        self.pet.paw_hover(self.at(2))
        self.pet.paw_click(self.at(2))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[2], '扫到哪只就能点到哪只')


class CaptionPendingTests(PetTestCase):
    """第 23 期：小字带上「待确认 N」——不开窗口就知道有没有事等着自己。"""

    def test_no_pending_keeps_the_plain_level(self):
        level = self.pet.agent.level
        self.assertEqual(self.pet.caption_text(), pet_ui.LEVEL_CAPTIONS[level])

    def test_pending_items_are_counted_on_the_caption(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.agent.fail('video', '超时', attempt=4)
        self.assertIn('待确认 2', self.pet.caption_text())
        self.pet.pump()
        self.assertIn('待确认 2', self.pet.caption.cget('text'), '心跳里就该写到小字上')

    def test_a_cleared_list_takes_the_count_away(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.assertIn('待确认 1', self.pet.caption_text())
        self.pet.agent.clear_failures()
        self.assertNotIn('待确认', self.pet.caption_text())

    def test_paused_still_wins(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.agent.pause('歇会儿')
        self.assertEqual(self.pet.caption_text(), pet_ui.PAUSED_CAPTION)

    def test_wider_pending_text_folds_down_instead_of_over_the_cat(self):
        """第 R2933 期：小字宽度钉死在 DOCK_CAPTION_ROOM 上——「待确认 N」另起一行折下，不加宽。"""
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.draw()
        self.win.update_idletasks()
        caption = self.pet.caption
        self.assertEqual(int(caption.cget('wraplength')), pet_ui.DOCK_CAPTION_ROOM, '宽度得钉死')
        self.assertLessEqual(caption.winfo_reqwidth(), pet_ui.DOCK_CAPTION_ROOM, '小字最多占 DOCK_CAPTION_ROOM 宽')
        self.assertIn('待确认', caption.cget('text'))

    def test_the_caption_stays_black_in_every_case(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.pump()
        self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK)


class PawTests(PetTestCase):
    """第 19 期：自动化等级外置成一排猫爪，点哪一爪就切到哪一档。"""

    def test_a_paw_is_a_pad_and_four_toes(self):
        parts = pet_ui.paw_parts(0, 0)
        self.assertEqual(len(parts), 5)
        self.assertTrue(all(part[0] == 'oval' for part in parts))
        self.assertGreater(parts[0][3], max(part[3] for part in parts[1:]), '掌垫比脚趾大')

    def test_the_paws_sit_at_the_dock_right_edge(self):
        """第 R2946 期：猫爪列收在簇右缘内侧，对「头像＋小字」整组垂直居中。"""
        info = self.pet.paws.place_info()
        self.assertEqual(float(info['relx']), 1.0)
        self.assertEqual(info['anchor'], 'ne')
        layout = self.pet._cluster_layout()
        self.assertAlmostEqual(float(info['x']), layout['paw_x'], delta=1)
        dock_w = self.fake.pet_dock.winfo_width()
        paw_right = layout['paw_x'] + dock_w
        self.assertAlmostEqual(paw_right,
                               pet_ui.DOCK_CLUSTER_W - pet_ui.DOCK_PAW_RIGHT + max(0.0, (dock_w - pet_ui.DOCK_CLUSTER_W) / 2.0),
                               delta=1, msg='猫爪列视觉右沿收在簇右缘内侧 DOCK_PAW_RIGHT')
        caption = self.pet.caption
        height = int(caption.winfo_reqheight()) if caption is not None else 0
        if height <= 0:
            height = 2 * pet_ui.PET_LAYOUT['caption_height']
        group = pet_ui.SIZE + pet_ui.DOCK_CAPTION_GAP + height
        expected = layout['avatar_y'] + (group - pet_ui.PAW_COL_HEIGHT) / 2.0
        self.assertAlmostEqual(float(info['y']), expected, delta=2,
                               msg='猫爪列顶边＝整组居中后的顶边')

    def test_the_paws_and_the_patch_never_overlap(self):
        """头像在底栏左列、猫爪列在右沿：视觉与命中区都不压头像；小字在头像正下方。"""
        self.win.geometry('800x600+0+0')
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.update()
        patch = self.pet.canvas.place_info()
        paws = self.pet.paws.place_info()
        self.assertEqual(paws['anchor'], 'ne')
        layout = self.pet._cluster_layout()
        self.assertAlmostEqual(float(paws['x']), layout['paw_x'], delta=1)
        avatar_right = (self.pet.canvas.winfo_rootx() + self.pet.canvas.winfo_width())
        self.assertGreater(self.pet.paws.winfo_rootx(), avatar_right,
                           '猫爪列在头像右侧，矩形不相交')
        for hit in self.pet.paw_hits:
            self.assertGreaterEqual(hit.winfo_rootx(), avatar_right,
                                    '猫爪命中区左沿不压头像右沿')
        self.assertEqual(int(self.pet.canvas.cget('height')), pet_ui.SIZE)
        self.assertEqual(int(self.pet.paws.cget('height')), pet_ui.PAW_COL_HEIGHT)
        self.assertEqual(int(self.pet.paws.cget('width')), pet_ui.PAW_COL_WIDTH)
        caption = self.pet.caption.place_info()
        self.assertGreaterEqual(int(float(caption['y'])),
                                int(float(patch['y'])) + pet_ui.SIZE,
                                '等级小字落在头像下方（第 R2933 期），不再占右侧那一格')
        # 底栏：按「小字实高」定高（宿主 align_header 同步 patch_room），内容不反向撑高。
        dock = self.fake.pet_dock
        self.assertEqual(int(dock.cget('height')), pet_ui.DOCK_ROOM)
        self.assertFalse(bool(dock.pack_propagate()), '底栏不随 place 子控件收缩')
        self.assertGreaterEqual(pet_ui.DOCK_ROOM, pet_ui.SIZE, '头像要装得下')

    def test_the_selected_paw_is_filled_with_the_level_colour(self):
        self.pet.draw_paws('auto', force=True)
        self.assertEqual(len(self.pet.paws.find_withtag('paw')), 5 * len(pet_ui.PAW_LEVELS))
        marked = self.pet.paws.find_withtag('paw-auto')
        self.assertTrue(marked, '当前档那只爪要认得出来')
        self.assertEqual(self.pet.paws.itemcget(marked[0], 'fill'), pet_ui.PAW_COLORS['auto'][0])

    def test_switching_the_level_repaints_the_paws(self):
        self.pet.set_level('hint')
        chosen = self.pet.paws.find_withtag('paw-hint')
        self.assertEqual(self.pet.paws.itemcget(chosen[0], 'fill'), pet_ui.PAW_COLORS['hint'][0])
        other = self.pet.paws.find_withtag('paw-auto')
        self.assertEqual(self.pet.paws.itemcget(other[0], 'fill'), pet_ui.PAW_IDLE[0],
                         '没选中的爪是淡灰，旧档的填色要一起换掉')

    def test_the_paws_are_evenly_spaced(self):
        """第 2876 期：用户要「间距保持一致」——弧形取消，三只爪等距直排。"""
        self.assertEqual(pet_ui.PAW_ARC, 0)
        self.assertEqual([pet_ui.paw_dy(index) for index in range(3)],
                         [0, 0, 0], '三只爪不再下坠，等距直排')
        self.assertEqual(pet_ui.paw_dy(9), 0, '越界不挪')
        self.assertEqual(pet_ui.paw_dy('不是个号'), 0)
        self.pet.draw_paws('auto', force=True)
        boxes = [self.pet.paws.bbox(item) for item in self.pet.paws.find_withtag('paw')]
        step = pet_ui.PAW_STEP

        def drop(index):
            top = index * step
            return max(box[3] for box in boxes
                       if top <= (box[1] + box[3]) / 2.0 < top + pet_ui.PAW_SIZE) - (top + pet_ui.PAW_SIZE)

        for index in range(3):
            self.assertAlmostEqual(drop(index), 0, delta=1,
                                   msg='第 %d 只爪与相邻爪的间距一致' % index)

    def test_the_click_picks_the_paw_under_the_cursor(self):
        step = pet_ui.PAW_STEP
        self.pet.paw_click(_Point(2 * step + pet_ui.PAW_SIZE // 2))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[2])
        self.pet.paw_click(_Point(pet_ui.PAW_SIZE // 2))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[0])
        self.assertIsNone(self.pet.paw_click(_Point(9 * step)), '超出范围的点击不认领')


class PuffTailTests(unittest.TestCase):
    """第 25 期第 2 条：可爱话那一档的尾巴从右下角挑出来，根要落在框身里（不然接缝会露出来）。

    第 57 期第 1 条：外形统一成方框之后，「根落在里面」的判据照旧，只是框身换成了方框。
    """

    def test_the_tail_root_sits_inside_the_puff_body(self):
        for width, height in ((300, 150), (300, 216), (240, 132)):
            with self.subTest(size=(width, height)):
                x, y = pet_cloud.shape_root(pet_cloud.SHAPE_PUFF, width, height)
                self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_PUFF, width, height, x, y),
                                '尾巴根露在云身外头了：接缝会被看见')
                self.assertGreater(x, width * 0.55, '根落在靠右那半边')
                self.assertGreater(y, height * 0.55, '根落在靠下那半边')

    def test_the_other_shapes_keep_their_own_root(self):
        for shape in (pet_cloud.SHAPE_CLOUD, pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                width = pet_cloud.shape_width(shape)
                height = pet_cloud.shape_min_body(shape)
                x, _y = pet_cloud.shape_root(shape, width, height)
                self.assertGreater(x, width / 2.0)


class RingTests(PetTestCase):
    """第 21 期：用户要的「删除三虎头像背后的弧线」。"""

    def test_no_arc_stands_behind_the_cat(self):
        canvas = self.pet.canvas
        for pose in pet_ui.POSES:
            with self.subTest(pose=pose):
                self.pet.cat.pose = pose
                self.pet.draw(0)
                self.assertEqual(canvas.find_withtag('ring'), (), '脸上不再挂那条进度弧线')

    def test_paint_ignores_the_percent_instead_of_drawing_a_ring(self):
        canvas = self.pet.canvas
        for percent in (0.0, 25.0, 100.0):
            with self.subTest(percent=percent):
                pet_ui.paint(canvas, step=0, percent=percent)
                self.assertEqual(canvas.find_withtag('ring'), ())
        self.assertTrue(canvas.find_withtag('fur'), '猫还在')


class AnchorTests(PetTestCase):
    """第 21 期：云朵框往下挪一条尾巴带，底部对齐左侧那行标题文字（＝贴片下沿）。"""

    def test_the_body_bottom_lands_on_the_patch_bottom(self):
        cloud = self.pet.cloud()
        # 贴片摆在界面右上角（真实位置）：第 24 期起云身落点还要过一道「不许压住三虎」的闸，
        # 摆在屏幕正中的假贴片会被那道闸挪走，量到的就不是对齐关系了。
        cloud._patch_rect = lambda: (1200.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._work_right = lambda: 1920
        self.assertEqual(pet_cloud.ANCHOR_DROP, pet_cloud.TAIL, '下移的就是那一条尾巴带')
        self.assertEqual(cloud._bottom(), 200.0 + pet_ui.SIZE + pet_cloud.ANCHOR_DROP)
        cloud._render()
        _left, top = cloud._origin()
        self.assertEqual(top + cloud._body, 200.0 + pet_ui.SIZE,
                         '云身下沿落在贴片下沿上——比原来低了一条尾巴带（用户要的「还要往下移」）')


class GrowTests(PetTestCase):
    """第 19 期：圆气泡从三虎耳朵那头一档一档长出来，不重叠、字不会被盖。"""

    def test_the_grow_starts_near_the_ear_and_lands_on_target(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        seen = []
        cloud.win.geometry = lambda geo: seen.append(geo)
        final = (400, 300)
        cloud._grow_to(final, pet_cloud.GROW_STEPS[0])
        cloud._grow_to(final, 1.0)

        def point(geo):
            parts = geo.lstrip('+').split('+')
            return int(parts[0]), int(parts[1])

        first, last = point(seen[0]), point(seen[-1])
        self.assertEqual(last, final, '走到最后一拍就是该在的地方')
        ear_x, ear_y = cloud._ear()
        self.assertLess(abs(first[0] - ear_x), abs(last[0] - ear_x), '起步时更靠近耳朵')
        self.assertLess(abs(first[1] - ear_y), abs(last[1] - ear_y))

    def test_the_label_is_placed_only_after_the_grow(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        place = []
        cloud._place_label = lambda: place.append(1)
        cloud._grow_to((10, 10), 1.0)
        self.assertEqual(place, [], '长的那几拍先不摆字')


class RoundBubbleTests(PetTestCase):
    """第 21 期：圆气泡瘦身——只带最近一条、不编号，字落在圆的内接方框里居中。"""

    def round_cloud(self, text, long=True):
        cloud = self.pet.cloud()
        cloud.long = long
        cloud.append(text)
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        return cloud

    def test_only_the_newest_line_shows(self):
        cloud = self.round_cloud('三虎：第一句')
        cloud.append('三虎：第二句')
        body = cloud._body_text()
        self.assertIn('第二句', body)
        self.assertNotIn('第一句', body, '圆里只留最近那一条，不再把前几条一起搬进来')

    def test_the_round_bubble_numbers_its_line_too(self):
        cloud = self.round_cloud('进度：剧本准备 20%')
        self.assertIn('剧本准备 20%', cloud._body_text())
        self.assertRegex(cloud._body_text(), r'^\d+\.\s', '第 22 期起贴纸也编号')

    def test_the_number_keeps_its_sentence_on_the_first_line(self):
        """第 24 期第 7 条：窄框里编号要和正文挤在同一行——原来用普通空格，头一行只剩一个编号。"""
        cloud = self.round_cloud('我把镜头号重排了一遍，你瞅瞅？')
        wrap = int(float(cloud.label.cget('wraplength')))
        self.assertGreater(wrap, 0, '圆里的字也得有个换行宽度')
        text = cloud._body_text()
        font = cloud.label.cget('font')
        # 第 27 期第 3 条把椭圆加宽之后，这句话在原来的宽度下一行就放得下，两种空格
        # 看不出差别了；把换行宽度收到「编号＋头半句刚好放得下」那一档，NBSP 的作用照样验得出来。
        wrap = min(wrap, 140)
        tight = self.tk.Label(self.win, text=text, wraplength=wrap,
                              justify='left', anchor='nw', font=font)
        loose = self.tk.Label(self.win, text=text.replace(pet_cloud.NUMBER_GAP, ' '), wraplength=wrap,
                              justify='left', anchor='nw', font=font)
        self.addCleanup(tight.destroy)
        self.addCleanup(loose.destroy)
        self.win.update_idletasks()
        self.assertLess(tight.winfo_reqheight(), loose.winfo_reqheight(),
                        '编号那行要真的带上正文，不能只剩一个编号')

    def test_the_text_box_is_inscribed_in_the_circle_and_centred(self):
        cloud = self.round_cloud('进度：剧本准备 20%')
        width, height = cloud.width(), cloud._body
        x, y, w, h = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, width, height)
        self.assertAlmostEqual(x + w / 2.0, width / 2.0, delta=2, msg='框在圆里横向居中')
        self.assertAlmostEqual(y + h / 2.0, height / 2.0, delta=2, msg='纵向也居中')
        for cx, cy in ((x, y), (x + w, y + h), (x, y + h), (x + w, y)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_ROUND, width, height, cx, cy),
                            '四角都在圆里（字不压弧线）: (%.1f, %.1f)' % (cx, cy))
        self.assertGreaterEqual(w, 100, '框太小就写不下字')

    def test_the_progress_text_is_a_few_short_lines(self):
        text = self.pet.progress_text()
        lines = [line for line in text.split('\n') if line.strip()]
        self.assertLessEqual(len(lines), pet_ui.PROGRESS_GAPS + 3, '圆里就写几行，明细留给状态栏')
        self.assertNotIn('\n\n', text, '不留空行：圆里地方小')

    def test_the_bubble_grows_only_as_far_as_the_text_needs(self):
        small = self.round_cloud('进度：20%')
        floor = small._body
        big = self.round_cloud('进度：剧本准备 20%\n预计剩余 12 分钟\n'
                               '首帧还差 36 个镜头（08 首帧管理 → 手动制作首帧）')
        self.assertGreaterEqual(big._body, floor, '字多就大一点')
        self.assertLessEqual(big._body, pet_cloud.MAX_BODY, '再长也不许撑破上限')

    def test_the_shapes_are_smaller_than_they_were(self):
        self.assertLess(pet_cloud.WIDTH, 420)
        self.assertLess(pet_cloud.MAX_BODY, 300)
        # 第 27 期第 3 条：椭圆气泡按 ROUND_WIDTH 定宽（比原来那个方框宽一截），
        # 高度还是瘦身之后那一档。
        self.assertEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND], pet_cloud.ROUND_WIDTH)
        self.assertGreater(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND],
                           pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND], '宽要真的比高大，才像椭圆')
        self.assertLessEqual(pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND], 200)
        # 第 28 期第 1 条：字号提到 15 号之后，云朵框跟着加宽到 400（仍然只是个说话的气泡，不过度）
        self.assertLessEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF], 420)

    def test_the_frame_is_wide_enough_for_a_longer_line(self):
        """第 57 期第 1 条：方框的写字框占满框身大半，同一行多放得下几个字。"""
        cloud = self.round_cloud('进度：剧本准备 20%')
        x, y, w, h = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, cloud.width(), cloud._body)
        self.assertGreaterEqual(w, 190, '比原来那个正方形（约 112 宽）宽出一大截')
        self.assertGreaterEqual(w, 0.85 * cloud.width(), '写字框占满框身')
        for cx, cy in ((x, y), (x + w, y + h), (x, y + h), (x + w, y)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_ROUND, cloud.width(), cloud._body, cx, cy),
                            '四角还是落在框身里: (%.1f, %.1f)' % (cx, cy))


class StickerFitTests(PetTestCase):
    """第 21 期：贴纸要装得下那几个字——写字框装不下的高度，形状就得跟着长大。

    原来只按「字高＋内边距」定云身高度，而心／标签的写字框是按比例内缩出来的（只有云身的
    四成上下），字比那个框高时就直接顶到形状外面去了（开机那句话当初就是这么挤出框外的）。
    """

    def framed(self, shape_hint=None):
        cloud = self.pet.cloud()
        cloud._bottom = lambda: 600.0                 # 钉住落点：别让「上方还剩多少」影响云身高度
        cloud._screen_height = lambda: 1080
        return cloud

    def test_the_puff_grows_to_hold_the_greeting(self):
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(h, cloud._content_height(), '云朵框的写字框要装得下这一句话')
        for cx, cy in ((x + 4, y + 4), (x + w - 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_PUFF, cloud.width(), cloud._body, cx, cy),
                            '写字框要在云身里：角 (%.1f, %.1f)' % (cx, cy))

    def test_the_puff_text_box_fills_the_bubble(self):
        """第 25 期第 5 条：打招呼那几句话要写满到框边——写字框太窄就会一行两三个字地往下掉。"""
        cloud = self.framed()
        cloud.greet()
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(w, 160, '写字框太窄了：%.0f 像素' % w)
        self.assertGreaterEqual(w, 0.55 * cloud.width(), '宽度要占云身大半')
        self.assertGreaterEqual(x, 0, '框要落在云身里')
        self.assertLessEqual(x + w, cloud.width())

    def test_the_tag_holds_its_sentence_as_well(self):
        cloud = self.framed()
        cloud.banner('三虎：今日日报已备好——36 个镜头、12 张首帧入账。明天见，台账我都记着呢。')
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_TAG)
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(h, cloud._content_height(), '标签框要装得下这一句')
        self.assertGreaterEqual(w, 120, '框太窄就一句一断，读起来费劲')
        for cx, cy in ((x + 4, y + 4), (x + w - 4, y + h - 4)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_TAG, cloud.width(), cloud._body, cx, cy))

    def test_the_greeting_sticker_has_no_number(self):
        """第 26 期第 6 条：打招呼与随口一句的可爱话不带排序数字（原来贴纸也编号）。"""
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud._body_text(), pet_cloud.GREETING, '招呼就是那一句话，前面不挂编号')
        self.assertNotIn(pet_cloud.NUMBER_GAP, cloud._body_text())
        cloud.whisper('三虎：尾巴甩一甩，等你下一条指令。')
        self.assertEqual(cloud._body_text(), '三虎：尾巴甩一甩，等你下一条指令。')

    def test_the_progress_bubble_numbers_every_line(self):
        """第 26 期第 4 条：提示框一段有好几行，每一行都得带号（原来只有头一行带）。"""
        cloud = self.framed()
        cloud.progress('进度：脚本准备 20%\n预计剩余 12 分钟\n首帧还差 36 个镜头')
        rows = cloud._body_text().split('\n')
        self.assertEqual(len(rows), 3)
        for index, row in enumerate(rows, start=1):
            self.assertTrue(row.startswith('%d.%s' % (index, pet_cloud.NUMBER_GAP)),
                            '第 %d 行没带号：%r' % (index, row))

    def test_the_text_is_a_little_smaller_but_still_readable(self):
        """第 49 期第 3 条：用户要「聊天框文字适当缩小」——正文 13 号（比第 28 期的 15 号小一档，
        仍比最初那版 11 号大），贴纸从 13 号试起、6 号兜底。"""
        from ui_tokens import FONTS
        self.assertEqual(pet_cloud.FONT, FONTS['pet_body'])
        self.assertEqual(int(pet_cloud.STICKER_FONTS[0]), 13, '贴纸也从 13 号试起')
        self.assertEqual(int(pet_cloud.STICKER_FONTS[-1]), 6, '兜底那一档留着，不然话会被裁掉')
        self.assertLess(int(pet_cloud.STICKER_FONTS[-1]), int(pet_cloud.STICKER_FONTS[0]),
                        '仍然是从大到小一档一档试下去')
        cloud = self.framed()
        cloud.greet()   # 先把窗搭起来，确认行才在
        self.assertFalse(hasattr(cloud, 'entry'),
                         '第 29 期第 5 条：输入框整个拿掉，字号这条只剩正文与贴纸要看')

    def test_the_greeting_keeps_the_biggest_font(self):
        """第 28 期第 1 条：打招呼那句话不该被收到小号字——云朵框加宽到 400 之后，最大那档字号下三行正好装得下。"""
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        size = int(str(cloud.label.cget('font')).split()[-1])
        self.assertEqual(size, int(pet_cloud.STICKER_FONTS[0]),
                         '呼吸框里的话要用最大那档字号：%s' % str(cloud.label.cget('font')))
        self.assertLessEqual(cloud._content_height(), cloud._room(), '支撑在框里，不许裁字')
        self.assertGreaterEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF], 400,
                                '框窄了这句话就要收到 13 号（用户就是这么看不清的）')

    def test_a_sticker_shrinks_its_font_when_the_room_is_short(self):
        """第 26 期第 7 条：云身长不高时把字号收一档，别让话说到一半被裁掉。"""
        cloud = self.pet.cloud()
        cloud._bottom = lambda: 210.0          # 三虎上方只剩这么高，云身顶到上限
        cloud._screen_height = lambda: 1080
        cloud.whisper('三虎：' + '这句可爱话挺长的，要看看云朵框装不装得下这么多字。' * 3)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertLessEqual(cloud._content_height(), cloud._room(),
                             '正文要完整待在框里：%d > %d' % (cloud._content_height(), cloud._room()))

    @staticmethod
    def hugged(cloud):
        """第 58 期第 5 条：框身该有的高度＝max(最小高度, 内容 ＋ 内边距 ＋ 顶上那条「关闭」 ＋ 余量)。"""
        return max(pet_cloud.shape_min_body(cloud.shape),
                   cloud._content_height() + 2 * pet_cloud.PAD + cloud._close_strip() + 8)

    def test_the_greeting_bubble_hugs_the_two_lines(self):
        """第 58 期第 5 条：开机招呼那朵框按内容定高（用户报的「没有根据内容自动调整框的大小」）。

        原来量到的是 374×230、里面只写两行字——底数还留着「一圈鼓包／椭圆」时代那几档
        （PUFF 200／ROUND 188／TAG 110），第 57 期外形统一成方框之后它们就只是白留一片空白。
        """
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertEqual(cloud._body, self.hugged(cloud), '框身贴着这一句话长')
        self.assertLess(cloud._body, 200, '不再是原来那档 200 的底数')
        self.assertGreaterEqual(cloud._room(), cloud._content_height(),
                                '顶上那条「关闭」也算进去了，正文完整待在框里')
        self.assertEqual(int(cloud.canvas.cget('height')), cloud._body + pet_cloud.TAIL,
                         '浮窗跟着框身一起收')
        self.assertLess(cloud.width(), pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF],
                        '宽度也照着这句话收，不再拉满')

    def test_the_other_stickers_hug_their_line_too(self):
        """第 58 期第 5 条：可爱话／提示／标签三档贴纸同样按内容定高，不留一大片空白。

        这一条与上面那条分工不同：上面盯的是招呼那句（内容短、正好被底数压住），这里盯的是
        「内容比最小高度还高」的时候——框身必须就停在「内容 ＋ 内边距 ＋ 顶上那条关闭」上，
        不能再多留一截空白（原来 PUFF 200／ROUND 188／TAG 110 三档底数就是这么白的）。
        """
        said = '进度：剧本准备 20%，预计剩余 12 分钟，首帧还差 36 个镜头（08 首帧管理 → 手动制作首帧）。'
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                cloud = self.framed()
                cloud.append(said)
                cloud.show(pinned=False, shape=shape)
                self.assertEqual(cloud.shape, shape)
                self.assertEqual(cloud._body, self.hugged(cloud), '框身＝这一条内容的高度')
                self.assertLessEqual(cloud._body,
                                     cloud._content_height() + 2 * pet_cloud.PAD + cloud._close_strip() + 8,
                                     '比内容高的那一截只能是内边距与「关闭」那一条')
                self.assertGreaterEqual(cloud._room(), cloud._content_height(), '正文不裁')


class BubbleColorTests(PetTestCase):
    """第 26 期第 5 条：云朵框红、提示框蓝、对话框绿——三种框按用途分色。"""

    @staticmethod
    def channel(color):
        return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))

    def test_the_cloud_is_red(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_PUFF][1])
        self.assertGreater(red, green, '云朵框要偏红')
        self.assertGreater(red, blue)

    def test_the_progress_bubble_is_blue(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_ROUND][1])
        self.assertGreater(blue, red, '提示框要偏蓝')
        self.assertGreater(blue, green)

    def test_the_chat_box_is_green(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD][1])
        self.assertGreater(green, red, '对话框要偏绿')
        self.assertGreater(green, blue)

    def test_confirming_asks_in_the_green_chat_box(self):
        self.pet.confirm('要按一次 Seedream 首帧吗？')
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertIn('要按一次 Seedream 首帧吗', cloud.transcript())


class PanelTextTests(PetTestCase):
    """第 26 期第 4 条：进度面板按节排版、逐行编号。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def test_the_panel_opens_with_the_progress_title(self):
        """第 36 期第 10 条：面板正文开头就是「当前进度：」。"""
        text = self.pet.panel_text()
        self.assertTrue(text.startswith(pet_ui.PANEL_HEAD), text[:40])
        self.assertEqual(pet_ui.PANEL_HEAD, '当前进度：')

    def test_the_panel_is_split_into_sections(self):
        text = self.pet.panel_text()
        self.assertIn('【现在在做什么】', text)
        self.assertIn('【速度与命中】', text)
        self.assertIn('【配额与设置】', text)
        self.assertNotIn('\n\n', text, '不空行：一节里一条一行')

    def test_the_panel_fallback_bubble_keeps_its_own_numbering(self):
        """没有只读文本窗时进度面板退回圆气泡：那份正文自带节名与编号，不许再套一层。"""
        cloud = self.pet.cloud()
        text = self.pet.panel_text()
        cloud.progress(text)
        self.assertEqual(cloud._body_text(), text)
        plain = self.pet.cloud()
        plain.progress('1. 正在做：第 08 步首帧')
        self.assertIn(pet_cloud.NUMBER_GAP, plain._body_text())

    def test_every_panel_row_is_numbered_and_keeps_its_value(self):
        rows = dict(self.pet.rows())
        text = self.pet.panel_text()
        lines = [line for line in text.split('\n') if line[:1].isdigit()]
        self.assertEqual(len(lines), len(rows), '面板每一条都在，且各占一行')
        for index, line in enumerate(lines, start=1):
            self.assertTrue(line.startswith('%d.%s' % (index, pet_cloud.NUMBER_GAP)), line)
        for name, value in rows.items():
            self.assertIn('%s%s%s' % (name, pet_ui.PANEL_DIVIDER, value), text,
                          '「%s」那一行的值不许丢' % name)


class _PatchCanvas:
    """贴片替身：只带那一把几何接口，坐标想怎么报就怎么报。"""

    def __init__(self, left=1076, top=191, width=64, height=64, mapped=1):
        self.geometry = {'left': left, 'top': top, 'width': width, 'height': height, 'mapped': mapped}

    def winfo_width(self):
        return self.geometry['width']

    def winfo_height(self):
        return self.geometry['height']

    def winfo_rootx(self):
        return self.geometry['left']

    def winfo_rooty(self):
        return self.geometry['top']

    def winfo_ismapped(self):
        return self.geometry['mapped']

    def cget(self, name):
        # 真 Tk 里贴片还没映射出来时 winfo_width 报 0／1，cget('width') 仍是配好的那个寄寸
        return pet_cloud.PET_SIZE if name in ('width', 'height') else 0

    def bind(self, *args, **kwargs):
        return None


class PatchRectTrustTests(PetTestCase):
    """第 49 期第 1 条：主窗口最小化／收起那一拍量出来的贴片坐标是假的，不许拿它算落点。"""

    def cloud_with(self, **geometry):
        self.pet.canvas = _PatchCanvas(**geometry)
        return self.pet.cloud()

    def test_a_good_reading_is_kept(self):
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))

    def test_an_unmapped_patch_falls_back_to_the_last_good_reading(self):
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))
        self.pet.canvas.geometry.update({'left': 768, 'top': 1004, 'mapped': 0})   # 最小化那一拍
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0),
                         '贴片没映射：这一次的量值一个字节都不许用')

    def test_a_patch_with_no_size_is_not_trusted(self):
        """贴片报 0×0：退回配置的那个尺寸，绝不拿 0 去算落点。"""
        cloud = self.cloud_with(width=0, height=0)
        self.assertEqual(cloud._patch_rect(),
                         (1076.0, 191.0, float(pet_cloud.PET_SIZE), float(pet_cloud.PET_SIZE)),
                         '量成 0 的贴片不能当真：用配好的那个寄寸')

    def test_a_one_pixel_patch_is_not_trusted(self):
        """真机上没映射的贴片报 1×1（实测）：这种量值也不许拿去算落点。"""
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))
        self.pet.canvas.geometry.update({'width': 1, 'height': 1})
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0),
                         '量成 1 像素的贴片不能当真，还用上一次量准的')

    def test_a_configure_while_minimised_leaves_the_cloud_where_it_was(self):
        cloud = self.cloud_with()
        cloud.show(pinned=False)
        spot = cloud._origin()
        self.pet.canvas.geometry.update({'left': 768, 'top': 1004, 'mapped': 0})
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(cloud._origin(), spot, '最小化那一拍不许挪窝：一挪就是「从右边跳到左边」')


class CheekAndTailTests(PetTestCase):
    """第 24 期第 2／9 条：尾巴尖钉在三虎的脸颊上，云身怎么变都只是让尾巴变长变短。"""

    def placed(self, anchor=(1200.0, 320.0), bottom=384.0):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        rect = (anchor[0] - pet_ui.SIZE * pet_cloud.CHEEK_X,
                anchor[1] - pet_ui.SIZE * pet_cloud.CHEEK_Y, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._anchor = lambda: anchor
        cloud._patch_rect = lambda: rect
        cloud._bottom = lambda: bottom
        cloud._work_right = lambda: 1920
        cloud._render()
        return cloud

    def test_the_pet_has_a_cheek_to_point_at(self):
        left, top, width, height = 100.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE)
        cloud = self.pet.cloud()
        cloud._patch_rect = lambda: (left, top, width, height)
        self.assertEqual(cloud._cheek(), (left + width * pet_cloud.CHEEK_X,
                                          top + height * pet_cloud.CHEEK_Y))
        self.assertEqual(cloud._anchor(), cloud._cheek(), '云身与尾巴共用一个锚点')

    def test_the_tip_lands_on_the_cheek_of_the_pet(self):
        anchor = (1200.0, 320.0)
        cloud = self.placed(anchor=anchor)
        left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        self.assertAlmostEqual(left + tip_x, anchor[0], delta=1, msg='尖角指着脸颊那一列')
        self.assertAlmostEqual(top + tip_y, anchor[1], delta=1)

    def test_the_tip_keeps_its_place_when_the_body_resizes(self):
        """界面缩放：云身长高或压矮，尖角仍钉在脸颊那一点上（用户要的「尾巴始终在原位」）。"""
        anchor = (1200.0, 320.0)
        spots = []
        for body in (pet_cloud.MIN_BODY, 160, pet_cloud.MAX_BODY):
            cloud = self.placed(anchor=anchor)
            cloud._fit_body = lambda wanted, body=body: int(body)
            cloud._render()
            left, top = cloud._origin()
            tip_x, tip_y = cloud._tip()
            spots.append((left + tip_x, top + tip_y, cloud._body))
        self.assertEqual([spot[2] for spot in spots], [pet_cloud.MIN_BODY, 160, pet_cloud.MAX_BODY],
                         '云身真的换过高度，这条才盯得住')
        for spot in spots:
            self.assertAlmostEqual(spot[0], anchor[0], delta=1)
            self.assertAlmostEqual(spot[1], anchor[1], delta=1)


class AvoidPetTests(PetTestCase):
    """第 24 期第 9 条：云身可以压住界面里的文字，但不许压住三虎，而且别移太远。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._patch_rect = lambda: (1000.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        return cloud

    def covers_the_pet(self, cloud, spot):
        left, top = spot
        # 只量云身那一块方框：尾巴是按用户要求「指着脸颊」的指针，本来就碰到三虎
        # （见 pet_cloud.Cloud._avoid_pet 的说明）。
        width, height = cloud.width(), cloud._body
        rect = cloud._patch_rect()
        return not (left + width <= rect[0] - pet_cloud.PET_GAP
                    or left >= rect[0] + rect[2] + pet_cloud.PET_GAP
                    or top + height <= rect[1] - pet_cloud.PET_GAP
                    or top >= rect[1] + rect[3] + pet_cloud.PET_GAP)

    def test_a_spot_that_does_not_touch_the_pet_is_left_alone(self):
        cloud = self.cloud()
        spot = (100, 100)
        self.assertEqual(cloud._avoid_pet(*spot), spot, '没压着就一个像素都不动')

    def test_a_spot_on_the_pet_moves_only_just_enough(self):
        cloud = self.cloud()
        spot = (int(cloud._patch_rect()[0]) - 40, 200)      # 右边压在猫脸上
        moved = cloud._avoid_pet(*spot)
        self.assertFalse(self.covers_the_pet(cloud, moved), '让开之后不许再压着三虎')
        self.assertLessEqual(moved[0], spot[0], '往左让')
        self.assertLess(spot[0] - moved[0], cloud.total_width(), '只挪到刚好不压着，别移太远')

    def test_the_real_layout_never_covers_the_pet(self):
        """真实落点：云身站在三虎左边，一条缝都不压（第 24 期起落点还要过这道闸）。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._patch_rect = lambda: (1500.0, 100.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._bottom = lambda: 100.0 + pet_ui.SIZE + pet_cloud.ANCHOR_DROP
        cloud._work_right = lambda: 1920
        cloud._render()
        self.assertFalse(self.covers_the_pet(cloud, cloud._origin()))


class MaxGapTests(PetTestCase):
    """第 25 期第 4 条：云身离三虎最多 MAX_GAP 那么远（被屏幕边／界面推得太开就拉回来）。"""

    def cloud(self, left=1500.0, top=100.0):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        spot = (left, top, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._patch_rect = lambda: spot
        cloud._bottom = lambda: spot[1] + spot[3] + pet_cloud.ANCHOR_DROP
        cloud._work_right = lambda: 3000
        cloud._screen_height = lambda: 1080
        return cloud

    def gap(self, cloud):
        left, _top = cloud._origin()
        return cloud._patch_rect()[0] - (left + cloud.width())

    def test_a_cloud_pushed_far_away_is_pulled_back(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)     # 屏幕挤得只能摆在界面最左边
        self.assertGreater(cloud._patch_rect()[0] - (60.0 + cloud.width()), pet_cloud.MAX_GAP,
                           '这条用例得真把它推远，才盯得住')
        self.assertLessEqual(self.gap(cloud), pet_cloud.MAX_GAP, '拉回来之后就不该再那么远')
        self.assertGreater(self.gap(cloud), 0, '拉回来也不许压到三虎身上')

    def test_a_cloud_that_is_already_close_is_left_alone(self):
        cloud = self.cloud()
        left, top = cloud._origin()
        self.assertLessEqual(self.gap(cloud), pet_cloud.MAX_GAP)
        self.assertEqual(cloud._near_pet(left, top), (int(left), int(top)), '已经在近处：一个像素都不动')

    def test_it_is_not_pulled_out_of_the_screen(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)
        cloud._work_right = lambda: 380          # 屏幕只剩这么宽：拉回来就出界了
        left, _top = cloud._origin()
        self.assertEqual(int(left), 60, '宁远离，不越界')

    def test_the_tail_still_lands_on_the_cheek_after_being_pulled(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)
        left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        cheek_x, cheek_y = cloud._cheek()
        self.assertAlmostEqual(left + tip_x, cheek_x, delta=1, msg='拉近了也要指着脸颊')
        self.assertAlmostEqual(top + tip_y, cheek_y, delta=1)


if __name__ == '__main__':
    unittest.main()
