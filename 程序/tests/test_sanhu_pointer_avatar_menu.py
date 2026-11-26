# -*- coding: utf-8 -*-
"""UX-SANHU-FIX 回归：三虎聊天框左下角指向、三模式日夜配色与右键菜单重构。"""
import unittest
from unittest import mock

import ui.pet_ask as pet_ask
import ui.pet_cloud as pet_cloud
import ui.pet_ui as pet_ui
import ui.ui_theme as ui_theme
import ui_tokens
from tests.test_pet_ui import PetTestCase


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class BottomLeftPointerTests(PetTestCase):
    """需求 1：三虎在左下角停靠区时，聊天框尾巴根部与尖端同步指向左下角三虎；右侧布局兼容。"""

    def _make_cloud(self, *, window_rect, patch_rect, monitor=(0, 0, 1920, 1080)):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud._monitor = lambda: monitor
        cloud._window_rect = lambda: window_rect
        cloud._patch_rect = lambda: patch_rect
        cloud._render()
        return cloud

    def test_bottom_left_docked_cloud_points_left_down_to_sanhu_without_covering_pet(self):
        win_rect = (100, 80, 1000, 780)
        patch = (116.0, 700.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud = self._make_cloud(window_rect=win_rect, patch_rect=patch)
        left, top = cloud._origin()
        body_bottom = top + cloud._shift() + cloud._body
        patch_top = patch[1] - pet_cloud.PET_GAP
        self.assertEqual(left, win_rect[0] + pet_cloud.MARGIN, '左下角停靠时气泡左沿贴合窗口左内边')
        self.assertLessEqual(body_bottom, patch_top, '气泡主体落在三虎正上方且不压住三虎')

        tip_x, tip_y = cloud._tip()
        self.assertLess(tip_x, cloud.width() * 0.45,
                        '尖端必须指向左下角三虎，不再锁死在右侧 75%% (%s/%s)' % (tip_x, cloud.width()))
        target_x = patch[0] + patch[2] * 0.5
        self.assertAlmostEqual(left + tip_x, target_x, delta=2, msg='尖端横向对准三虎头像视觉中心')
        self.assertGreaterEqual(tip_y, cloud._body + 6)
        self.assertLessEqual(tip_y, cloud._body + pet_cloud.TAIL - 2)

        kind, points = cloud._tail_polygon()
        self.assertEqual(kind, 'poly')
        root_x = (points[0][0] + points[-1][0]) / 2.0
        self.assertLess(root_x, cloud.width() * 0.45, '尾巴根部应同步落在气泡底边偏左')
        nearest = min(points, key=lambda spot: (spot[0] - tip_x) ** 2 + (spot[1] - tip_y) ** 2)
        self.assertAlmostEqual(nearest[0], tip_x, delta=2)
        self.assertAlmostEqual(nearest[1], tip_y, delta=2)
        shift = cloud._shift()
        for bx, by in (points[0], points[-1]):
            self.assertTrue(pet_cloud.inside_shape(cloud.shape, cloud.width(), cloud._body, bx, by - shift),
                            '尾巴底边必须藏在气泡主体内')

    def test_maximized_bottom_left_docked_cloud_stays_above_sanhu(self):
        win_rect = (0, 0, 1920, 1040)
        patch = (16.0, 976.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud = self._make_cloud(window_rect=win_rect, patch_rect=patch, monitor=(0, 0, 1920, 1040))
        left, top = cloud._origin()
        self.assertEqual(left, pet_cloud.MARGIN)
        self.assertGreater(top, 500, '最大化窗口左下角三虎不应把气泡弹飞到屏幕左上角 (8, 8)')
        self.assertLessEqual(top + cloud._body, patch[1] - pet_cloud.PET_GAP)
        tip_x, _tip_y = cloud._tip()
        self.assertLess(tip_x, cloud.width() * 0.45)

    def test_right_side_pet_keeps_right_pointing_tail_compatibility(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        patch = (1200.0, 300.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._monitor = lambda: (0, 0, 1920, 1080)
        cloud._window_rect = lambda: None
        cloud._patch_rect = lambda: patch
        cloud._render()
        left, _top = cloud._origin()
        tip_x, _tip_y = cloud._tip()
        cheek_x, _cheek_y = cloud._cheek()
        self.assertGreaterEqual(tip_x, int(cloud.width() * 0.75), '右侧三虎场景保留右侧指向')
        self.assertAlmostEqual(left + tip_x, cheek_x, delta=2)
        _kind, points = cloud._tail_polygon()
        root_x = (points[0][0] + points[-1][0]) / 2.0
        expected_root = pet_cloud.shape_root(cloud.shape, cloud.width(), cloud._body)[0]
        self.assertAlmostEqual(root_x, expected_root, delta=1)

    def test_real_tk_window_bottom_left_dock_drawn_polygon_points_to_sanhu(self):
        # 复现真实 Desktop 左侧栏底栏停靠布局（宽 DESKTOP_LAYOUT['sidebar_width'] 贴窗口左下角）
        self.fake.pet_dock.pack_forget()
        sidebar = self.ttk.Frame(self.win, width=ui_tokens.DESKTOP_LAYOUT['sidebar_width'])
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self.fake.pet_dock.pack(in_=sidebar, side='bottom', fill='x')
        self.win.geometry('880x620+60+60')
        self.win.deiconify()
        self.win.update()
        self.pet._align_paws()
        self.win.update()
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud._render()
        self.win.update_idletasks()
        left, top = cloud._origin()
        avatar = self.pet.canvas
        ax, ay = avatar.winfo_rootx(), avatar.winfo_rooty()
        aw = avatar.winfo_width()
        self.assertLessEqual(top + cloud._shift() + cloud._body, ay - pet_cloud.PET_GAP + 1)
        coords = cloud.canvas.coords(cloud.canvas.find_withtag('cloud')[-1])
        pts = list(zip(coords[0::2], coords[1::2]))
        tip_pt = max(pts, key=lambda spot: spot[1])
        self.assertLess(tip_pt[0], cloud.width() * 0.45, '真 Tk 画布绘制出的尾巴尖应落在左侧')
        self.assertAlmostEqual(left + tip_pt[0], ax + aw * 0.5, delta=3)


class ThreeModeAvatarColorTests(PetTestCase):
    """需求 2：只提醒/半自动/全自动三模式不同配色，日夜双主题高对比同步，暂停态置灰。"""

    def setUp(self):
        super().setUp()
        self._origin_theme = ui_tokens.current_theme()
        ui_tokens.set_theme('day')
        self.addCleanup(ui_tokens.set_theme, self._origin_theme)

    def _avatar_colors(self):
        fur = self.pet.canvas.find_withtag('fur')[-1]
        star = self.pet.canvas.find_withtag('sparkle')[0]
        return (
            str(self.pet.canvas.itemcget(fur, 'fill')).upper(),
            str(self.pet.canvas.itemcget(fur, 'outline')).upper(),
            str(self.pet.canvas.itemcget(star, 'fill')).upper(),
        )

    def test_three_modes_have_distinct_fur_outline_and_star_colors_in_day_and_night(self):
        by_theme = {}
        for theme in ('day', 'night'):
            ui_tokens.set_theme(theme)
            ui_theme.refresh_native_widgets(self.win)
            mode_colors = {}
            for level in ('hint', 'semi', 'auto'):
                self.pet.agent.set_level(level)
                self.pet.draw()
                self.pet.draw_paws(level=level, force=True)
                fur_fill, fur_outline, star_fill = self._avatar_colors()
                mode_colors[level] = (fur_fill, fur_outline, star_fill)
                self.assertEqual(fur_fill, ui_tokens.PET_PALETTE[f'level_{level}'].upper())
                self.assertEqual(fur_outline, ui_tokens.PET_PALETTE[f'level_{level}_outline'].upper())
                self.assertEqual(star_fill, ui_tokens.PET_PALETTE[f'level_{level}_accent'].upper())
                paw_item = self.pet.paws.find_withtag('paw-' + level)[0]
                self.assertEqual(str(self.pet.paws.itemcget(paw_item, 'fill')).upper(), fur_fill)
            self.assertEqual(len({v[0] for v in mode_colors.values()}), 3, f'{theme} 三模式毛色必须两两不同')
            self.assertEqual(len({v[1] for v in mode_colors.values()}), 3, f'{theme} 三模式描边必须两两不同')
            caption_fg = str(self.pet.caption.cget('foreground')).upper()
            self.assertEqual(caption_fg, ui_tokens.PET_PALETTE['caption_ink'].upper())
            self.assertGreaterEqual(_contrast(caption_fg, ui_tokens.COLORS['background_primary']), 4.5,
                                    f'{theme} 标题文字对背景对比度不足')
            by_theme[theme] = mode_colors
        for level in ('hint', 'semi', 'auto'):
            self.assertNotEqual(by_theme['day'][level][0], by_theme['night'][level][0], f'{level} 日夜毛色应区分')
            self.assertNotEqual(by_theme['day'][level][1], by_theme['night'][level][1], f'{level} 日夜描边应区分')

    def test_paused_mood_turns_avatar_grey_in_both_themes(self):
        for theme in ('day', 'night'):
            ui_tokens.set_theme(theme)
            self.pet.agent.set_level('auto')
            self.pet.agent.pause('测试暂停')
            self.pet.draw()
            fur_fill, fur_outline, _star = self._avatar_colors()
            self.assertEqual(fur_fill, ui_tokens.PET_PALETTE['mood_paused'].upper())
            self.assertEqual(fur_outline, ui_tokens.PET_PALETTE['mood_paused_line'].upper())
            self.assertEqual(str(self.pet.caption.cget('foreground')).upper(),
                             ui_tokens.PET_PALETTE['caption_ink'].upper())
            self.pet.agent.resume()

    def test_theme_refresh_hook_redraws_avatar_paws_and_caption_automatically(self):
        self.pet.agent.set_level('semi')
        self.pet.draw()
        self.pet.draw_paws(force=True)
        day_fur = self._avatar_colors()[0]
        ui_tokens.set_theme('night')
        ui_theme.refresh_native_widgets(self.win)
        night_fur = self._avatar_colors()[0]
        self.assertNotEqual(day_fur, night_fur, '切夜间主题时 _refresh_theme_colors 必须自动重绘头像')
        self.assertEqual(night_fur, ui_tokens.PET_PALETTE['level_semi'].upper())
        paw_item = self.pet.paws.find_withtag('paw-semi')[0]
        self.assertEqual(str(self.pet.paws.itemcget(paw_item, 'fill')).upper(),
                         ui_tokens.PET_PALETTE['level_semi'].upper())
        self.assertEqual(str(self.pet.caption.cget('foreground')).upper(),
                         ui_tokens.PET_PALETTE['caption_ink'].upper())


class SanhuContextMenuTests(PetTestCase):
    """需求 3：三虎右键菜单重构、频率排序、防重复与失效动作修复。"""

    def setUp(self):
        super().setUp()
        self._origin_theme = ui_tokens.current_theme()
        ui_tokens.set_theme('day')
        self.addCleanup(ui_tokens.set_theme, self._origin_theme)

    def _groups(self):
        blocks, current = [], []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) == 'separator':
                blocks.append(current)
                current = []
                continue
            current.append(str(self.pet.menu.entrycget(index, 'label')))
        blocks.append(current)
        return blocks

    def test_menu_structure_blocks_frequency_order_and_no_duplicates(self):
        blocks = self._groups()
        self.assertEqual(len(blocks), 4, '新菜单应分成 4 块（3 条分隔线）')
        self.assertEqual(blocks[0], ['向三虎提问', '推进当前阶段', pet_ui.PANEL_MENU_LABEL])
        self.assertEqual(blocks[1], ['【任务控制】', self.pet.pause_label(), '重试失败项',
                                     pet_ui.DETAIL_MENU_LABEL, '跳过当前阻塞项'])
        self.assertEqual(blocks[2], ['【常用工具】', self.pet.model_label(), '语音识别设置…',
                                     self.pet.theme_label(), self.pet.snooze_label(), '今日日报'])
        self.assertEqual(blocks[3], ['打开设置…', pet_ui.QUIT_LABEL])
        flat = [label for block in blocks for label in block]
        self.assertEqual(len(flat), len(set(flat)), '菜单不允许重复条目')
        self.assertNotIn('一键执行（重试＋补首帧＋日报）', flat)
        self.assertNotIn('跳过这张', flat)
        self.assertEqual(self.pet.menu.type(self.pet.menu_index['settings']), 'command',
                         '「打开设置…」应为单一入口，不再保留 7 项重复级联菜单')
        self.assertEqual(flat[-1], pet_ui.QUIT_LABEL)

    def test_retry_failures_clears_block_and_restarts_failed_stage(self):
        started = []
        self.fake.pet_start = lambda stage: started.append(stage) or ('已重启「%s」' % stage)
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.auto.blocked = ('keyframe', '超时')
        self.pet.menu.invoke(self.pet.menu_index['retry'])
        self.assertEqual(self.pet.agent.failures, [])
        self.assertIsNone(self.pet.auto.blocked, '重试失败项必须解除 auto.blocked')
        self.assertNotIn('pet', self.fake.kicks, '不得再空调用不存在的 kick_unattended("pet")')
        self.assertIn('keyframe', started, '必须真实把失败阶段重新放回执行链')
        self.assertIn('已重试失败项', self.pet.notice)

    def test_pause_menu_entry_invokes_act_once_and_resume_clears_declined_set(self):
        calls = []
        original_act = self.pet.act

        def wrapped_act(action, at=None, speak=True):
            calls.append(action)
            return original_act(action, at=at, speak=speak)

        self.pet.act = wrapped_act
        self.pet.menu.invoke(self.pet.menu_index['pause'])
        self.assertEqual(len(calls), 1, '暂停菜单项不得双重包裹 act()')
        self.assertTrue(self.pet.agent.paused)

        pet_ask.declined_set(self.pet).add('video')
        calls.clear()
        self.pet.menu.invoke(self.pet.menu_index['pause'])
        self.assertEqual(len(calls), 1, '继续菜单项不得双重包裹 act()')
        self.assertFalse(self.pet.agent.paused)
        self.assertEqual(pet_ask.declined_set(self.pet), set(), '_click_resume 必须清空 declined_set')

    def test_skip_failure_clears_auto_blocked(self):
        self.pet.agent.fail('video', '被限流', attempt=4)
        self.pet.auto.blocked = ('video', '被限流')
        self.pet.menu.invoke(self.pet.menu_index['skip'])
        self.assertEqual(self.pet.agent.failures, [])
        self.assertIsNone(self.pet.auto.blocked, '跳过当前阻塞项必须解除 auto.blocked')
        self.assertIn('已跳过当前阻塞项', self.pet.notice)

    def test_theme_toggle_speech_settings_daily_report_and_advance_stage(self):
        # 1) 主题切换
        self.pet.menu.invoke(self.pet.menu_index['theme'])
        self.assertEqual(ui_tokens.current_theme(), 'night')
        self.assertIn('夜间', self.pet.notice)
        self.pet.menu.invoke(self.pet.menu_index['theme'])
        self.assertEqual(ui_tokens.current_theme(), 'day')
        self.assertIn('日间', self.pet.notice)

        # 2) 语音识别设置
        opened_speech = []
        with mock.patch('ui.speech_settings_ui.open_speech_settings',
                        side_effect=lambda pet, parent=None: opened_speech.append(parent)):
            self.pet.menu.invoke(self.pet.menu_index['speech'])
        self.assertEqual(opened_speech, [self.win])
        self.assertIn('语音识别设置', self.pet.notice)

        # 3) 今日日报
        self.pet.menu.invoke(self.pet.menu_index['report'])
        self.assertIsNotNone(self.pet.report_path)
        self.assertTrue(self.pet.report_path.is_file())
        self.assertIn('今日日报', self.pet.notice)

        # 4) 推进当前阶段：免费阶段正常触发，付费阶段拒答绝不越权执行
        started = []
        self.fake.pet_start = lambda stage: started.append(stage) or ('已开始「%s」' % stage)
        self.fake.page_index = 2  # storyboard（免费）
        self.pet.menu.invoke(self.pet.menu_index['advance'])
        self.assertEqual(started, ['storyboard'])
        self.assertIn('初步分镜', self.pet.notice)

        started.clear()
        self.fake.page_index = 9  # video（付费）
        self.pet.asker = lambda title, text: False
        self.pet.menu.invoke(self.pet.menu_index['advance'])
        self.assertEqual(started, [], '付费阶段被拒绝时绝不越权扣费派发')
        self.assertIn('视频生成', self.pet.notice)


if __name__ == '__main__':
    unittest.main()
