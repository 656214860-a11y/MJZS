"""R1483：新版制作锁契约、日期门禁、持久化、简报与发送。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import script_contract as contract
import workflow_settings
import master_skill
import stage_config
import idea_chat
from idea_brief_form import extract_brief_creation, inline_required_missing
from stage_execution_service import save_writing_production_locks


class ProductionLockContractTests(unittest.TestCase):
    def test_definitions_and_required_date(self):
        items = {item['key']: item for item in contract.PRODUCTION_LOCK_DEFINITIONS}
        self.assertEqual(len(items), 11)
        self.assertEqual(list(items)[:5], ['aspect_ratio', 'resolution', 'fps', 'delivery_format', 'video_model_version'])
        self.assertEqual(items['track']['options'], ['国内剧', '海外剧', '解说叙事类', '其他'])
        self.assertNotIn('default', items['track'])
        self.assertNotIn('default', items['material_source'])
        self.assertEqual(items['reference_mode']['depends_on'], {'video_model_version': 'Seedance 2.5'})
        self.assertEqual(items['splice_mode']['default'], '末帧定格承接')
        self.assertEqual(items['style_base']['options'], ['真人实拍质感', '2D 手绘动画', '3D CG 动画', '水墨二维'])
        for key in ('track', 'material_source'):
            self.assertIn(key, contract.STAGE_LOCK_REQUIREMENTS['script'])
            self.assertEqual(items[key]['required_from'], '2026-10-15')
            self.assertNotIn(key, contract.stage_lock_requirements('script', '2026-10-14'))
            self.assertIn(key, contract.stage_lock_requirements('script', '2026-10-15'))
        self.assertEqual({item['key'] for item in workflow_settings.refresh_workflow_presets()['AIGC全流程']['locks']}, set(items))

    def test_creation_date_uses_registry_not_copied_directory_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('stage_config.read_json', return_value={'projects': [{'path': str(root), 'created_at': '2026-10-14'}]}):
                self.assertEqual(stage_config.project_created_at(root), '2026-10-14')
            with patch('stage_config.read_json', return_value={'projects': [{'path': str(root), 'created_at': '2026-10-15'}]}):
                self.assertEqual(stage_config.project_created_at(root), '2026-10-15')
            with patch('stage_config.read_json', return_value={}):
                self.assertIsNone(stage_config.project_created_at(root))

    def test_gate_old_warns_new_blocks_and_selected_passes(self):
        config = {'workflow_name': 'AIGC全流程', 'stage': 'writing', 'project_created_at': '2026-10-14'}
        self.assertEqual(master_skill.gate(config, check_references=False), '')
        self.assertEqual(len(config['workflow_lock_warnings']), 2)
        config['project_created_at'] = '2026-10-15'
        blocked = master_skill.gate(config, check_references=False)
        self.assertIn('赛道', blocked)
        self.assertIn('素材来源', blocked)
        config['workflow_lock'] = {'track': '海外剧', 'material_source': '原创'}
        self.assertEqual(master_skill.gate(config, check_references=False), '')

    def test_publisher_roundtrip_and_card_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage_config.put_workflow(root, {'name': 'AIGC全流程', 'lock': {}})
            values = {'track': '海外剧', 'material_source': '原创', 'reference_mode': '首尾帧模式',
                      'splice_mode': '空镜过渡', 'style_base': '水墨二维', 'style_directors': '徐克，王家卫'}
            save_writing_production_locks(root, values)
            self.assertEqual(stage_config.workflow_lock(root), values)
            with self.assertRaisesRegex(ValueError, '最多 4'):
                save_writing_production_locks(root, {'style_directors': '甲,乙,丙,丁,戊'})
            self.assertEqual(stage_config.workflow_lock(root), values)

    def test_all_aliases_and_inline_date_gate(self):
        for item in contract.PRODUCTION_LOCK_DEFINITIONS[5:]:
            for label in (item['label'], *item['aliases']):
                fields = extract_brief_creation(label + '：测试值', include_extra=True)
                self.assertEqual(fields[label], '测试值')
                self.assertEqual(idea_chat._brief_value(label + '：测试值', (item['label'], *item['aliases'])), '测试值')
        self.assertEqual(inline_required_missing(None, '交付形态：两者都交付', required_labels=(), created_at='2026-10-14'), ())
        self.assertEqual(inline_required_missing(None, '交付形态：两者都交付', required_labels=(), created_at='2026-10-15'), ('赛道', '素材来源'))

    def test_injection_all_stages_and_reference_dependency(self):
        locks = {'track': '海外剧', 'material_source': '原创', 'reference_mode': '首尾帧模式',
                 'video_model_version': 'Seedance 2.5', 'splice_mode': '空镜过渡', 'style_base': '', 'style_directors': '徐克'}
        for stage in ('writing', 'storyboard', 'keyframe', 'video', 'audio', 'edit'):
            prompt = workflow_settings.skill_prompt({'workflow_lock': locks}, stage)
            for key in ('track', 'material_source', 'reference_mode', 'splice_mode', 'style_directors'):
                self.assertIn(key + '=', prompt)
            self.assertNotIn('style_base=', prompt)
            self.assertIn('以项目锁定值为准，不要再向用户弹问这些锁', prompt)
        locks['video_model_version'] = 'MiniMax H3'
        self.assertNotIn('reference_mode=', workflow_settings.skill_prompt({'workflow_lock': locks}, 'video'))
