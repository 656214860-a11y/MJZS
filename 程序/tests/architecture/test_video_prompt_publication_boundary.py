"""视频提示词的手动/自动保存不得由 UI 直接发布成果。"""
import ast
import os
import unittest
from tests.architecture._scan import entity_file, stage_execution_source

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _method(name):
    tree = ast.parse(open(os.path.join(ROOT, 'app.py'), encoding='utf-8').read())
    holder = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
    return ast.get_source_segment(open(os.path.join(ROOT, 'app.py'), encoding='utf-8').read(),
                                  next(node for node in holder.body if isinstance(node, ast.FunctionDef) and node.name == name))


class VideoPromptPublicationBoundaryTests(unittest.TestCase):
    def test_manual_and_auto_save_delegate_to_publication_service(self):
        for name in ('save_prompt', 'flush_prompt'):
            source = _method(name)
            with self.subTest(method=name):
                self.assertIn('stage_execution_service import publish_video_prompt', source)
                self.assertIn('publish_video_prompt(self.studio,', source)
                self.assertNotIn("'video_prompts'", source)

    def test_manual_import_delegates_draft_publication_to_service(self):
        source = _method('import_prompt')
        self.assertIn('stage_execution_service import import_video_prompt', source)
        self.assertIn('import_video_prompt(self.studio,', source)
        self.assertNotIn("'video_prompts'", source[source.index('import_video_prompt'):])

    def test_agent_result_delegates_visible_publication_to_service(self):
        source = open(os.path.join(ROOT, 'video_prompt_results.py'), encoding='utf-8').read()
        self.assertIn('stage_execution_service import publish_video_prompt', source)
        self.assertIn('publish_video_prompt(studio, sid, text)', source)
        self.assertNotIn('save_text(path.with_suffix', source)
        self.assertNotIn('save(studio.episode_path', source)

    def test_service_owns_all_prompt_artifact_names(self):
        source = entity_file('video_prompt_publication').read_text(encoding='utf-8')
        self.assertIn('def publish(', source)
        self.assertIn('def stage_import(', source)
        self.assertNotIn('stage_execution_service', source)
        self.assertNotIn('from agent.core import fingerprint, read, restore_bytes, save, save_bytes', source)
        for name in ("'video_prompts'", "'当前提示词.txt'", "'.json'", "'.txt'"):
            self.assertIn(name, source)

    def test_l2_requires_l3_publishers_for_legacy_and_import_paths(self):
        source = entity_file('video_prompt_publication').read_text(encoding='utf-8')
        stage = stage_execution_source()
        self.assertIn('def _publish_legacy_bundle(artifacts, *, publish_bundle=None)', source)
        self.assertIn('def _import_gateway(gateway)', source)
        self.assertNotIn('save_bytes(', source)
        self.assertNotIn('save(target, record)', source)
        self.assertIn('def video_prompt_gateway()', stage)
        self.assertIn('def publish_video_prompt(', stage)
        self.assertIn('def import_video_prompt(', stage)
