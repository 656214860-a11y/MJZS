"""P0/Q26: origin is durable provenance, independent from index caches."""
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from infra import file_index
from orchestrator import stage_publication
from contract.project_context import ProjectContext
from contract import stage_layout
from domain import audio_import_service, global_library_service


class FileOriginProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()

    def make(self, name, content=b'content'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def origins(self):
        return {row.path: row.origin for row in file_index.rows(self.root)}

    def test_import_origin_survives_cache_deletion_and_rebuild(self):
        path = self.make('uploaded.png')
        file_index.record_origin(self.root, [path], '用户上传')
        file_index.rebuild(self.root)
        file_index.index_path(self.root).unlink()
        self.assertEqual(self.origins()['uploaded.png'], '用户上传')
        self.assertTrue(stage_layout.workflow_dir(self.root, '文件索引', '来源记录.json').is_file())
        self.assertNotIn('来源记录.json', self.origins())

    def test_cache_origin_is_not_a_fact_and_legacy_defaults_to_system(self):
        self.make('legacy.png')
        payload = file_index.rebuild(self.root)
        payload['files'][0]['origin'] = '模型产出'
        file_index.index_path(self.root).write_text(json.dumps(payload), encoding='utf-8')
        self.assertEqual(file_index.read(self.root)['files'][0]['origin'], '系统生成')

    def test_concurrent_records_do_not_lose_entries(self):
        paths = [self.make(f'input_{n}.png') for n in range(16)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda p: file_index.record_origin(self.root, [p], '用户上传'), paths))
        self.assertEqual(set(self.origins().values()), {'用户上传'})
        self.assertEqual(len(self.origins()), 16)

    def test_paths_and_origins_are_validated_before_any_write(self):
        self.make('ok.png')
        for path in ('../escape.png', 'x/../ok.png', 'C:evil.png', 'private/key.png', self.root.parent / 'outside.png'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                file_index.record_origin(self.root, ['ok.png', path], '用户上传')
        with self.assertRaises(ValueError):
            file_index.record_origin(self.root, ['ok.png'], 'guess')
        self.assertFalse(stage_layout.workflow_dir(self.root, '文件索引', '来源记录.json').exists())

    def test_missing_file_does_not_acquire_a_fact(self):
        file_index.record_origin(self.root, ['missing.png'], '用户上传')
        metadata = stage_layout.workflow_dir(self.root, '文件索引', '来源记录.json')
        self.assertTrue(not metadata.exists() or 'missing.png' not in metadata.read_text(encoding='utf-8'))

    def test_model_publication_refreshes_existing_cache_without_context(self):
        file_index.rebuild(self.root)
        target = self.root / 'generated.png'
        stage_publication.publish_stage_bytes(target, b'generated', bool, lambda _: None, origin='模型产出')
        self.assertEqual(file_index.read(self.root)['files'][0]['origin'], '模型产出')

    def test_context_records_without_first_scan_and_import_override_is_preserved(self):
        context = ProjectContext.snapshot(self.root, lambda stage: self.root / stage)
        target = self.root / 'generated.txt'
        with mock.patch.object(file_index, 'build', side_effect=AssertionError('unexpected scan')):
            stage_publication.publish_stage_text(target, 'generated', bool, lambda _: None, context=context, origin='模型产出')
        self.assertFalse(file_index.index_path(self.root).exists())
        self.assertEqual(self.origins()['generated.txt'], '模型产出')
        stage_publication.publish_stage_bytes(target, b'import', bool, lambda _: None, context=context, origin='用户上传')
        stage_publication.publish_stage_bytes(target, b'import again', bool, lambda _: None, context=context)
        self.assertEqual(self.origins()['generated.txt'], '用户上传')

    def test_unmarked_publication_defaults_to_system(self):
        stage_publication.publish_stage_text(self.root / 'report.txt', 'report', bool, lambda _: None,
                                             context=ProjectContext.snapshot(self.root, lambda stage: self.root / stage))
        self.assertEqual(self.origins()['report.txt'], '系统生成')

    def test_bundle_explicit_user_origin(self):
        stage_publication.publish_stage_bundle({self.root / 'a.png': b'a', self.root / 'b.png': b'b'},
                                              bool, lambda: None, context=ProjectContext.snapshot(self.root, lambda stage: self.root / stage), origin='用户上传')
        self.assertEqual(set(self.origins().values()), {'用户上传'})

    def test_audio_import_records_user_origin(self):
        source = self.make('external.wav', b'RIFFaudio')
        def publish(destination, original):
            destination.write_bytes(original.read_bytes())
        result = audio_import_service.import_audio(self.root, source, publish=publish)
        self.assertTrue(result.ok)
        self.assertEqual(self.origins()[result.data.relative_to(self.root).as_posix()], '用户上传')

    def test_global_copy_records_user_and_source_and_failure_leaves_no_fact(self):
        library = self.root.parent / 'library'
        library.mkdir()
        (library / 'image.png').write_bytes(b'image')
        target = global_library_service.copy_to_project(library, 'image.png', self.root)
        self.assertEqual(self.origins()[target.relative_to(self.root).as_posix()], '用户上传')
        manifest = stage_layout.shared_paths(self.root)['root'] / global_library_service.SHARED_SUB / global_library_service.SOURCE_MANIFEST
        self.assertTrue(manifest.is_file())
        with mock.patch.object(file_index, 'update', side_effect=OSError('failure')):
            with self.assertRaises(OSError):
                global_library_service.copy_to_project(library, 'image.png', self.root)
        facts = stage_layout.workflow_dir(self.root, '文件索引', '来源记录.json').read_text(encoding='utf-8')
        self.assertNotIn('_2.png', facts)

    def test_keyframe_register_records_user_origin_in_project_root(self):
        from agent.core import save
        from ui import keyframe_import
        from domain import keyframe_evidence
        from tests.image_fixtures import png
        folder = self.root / '03初步分镜' / '分镜文档'
        folder.mkdir(parents=True)
        source = folder / 'episode.json'
        shot = {'id': 'SH001', 'frame': 'frames/SH001.png', 'frame_prompt': '街道'}
        episode = {'episode_id': 'EP001', 'shots': [shot]}
        save(source, episode)
        image = self.make('external.png', png())
        item = {'shot_id': 'SH001', 'shot_signature': keyframe_import.fingerprint(shot),
                'source_evidence': keyframe_evidence.source_evidence(source, episode, shot)}
        target = keyframe_import.register(source, item, image)
        self.assertEqual(self.origins()[target.relative_to(self.root).as_posix()], '用户上传')
        file_index.rebuild(self.root)
        self.assertEqual(self.origins()[target.relative_to(self.root).as_posix()], '用户上传')

    def test_global_rebuild_and_refresh_use_origin_facts(self):
        path = self.make('library.png')
        file_index.record_origin(self.root, [path], '用户上传')
        file_index.rebuild_global(self.root)
        self.assertEqual(file_index.global_rows(self.root)[0].origin, '用户上传')


if __name__ == '__main__':
    unittest.main()
