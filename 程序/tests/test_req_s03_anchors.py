"""REQ-S03 测试锚定：初步分镜 12 条「✅ 但无测试锚定」需求的行为锚点。

每条测试只使用 ``tempfile`` 临时项目与桩件，不联网、不打开真实用户项目；测试名与
docstring 都写明锚定的 ``REQ-S03-xx``。断言对应需求原文里可判定的那句行为，删除或
改反对应生产代码后应转红。
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import infra.file_cache as file_cache
import stage_config
from orchestrator import stage_handler_registry
import stage_parallel
import storyboard_catalog_service
from contract import storyboard_contract
import storyboard_selection
import workflow_settings
from agent.core import read, save
from project_context_factory import project_context
from stage_completion_service import completion_evidence
from desktop import Desktop
from ui.pet_ui_stages import stage_run_action


def _shot(sid='SH001', duration=5, **extra):
    shot = {'id': sid, 'title': '镜头', 'duration': duration, 'characters': [],
            'location': 'LOC_001', 'props': [],
            'frame': 'frames/%s.png' % sid, 'frame_prompt': '动作起点',
            'video_prompt': '景别机位、动作起止与对白', 'dialogue': []}
    shot.update(extra)
    return shot


def _board(episode_id='EP001', shots=None):
    shots = [_shot()] if shots is None else shots
    return {'episode_id': episode_id, 'title': '测试集',
            'duration': sum(shot['duration'] for shot in shots), 'shots': shots}


def _working(root):
    folder = Path(root) / '03初步分镜' / '分镜拆分'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _script(root, name):
    path = Path(root) / '01剧本准备' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# 第一集\n\n正式剧本\n', encoding='utf-8')
    return path


class _Pet:
    def __init__(self):
        self.events = []
        self.reported = []
        self.auto = type('Auto', (), {'active': None})()

    def _emit(self, event, **payload):
        self.events.append((event, payload))


class _Host:
    present_stage = Desktop.present_stage

    def __init__(self, root):
        self.root = root
        self.pet = _Pet()
        self.opened = []

    def open_storyboard_skill(self, value):
        self.opened.append(value)

    def pet_report(self, stage, text):
        self.pet.reported.append((stage, text))


class ReqS03DocAnchorTests(unittest.TestCase):
    def test_req_s03_51_legacy_flow_coexists_but_stage_preset_is_authoritative(self):
        """REQ-S03-51：旧单独流程默认技能是兼容层，AIGC 全流程阶段预设才是权威。"""
        legacy = workflow_settings.DEFAULT_SKILLS['storyboard']
        self.assertEqual(legacy, 'short-drama-storyboard')
        self.assertIn('pipeline-storyboard-draft', stage_config.default_entry('storyboard')['skills'])
        self.assertNotEqual(legacy, 'pipeline-storyboard-draft', '兼容层与阶段默认必须保留为两条不同入口')


class ReqS03AnchorTests(unittest.TestCase):
    def test_req_s03_04_presentation_rejection_does_not_report_success(self):
        host = _Host(Path('D:/project'))
        host.pet.auto.active = 'storyboard'
        plan = {'scripts': ['script'], 'todo': [], 'revise': []}
        for method, pending in (('pet_report', []), ('open_storyboard_skill', ['script'])):
            with self.subTest(method=method), \
                    patch.object(stage_handler_registry, 'storyboard_work_plan',
                                 return_value=dict(plan, todo=pending)), \
                    patch.object(host, method, return_value=False) as action:
                self.assertIs(stage_handler_registry.start(
                    host, 'storyboard', run_action=stage_run_action), False)
                action.assert_called_once()
                self.assertEqual(host.pet.events, [])
                action.side_effect = RuntimeError('presentation failed')
                with self.assertRaisesRegex(RuntimeError, 'presentation failed'):
                    stage_handler_registry.start(host, 'storyboard', run_action=stage_run_action)
                self.assertEqual(action.call_count, 2)
                self.assertEqual(host.pet.events, [])

    def test_req_s03_04_missing_presentation_action_rejects_pending_work(self):
        host = _Host(Path('D:/project'))
        with patch.object(stage_handler_registry, 'storyboard_work_plan',
                          return_value={'scripts': ['script'], 'todo': ['script'], 'revise': []}):
            with self.assertRaisesRegex(RuntimeError, '缺少'):
                stage_handler_registry.start(host, 'storyboard', 'manual')
        self.assertEqual(host.opened, [])

    def test_req_s03_04_unknown_presentation_action_is_rejected(self):
        host = _Host(Path('D:/project'))
        with self.assertRaisesRegex(ValueError, '未知阶段呈现动作'):
            stage_run_action(host, 'storyboard', 'auto', presentation='OPEN_STORYBOARD')
        self.assertEqual((host.opened, host.pet.reported, host.pet.events), ([], [], []))

    # --- 启动与输入 -------------------------------------------------------
    def test_req_s03_03_workflow_lock_blocks_manual_and_auto_before_start(self):
        """REQ-S03-03：启动前先过总控制作锁门禁，手动与自动同样阻断；入口只有 stage_handler_registry.start()。"""
        host = _Host(Path('D:/project'))
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            with patch.dict('contract.script_contract.STAGE_LOCK_REQUIREMENTS',
                            {'storyboard': ('aspect_ratio',)}), \
                    patch.object(stage_config, 'project_created_at', return_value=None), \
                    patch.object(stage_config, 'workflow_lock', return_value={}):
                host.root = project
                manual = stage_handler_registry.start(host, 'storyboard', 'manual')
                auto = stage_handler_registry.start(
                    host, 'storyboard', 'auto', run_action=stage_run_action)
        for result in (manual, auto):
            self.assertIn('画幅', result)
            self.assertIn('发送框内写明制作锁', result)
        self.assertEqual(host.opened, [], '门禁拦住时不能打开分镜任务')
        self.assertEqual(host.pet.events, [('stage.failed', {'stage': 'storyboard', 'error': auto})])

        # 锁门禁通过后，分镜阶段也只能由这个入口转到 _start_storyboard。
        with patch.object(stage_handler_registry, '_start_storyboard', return_value=('started', '', None)) as stage:
            self.assertEqual(stage_handler_registry.start(host, 'storyboard', 'manual'), 'started')
        stage.assert_called_once_with(host, 'manual')

    def test_req_s03_04_empty_work_plan_skips_agent_and_only_auto_reports(self):
        """REQ-S03-04：待办与待修订都为空时不再启动 Agent；自动播报，手动无动作。"""
        host = _Host(Path('D:/project'))
        script = Path('D:/project/a.md')
        empty = {'scripts': [script], 'existing': [], 'made': set(), 'used': set(),
                 'todo': [], 'revise': []}
        with patch.object(stage_handler_registry, 'storyboard_work_plan', return_value=empty):
            self.assertEqual(stage_handler_registry.start(host, 'storyboard', 'manual'), '')
            self.assertEqual(host.opened, [])
            host.pet.auto.active = 'storyboard'
            text = stage_handler_registry.start(host, 'storyboard', 'auto', run_action=stage_run_action)
        self.assertIn('已确认所有已选结构剧本的分镜均已生成并采用', text)
        self.assertEqual(host.pet.reported, [('storyboard', text)])
        self.assertEqual(host.pet.events, [])
        self.assertEqual(host.opened, [])

        pending = dict(empty, todo=[script])
        with patch.object(stage_handler_registry, 'storyboard_work_plan', return_value=pending):
            self.assertIn('已经在准备分镜任务', stage_handler_registry.start(
                host, 'storyboard', 'manual', run_action=stage_run_action))
        self.assertEqual(host.opened, [None])

    def test_req_s03_06_single_json_per_episode_and_stitch_across_scenes(self):
        """REQ-S03-06：同一集只输出一份分镜 JSON，已存在则跳过说明；各场景按剧本顺序拼接并核对衔接。"""
        text = stage_parallel.brief_text('storyboard')
        for phrase in ('同一集只输出一份分镜 JSON', '不生成副本、不换文件名重写',
                       '按剧本顺序拼接', '上一场结束状态＝下一场开始状态'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            data = _board()
            save(folder / 'EP001_甲_分镜.json', data)
            save(folder / 'EP001_乙_分镜.json', data)
            entries = storyboard_catalog_service.catalog(project_context(root), 'storyboard')
            self.assertEqual(len(entries), 1, '同一集的同内容副本只能算一份分镜')

    def test_req_s03_15_contract_requires_triplet_without_duplicating_archives(self):
        """REQ-S03-15：每镜写清镜头三元组并按动作闭合点切镜；不重复写结构剧本的角色／场景／道具档案。"""
        text = storyboard_contract.rules()
        for phrase in ('每镜先写清镜头三元组', '核心人物／画面主体', '可见动作', '景别机位与运镜',
                       '按动作闭合点切镜', '不要把结构剧本的角色／场景／道具档案重复写入分镜初稿'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_req_s03_20_storyboard_stage_does_not_write_batch_id(self):
        """REQ-S03-20：03 不写 batch_id，批次划分归 07；阶段并行提示明确本阶段不写。"""
        text = stage_parallel.brief_text('storyboard')
        self.assertIn('批次划分（batch_id）属于 07 分镜定稿，本阶段不写', text)
        self.assertNotIn('batch_id', storyboard_contract.rules())

    # --- 采用与取消采用 ---------------------------------------------------
    def test_req_s03_30_adoption_validates_the_whole_batch_before_writing(self):
        """REQ-S03-30：采用前对整批（已采用＋新增）逐份校验；任一份不过整批拒绝，采用记录与资产计划不变。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            script = _script(root, 'EP001_正式剧本.md')
            good = folder / 'EP001_分镜.json'
            data = _board()
            data['source_script'] = script.relative_to(root).as_posix()
            save(good, data)
            bad = folder / 'EP002_分镜.json'
            save(bad, _board('EP002', [_shot('SH002', duration=1)]))
            orphan = folder / 'EP003_分镜.json'
            orphan_data = _board('EP003', [_shot('SH003')])
            orphan_data['source_script'] = '01剧本准备/已删除的剧本.md'
            save(orphan, orphan_data)

            with patch('asset_plan._sync_plan') as sync:
                storyboard_selection.adopt(root, [good])
                sync.reset_mock()
                # 已采用的那份来源失效时，新增一份合法分镜也必须整批拒绝。
                spare = folder / 'EP005_分镜.json'
                spare_data = _board('EP005', [_shot('SH005')])
                spare_data['source_script'] = script.relative_to(root).as_posix()
                save(spare, spare_data)
                original = script.read_text(encoding='utf-8')
                script.unlink()
                with self.assertRaises(ValueError) as caught:
                    storyboard_selection.adopt(root, [spare])
                self.assertIn(good.name, str(caught.exception))
                self.assertIn('不存在或已迁移', str(caught.exception))
                script.write_text(original, encoding='utf-8')
                sync.assert_not_called()
                with self.assertRaises(ValueError) as caught:
                    storyboard_selection.adopt(root, [bad])
                self.assertIn(bad.name, str(caught.exception))
                self.assertIn('时长', str(caught.exception))
                with self.assertRaises(ValueError) as caught:
                    storyboard_selection.adopt(root, [orphan])
                self.assertIn(orphan.name, str(caught.exception))
                self.assertIn('不存在或已迁移', str(caught.exception))
                sync.assert_not_called()

            self.assertEqual(storyboard_selection.adopted(root), [good.resolve()])

    def test_req_s03_31_syncs_assets_before_writing_adoption_and_falls_back(self):
        """REQ-S03-31：采用成功后先同步资产计划，再写 adopted_storyboards／frame_json；缺清单时回退旧单值。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            board = folder / 'EP001_分镜.json'
            save(board, _board())
            seen = {}

            def sync(project, library, sources, **_kwargs):
                settings = Path(project) / 'ui_settings.json'
                seen['at_sync'] = read(settings) if settings.is_file() else None
                seen['sources'] = list(sources)

            with patch('asset_plan._sync_plan', side_effect=sync):
                storyboard_selection.adopt(root, [board])
            self.assertNotIn('adopted_storyboards', seen['at_sync'] or {})
            self.assertEqual(seen['sources'], [board.resolve()])

            prefs = read(root / 'ui_settings.json')
            relative = board.relative_to(root).as_posix()
            self.assertEqual(prefs['adopted_storyboards'], [relative])
            self.assertEqual(prefs['frame_json'], relative)

            file_cache.clear()
            save(root / 'ui_settings.json', {'frame_json': relative})
            self.assertEqual(storyboard_selection.adopted(root), [board.resolve()],
                             'adopted_storyboards 缺失时应回退读旧单值 frame_json')
            with self.assertRaises(ValueError):
                storyboard_selection.adopt(root, [root.parent / '项目外.json'])

    def test_req_s03_32_auto_adopt_batches_new_files_and_syncs_plan_once(self):
        """REQ-S03-32：只采用新出现且已稳定的 JSON；刚写入的 waiting、坏文件只跳过；整批只同步一次资产计划。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            first = folder / 'EP001_分镜.json'
            second = folder / 'EP002_分镜.json'
            fresh = folder / 'EP003_分镜.json'
            bad = folder / 'EP004_分镜.json'
            save(first, _board('EP001', [_shot('SH001')]))
            save(second, _board('EP002', [_shot('SH002')]))
            save(fresh, _board('EP003', [_shot('SH003')]))
            save(bad, _board('EP004', [_shot('SH004', duration=1)]))
            old = time.time() - 60
            for path in (first, second, bad):
                os.utime(path, (old, old))

            with patch('asset_plan._sync_plan') as sync:
                result = storyboard_selection.adopt_pending(root)
            self.assertEqual(result['adopted'], [first.resolve(), second.resolve()])
            self.assertEqual(result['waiting'], [fresh.resolve()])
            self.assertIn(str(bad.resolve()), result['failed'])
            self.assertEqual(sync.call_count, 1)
            self.assertEqual(storyboard_selection.adopted(root), [first.resolve(), second.resolve()])

            os.utime(fresh, None)
            with patch('asset_plan._sync_plan') as sync_again:
                again = storyboard_selection.adopt_pending(root)
            self.assertEqual(again['adopted'], [])
            self.assertEqual(sync_again.call_count, 0)

    def test_req_s03_33_remove_only_updates_lists_and_focus_requires_adoption(self):
        """REQ-S03-33：取消采用只改清单与当前指针并按剩余清单重同步，不删文件；focus 只能指向已采用。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            first = folder / 'EP001_分镜.json'
            second = folder / 'EP002_分镜.json'
            third = folder / 'EP003_分镜.json'
            save(first, _board('EP001', [_shot('SH001')]))
            save(second, _board('EP002', [_shot('SH002')]))
            save(third, _board('EP003', [_shot('SH003')]))
            with patch('asset_plan._sync_plan'):
                storyboard_selection.adopt(root, [first, second])
            with self.assertRaises(ValueError):
                storyboard_selection.focus(root, third)

            with patch('asset_plan._sync_plan') as sync:
                remaining = storyboard_selection.remove(root, [second])
            self.assertEqual(remaining, [first.resolve()])
            self.assertEqual(sync.call_count, 1)
            self.assertEqual(sync.call_args.args[2], [first.resolve()])
            self.assertTrue(second.is_file(), '取消采用不能删除分镜文件')
            self.assertEqual(storyboard_selection.adopted(root), [first.resolve()])
            self.assertEqual(read(root / 'ui_settings.json')['frame_json'],
                             first.relative_to(root).as_posix())
            storyboard_selection.focus(root, first)
            self.assertEqual(read(root / 'ui_settings.json')['frame_json'],
                             first.relative_to(root).as_posix())

    def test_req_s03_34_prune_invalid_adoptions_keeps_json_and_assets(self):
        """REQ-S03-34：来源剧本已失效的 JSON 由 prune_invalid_adoptions 取消采用，保留 JSON 文件和历史资产。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            first_script = _script(root, 'EP001_正式剧本.md')
            second_script = _script(root, 'EP002_正式剧本.md')
            good = folder / 'EP001_分镜.json'
            good_data = _board('EP001', [_shot('SH001')])
            good_data['source_script'] = first_script.relative_to(root).as_posix()
            save(good, good_data)
            orphan = folder / 'EP002_分镜.json'
            orphan_data = _board('EP002', [_shot('SH002')])
            orphan_data['source_script'] = second_script.relative_to(root).as_posix()
            save(orphan, orphan_data)
            assets = root / '05资产管理' / 'assets' / '资产清单' / 'assets.json'
            save(assets, {'CHAR_001': {'name': '角色甲'}})
            with patch('asset_plan._sync_plan'):
                storyboard_selection.adopt(root, [good, orphan])

            second_script.unlink()
            removed = storyboard_selection.prune_invalid_adoptions(root)
            self.assertEqual(removed, (str(orphan.resolve()),))
            self.assertTrue(orphan.is_file(), '失效来源只取消采用，不删分镜文件')
            self.assertEqual(storyboard_selection.adopted(root), [good.resolve()])
            self.assertTrue(assets.is_file(), '历史资产必须保留')
            self.assertEqual(read(assets)['CHAR_001']['name'], '角色甲')

    def test_req_s03_35_seed_storyboard_is_not_counted_as_produced(self):
        """REQ-S03-35：刚创建项目的种子分镜（EP001/SH001/待编写）不当作已制作的分镜。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            seed = {'episode_id': 'EP001', 'title': '未命名', 'shots': [{
                'id': 'SH001', 'title': '待编写', 'duration': 5,
                'characters': ['CHAR_001'], 'location': 'LOC_001',
                'frame': 'frames/SH001.png',
                'video_prompt': '待填写镜头画面、动作和对白', 'dialogue': []}]}
            save(folder / 'episode.json', seed)
            save(folder / 'EP001_改名_分镜.json', seed)
            self.assertEqual(storyboard_catalog_service.catalog(project_context(root), 'storyboard'), [])
            from stage_execution_service import storyboard_produced_scripts
            self.assertEqual(storyboard_produced_scripts(root), set())

    # --- 完成核验 ---------------------------------------------------------
    def test_req_s03_41_completion_needs_an_adopted_storyboard_with_shots(self):
        """REQ-S03-41：完成 = 至少一份已采用且含镜头的分镜 JSON；没有时报明确原因。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = _working(root)
            self.assertEqual(completion_evidence(root, 'storyboard'),
                             (False, '还没有已采用且含镜头的分镜 JSON'))

            empty = folder / 'EP001_分镜.json'
            save(empty, _board('EP001', []))
            save(root / 'ui_settings.json', {'adopted_storyboards': [empty.relative_to(root).as_posix()]})
            file_cache.clear()
            self.assertEqual(completion_evidence(root, 'storyboard'),
                             (False, '还没有已采用且含镜头的分镜 JSON'))

            good = folder / 'EP002_分镜.json'
            save(good, _board('EP002', [_shot('SH002')]))
            save(root / 'ui_settings.json', {'adopted_storyboards': [good.relative_to(root).as_posix()]})
            file_cache.clear()
            self.assertEqual(completion_evidence(root, 'storyboard'), (True, ''))


if __name__ == '__main__':
    unittest.main()
