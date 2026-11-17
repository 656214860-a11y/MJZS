# -*- coding: utf-8 -*-
"""REQ-S13 测试锚定：质检与交付阶段此前标 ✅ 却无测试锚定的 20 条需求。

覆盖 REQ-S13-02/03/10/12/13/14/20/21/22/23/30/31/33/34/35/36/40/41/42/43。
这些编号原登记在 `维护记录/需求锚定基线.json` 的 `untested_done`，本文件把锚点落在
`stage_completion_service`／`usage_overview`／`delivery_import_service` 的真实函数与常量
上，未 mock 被测事实、未改产品代码；需要落盘时一律在 `tempfile.TemporaryDirectory()`
隔离目录内进行（不打开任何真实用户项目）。
"""
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from infra import model_diagnostics
import pet_llm
import stage_completion_service
import usage_overview as uo
from agent.core import file_hash, read, save

ROOT = Path(__file__).resolve().parents[1]


def _event(folder, usage, stage='script', ok=True, day='2026-10-14'):
    stamp = datetime.strptime(day + ' 10:00:00', '%Y-%m-%d %H:%M:%S')
    return model_diagnostics.record(
        folder, {'ok': ok, 'status': 200 if ok else 500, 'model': 'm-anchor',
                 'usage': usage, 'text': 'SECRET 正文'}, {'stage': stage}, at=stamp)


class DeliveryRequirementAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'storyboard' / 'episode.json'
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S01'}]})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(self.source), 'adopted_storyboards': [str(self.source)]})
        save(self.root / 'config.json', {'ffprobe': 'test-probe'})

    # ---- 共用夹具 -------------------------------------------------------
    def artifact(self, name='MASTER.mp4'):
        folder = stage_completion_service.media_output_folders(self.root, 'delivery')[0][0]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(b'fixture-media')
        return path

    def prepare(self, path, streams=None):
        result = {'format': {'duration': '2.5'},
                  'streams': streams or [{'codec_type': 'video', 'width': 1280, 'height': 720},
                                         {'codec_type': 'audio'}]}
        with patch('agent.media.probe', return_value=result):
            return stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])

    def confirm(self, prepared):
        return stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)

    def commercial_evidence(self):
        """一份覆盖成片与剧本、字段齐全的合法商用资料；供逐字段反例复用。"""
        path = self.artifact()
        self.confirm(self.prepare(path))
        evidence = stage_completion_service.commercial_template(self.root)
        proof = self.root / 'authorization.txt'
        proof.write_text('test-only authorization fixture', encoding='utf-8')
        evidence.update(inventory_reviewer='test reviewer', inventory_complete=True)
        for key, group in evidence['categories'].items():
            group['items'] = []
            group['unused_reason'] = 'test fixture does not use this category'
            if key in ('script', 'video'):
                media = self.source if key == 'script' else path
                group['items'] = [{'path': media.relative_to(self.root).as_posix(),
                    'sha256': file_hash(media), 'source': 'test original',
                    'rights_holder': 'test owner', 'license': 'test permission',
                    'commercial_allowed': True, 'derivative_allowed': True, 'obligations_fulfilled': True,
                    'authorization': {'path': 'authorization.txt', 'sha256': file_hash(proof)}}]
        for review in evidence['content_review'].values():
            review.update(status='cleared', reviewer='test reviewer', evidence='test manual review')
        return evidence, proof, path

    # ---- 输入与依赖 -----------------------------------------------------
    def test_req_s13_02_scope_binds_adopted_storyboard_with_shots(self):
        """REQ-S13-02：核验绑定当前已采用分镜；未选定或无镜头报错、不产出；切集／改稿使旧确认失效。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, '选择当前已采用的分镜'):
                stage_completion_service.media_scope(root)
            source = root / 'storyboard' / 'episode.json'
            save(source, {'id': 'EP01', 'shots': []})
            save(root / 'ui_settings.json', {'frame_json': str(source), 'adopted_storyboards': [str(source)]})
            with self.assertRaisesRegex(ValueError, '没有可核验的镜头'):
                stage_completion_service.media_scope(root)
        scope = stage_completion_service.media_scope(self.root)
        self.assertEqual(scope['project'], str(self.root))
        self.assertEqual(scope['source'], 'storyboard/episode.json')
        self.confirm(self.prepare(self.artifact()))
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})   # 改分镜
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    def test_req_s13_03_missing_ffprobe_errors_not_suffix_passthrough(self):
        """REQ-S13-03：缺 FFprobe（config.json 与随附工具都没有）直接报错，不退化按扩展名放行。"""
        save(self.root / 'config.json', {})
        path = self.artifact()
        with patch('contract.platform_tools.tool_path', return_value=None):
            with self.assertRaisesRegex(ValueError, 'FFprobe'):
                stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    # ---- 导入与校验流程 -------------------------------------------------
    def test_req_s13_10_delivery_page_buttons_match_the_manual_flow(self):
        """REQ-S13-10：交付页按钮与「导入成片→校验确认→生成待填→核验商用」流程一致。"""
        source = (ROOT / 'desktop_media_pages.py').read_text(encoding='utf-8')
        for label in ('导入剪映最终成片', '校验并确认本阶段成果',
                      '生成商用待填资料', '核验商用交付资料'):
            with self.subTest(label=label):
                self.assertIn(label, source)

    def test_req_s13_12_probe_freezes_pending_review_and_never_autocompletes(self):
        """REQ-S13-12：真实视频流＋有限正时长；校验期间改文件失败；结果冻结 pending_review，不自动完成。"""
        path = self.artifact()
        prepared = self.prepare(path)
        self.assertEqual(prepared['status'], 'pending_review')
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        bad_cases = ({'format': {'duration': 1}, 'streams': [{'codec_type': 'audio'}]},
                     {'format': {'duration': 0}, 'streams': [{'codec_type': 'video', 'width': 10, 'height': 10}]})
        for bad in bad_cases:
            with self.subTest(bad=bad), patch('agent.media.probe', return_value=bad):
                with self.assertRaises(ValueError):
                    stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])

        def probe(*_):
            path.write_bytes(b'replacement')
            return {'format': {'duration': 1}, 'streams': [{'codec_type': 'video', 'width': 10, 'height': 10},
                                                           {'codec_type': 'audio'}]}
        with patch('agent.media.probe', side_effect=probe), \
                self.assertRaisesRegex(ValueError, '校验期间'):
            stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])

    def test_req_s13_13_output_must_be_nonempty_media_in_delivery_dir(self):
        """REQ-S13-13：成果须在本项目交付目录内且非空；字幕／压缩包不能替代媒体。"""
        folder = stage_completion_service.media_output_folders(self.root, 'delivery')[0][0]
        folder.mkdir(parents=True, exist_ok=True)
        for name in ('subtitle.srt', 'archive.zip', 'empty.mp4'):
            path = folder / name
            path.write_bytes(b'' if name == 'empty.mp4' else b'x')
            with self.subTest(name=name), \
                    patch('agent.media.probe', return_value={'format': {'duration': 1}, 'streams': [
                        {'codec_type': 'video', 'width': 10, 'height': 10}]}):
                with self.assertRaises(ValueError):
                    stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'MASTER.mp4'
            external.write_bytes(b'outside-media')
            with self.assertRaises(ValueError):
                stage_completion_service.prepare_media_completion(self.root, 'delivery', [external])

    def test_req_s13_14_only_explicit_confirmation_writes_complete_and_pending(self):
        """REQ-S13-14：只有显式确认才写 status=complete/reviewed=true 与 commercial_status=pending；确认前重核冻结版本。"""
        path = self.artifact()
        prepared = self.prepare(path)
        path.write_bytes(b'changed-after-probe')
        with self.assertRaises(ValueError):
            self.confirm(prepared)
        path.write_bytes(b'fixture-media')
        target = self.confirm(prepared)
        data = read(target)
        self.assertEqual(data['status'], 'complete')
        self.assertIs(data['reviewed'], True)
        self.assertEqual(data['commercial_status'], 'pending')

    # ---- 产出与完成 -----------------------------------------------------
    def test_req_s13_20_completion_is_the_frozen_confirmation_manifest(self):
        """REQ-S13-20：阶段完成＝成果确认清单存在且 schema／阶段／范围一致、complete＋reviewed、大小与哈希相符。"""
        path = self.artifact()
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        prepared = self.prepare(path)
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        target = self.confirm(prepared)
        expected = stage_completion_service.media_manifest_path(
            self.root, 'delivery', stage_completion_service.media_scope(self.root))
        self.assertEqual(target, expected)
        self.assertEqual(expected.parent.name, '成果确认')
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        data = read(expected)
        self.assertEqual(data['schema'], 1)
        self.assertEqual(data['stage'], 'delivery')
        self.assertEqual(data['scope'], stage_completion_service.media_scope(self.root))
        tampered = dict(data, outputs=[dict(data['outputs'][0],
                                           size=data['outputs'][0]['size'] + 1)])
        save(expected, tampered)
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    def test_req_s13_21_media_or_storyboard_change_invalidates_completion(self):
        """REQ-S13-21：成片被替换或修改、分镜版本变化后，完成判定失效，须重新校验确认。"""
        path = self.artifact()
        self.confirm(self.prepare(path))
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        original = path.read_bytes()
        path.write_bytes(b'z' * len(original))
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        path.write_bytes(original)
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        second = self.root / 'storyboard' / 'episode2.json'
        save(second, {'id': 'EP02', 'shots': [{'id': 'S01'}]})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(second), 'adopted_storyboards': [str(second)]})
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    def test_req_s13_22_emit_verified_completion_gates_stage_completed(self):
        """REQ-S13-22：完成判定走 emit_verified_completion——核验通过才发 stage.completed。"""
        events = []
        emit = lambda *args, **kwargs: (events.append((args, kwargs)), {'ok': True})[1]
        ok, _detail, _emitted = stage_completion_service.emit_verified_completion(
            self.root, 'delivery', '模型说做完了', emit)
        self.assertFalse(ok)
        self.assertEqual(events, [])
        self.confirm(self.prepare(self.artifact()))
        ok, _detail, _emitted = stage_completion_service.emit_verified_completion(
            self.root, 'delivery', '完成', emit)
        self.assertTrue(ok)
        self.assertEqual([args[0] for args, _kwargs in events], ['stage.completed'])
        self.assertEqual(events[0][1]['stage'], 'delivery')

    def test_req_s13_23_completion_does_not_depend_on_commercial_evidence(self):
        """REQ-S13-23：完成判定不依赖商用资料；商用核验通过与否不影响阶段是否完成。"""
        self.confirm(self.prepare(self.artifact()))
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])
        self.assertFalse(stage_completion_service.commercial_delivery_status(self.root)[0])
        with self.assertRaises(ValueError):
            stage_completion_service.validate_commercial_evidence(self.root, {})
        self.assertTrue(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    # ---- 商用交付资料 ---------------------------------------------------
    def test_req_s13_30_commercial_template_requires_confirmation_and_refuses_overwrite(self):
        """REQ-S13-30：生成待填资料需先有已确认成果；待填文件已存在时拒绝覆盖。"""
        self.artifact()
        with self.assertRaises((OSError, ValueError)):
            stage_completion_service.create_commercial_template(self.root)
        pending = stage_completion_service.commercial_evidence_path(self.root).with_suffix('.pending.json')
        self.assertFalse(pending.exists())
        self.confirm(self.prepare(self.artifact()))
        target = stage_completion_service.create_commercial_template(self.root)
        self.assertTrue(target.is_file())
        self.assertIn('.commercial.pending.json', target.name)
        with self.assertRaisesRegex(ValueError, '已存在'):
            stage_completion_service.create_commercial_template(self.root)

    def test_req_s13_31_template_prefills_sources_without_granting_rights(self):
        """REQ-S13-31：待填资料预填剧本／成片与 edit_bundle 登记的镜头／参考／字体，授权字段留空，来源缺失或版本变化写警告。"""
        path = self.artifact()
        self.confirm(self.prepare(path))
        folder = path.parent
        source = folder / 'source.mp4'
        source.write_bytes(b'original shot source')
        font = folder / 'font.ttc'
        font.write_bytes(b'test-only font')
        save(folder / 'edit_bundle.json', {
            'master': path.name, 'master_sha256': file_hash(path),
            'manifest': [{'source': source.name, 'sha256': file_hash(source)},
                         {'source': source.name, 'sha256': 'stale-digest'},
                         {'sha256': file_hash(source)}],
            'fonts': [{'path': font.name, 'sha256': file_hash(font)}]})
        template = stage_completion_service.commercial_template(self.root)
        self.assertEqual(len(template['categories']['script']['items']), 1)
        self.assertEqual(len(template['categories']['video']['items']), 2)   # 成片＋镜头来源
        self.assertEqual(len(template['categories']['font']['items']), 1)
        for group in template['categories'].values():
            for item in group['items']:
                self.assertFalse(item['commercial_allowed'])
                self.assertFalse(item['derivative_allowed'])
                self.assertFalse(item['obligations_fulfilled'])
                self.assertEqual(item['rights_holder'], '')
                self.assertEqual(item['license'], '')
                self.assertEqual(item['authorization'], {'path': '', 'sha256': ''})
        warnings = template['inventory_warnings']
        self.assertTrue(any('来源版本已改变' in item for item in warnings))
        self.assertTrue(any('缺少路径' in item for item in warnings))

    def test_req_s13_33_every_item_needs_rights_and_a_frozen_authorization_file(self):
        """REQ-S13-33：每个素材条目须有来源／权利人／许可／可商用／可衍生／义务，并附本项目内路径＋SHA256 一致的授权文件。"""
        evidence, _proof, _path = self.commercial_evidence()
        self.assertTrue(stage_completion_service.validate_commercial_evidence(self.root, evidence))
        for field in ('source', 'rights_holder', 'license'):
            wrong = deepcopy(evidence)
            wrong['categories']['script']['items'][0][field] = ''
            with self.subTest(field=field), \
                    self.assertRaisesRegex(ValueError, '授权范围或履约记录不完整'):
                stage_completion_service.validate_commercial_evidence(self.root, wrong)
        for field in ('commercial_allowed', 'derivative_allowed', 'obligations_fulfilled'):
            wrong = deepcopy(evidence)
            wrong['categories']['script']['items'][0][field] = False
            with self.subTest(field=field), \
                    self.assertRaisesRegex(ValueError, '授权范围或履约记录不完整'):
                stage_completion_service.validate_commercial_evidence(self.root, wrong)
        for authorization in ({'path': '', 'sha256': ''},
                              {'path': '../outside.txt', 'sha256': 'deadbeef'}):
            wrong = deepcopy(evidence)
            wrong['categories']['script']['items'][0]['authorization'] = authorization
            with self.subTest(authorization=authorization):
                with self.assertRaises(ValueError):
                    stage_completion_service.validate_commercial_evidence(self.root, wrong)
        wrong = deepcopy(evidence)
        wrong['categories']['script']['items'][0]['authorization']['sha256'] = 'deadbeef'
        with self.assertRaisesRegex(ValueError, '摘要不一致'):
            stage_completion_service.validate_commercial_evidence(self.root, wrong)

    def test_req_s13_34_inventory_covers_actual_script_and_delivery(self):
        """REQ-S13-34：清单须覆盖当前分镜实际剧本来源与全部交付成片；覆盖不全即报错。"""
        script = self.root / 'original.md'
        script.write_text('original story', encoding='utf-8')
        board = read(self.source)
        board['source_script'] = 'original.md'
        save(self.source, board)
        evidence, _proof, path = self.commercial_evidence()
        with self.assertRaisesRegex(ValueError, '剧本授权清单'):
            stage_completion_service.validate_commercial_evidence(self.root, evidence)
        evidence['categories']['script']['items'][0].update(path='original.md', sha256=file_hash(script))
        self.assertTrue(stage_completion_service.validate_commercial_evidence(self.root, evidence))
        # 成片摘要须在视频类且与当前成片一致，否则覆盖不全即报错。
        missing_master = deepcopy(evidence)
        missing_master['categories']['video']['items'] = []
        with self.assertRaisesRegex(ValueError, '缺少素材'):
            stage_completion_service.validate_commercial_evidence(self.root, missing_master)
        other = self.root / 'other.mp4'
        other.write_bytes(b'other-media')
        covered_elsewhere = deepcopy(evidence)
        covered_elsewhere['categories']['video']['items'] = [
            dict(evidence['categories']['script']['items'][0],
                 path='other.mp4', sha256=file_hash(other))]
        with self.assertRaisesRegex(ValueError, '未覆盖实际交付成片'):
            stage_completion_service.validate_commercial_evidence(self.root, covered_elsewhere)

    def test_req_s13_34_inventory_covers_shot_reference_font_versions(self):
        """REQ-S13-34：edit_bundle 登记的镜头来源、参考来源、字体版本也须被清单覆盖，覆盖不全即报错。"""
        evidence, proof, path = self.commercial_evidence()
        output = self.root / evidence['categories']['video']['items'][0]['path']
        shot = self.root / 'shot.mp4'
        shot.write_bytes(b'original shot source')
        save(output.parent / 'edit_bundle.json', {
            'master': output.name, 'master_sha256': file_hash(output),
            'manifest': [{'shot': 'S01', 'version': 1, 'sha256': file_hash(shot)}]})
        with self.assertRaisesRegex(ValueError, '镜头来源'):
            stage_completion_service.validate_commercial_evidence(self.root, evidence)
        item = dict(evidence['categories']['video']['items'][0], path='shot.mp4', sha256=file_hash(shot))
        evidence['categories']['video']['items'].append(item)
        self.assertTrue(stage_completion_service.validate_commercial_evidence(self.root, evidence))
        reference = output.parent / 'reference.png'
        reference.write_bytes(b'test-reference')
        bundle = read(output.parent / 'edit_bundle.json')
        bundle['references'] = [{'path': 'reference.png', 'sha256': file_hash(reference)}]
        save(output.parent / 'edit_bundle.json', bundle)
        with self.assertRaisesRegex(ValueError, '参考授权'):
            stage_completion_service.validate_commercial_evidence(self.root, evidence)
        evidence['categories']['reference']['items'] = [
            dict(item, path=reference.relative_to(self.root).as_posix(), sha256=file_hash(reference))]
        self.assertTrue(stage_completion_service.validate_commercial_evidence(self.root, evidence))
        font = output.parent / 'font.ttc'
        font.write_bytes(b'test-only font')
        bundle = read(output.parent / 'edit_bundle.json')
        bundle['fonts'] = [{'path': 'font.ttc', 'sha256': file_hash(font)}]
        save(output.parent / 'edit_bundle.json', bundle)
        with self.assertRaisesRegex(ValueError, '字体授权'):
            stage_completion_service.validate_commercial_evidence(self.root, evidence)
        evidence['categories']['font']['items'] = [
            dict(item, path=font.relative_to(self.root).as_posix(), sha256=file_hash(font))]
        self.assertTrue(stage_completion_service.validate_commercial_evidence(self.root, evidence))

    def test_req_s13_35_content_review_and_reviewer_confirmation(self):
        """REQ-S13-35：侵权／NSFW／敏感三项须各为 cleared 且有审核人和证据；审核人须确认清单覆盖全部采用素材。"""
        evidence, _proof, _path = self.commercial_evidence()
        for key in ('infringement', 'nsfw', 'sensitive'):
            for field in ('status', 'reviewer', 'evidence'):
                wrong = deepcopy(evidence)
                wrong['content_review'][key][field] = 'pending' if field == 'status' else ''
                with self.subTest(key=key, field=field), \
                        self.assertRaisesRegex(ValueError, '内容风险未完成审核'):
                    stage_completion_service.validate_commercial_evidence(self.root, wrong)
        for field, value in (('inventory_complete', False), ('inventory_reviewer', '')):
            wrong = deepcopy(evidence)
            wrong[field] = value
            with self.subTest(field=field), \
                    self.assertRaisesRegex(ValueError, '需由审核人确认清单覆盖'):
                stage_completion_service.validate_commercial_evidence(self.root, wrong)

    def test_req_s13_36_commercial_evidence_binds_master_and_storyboard(self):
        """REQ-S13-36：商用资料绑定成片摘要与分镜版本，成片／分镜变化后须重新审查；结论只据人工记录。"""
        self.confirm(self.prepare(self.artifact()))
        scope = stage_completion_service.media_scope(self.root)
        with self.assertRaisesRegex(ValueError, '不属于当前采用分镜版本'):
            stage_completion_service.validate_commercial_evidence(
                self.root, {'schema': 1, 'scope': {'project': 'other'}, 'outputs': []})
        with self.assertRaisesRegex(ValueError, '对应成片已改变'):
            stage_completion_service.validate_commercial_evidence(
                self.root, {'schema': 1, 'scope': scope, 'outputs': []})
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})
        with self.assertRaises(ValueError):
            stage_completion_service.validate_commercial_evidence(
                self.root, {'schema': 1, 'scope': scope, 'outputs': []})
        evidence, _proof, _path = self.commercial_evidence()
        stage_completion_service.confirm_commercial_evidence(self.root, evidence)
        ok, text = stage_completion_service.commercial_delivery_status(self.root)
        self.assertTrue(ok)
        self.assertIn('依据人工', text)

    # ---- 用量与成本 -----------------------------------------------------
    def test_req_s13_40_usage_is_unknown_not_zero_and_blocked_not_counted(self):
        """REQ-S13-40：只读汇总已落盘事件；无用量记未知不记 0；发送前被拦截的不计远端调用。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / 'logs'
            _event(logs, {})
            _event(logs, {'total_tokens': 7})
            model_diagnostics.record(
                logs, {'ok': False, 'status': 0, 'model': 'm-anchor', 'usage': {}, 'text': 'x'},
                {'stage': 'script', 'not_submitted': True})
            summary = uo.summarize(root)
            self.assertEqual(summary['total']['calls'], 2)
            self.assertEqual(summary['total']['unknown_usage'], 1)
            self.assertEqual(summary['total']['total_tokens'], 7)
            self.assertEqual(summary['not_submitted'], 1)

    def test_req_s13_41_denominator_uses_confirmed_delivery_only(self):
        """REQ-S13-41：成本分母只取已确认且内容未变的成片时长；重复或不在交付目录报错；无证据只能手工秒数并标明未绑定。"""
        path = self.artifact()
        self.confirm(self.prepare(path))
        result = uo.delivery_duration(self.root, [str(path)])
        self.assertEqual(result['duration_seconds'], 2.5)
        for bad in ([], [str(path), str(path)], [str(self.root / 'outside.mp4')]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                uo.delivery_duration(self.root, bad)
        save(self.root / 'cost_profile.json', {
            'duration_seconds': 30,
            'price_table': {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'},
            'overheads': {'gpu': 0, 'storage': 0, 'bandwidth': 0}})
        self.assertIn('尚未绑定交付证据', uo.report_text(uo.summarize(self.root)))

    def test_req_s13_41_one_export_per_adopted_storyboard(self):
        """REQ-S13-41：每份采用分镜只计一个导出，同一集的多个导出不能重复计入时长。"""
        first = self.artifact('first.mp4')
        alternate = self.artifact('alternate.mp4')
        prepared = self.prepare(first)
        prepared['outputs'].extend(self.prepare(alternate)['outputs'])
        self.confirm(prepared)
        with self.assertRaisesRegex(ValueError, '多个导出'):
            uo.delivery_duration(self.root, [str(first), str(alternate)])

    def test_req_s13_42_missing_cost_items_stay_separate_and_never_zero_filled(self):
        """REQ-S13-42：GPU／存储／带宽与未关联台账的 Comfy 任务单列，总成本只在录入项齐全时给出，绝不补零。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = pet_llm.RequestLedger(root)
            ledger.settle('fixture', kind='seconds', amount=10)
            ledger.save()
            table = {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'}
            cost = uo.cost_per_minute(root, 60, table)
            self.assertEqual(cost['known_per_minute'], 2)
            self.assertIsNone(cost['total_per_minute'])
            self.assertEqual(set(cost['missing_overheads']), {'gpu', 'storage', 'bandwidth'})
            self.assertEqual(cost['basis'], 'recorded_usage_estimate_not_supplier_invoice')
            save(root / 'workflows' / 'comfy_x.json', {'state': 'downloaded', 'cost_request_id': 'missing'})
            cost = uo.cost_per_minute(root, 60, table, dict(gpu=0, storage=1, bandwidth=0))
            self.assertIsNone(cost['total_per_minute'])
            self.assertEqual(cost['untracked_comfy'], ['comfy_x.json'])

    def test_req_s13_43_human_cost_and_time_are_separate_and_unknown_when_absent(self):
        """REQ-S13-43：人工费用与人工耗时单列，缺失显示未知；含人工全成本仅在其余项齐全且人工金额已填时给出。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ledger = pet_llm.RequestLedger(root)
            ledger.settle('fixture', kind='seconds', amount=10)
            ledger.save()
            table = {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'}
            cost = uo.cost_per_minute(root, 60, table, dict(gpu=0, storage=0, bandwidth=0))
            self.assertIsNone(cost['human_amount'])
            self.assertIsNone(cost['human_per_minute'])
            self.assertIsNone(cost['human_minutes'])
            self.assertIsNone(cost['including_human_per_minute'])
            cost = uo.cost_per_minute(root, 60, table, dict(gpu=0, storage=0, bandwidth=0, human=2),
                                      human_minutes=15)
            self.assertEqual(cost['human_per_minute'], 2)
            self.assertEqual(cost['human_minutes'], 15)
            self.assertEqual(cost['including_human_per_minute'], 4)

    def test_req_s13_27_edit_completion_reads_delivery_export_folder(self):
        """REQ-S13-27：后期剪辑完成核验读取交付阶段归属的 13质检交付/导出成片。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folders, suffixes = stage_completion_service.media_output_folders(root, 'edit')
            delivery_folder = next(folder for folder in folders if folder.name == '导出成片')
            self.assertIn('.mp4', suffixes)
            target = delivery_folder / 'MASTER.mp4'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'fixture-media')
            self.assertEqual(stage_completion_service._media_path(root, 'edit', target), target.resolve())
            target.unlink()
            with self.assertRaisesRegex(ValueError, '有效媒体文件'):
                stage_completion_service._media_path(root, 'edit', target)


if __name__ == '__main__':
    unittest.main()
