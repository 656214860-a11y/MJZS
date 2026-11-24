"""三虎手动／全自动模式的设置接管测试。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pet_agent
import ui.pet_ui as pet_ui
import ui.pet_ui_support as pet_ui_support
import infra.project_settings as project_settings
import stage_flow
import orchestrator.stage_exec as stage_exec
from orchestrator.desktop_auto_state import AutoStateHolderMixin
from ui.desktop_auto_flows import AutoFlowsMixin
from ui.desktop_automation_tick import AutomationTickMixin
from ui.desktop_pet_bridge import PetBridgeMixin


class _Desktop:
    def __init__(self, project):
        self.root = project
        self.win = None


class _ModeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class SanhuModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.pet = pet_ui.Pet(_Desktop(self.project))
        self.levels = []
        self.messages = []
        self.pet.set_level = lambda level, at=None: self.levels.append(level) or level
        self.pet.broadcast = lambda text, **_kwargs: self.messages.append(text) or text

    def test_auto_mode_enables_every_registered_auto_action(self):
        self.assertEqual(self.pet.mode, 'manual')
        self.assertEqual(self.pet.set_mode('auto'), 'auto')
        self.assertEqual(self.levels, ['auto'])
        self.assertTrue(all(project_settings.get(self.project, key) is True
                            for key in project_settings.DEFAULTS))
        self.assertTrue(all(self.pet.auto_variable(name).get() is True
                            for name in pet_ui.AUTO_VARIABLE_NAMES))
        self.assertIn('【模式】已切换到全自动模式', self.messages)
        self.assertIn('【模式】已打开全部自动制作开关', self.messages)

    def test_manual_mode_disables_every_registered_auto_action(self):
        self.pet.set_mode('auto')
        self.messages.clear()
        self.assertEqual(self.pet.set_mode('manual'), 'manual')
        self.assertEqual(self.levels, ['auto', 'hint'])
        self.assertTrue(all(project_settings.get(self.project, key) is False
                            for key in project_settings.DEFAULTS))
        self.assertTrue(all(self.pet.auto_variable(name).get() is False
                            for name in pet_ui.AUTO_VARIABLE_NAMES))
        self.assertIn('【模式】已切换到手动模式', self.messages)
        self.assertIn('【模式】已关闭全部自动制作开关', self.messages)

    def test_unknown_mode_does_not_change_the_current_mode(self):
        self.assertIsNone(self.pet.set_mode('semi'))
        self.assertEqual(self.pet.mode, 'manual')
        self.assertEqual(self.levels, [])

    def test_stage_ids_read_only_the_sanhu_owned_variables(self):
        self.assertFalse(self.pet.should_auto_run('01_storyboard_draft'))

    def test_mode_entry_state_tracks_the_single_set_mode_path(self):
        self.pet.mode_var = _ModeVar()
        self.assertEqual(self.pet.mode_label(), '模式：手动')
        self.pet.set_mode('auto')
        self.assertEqual(self.pet.mode_var.value, 'auto')
        self.assertEqual(self.pet.mode_label(), '模式：全自动')
        self.pet.set_mode('auto')
        self.assertTrue(self.pet.auto_storyboard_var.get())
        self.assertTrue(self.pet.should_auto_run('01_storyboard_draft'))
        self.assertTrue(self.pet.should_auto_run('storyboard'))
        self.assertTrue(self.pet.should_auto_run('02_assets'))
        self.assertTrue(self.pet.should_auto_run('05_first_frame'))
        self.assertTrue(self.pet.should_auto_run('07_video_gen'))
        self.assertTrue(self.pet.should_auto_run('08_audio_subtitle'))
        self.pet.set_mode('manual')
        self.assertFalse(self.pet.auto_storyboard_var.get())
        self.assertFalse(self.pet.should_auto_run('01_storyboard_draft'))

    def test_chat_level_switch_to_auto_takes_the_paw_entry(self):
        """聊天一句话切全自动与猫爪同一入口：模式与全部自动开关跟着走。"""
        self.pet.run_plan({'decision': {'run': True},
                           'plan': {'intent': 'level', 'params': {'level': 'auto'}}})
        self.assertEqual(self.pet.mode, 'auto')
        self.assertEqual(self.levels, ['auto', 'auto'])
        self.assertTrue(all(project_settings.get(self.project, key) is True
                            for key in project_settings.DEFAULTS))
        self.assertTrue(all(self.pet.auto_variable(name).get() is True
                            for name in pet_ui.AUTO_VARIABLE_NAMES))

    def test_chat_level_switch_to_semi_releases_auto_mode_and_switches(self):
        """全自动里聊天切半自动：退回手动模式、开关全关，不留第四种组合。"""
        self.pet.set_mode('auto')
        self.levels.clear()
        self.pet.run_plan({'decision': {'run': True},
                           'plan': {'intent': 'level', 'params': {'level': 'semi'}}})
        self.assertEqual(self.pet.mode, 'manual')
        self.assertEqual(self.levels, ['hint', 'semi'])
        self.assertTrue(all(project_settings.get(self.project, key) is False
                            for key in project_settings.DEFAULTS))
        self.assertTrue(all(self.pet.auto_variable(name).get() is False
                            for name in pet_ui.AUTO_VARIABLE_NAMES))

    def test_auto_completion_announces_and_queues_the_next_stage(self):
        self.pet.mode = 'auto'
        self.pet.auto = stage_flow.Auto(order=['storyboard', 'assets'])
        self.pet.auto.script_done('auto')
        self.assertEqual(self.pet.auto.next_stage(), 'storyboard')
        self.pet.bstate.advance_at = 99

        self.assertEqual(self.pet._auto_stage_completed({'stage': 'storyboard'}), 'assets')
        self.assertIsNone(self.pet.bstate.advance_at)
        self.assertIn('【下一阶段】资产管理 - 自动开始', self.messages)

    def test_auto_waits_for_script_structure_completion_before_dispatching_downstream(self):
        auto = stage_flow.Auto(order=['script_structure', 'storyboard'])
        auto.script_done('auto')
        self.assertEqual(auto.next_stage(), 'script_structure')
        self.assertIsNone(auto.next_stage(), '结构化剧本未收场时不能抢跑分镜')
        auto.done('script_structure', True)
        self.assertEqual(auto.next_stage(), 'storyboard')

    def test_old_structured_file_does_not_hide_a_current_structure_failure(self):
        """旧正稿可补历史漏记，但不能覆盖本轮明确的失败状态。"""
        from script_contract import canonical_structured_script_path
        structured = canonical_structured_script_path(self.project)
        structured.parent.mkdir(parents=True)
        structured.write_text('# 旧结构剧本\n', encoding='utf-8')
        self.pet.machine.fail('script_structure', '本轮 Writer 输出为空')
        self.pet.agent.set_level('auto')

        self.assertTrue(self.pet.arm_auto())
        self.assertEqual(self.pet.auto.pending()[0], 'script_structure')

    def test_auto_mode_dispatches_script_structure_instead_of_only_prompting(self):
        calls = []
        self.pet.desktop.pet_script_structure_batch = lambda: calls.append('run') or '已自动开始「剧本结构」'
        self.assertEqual(self.pet.script_structure_batch(), '已自动开始「剧本结构」')
        self.assertEqual(calls, ['run'])

    def test_auto_failure_broadcasts_block_and_halts_at_the_failed_stage(self):
        self.pet.mode = 'auto'
        self.pet.auto = stage_flow.Auto(order=['storyboard', 'assets'])
        self.pet.auto.script_done('auto')
        self.assertEqual(self.pet.auto.next_stage(), 'storyboard')

        self.assertIsNone(self.pet._auto_stage_failed({'stage': 'storyboard', 'error': '上游 JSON 不完整'}))
        self.assertIsNone(self.pet.auto.next_stage())
        self.assertEqual(self.pet.auto.state()['blocked'], 'storyboard')
        self.assertIn('【阻塞】初步分镜 未完成，自动执行已停止：上游 JSON 不完整', self.messages)


class _StatusLine:
    def __init__(self):
        self.value = ''

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _AutomationHost(AutoStateHolderMixin, PetBridgeMixin, AutoFlowsMixin, AutomationTickMixin):
    """auto_final_state／retry_auto_final 需要的最小宿主（不建窗口）。"""

    def __init__(self, root):
        self.root = root
        self.win = None
        self.studio = object()
        self.status = _StatusLine()
        self.worker = None
        self.page_index = None
        self.pet = None

    def asset_base(self):
        return Path(self.root) / 'episode'


class SanhuCopyWordingTests(unittest.TestCase):
    """三虎固定文案指向的入口必须还在界面上（不建窗口）。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        (self.project / 'episode').mkdir(parents=True)
        (self.project / 'episode' / 'assets.json').write_text('{}', encoding='utf-8')
        self.host = _AutomationHost(self.project)
        self.pet = pet_ui.Pet(self.host)
        self.pet.program = Path(self.temp.name)
        self.host.pet = self.pet
        for name in ('broadcast', 'whisper', 'announce', 'draw_paws', 'draw', 'refresh_menu_labels'):
            setattr(self.pet, name, lambda *args, **kwargs: None)
        patcher = mock.patch.object(pet_agent, 'save_settings', lambda *args, **kwargs: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_auto_final_off_copy_points_to_manual_sync(self):
        state = self.host.auto_final_state()
        self.assertEqual(state['kind'], 'off')
        for text in (state['text'], self.host.retry_auto_final()):
            self.assertNotIn('勾上', text)
            self.assertNotIn('没勾', text)
            self.assertIn('手动同步资产', text)
            self.assertIn('全自动', text)

    def test_final_page_ask_is_about_syncing_not_adopting(self):
        self.assertNotIn('采用掉', pet_ui_support.PAGE_ASKS[6][0])
        self.assertIn('定稿', pet_ui_support.PAGE_ASKS[6][0])

    def test_copy_does_not_name_removed_buttons(self):
        root = Path(__file__).resolve().parents[1]
        voice = (root / 'ui' / 'pet_ui_voice.py').read_text(encoding='utf-8')
        stages = (root / 'ui' / 'pet_ui_stages.py').read_text(encoding='utf-8')
        self.assertNotIn('点「确认」它就去办', voice)
        self.assertNotIn('按「导出」', stages)

    def test_unchecked_skill_copy_points_to_the_skill_icon(self):
        with mock.patch.object(stage_flow, 'selected_skills', return_value=[]):
            result = stage_exec.run(self.host, 'assets')
            self.assertIn('未勾选 SKILL', result['text'])
            self.assertIn('技能', result['text'])
            self.assertNotIn('阶段配置', result['text'])
            self.assertNotIn('恢复默认', result['text'])
            notice = self.pet.run_skill({'stage': 'assets', 'params': {}})
            self.assertIn('资产管理', notice)
            self.assertIn('技能', notice)
            self.assertNotIn('assets', notice)
            self.assertNotIn('阶段配置', notice)

    def test_buttons_named_by_new_copy_exist(self):
        root = Path(__file__).resolve().parents[1]
        media = (root / 'ui' / 'desktop_media_pages.py').read_text(encoding='utf-8')
        self.assertIn('手动制作交付', media)
        self.assertEqual('手动同步资产', stage_flow.MANUAL_LABELS['final'])
        shared = (root / 'desktop_shared_input.py').read_text(encoding='utf-8')
        self.assertIn('_toggle_skill_default', shared)
        self.assertIn('技能', shared)


if __name__ == '__main__':
    unittest.main()
