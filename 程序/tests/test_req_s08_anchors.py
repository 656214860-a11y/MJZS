# -*- coding: utf-8 -*-
"""REQ-S08 测试锚定：首帧管理（08）里标 ✅ 却没有测试锚点的 17 条需求。

覆盖 REQ-S08-11/12/13/14/15/16/17/18/19/20/21/22/23/24/30/31/32。这些编号原登记在
`维护记录/需求锚定基线.json` 的 `untested_done`，本轮补上落在真实代码行为上的锚点：

- 尺寸与画幅锁、追溯证据与校验原因、参考资产影响范围：`keyframe_evidence` 真实解码图片、
  真实算哈希，并把证据过 `stage_parallel.frames_ready` 这门禁；
- 三种批次模式与不可生成镜头：`keyframe_batch.batch_plan` 的真实计划；
- 手动导入与迟到结果：`keyframe_import.register` 真读真写分镜 JSON；
- 生命周期：`stage_execution_service` 的删除／恢复／替换注入发布器，失败真回滚；
- 模型来源：`keyframe_model_service` 读 `stage_config`；
- 付费确认与并行：`skill_templates` 解析的四步模板、`skill_registry` 的 paid 标记、
  `stage_parallel` 的真实 Governor；
- 阶段路径与完成／门禁：`stage_path_service`、`stage_completion_service`、`stage_parallel`；
- 视频侧缺首帧：`local_video.auto_plan` 的真实跳过计划。

所有断言针对真实函数与常量，不 mock 被测事实；需要落盘时一律在
``tempfile.TemporaryDirectory()`` 隔离目录内进行，不打开真实用户项目。
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import keyframe_batch as kb
import keyframe_evidence as evidence
import local_video
import pet_bus
import skill_registry
import skill_templates
import stage_completion_service
import stage_config
import stage_parallel
import stage_path_service
from agent.core import read, save
from keyframe_import import fingerprint, register
from production_model_contract import (
    LOCAL_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL,
)
from stage_execution_service import (
    delete_stage_keyframe, replace_stage_keyframe, restore_stage_keyframe,
)
from tests.image_fixtures import png


def _episode(root, folder='episode', episode_id='EP001',
             shots=('SH001', 'SH002', 'SH003'), frames=(), empty=(), deleted=()):
    """一集的镜头 JSON 与 frames 目录（与 keyframe_batch 同口径）。"""
    base = Path(root) / folder
    (base / 'frames').mkdir(parents=True, exist_ok=True)
    rows = []
    for sid in shots:
        shot = {'id': sid, 'title': sid, 'duration': 5, 'frame': 'frames/%s.png' % sid,
                'frame_prompt': sid + ' 的提示词'}
        if sid in deleted:
            shot['frame_deleted'] = True
        rows.append(shot)
    src = base / 'episode.json'
    src.write_text(json.dumps({'episode_id': episode_id, 'title': 'T', 'shots': rows},
                              ensure_ascii=False), encoding='utf-8')
    for sid in frames:
        (base / 'frames' / (sid + '.png')).write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 16)
    for sid in empty:
        (base / 'frames' / (sid + '.png')).write_bytes(b'')
    return src


def _attempt(src, sid, state):
    folder = Path(src).parent / '首帧任务'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ('seedream_%s.json' % sid)).write_text(
        json.dumps({'state': state, 'shot_id': sid}), encoding='utf-8')


def _target_ids(plan):
    return [item['shot_id'] for item in plan['targets']]


def _skip_reason(plan, sid):
    return next((item['reason'] for item in plan['skipped'] if item['shot_id'] == sid), '')


def _register_project(td):
    """和 keyframe_import.register 同口径的一集：SH001 缺首帧，frames 目录已就位。"""
    proj = Path(td) / 'p'
    (proj / 'episode' / 'frames').mkdir(parents=True, exist_ok=True)
    episode = {'episode_id': 'EP001', 'title': 'T',
               'shots': [{'id': 'SH001', 'title': '镜头', 'duration': 5,
                          'frame': 'frames/SH001.png', 'video_prompt': 'x'}]}
    src = proj / 'episode' / 'episode.json'
    src.write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
    return proj, src, episode


def _evidence_image(root, source, episode, shot, size=(16, 9), check=None,
                    **kwargs):
    """写一张真实 PNG 并把证据记进镜头（可选 expected_size／aspect_ratio）。"""
    image = root / shot['frame']
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(png(size=size))
    shot['frame_evidence'] = evidence.make_evidence(source, episode, shot, image,
                                                    **kwargs)
    save(source, episode)
    return image


class KeyframeRequirementAnchorTests(unittest.TestCase):
    def test_req_s08_11_frame_size_must_match_aspect_lock_and_expected_size(self):
        """REQ-S08-11：首帧尺寸必须符合项目画幅锁（workflow_lock.aspect_ratio）和记录的期望尺寸。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage_config.put_workflow(
                root, {'name': '项目', 'lock': {'项目': {'aspect_ratio': '9:16'}}})
            self.assertEqual(stage_config.workflow_lock(root)['aspect_ratio'], '9:16')
            source = root / 'adopted.json'
            shot = {'id': 'SH001', 'frame': 'good.png'}
            episode = {'shots': [shot]}
            image = _evidence_image(root, source, episode, shot, size=(16, 9),
                                    expected_size=(16, 9))

            def frames_ready():
                with patch.object(stage_parallel, '_adopted',
                                  return_value=[(source, [shot])]), \
                        patch.object(stage_parallel, 'has_run', return_value=True), \
                        patch('storyboard_paths.media_root', return_value=root):
                    return stage_parallel.frames_ready(root)

            # 16:9 的图对不上 9:16 的项目画幅锁 → 门禁不通过，并说明是画幅问题。
            result = frames_ready()
            self.assertFalse(result['ok'])
            self.assertIn('画幅', ' '.join(result['problems']))
            # 换成与画幅锁一致、且与记录期望尺寸一致的 9:16 → 通过。
            image.write_bytes(png(size=(9, 16)))
            shot['frame_evidence'] = evidence.make_evidence(
                source, episode, shot, image, expected_size=(9, 16))
            save(source, episode)
            self.assertTrue(frames_ready()['ok'], frames_ready()['problems'])
            # 期望尺寸与图片事实对不上时，生成证据这一步就拒绝。
            with self.assertRaisesRegex(ValueError, '尺寸'):
                evidence.make_evidence(source, episode, shot, image, expected_size=(16, 9))

    def test_req_s08_12_three_modes_target_only_shots_without_a_frame(self):
        """REQ-S08-12：三种模式；只补缺失只处理没有首帧的镜头、已成功永不重复、本集之外不进计划。"""
        with tempfile.TemporaryDirectory() as td:
            src = _episode(td, frames=('SH001',), deleted=('SH003',))
            _episode(td, folder='other', episode_id='EP002', shots=('SH900', 'SH901'))
            plan = kb.batch_plan(src)
            self.assertEqual(plan['mode'], kb.MODE_MISSING)
            self.assertEqual(plan['mode_label'], '只补缺失')
            self.assertEqual(plan['episode'], 'EP001')
            self.assertEqual(_target_ids(plan), ['SH002'])
            self.assertEqual(sorted(kb.BATCH_MODES),
                             sorted([kb.MODE_MISSING, kb.MODE_RETRY, kb.MODE_REPLACE]))
            self.assertNotIn('SH900', _target_ids(plan))     # 另一集的镜头不进本集计划
            # 已成功的镜头在三种模式下都不进目标集。
            done = _episode(td, folder='done', shots=('SH001', 'SH002'),
                            frames=('SH001', 'SH002'))
            for mode in kb.BATCH_MODES:
                self.assertEqual(_target_ids(kb.batch_plan(done, mode=mode)), [], mode)
            # 显式替换点名已有首帧的镜头才重做。
            named = kb.batch_plan(done, shot_ids=['SH001'], mode=kb.MODE_REPLACE)
            self.assertEqual(_target_ids(named), ['SH001'])
            self.assertIn('覆盖', named['targets'][0]['note'])

    def test_req_s08_13_deleted_never_revived_and_unbuildable_shots_reported(self):
        """REQ-S08-13：已删除的首帧任何模式都不复活；空文件／未配置／越界列为不可生成并给出原因。"""
        with tempfile.TemporaryDirectory() as td:
            src = _episode(td, shots=('SH001', 'SH002', 'SH003', 'SH004'),
                           empty=('SH002',), deleted=('SH003',))
            data = json.loads(Path(src).read_text(encoding='utf-8'))
            data['shots'][0]['frame'] = ''                    # SH001 未配置路径
            data['shots'][3]['frame'] = '../../outside.png'   # SH004 路径越界
            Path(src).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            for mode in kb.BATCH_MODES:
                plan = kb.batch_plan(src, shot_ids=['SH001', 'SH002', 'SH003', 'SH004'],
                                     mode=mode)
                self.assertEqual(_target_ids(plan), [], mode)
                self.assertIn('未配置', _skip_reason(plan, 'SH001'))
                self.assertIn('空文件', _skip_reason(plan, 'SH002'))
                self.assertIn('已删除', _skip_reason(plan, 'SH003'))
                self.assertIn('越界', _skip_reason(plan, 'SH004'))
                # 已删除的镜头要指向首帧管理页去恢复，不静默跳过。
                self.assertIn(pet_bus.stage_label('keyframe'),
                              _skip_reason(plan, 'SH003'))

    def test_req_s08_14_uncertain_and_unusable_done_are_reported_not_resubmitted(self):
        """REQ-S08-14：结果不确定的旧任务标「结果待核实」不自动重提；记录称完成但文件不可用同样报告。"""
        with tempfile.TemporaryDirectory() as td:
            src = _episode(td, shots=('SH001', 'SH002'), frames=('SH001',))
            _attempt(src, 'SH002', 'uncertain')
            missing = kb.batch_plan(src)                       # 只补缺失不重复付费
            self.assertEqual(_target_ids(missing), [])
            self.assertIn('重试失败', _skip_reason(missing, 'SH002'))
            self.assertIn('结果待核实', _skip_reason(missing, 'SH002'))
            retry = kb.batch_plan(src, mode=kb.MODE_RETRY)
            self.assertEqual(_target_ids(retry), ['SH002'])
            self.assertIn('结果待核实', retry['targets'][0]['note'])
            # 记录称已完成、但首帧文件不可用：仍要报出来。
            broken = _episode(td, folder='broken', shots=('SH001',), frames=())
            _attempt(broken, 'SH001', 'completed')
            retry2 = kb.batch_plan(broken, mode=kb.MODE_RETRY)
            self.assertEqual(_target_ids(retry2), ['SH001'])
            self.assertIn('记录称已完成，但首帧文件不可用', retry2['targets'][0]['note'])

    def test_req_s08_15_frame_prompt_prefers_frame_then_keyframe_never_video(self):
        """REQ-S08-15：首帧提示词取 frame_prompt，缺失退到 keyframe_prompt，不得用视频提示词代替。"""
        self.assertEqual(kb.frame_prompt({'frame_prompt': '首帧'}), '首帧')
        self.assertEqual(kb.frame_prompt({'keyframe_prompt': '关键帧'}), '关键帧')
        # frame_prompt 优先于 keyframe_prompt。
        self.assertEqual(kb.frame_prompt(
            {'frame_prompt': '首帧', 'keyframe_prompt': '关键帧'}), '首帧')
        # 只有视频提示词时，绝不代替。
        self.assertEqual(kb.frame_prompt({'video_prompt': '动作'}), '')
        self.assertEqual(kb.frame_prompt(
            {'video_prompt': '动作', 'first_frame_prompt': '起点'}), '起点')

    def test_req_s08_16_manual_import_rejects_bad_input_and_keeps_old_on_failure(self):
        """REQ-S08-16：手动导入须对应当前镜头：分镜已改／编号非法／非 PNG 拒绝；关联失败保留旧来源与已发布首帧。"""
        with tempfile.TemporaryDirectory() as td:
            proj, src, episode = _register_project(td)
            shot = episode['shots'][0]
            good = Path(td) / 'frame.png'
            good.write_bytes(png())
            item = {'shot_id': 'SH001', 'shot_signature': fingerprint(shot),
                    'source_evidence': evidence.source_evidence(src, episode, shot)}
            dest = register(src, item, good)
            self.assertTrue(dest.is_file())
            self.assertTrue((proj / 'episode' / read(src)['shots'][0]['frame']).is_file())
            # 分镜已被修改 → 拒绝。
            modified = {'shot_id': 'SH001',
                        'shot_signature': fingerprint(dict(shot, title='改了')),
                        'source_evidence': item['source_evidence']}
            with self.assertRaises(ValueError):
                register(src, modified, good)
            # 镜头号非法 → 拒绝。
            with self.assertRaises(ValueError):
                register(src, {'shot_id': '../bad',
                               'shot_signature': fingerprint(shot)}, good)
            # 非 PNG → 拒绝。
            bad = Path(td) / 'bad.png'
            bad.write_bytes(b'not png')
            with self.assertRaises(ValueError):
                register(src, {'shot_id': 'SH001', 'shot_signature': fingerprint(shot)},
                         bad)
        with tempfile.TemporaryDirectory() as td:
            proj, src, episode = _register_project(td)
            before = src.read_bytes()
            good = Path(td) / 'frame.png'
            good.write_bytes(png())
            item = {'shot_id': 'SH001', 'shot_signature': fingerprint(episode['shots'][0]),
                    'source_evidence': evidence.source_evidence(src, episode, episode['shots'][0])}
            with patch('keyframe_import.save', side_effect=OSError('磁盘已满')):
                with self.assertRaises(OSError):
                    register(src, item, good)
            # 关联失败：旧来源（分镜 JSON）不动，已发布的首帧保留，不留半成品。
            self.assertEqual(src.read_bytes(), before)
            self.assertEqual(len(list((proj / 'episode' / 'frames').glob('EP001_SH001_*.png'))), 1)

    def test_req_s08_17_late_result_is_not_adopted_when_the_source_changed(self):
        """REQ-S08-17：后台生成结果迟到时，来源分镜已变化则不采用（镜头签名或来源证据不符都拒）。"""
        with tempfile.TemporaryDirectory() as td:
            proj, src, episode = _register_project(td)
            shot = episode['shots'][0]
            generated = Path(td) / 'generated.png'
            generated.write_bytes(png())
            item = {'shot_id': 'SH001', 'shot_signature': fingerprint(shot),
                    'source_evidence': evidence.source_evidence(src, episode, shot)}
            # 生成期间镜头本身被改（签名变）→ 不采用。
            episode['shots'][0]['title'] = '改过了'
            save(src, episode)
            with self.assertRaises(ValueError):
                register(src, item, generated)
            self.assertNotIn('frame_evidence', read(src)['shots'][0])
            self.assertTrue(generated.is_file())                # 生成图保留，未丢失
        with tempfile.TemporaryDirectory() as td:
            proj, src, episode = _register_project(td)
            shot = episode['shots'][0]
            generated = Path(td) / 'generated.png'
            generated.write_bytes(png())
            item = {'shot_id': 'SH001', 'shot_signature': fingerprint(shot),
                    'source_evidence': evidence.source_evidence(src, episode, shot)}
            # 签名没变、但来源内容（整集／提示词／参考资产）变了 → 同样不采用。
            episode['title'] = '换稿了'
            save(src, episode)
            with self.assertRaisesRegex(ValueError, '分镜或参考资产'):
                register(src, item, generated)
            self.assertNotIn('frame_evidence', read(src)['shots'][0])

    def test_req_s08_18_stage_config_is_the_only_model_source(self):
        """REQ-S08-18：首帧模型以阶段配置 keyframe.model 为唯一来源；可选模型始终含两个原生模型。"""
        from keyframe_model_service import current_model, production_choices
        choices = [value for value, _label in production_choices('unused-project')]
        self.assertIn(LOCAL_KEYFRAME_MODEL, choices)
        self.assertIn(SEEDREAM_KEYFRAME_MODEL, choices)
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'keyframe', model=SEEDREAM_KEYFRAME_MODEL)
            self.assertEqual(current_model(td), SEEDREAM_KEYFRAME_MODEL)
            stage_config.put(td, 'keyframe', model=LOCAL_KEYFRAME_MODEL)
            self.assertEqual(current_model(td), LOCAL_KEYFRAME_MODEL)

    def test_req_s08_19_paid_generation_needs_confirmation_and_same_shot_serial(self):
        """REQ-S08-19：有付费生成动作、生成须用户确认（模板第 3 步）；并行按镜头、同一镜头不并发。"""
        template = skill_templates.load_template('keyframe')
        self.assertEqual(template.steps[2].action, 'generate_keyframes')
        self.assertTrue(template.steps[2].needs_confirmation)
        self.assertTrue(template.steps[2].question)
        registry = skill_registry.default_registry()
        paid = {skill.name for skill in registry.getByStage('keyframe') if skill.paid}
        self.assertTrue({'firstframe-batch', 'firstframe-auto-fill', 'firstframe-retry'} <= paid)
        self.assertEqual(stage_parallel.unit('keyframe'), stage_parallel.SHOT)
        self.assertFalse(stage_parallel.serial_within('keyframe'))
        governor = stage_parallel.Governor(clock=lambda: 0.0)
        first = governor.acquire('keyframe', resource='SH001')
        self.assertTrue(first['ok'])
        self.assertTrue(governor.acquire('keyframe', resource='SH002')['ok'])
        self.assertFalse(governor.acquire('keyframe', resource='SH001')['ok'])

    def test_req_s08_20_evidence_records_image_facts_and_source_versions(self):
        """REQ-S08-20：每张首帧记录图片事实（尺寸、哈希）＋来源分镜、提示词、参考资产的版本哈希。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'episode.json'
            shot = {'id': 'SH001', 'frame': 'frames/SH001.png', 'frame_prompt': '街道',
                    'characters': ['CHAR_001']}
            episode = {'episode_id': 'EP001', 'shots': [shot]}
            save(source, episode)
            image = root / 'frames' / 'SH001.png'
            image.parent.mkdir()
            raw = png()
            image.write_bytes(raw)
            save(root / 'assets.json', {'CHAR_001': {'name': '主角', 'image': 'reference.png'}})
            (root / 'reference.png').write_bytes(png(color='blue'))
            record = evidence.make_evidence(source, episode, shot, image, expected_size=(16, 9))
            self.assertEqual(record['version'], 1)
            self.assertEqual(record['image']['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual((record['image']['width'], record['image']['height']), (16, 9))
            src = record['source']
            self.assertEqual(src['shot_id'], 'SH001')
            self.assertTrue(src['storyboard_sha256'])
            self.assertTrue(src['prompt_sha256'])
            ref = next(row for row in src['references'] if row['id'] == 'CHAR_001')
            self.assertEqual(ref['sha256'],
                             hashlib.sha256((root / 'reference.png').read_bytes()).hexdigest())
            self.assertTrue(ref['metadata'])
            # 提示词一变，来源版本哈希跟着变（说明它记录的是提示词版本）。
            changed = dict(shot, frame_prompt='雨夜街道')
            self.assertNotEqual(evidence.source_evidence(source, episode, changed)['prompt_sha256'],
                                src['prompt_sha256'])

    def test_req_s08_21_review_reasons_are_distinct_and_never_silently_pass(self):
        """REQ-S08-21：缺证据／外部替换（mtime 相同）／来源变化／缺资产版本，原因分明且都要重新导入复核。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'episode.json'
            shot = {'id': 'SH001', 'frame': 'frames/SH001.png', 'frame_prompt': '街道'}
            episode = {'episode_id': 'EP001', 'shots': [shot]}
            save(source, episode)
            image = _evidence_image(root, source, episode, shot)

            # 缺证据（旧首帧）。
            legacy = dict(shot)
            legacy.pop('frame_evidence', None)
            problem = evidence.frame_problem(source, episode, legacy, image)
            self.assertIn('缺少来源', problem)
            self.assertIn('重新', problem)
            # 被外部替换：即使 mtime 相同也要复核。
            stamp = image.stat()
            image.write_bytes(png(color='blue'))
            os.utime(image, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            problem = evidence.frame_problem(source, episode, shot, image)
            self.assertIn('外部替换', problem)
            self.assertIn('重新', problem)
            image.write_bytes(png())
            # 来源分镜／提示词变化。
            shot['frame_prompt'] = '雨夜街道'
            problem = evidence.frame_problem(source, episode, shot, image)
            self.assertIn('来源', problem)
            self.assertIn('重新', problem)
            shot['frame_prompt'] = '街道'
            # 参考资产缺可核对版本。
            facts = evidence.image_facts(image)
            shot['frame_evidence'] = {'version': 1, 'image': facts, 'expected_size': None,
                                      'aspect_ratio': '',
                                      'source': {'storyboard_sha256': 'x', 'shot_id': 'SH001',
                                                 'prompt_sha256': 'y',
                                                 'references': [{'id': 'CHAR_001',
                                                                 'metadata': 'm', 'sha256': None}]}}
            problem = evidence.frame_problem(source, episode, shot, image)
            self.assertIn('缺少可核对版本', problem)
            self.assertIn('重新', problem)

    def test_req_s08_22_one_shots_asset_change_only_invalidates_its_own_frame(self):
        """REQ-S08-22：一个镜头的参考资产变化只影响引用它的镜头，其他镜头的首帧不失效。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'episode.json'
            first = {'id': 'SH001', 'frame': 'frames/SH001.png', 'frame_prompt': '一',
                     'characters': ['CHAR_001']}
            second = {'id': 'SH002', 'frame': 'frames/SH002.png', 'frame_prompt': '二'}
            episode = {'episode_id': 'EP001', 'shots': [first, second]}
            save(source, episode)
            save(root / 'assets.json', {'CHAR_001': {'name': '主角', 'image': 'reference.png'}})
            reference = root / 'reference.png'
            reference.write_bytes(png())
            _evidence_image(root, source, episode, first)
            _evidence_image(root, source, episode, second)
            self.assertEqual(evidence.frame_problem(source, episode, first,
                                                    root / first['frame']), '')
            self.assertEqual(evidence.frame_problem(source, episode, second,
                                                    root / second['frame']), '')
            # 只改被 SH001 引用的资产：SH001 要复核，SH002 不受影响。
            reference.write_bytes(png(color='blue'))
            self.assertIn('来源', evidence.frame_problem(source, episode, first,
                                                        root / first['frame']))
            self.assertEqual(evidence.frame_problem(source, episode, second,
                                                    root / second['frame']), '')

    def test_req_s08_23_delete_restore_replace_go_through_recycle(self):
        """REQ-S08-23：删除走回收站可恢复；替换把旧版本放回收站；删除／恢复／替换可回滚。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            image = base / 'frames/SH001.png'
            image.parent.mkdir()
            image.write_bytes(b'png')
            source = base / 'episode.json'
            episode = {'shots': [{'id': 'SH001', 'frame': 'frames/SH001.png'}]}
            save(source, episode)
            shot = episode['shots'][0]
            self.assertTrue(delete_stage_keyframe(base, source, episode, shot).ok)
            self.assertFalse(image.exists())
            self.assertTrue(read(source)['shots'][0]['frame_deleted'])
            self.assertTrue(any(path.name == 'SH001.png'
                                for path in (base / '工作流任务/回收站').rglob('*')
                                if path.is_file()))
            self.assertTrue(restore_stage_keyframe(base, source, episode, shot).ok)
            self.assertTrue(image.is_file())
            self.assertNotIn('frame_deleted', read(source)['shots'][0])
            self.assertTrue(replace_stage_keyframe(base, source, episode,
                                                   episode['shots'][0], png()).ok)
            self.assertEqual(image.read_bytes(), png())
            self.assertTrue(any(path.name == 'SH001.png'
                                for path in (base / '工作流任务/回收站').rglob('*')
                                if path.is_file()))

    def test_req_s08_23_failed_delete_rolls_back_frame_and_state(self):
        """REQ-S08-23：删除时保存分镜状态失败，回滚到原首帧和原状态。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            image = base / 'frames/SH001.png'
            image.parent.mkdir()
            image.write_bytes(b'png')
            source = base / 'episode.json'
            episode = {'shots': [{'id': 'SH001', 'frame': 'frames/SH001.png'}]}
            save(source, episode)
            shot = episode['shots'][0]
            with patch('stage_execution_service.publish_keyframe_episode',
                       side_effect=OSError('磁盘不可用')):
                result = delete_stage_keyframe(base, source, episode, shot)
            self.assertFalse(result.ok)
            self.assertTrue(image.is_file())
            self.assertNotIn('frame_deleted', shot)

    def test_req_s08_23_failed_replace_rolls_back_previous_frame(self):
        """REQ-S08-23：替换时保存分镜状态失败，回滚到替换前的首帧。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            image = base / 'frames/SH001.png'
            image.parent.mkdir()
            image.write_bytes(b'png')
            source = base / 'episode.json'
            episode = {'shots': [{'id': 'SH001', 'frame': 'frames/SH001.png'}]}
            save(source, episode)
            shot = episode['shots'][0]
            with patch('stage_execution_service.publish_keyframe_episode',
                       side_effect=OSError('磁盘不可用')):
                result = replace_stage_keyframe(base, source, episode, shot, png())
            self.assertFalse(result.ok)
            self.assertEqual(image.read_bytes(), b'png')

    def test_req_s08_24_frames_dir_is_numbered_and_legacy_is_read_only(self):
        """REQ-S08-24：写入 08首帧管理/；旧目录 07首帧管理 只读兼容、不回写。"""
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_path_service.write_dir(td, 'keyframe'),
                             Path(td) / '08首帧管理')
            dirs = stage_path_service.read_dirs(td, 'keyframe')
            self.assertEqual(dirs[0], Path(td) / '08首帧管理')
            self.assertIn(Path(td) / '07首帧管理', dirs)
            self.assertNotIn('07首帧管理', str(stage_path_service.write_dir(td, 'keyframe')))
            # 旧目录有成果时只读回退到它，写入目录仍是新编号目录。
            legacy = Path(td) / '07首帧管理'
            legacy.mkdir()
            (legacy / 'old.png').write_bytes(b'x')
            self.assertEqual(stage_path_service.existing_dir(td, 'keyframe'), legacy)
            self.assertEqual(stage_path_service.write_dir(td, 'keyframe'),
                             Path(td) / '08首帧管理')

    def test_req_s08_30_completion_needs_frames_ready_and_a_started_stage(self):
        """REQ-S08-30：阶段完成＝frames_ready 通过且本阶段已开始；模型文字／界面提示不算证据。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'adopted.json'
            # 从没开始过的阶段：既没有首帧、也没跑过 → 门禁放行，但不算完成。
            blank = {'id': 'SH001'}
            with patch.object(stage_parallel, '_adopted',
                              return_value=[(source, [blank])]), \
                    patch.object(stage_parallel, 'has_run', return_value=False), \
                    patch('storyboard_paths.media_root', return_value=root):
                result = stage_parallel.frames_ready(root)
                self.assertTrue(result['ok'])
                self.assertFalse(result['started'])
                self.assertFalse(stage_completion_service.completion_evidence(root, 'keyframe')[0])
            # 已开始、每个镜头都有通过证据校验的首帧 → 完成。
            shot = {'id': 'SH001', 'frame': 'good.png'}
            episode = {'shots': [shot]}
            image = _evidence_image(root, source, episode, shot)

            def check(started):
                with patch.object(stage_parallel, '_adopted',
                                  return_value=[(source, [shot])]), \
                        patch.object(stage_parallel, 'has_run', return_value=started), \
                        patch('storyboard_paths.media_root', return_value=root):
                    return (stage_parallel.frames_ready(root),
                            stage_completion_service.completion_evidence(root, 'keyframe')[0])

            result, complete = check(True)
            self.assertTrue(result['ok'])
            self.assertTrue(result['started'])
            self.assertTrue(complete)
            # 界面／文字不是证据：文件坏了就一点也不算完成。
            image.write_bytes(b'\x89PNG\r\n\x1a\ninvalid')
            result, complete = check(True)
            self.assertFalse(result['ok'])
            self.assertFalse(complete)

    def test_req_s08_31_sg04_blocks_previs_when_keyframe_frames_are_bad(self):
        """REQ-S08-31：S08→S09（S09 白模预演）门禁 SG-04 在本阶段已开始且缺帧／校验不过时阻塞并说明原因。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'adopted.json'
            shot = {'id': 'SH001'}
            with patch.object(stage_parallel, '_adopted', return_value=[(source, [shot])]), \
                    patch.object(stage_parallel, 'has_run', return_value=True), \
                    patch('storyboard_paths.media_root', return_value=root):
                result = stage_parallel.evaluate(root, 'previs')
                self.assertEqual(result['id'], 'SG-04')
                self.assertFalse(result['ok'])
                self.assertIn('未配置首帧路径', ' '.join(result['problems']))
                self.assertEqual(stage_parallel.blocked_stages(root, 'previs'), ('keyframe',))
                self.assertIn('首帧管理', stage_parallel.blocked_text(result))
            # 空项目不拦。
            self.assertTrue(stage_parallel.evaluate(root, 'previs')['ok'])

    def test_req_s08_32_video_skips_shots_without_a_frame_and_points_to_keyframe(self):
        """REQ-S08-32：视频侧遇到缺首帧的镜头拒绝／跳过，给出「尚无首帧」原因并指向首帧管理页。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            frames = root / 'frames'
            frames.mkdir()
            (frames / 'SH001.png').write_bytes(b'x')
            source = root / 'episode' / 'episode.json'
            source.parent.mkdir()
            shots = [{'id': 'SH001', 'frame': 'frames/SH001.png', 'duration': 5, 'video_prompt': '一'},
                     {'id': 'SH002', 'frame': 'frames/SH002.png', 'duration': 5, 'video_prompt': '二'}]
            source.write_text(json.dumps({'episode_id': 'EP001', 'shots': shots},
                                         ensure_ascii=False), encoding='utf-8')

            class FakeStudio(local_video.LocalStudio):
                def __init__(self):
                    self.root = root
                    self.episode = json.loads(source.read_text(encoding='utf-8'))
                    self.cfg = {}

                def state(self):
                    return {'shots': {}}

                def frame(self, shot, required=True):
                    return (root / shot.get('frame', 'frames/none.png')).resolve()

            submit, _poll, skipped = local_video.auto_plan(root, source, FakeStudio())
            self.assertEqual(submit, ['SH001'])
            self.assertEqual([sid for sid, _reason in skipped], ['SH002'])
            self.assertIn('尚无首帧', skipped[0][1])
            self.assertIn(pet_bus.stage_step('keyframe'), skipped[0][1])   # 指向第08步首帧管理


if __name__ == '__main__':
    unittest.main(verbosity=2)
