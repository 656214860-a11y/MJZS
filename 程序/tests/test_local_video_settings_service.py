import tempfile
import unittest
import shutil
from pathlib import Path

from agent.core import read, save, save_bytes
from local_video_settings_service import save_local_video_settings
from stage_execution_service import publish_local_video_settings


class LocalVideoSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.config = self.project / 'config.json'
        save(self.config, {'video_backend': 'wan', 'keep': 'value'})
        self.source = self.project / 'chosen.json'
        self.source.write_text('{"1": {}}', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_publishes_hashed_workflow_and_config(self):
        updated = publish_local_video_settings(self.project, read(self.config), {'workflow': str(self.source), 'url': 'http://127.0.0.1:8189'})
        target = Path(updated['local_video']['workflow'])
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(read(self.config), updated)
        self.assertEqual(updated['video_backend'], 'comfy')

    def test_publication_invalidates_workflow_and_config_cache_entries(self):
        import file_cache
        file_cache.read_json(self.config)
        updated = publish_local_video_settings(self.project, read(self.config),
                                               {'workflow': str(self.source)})
        target = Path(updated['local_video']['workflow'])
        file_cache.read_json(target)
        events = []
        gateway = {'publish_json': save, 'publish_bytes': save_bytes,
                   'copy_file': shutil.copy2,
                   'replace_file': lambda source, destination: Path(source).replace(destination),
                   'published': lambda path: events.append(Path(path))}
        self.source.write_text('{"2": {}}', encoding='utf-8')
        refreshed = save_local_video_settings(self.project, read(self.config),
                                              {'workflow': str(self.source)}, gateway=gateway)
        self.assertEqual(events, [Path(refreshed['local_video']['workflow']), self.config])

    def test_config_failure_restores_replaced_workflow_and_config(self):
        first = publish_local_video_settings(self.project, read(self.config), {'workflow': str(self.source)})
        target = Path(first['local_video']['workflow'])
        old_target, old_config = target.read_bytes(), self.config.read_bytes()
        self.source.write_text('{"2": {}}', encoding='utf-8')
        gateway = {'publish_json': lambda *_: (_ for _ in ()).throw(OSError('config failed')),
                   'publish_bytes': save_bytes,
                   'copy_file': shutil.copy2,
                   'replace_file': lambda source, target: Path(source).replace(target),
                   'published': lambda _path: None}
        with self.assertRaisesRegex(OSError, 'config failed'):
            save_local_video_settings(self.project, read(self.config), {'workflow': str(self.source)}, gateway=gateway)
        self.assertEqual(self.config.read_bytes(), old_config)
        self.assertEqual(target.read_bytes(), old_target)

    def test_rejects_missing_l3_gateway(self):
        with self.assertRaisesRegex(TypeError, 'L3'):
            save_local_video_settings(self.project, read(self.config), {'workflow': str(self.source)})
