# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from project_stages import audio
from stage_completion_service import (completion_evidence, media_output_folders, media_scope,
    prepare_media_completion, confirm_media_completion, media_manifest_path)
from agent.core import save, read


class CompletionEvidenceTests(unittest.TestCase):
    def test_missing_project_keeps_lightweight_host_compatible(self):
        self.assertEqual(completion_evidence(None, 'keyframe'), (True, ''))

    def test_subtitle_alone_does_not_complete_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = audio(root); folder.mkdir(parents=True)
            (folder / 'line.srt').write_text('字幕', encoding='utf-8')
            self.assertFalse(completion_evidence(root, 'audio')[0])

    def test_video_uses_injected_desktop_adapter_callback(self):
        with tempfile.TemporaryDirectory() as td:
            ok, detail = completion_evidence(Path(td), 'video', lambda: ('digest', False))
            self.assertTrue(ok)
            self.assertIn('全部下载', detail)

    def test_media_output_folders_keeps_delivery_formats_separate(self):
        root = Path('project')
        folders, suffixes = media_output_folders(root, 'delivery')
        self.assertEqual(folders, (root / '13质检交付', root / '12质检交付'))
        self.assertEqual(suffixes, {'.mp4', '.mov', '.mkv'})


class MediaCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'storyboard' / 'episode.json'
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S01'}]})
        self.select(self.source)
        save(self.root / 'config.json', {'ffprobe': 'test-probe'})

    def select(self, source):
        save(self.root / 'ui_settings.json', {'frame_json': str(source), 'adopted_storyboards': [str(source)]})

    def artifact(self, stage, name=None):
        folder = media_output_folders(self.root, stage)[0][0]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (name or ('output.wav' if stage == 'audio' else 'output.mp4'))
        path.write_bytes(b'fixture-media')
        return path

    def prepare(self, stage, path):
        kind = 'audio' if stage == 'audio' else 'video'
        result = {'format': {'duration': '2.5'}, 'streams': [{'codec_type': kind, 'width': 1280, 'height': 720}]}
        with patch('agent.media.probe', return_value=result):
            return prepare_media_completion(self.root, stage, [path])

    def test_cost_uses_confirmed_delivery_duration_and_rejects_stale_evidence(self):
        from usage_overview import summarize, report_text
        from pet_llm import RequestLedger
        path = self.artifact('delivery')
        ledger = RequestLedger(self.root)
        ledger.settle('fixture', kind='seconds', amount=10); ledger.save()
        save(self.root / 'cost_profile.json', {'duration_seconds': 999,
            'delivery_outputs': [path.relative_to(self.root).as_posix()],
            'price_table': {'rates': {'seconds': 0.2}, 'version': 'fixture', 'currency': 'CNY'},
            'overheads': {'gpu': 0, 'storage': 0, 'bandwidth': 0}})
        self.assertIn('cost_error', summarize(self.root))
        confirm_media_completion(self.root, 'delivery', self.prepare('delivery', path))
        summary = summarize(self.root)
        self.assertEqual(summary['cost']['duration_seconds'], 2.5)
        self.assertEqual(summary['cost']['total_per_minute'], 48)
        self.assertIn('摘要与分镜版本已核验', report_text(summary))
        original = path.read_bytes()
        path.write_bytes(b'x' * len(original))
        self.assertIn('cost_error', summarize(self.root))
        path.write_bytes(original)
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'changed'}]})
        self.assertIn('cost_error', summarize(self.root))

    def test_delivery_cost_counts_episodes_once_not_export_formats(self):
        from usage_overview import delivery_duration
        first = self.artifact('delivery', 'first.mp4')
        alternate = self.artifact('delivery', 'alternate.mp4')
        prepared = self.prepare('delivery', first)
        prepared['outputs'].extend(self.prepare('delivery', alternate)['outputs'])
        confirm_media_completion(self.root, 'delivery', prepared)
        with self.assertRaisesRegex(ValueError, '多个导出'):
            delivery_duration(self.root, [str(first), str(alternate)])
        second_source = self.source.with_name('second.json')
        save(second_source, {'id': 'EP02', 'shots': [{'id': 'S01'}]})
        self.select(second_source)
        second = self.artifact('delivery', 'second.mp4')
        confirm_media_completion(self.root, 'delivery', self.prepare('delivery', second))
        save(self.root / 'ui_settings.json', {'adopted_storyboards': [str(self.source), str(second_source)]})
        result = delivery_duration(self.root, [str(first), str(second)])
        self.assertEqual(result['duration_seconds'], 5)
        self.assertEqual(len(result['outputs']), 2)
        for selected in ([], [str(first), str(first)], [str(self.root / 'outside.mp4')]):
            with self.assertRaises(ValueError): delivery_duration(self.root, selected)

    def test_each_stage_requires_explicit_review_of_validated_artifact(self):
        for stage in ('audio', 'edit', 'delivery'):
            with self.subTest(stage=stage):
                path = self.artifact(stage)
                self.assertFalse(completion_evidence(self.root, stage)[0])
                prepared = self.prepare(stage, path)
                self.assertEqual(prepared['status'], 'pending_review')
                self.assertFalse(completion_evidence(self.root, stage)[0])
                manifest = confirm_media_completion(self.root, stage, prepared)
                self.assertEqual(read(manifest)['scope'], media_scope(self.root))
                self.assertEqual(completion_evidence(self.root, stage), (True, ''))

    def test_req_s12_24_edit_completion_bundle_must_match_selected_master(self):
        """REQ-S12-24：剪辑成果须与同目录来源清单的成片摘要和质检结论一致，单镜文件不能冒充成片。"""
        from agent.core import file_hash
        folder = self.root / '13质检交付' / '导出成片' / 'EP01_20261021'
        folder.mkdir(parents=True)
        master = folder / 'MASTER.mp4'; master.write_bytes(b'registered-master')
        shots = [folder / 'S01.mp4', folder / 'S02.mp4']
        for index, shot in enumerate(shots, 1):
            shot.write_bytes(('single-shot-%d' % index).encode())
        bundle_path = folder / 'edit_bundle.json'
        bundle = {'master': master.name, 'master_sha256': file_hash(master), 'qc': {'errors': []}}
        save(bundle_path, bundle)

        prepared = self.prepare('edit', master)
        self.assertEqual(prepared.get('warnings', []), [])
        confirm_media_completion(self.root, 'edit', prepared)
        self.assertTrue(completion_evidence(self.root, 'edit')[0])
        for shot in shots:
            with self.subTest(shot=shot.name), self.assertRaisesRegex(ValueError, '不是该次剪辑登记的成片'):
                self.prepare('edit', shot)
        renamed = folder / 'final_cut.mp4'; renamed.write_bytes(master.read_bytes())
        self.prepare('edit', renamed)

        bundle['master_sha256'] = 'deadbeef'
        save(bundle_path, bundle)
        with self.assertRaisesRegex(ValueError, '不是该次剪辑登记的成片'):
            self.prepare('edit', master)
        bundle['master_sha256'] = file_hash(master)
        bundle['qc'] = {'errors': ['画面尺寸与规格不符']}
        save(bundle_path, bundle)
        with self.assertRaisesRegex(ValueError, '剪辑质检未通过'):
            self.prepare('edit', master)
        for malformed in ([], {'master': master.name}):
            save(bundle_path, malformed)
            with self.subTest(bundle=malformed), self.assertRaises(ValueError):
                self.prepare('edit', master)

        bundle_path.unlink()
        external = self.prepare('edit', master)
        self.assertTrue(any('无来源清单' in item for item in external.get('warnings', [])))
        confirm_media_completion(self.root, 'edit', external)

    def test_req_s12_24_edit_completion_rechecks_bundle_before_final_confirmation(self):
        """REQ-S12-24：冻结待审后来源清单或质检结论变化，最终确认和完成证据都必须失效。"""
        from agent.core import file_hash
        folder = self.root / '13质检交付' / '导出成片' / 'EP01_20261021'
        folder.mkdir(parents=True)
        master = folder / 'MASTER.mp4'; master.write_bytes(b'registered-master')
        bundle_path = folder / 'edit_bundle.json'
        bundle = {'master': master.name, 'master_sha256': file_hash(master), 'qc': {'errors': []}}
        save(bundle_path, bundle)
        prepared = self.prepare('edit', master)

        bundle['master_sha256'] = 'deadbeef'; save(bundle_path, bundle)
        with self.assertRaisesRegex(ValueError, '不是该次剪辑登记的成片'):
            confirm_media_completion(self.root, 'edit', prepared)
        self.assertFalse(completion_evidence(self.root, 'edit')[0])
        bundle['master_sha256'] = file_hash(master)
        bundle['qc'] = {'errors': ['成片时长不足']}; save(bundle_path, bundle)
        with self.assertRaisesRegex(ValueError, '剪辑质检未通过'):
            confirm_media_completion(self.root, 'edit', prepared)
        save(bundle_path, {'master': master.name})
        self.assertFalse(completion_evidence(self.root, 'edit')[0])

    def commercial_fixture(self):
        from agent.core import file_hash
        from stage_completion_service import commercial_template
        path = self.artifact('delivery')
        confirm_media_completion(self.root, 'delivery', self.prepare('delivery', path))
        evidence = commercial_template(self.root)
        proof = self.root / 'authorization.txt'; proof.write_text('test-only authorization fixture')
        evidence.update(inventory_reviewer='test reviewer', inventory_complete=True)
        for key, group in evidence['categories'].items():
            group['items'] = []
            group['unused_reason'] = 'test fixture does not use this category'
            if key in ('script', 'video'):
                media = self.source if key == 'script' else path
                group['items'] = [{'path': media.relative_to(self.root).as_posix(), 'sha256': file_hash(media),
                    'source': 'test original', 'rights_holder': 'test owner', 'license': 'test permission',
                    'commercial_allowed': True, 'derivative_allowed': True, 'obligations_fulfilled': True,
                    'authorization': {'path': 'authorization.txt', 'sha256': file_hash(proof)}}]
        for review in evidence['content_review'].values():
            review.update(status='cleared', reviewer='test reviewer', evidence='test manual review')
        return evidence, proof

    def test_technical_delivery_is_not_commercial_approval(self):
        from stage_completion_service import commercial_delivery_status, commercial_template, validate_commercial_evidence
        self.commercial_fixture()
        self.assertFalse(commercial_delivery_status(self.root)[0])
        with self.assertRaises(ValueError):
            validate_commercial_evidence(self.root, commercial_template(self.root))

    def test_imported_media_source_receipt_is_not_permission_and_is_version_bound(self):
        from stage_completion_service import commercial_template, validate_commercial_evidence, publish_imported_media
        from agent.core import file_hash
        evidence, _ = self.commercial_fixture()
        video = evidence['categories']['video']['items'][0]
        output = self.root / video['path']
        save(output.with_name(output.name + '.source.json'), {'schema': 1, 'kind': 'video',
             'source': 'external-editor/master.mp4', 'imported_file': output.name, 'sha256': video['sha256'],
             'rights_status': 'unknown'})
        item = commercial_template(self.root)['categories']['video']['items'][0]
        self.assertIn('external-editor', item['source'])
        self.assertFalse(item['commercial_allowed'])
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        audio = self.root / 'audio.wav'
        publish_imported_media(audio, output, lambda _: True, 'audio')
        receipt = read(audio.with_name(audio.name + '.source.json'))
        self.assertEqual(receipt['sha256'], file_hash(audio))
        receipt['sha256'] = 'outdated'
        save(output.with_name(output.name + '.source.json'), dict(receipt, imported_file=output.name))
        with self.assertRaisesRegex(ValueError, '导入来源'):
            validate_commercial_evidence(self.root, evidence)

    def test_commercial_template_prefills_known_sources_without_granting_rights(self):
        import os
        from agent.core import file_hash
        from stage_completion_service import commercial_template, validate_commercial_evidence
        evidence, _ = self.commercial_fixture()
        video = evidence['categories']['video']['items'][0]
        output = self.root / video['path']
        source = self.root / 'source.mp4'; source.write_bytes(b'original source')
        font = output.parent / 'font.ttc'; font.write_bytes(b'test-only font')
        row = {'source': os.path.relpath(source, output.parent), 'sha256': file_hash(source)}
        save(output.parent / 'edit_bundle.json', {'master': output.name, 'master_sha256': video['sha256'],
             'manifest': [row, row, {'sha256': 'legacy'}],
             'fonts': [{'path': 'font.ttc', 'sha256': file_hash(font)}]})
        template = commercial_template(self.root)
        self.assertEqual(len(template['categories']['script']['items']), 1)
        self.assertEqual(len(template['categories']['video']['items']), 2)
        self.assertEqual(len(template['categories']['font']['items']), 1)
        self.assertTrue(any('缺少路径' in message for message in template['inventory_warnings']))
        for group in template['categories'].values():
            for item in group['items']:
                self.assertFalse(item['commercial_allowed'])
                self.assertEqual(item['authorization'], {'path': '', 'sha256': ''})
        self.assertFalse(template['inventory_complete'])
        with self.assertRaises(ValueError):
            validate_commercial_evidence(self.root, template)
        source.write_bytes(b'changed source')
        self.assertTrue(any('版本已改变' in warning for warning in commercial_template(self.root)['inventory_warnings']))
        source.unlink()
        self.assertTrue(any('来源缺失' in warning for warning in commercial_template(self.root)['inventory_warnings']))

    def test_commercial_inventory_must_cover_actual_delivery_and_known_sources(self):
        from copy import deepcopy
        from agent.core import file_hash
        from stage_completion_service import validate_commercial_evidence
        evidence, _ = self.commercial_fixture()
        video = evidence['categories']['video']['items'][0]
        source = self.root / 'source.mp4'; source.write_bytes(b'original source')
        source_item = dict(video, path='source.mp4', sha256=file_hash(source))
        wrong = deepcopy(evidence)
        wrong['categories']['video']['items'] = [source_item]
        with self.assertRaisesRegex(ValueError, '实际交付'):
            validate_commercial_evidence(self.root, wrong)
        output = self.root / video['path']
        save(output.parent / 'edit_bundle.json', {'master': output.name, 'master_sha256': video['sha256'],
             'manifest': [{'shot': 'S01', 'version': 1, 'sha256': file_hash(source)}]})
        with self.assertRaisesRegex(ValueError, '镜头来源'):
            validate_commercial_evidence(self.root, evidence)
        wrong = deepcopy(evidence)
        wrong['categories']['image']['items'].append(source_item)
        with self.assertRaisesRegex(ValueError, '镜头来源'):
            validate_commercial_evidence(self.root, wrong)
        evidence['categories']['video']['items'].append(source_item)
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        import os
        bundle_path = output.parent / 'edit_bundle.json'
        bundle = read(bundle_path)
        bundle['manifest'][0]['source'] = os.path.relpath(source, output.parent)
        save(bundle_path, bundle)
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        duplicate = self.root / 'duplicate.mp4'; duplicate.write_bytes(source.read_bytes())
        wrong = deepcopy(evidence)
        wrong['categories']['video']['items'][-1]['path'] = 'duplicate.mp4'
        with self.assertRaisesRegex(ValueError, '实际镜头来源'):
            validate_commercial_evidence(self.root, wrong)
        for bad_source in ('', 42, 'missing.mp4', str(self.root.parent / 'outside.mp4')):
            bundle['manifest'][0]['source'] = bad_source
            save(bundle_path, bundle)
            with self.subTest(source=bad_source), self.assertRaises(ValueError):
                validate_commercial_evidence(self.root, evidence)

    def test_commercial_reference_gate_requires_generation_version(self):
        import os
        from agent.core import file_hash
        from stage_completion_service import commercial_template, validate_commercial_evidence
        evidence, _ = self.commercial_fixture()
        video = evidence['categories']['video']['items'][0]
        output = self.root / video['path']
        reference = self.root / 'reference.png'; reference.write_bytes(b'test-reference')
        save(output.parent / 'edit_bundle.json', {'master': output.name, 'master_sha256': video['sha256'],
             'manifest': [{'sha256': video['sha256']}],
             'references': [{'path': os.path.relpath(reference, output.parent), 'sha256': file_hash(reference)}]})
        template = commercial_template(self.root)
        self.assertEqual(template['categories']['reference']['items'][0]['path'], 'reference.png')
        with self.assertRaisesRegex(ValueError, '参考授权'):
            validate_commercial_evidence(self.root, evidence)
        item = dict(video, path='reference.png', sha256=file_hash(reference))
        evidence['categories']['image']['items'] = [item]
        with self.assertRaisesRegex(ValueError, '参考授权'):
            validate_commercial_evidence(self.root, evidence)
        evidence['categories']['reference']['items'] = [item]
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        bundle = read(output.parent / 'edit_bundle.json')
        bundle['references'][0]['category'] = 'image'
        save(output.parent / 'edit_bundle.json', bundle)
        evidence['categories']['reference']['items'] = []
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        self.assertEqual(commercial_template(self.root)['categories']['image']['items'][0]['path'], 'reference.png')
        reference.write_bytes(b'changed-reference')
        item['sha256'] = file_hash(reference)
        with self.assertRaisesRegex(ValueError, '参考授权'):
            validate_commercial_evidence(self.root, evidence)

    def test_commercial_font_gate_covers_new_and_legacy_overlay_fonts(self):
        from copy import deepcopy
        from agent.core import file_hash
        from stage_completion_service import validate_commercial_evidence
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                evidence, _ = self.commercial_fixture()
                video = evidence['categories']['video']['items'][0]
                output = self.root / video['path']
                font = output.parent / 'font.ttc'; font.write_bytes(b'test-only font fixture')
                bundle = {'master': output.name, 'master_sha256': video['sha256'],
                          'manifest': [{'sha256': video['sha256']}]}
                if not legacy:
                    bundle['fonts'] = [{'path': 'font.ttc', 'sha256': file_hash(font)}]
                save(output.parent / 'edit_bundle.json', bundle)
                with self.assertRaisesRegex(ValueError, '字体授权'):
                    validate_commercial_evidence(self.root, evidence)
                item = dict(video, path=font.relative_to(self.root).as_posix(), sha256=file_hash(font))
                wrong = deepcopy(evidence); wrong['categories']['image']['items'] = [item]
                with self.assertRaisesRegex(ValueError, '字体授权'):
                    validate_commercial_evidence(self.root, wrong)
                evidence['categories']['font']['items'] = [item]
                self.assertTrue(validate_commercial_evidence(self.root, evidence))
                font.write_bytes(b'changed font fixture')
                with self.assertRaisesRegex(ValueError, '摘要'):
                    validate_commercial_evidence(self.root, evidence)

    def test_commercial_script_must_match_adopted_storyboard_source(self):
        from agent.core import file_hash
        from stage_completion_service import validate_commercial_evidence
        script = self.root / 'original.md'; script.write_text('original story')
        board = read(self.source); board['source_script'] = 'original.md'; save(self.source, board)
        evidence, _ = self.commercial_fixture()
        with self.assertRaisesRegex(ValueError, '剧本授权清单'):
            validate_commercial_evidence(self.root, evidence)
        item = evidence['categories']['script']['items'][0]
        item.update(path='original.md', sha256=file_hash(script))
        self.assertTrue(validate_commercial_evidence(self.root, evidence))
        script.write_text('changed story')
        with self.assertRaisesRegex(ValueError, '摘要'):
            validate_commercial_evidence(self.root, evidence)

    def test_commercial_script_missing_or_invalid_link_cannot_use_other_authorization(self):
        from stage_completion_service import validate_commercial_evidence
        for value in ('missing.md', '../outside.md', ['invalid']):
            with self.subTest(value=value):
                board = read(self.source); board['source_script'] = value; save(self.source, board)
                evidence, _ = self.commercial_fixture()
                with self.assertRaisesRegex(ValueError, '剧本来源'):
                    validate_commercial_evidence(self.root, evidence)

    def test_unlinked_storyboard_cannot_use_unrelated_script_authorization(self):
        from agent.core import file_hash
        from stage_completion_service import validate_commercial_evidence
        evidence, _ = self.commercial_fixture()
        unrelated = self.root / 'other.md'; unrelated.write_text('unrelated story')
        evidence['categories']['script']['items'][0].update(path='other.md', sha256=file_hash(unrelated))
        with self.assertRaisesRegex(ValueError, '剧本授权清单'):
            validate_commercial_evidence(self.root, evidence)

    def test_commercial_evidence_invalidated_by_authorization_change(self):
        from stage_completion_service import confirm_commercial_evidence, commercial_delivery_status
        evidence, proof = self.commercial_fixture()
        confirm_commercial_evidence(self.root, evidence)
        self.assertTrue(commercial_delivery_status(self.root)[0])
        proof.write_text('changed authorization')
        self.assertFalse(commercial_delivery_status(self.root)[0])

    def test_commercial_evidence_blocks_missing_category_risk_and_permission(self):
        from copy import deepcopy
        from stage_completion_service import validate_commercial_evidence
        evidence, _ = self.commercial_fixture()
        mutations = [lambda e: e['categories'].pop('font'),
            lambda e: e['categories']['script']['items'][0].update(commercial_allowed=False),
            lambda e: e['content_review']['nsfw'].update(status='pending'),
            lambda e: e['categories']['reference'].update(unused_reason=''),
            lambda e: e.update(inventory_complete=False),
            lambda e: e['categories']['script']['items'][0]['authorization'].update(path='../outside.txt'),
            lambda e: e.update(outputs=[])]
        for mutation in mutations:
            data = deepcopy(evidence); mutation(data)
            with self.assertRaises(ValueError): validate_commercial_evidence(self.root, data)

    def test_extensions_and_wrong_stage_cannot_replace_required_outputs(self):
        for stage, name in (('audio', 'subtitle.srt'), ('delivery', 'old.zip'), ('edit', 'sound.wav')):
            with self.subTest(stage=stage):
                path = self.artifact(stage, name)
                with self.assertRaises(ValueError):
                    self.prepare(stage, path)
                self.assertFalse(completion_evidence(self.root, stage)[0])

    def test_probe_failure_never_publishes_confirmation(self):
        path = self.artifact('delivery')
        with patch('agent.media.probe', side_effect=RuntimeError('invalid media')):
            with self.assertRaisesRegex(RuntimeError, 'invalid media'):
                prepare_media_completion(self.root, 'delivery', [path])
        self.assertFalse(media_manifest_path(self.root, 'delivery', media_scope(self.root)).exists())

    def test_invalid_stream_duration_and_dimensions_are_rejected(self):
        path = self.artifact('edit')
        cases = [{}, {'format': {'duration': 1}, 'streams': []},
                 {'format': {'duration': 1}, 'streams': [{'codec_type': 'audio'}]},
                 {'format': {'duration': 1}, 'streams': [{'codec_type': 'video', 'width': 0, 'height': 10}]}]
        cases += [{'format': {'duration': duration}, 'streams': [{'codec_type': 'video', 'width': 10, 'height': 10}]}
                  for duration in (0, -1, 'nan', 'inf')]
        for result in cases:
            with self.subTest(result=result), patch('agent.media.probe', return_value=result):
                with self.assertRaises(ValueError):
                    prepare_media_completion(self.root, 'edit', [path])

    def test_modified_media_invalidates_even_same_size_and_timestamp(self):
        import os
        path = self.artifact('audio')
        confirm_media_completion(self.root, 'audio', self.prepare('audio', path))
        stat = path.stat()
        path.write_bytes(b'changed-media')
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(path.stat().st_size, stat.st_size)
        ok, reason = completion_evidence(self.root, 'audio')
        self.assertFalse(ok)
        self.assertIn('替换或修改', reason)

    def test_source_change_and_episode_switch_invalidate(self):
        path = self.artifact('audio')
        prepared = self.prepare('audio', path)
        confirm_media_completion(self.root, 'audio', prepared)
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})
        self.assertFalse(completion_evidence(self.root, 'audio')[0])
        with self.assertRaises(ValueError):
            confirm_media_completion(self.root, 'audio', prepared)
        second = self.source.with_name('episode2.json')
        save(second, {'id': 'EP02', 'shots': [{'id': 'S01'}]})
        self.select(second)
        self.assertFalse(completion_evidence(self.root, 'audio')[0])

    def test_frozen_scope_checked_before_probe(self):
        scope = media_scope(self.root)
        path = self.artifact('audio')
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})
        with patch('agent.media.probe') as probe, self.assertRaises(ValueError):
            prepare_media_completion(self.root, 'audio', [path], scope=scope)
        probe.assert_not_called()

    def test_file_change_during_probe_rejected(self):
        path = self.artifact('audio')
        def probe(*_):
            path.write_bytes(b'replacement')
            return {'format': {'duration': 1}, 'streams': [{'codec_type': 'audio'}]}
        with patch('agent.media.probe', side_effect=probe), self.assertRaisesRegex(ValueError, '校验期间'):
            prepare_media_completion(self.root, 'audio', [path])

    def test_file_change_after_probe_before_review_rejected(self):
        path = self.artifact('audio')
        prepared = self.prepare('audio', path)
        path.write_bytes(b'replacement')
        with self.assertRaises(ValueError):
            confirm_media_completion(self.root, 'audio', prepared)

    def test_manifest_cannot_be_used_for_another_project_or_stage(self):
        prepared = self.prepare('audio', self.artifact('audio'))
        with self.assertRaises(ValueError):
            confirm_media_completion(self.root, 'edit', prepared)
        prepared['scope']['project'] = str(self.root.parent)
        with self.assertRaises(ValueError):
            confirm_media_completion(self.root, 'audio', prepared)

    def test_legacy_folder_can_be_explicitly_adopted(self):
        path = self.root / '12质检交付' / 'legacy.mp4'
        path.parent.mkdir()
        path.write_bytes(b'legacy-media')
        self.assertFalse(completion_evidence(self.root, 'delivery')[0])
        confirm_media_completion(self.root, 'delivery', self.prepare('delivery', path))
        self.assertTrue(completion_evidence(self.root, 'delivery')[0])

    def test_malformed_manifest_fails_closed(self):
        prepared = self.prepare('audio', self.artifact('audio'))
        manifest = confirm_media_completion(self.root, 'audio', prepared)
        for outputs in ([None], [{'path': prepared['outputs'][0]['path'], 'validation': []}], []):
            with self.subTest(outputs=outputs):
                save(manifest, dict(prepared, status='complete', reviewed=True, outputs=outputs))
                self.assertFalse(completion_evidence(self.root, 'audio')[0])

    def test_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / 'output.wav'
            path.write_bytes(b'external-media')
            with self.assertRaises(ValueError):
                self.prepare('audio', path)

    def test_real_probe_accepts_wave_and_rejects_fake_mp4(self):
        import struct
        from platform_tools import tool_path
        executable = tool_path('ffprobe') or 'D:/Tools/ffmpeg/bin/ffprobe.exe'
        self.assertTrue(Path(executable).is_file(), '测试用 FFprobe 必须可用以验证真实媒体链路')
        save(self.root / 'config.json', {'ffprobe': executable})
        path = self.artifact('audio')
        pcm = b'\0\0' * 8000
        path.write_bytes(b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt '
                         + struct.pack('<IHHIIHH', 16, 1, 1, 8000, 16000, 2, 16)
                         + b'data' + struct.pack('<I', len(pcm)) + pcm)
        prepared = prepare_media_completion(self.root, 'audio', [path])
        confirm_media_completion(self.root, 'audio', prepared)
        self.assertTrue(completion_evidence(self.root, 'audio')[0])
        fake = self.artifact('delivery')
        with self.assertRaises(RuntimeError):
            prepare_media_completion(self.root, 'delivery', [fake])
        self.assertFalse(completion_evidence(self.root, 'delivery')[0])

    def test_desktop_entry_requires_confirmation_and_rechecks_project(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from desktop import Desktop
        path = self.artifact('audio')
        host = SimpleNamespace(root=self.root, win=object(), pet=Mock())
        pending = []
        host.async_ = lambda work, done: pending.append((work, done))
        with patch('desktop.FileDialog') as dialog:
            dialog.return_value.open_files.return_value = [path]
            Desktop.confirm_stage_media(host, 'audio')
        work, done = pending.pop()
        with patch('agent.media.probe', return_value={'format': {'duration': 1}, 'streams': [{'codec_type': 'audio'}]}):
            prepared = work()
        with patch('desktop.confirm', return_value=False):
            done(prepared)
        self.assertFalse(completion_evidence(self.root, 'audio')[0])
        host.pet.report_done.assert_not_called()
        host.root = self.root.parent
        with patch('desktop.confirm') as ask, self.assertRaisesRegex(ValueError, '项目已切换'):
            done(prepared)
        ask.assert_not_called()
        host.root = self.root
        with patch('desktop.confirm', return_value=True):
            done(prepared)
        self.assertTrue(completion_evidence(self.root, 'audio')[0])
        host.pet.report_done.assert_called_once_with('audio', '本集成果已校验并确认')


if __name__ == '__main__':
    unittest.main()
