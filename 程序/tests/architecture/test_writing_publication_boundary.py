"""剧本模型工具的可见成果必须经 L3 注入发布器。"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class WritingPublicationBoundaryTests(unittest.TestCase):
    def test_l2_writers_have_no_direct_save_text_and_require_injected_publication(self):
        for name, functions in {
            'writing_tools.py': {'write_file'},
            'writing_api.py': {'_write_script_raw'},
        }.items():
            tree = ast.parse((ROOT / name).read_text(encoding='utf-8'))
            rows = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
            for function in functions:
                node = rows[function]
                names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
                self.assertIn('publish', names)
                self.assertNotIn('save_text', names)

    def test_desktop_uses_l3_writing_entrypoint(self):
        stage_source = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        desktop_source = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('return reply(project, creative, progress=progress, cancelled=cancelled, stream=stream,', stage_source)
        self.assertIn('publish=publish_stage_text)', stage_source)
        self.assertIn('from stage_execution_service import reply_to_writing', desktop_source)

    def test_preparation_bundle_requires_l3_publisher(self):
        tree = ast.parse((ROOT / 'writing.py').read_text(encoding='utf-8'))
        prepare = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'prepare')
        names = {child.id for child in ast.walk(prepare) if isinstance(child, ast.Name)}
        self.assertIn('publish', names)
        self.assertFalse({'save', 'save_text', 'save_bytes', 'copyfile'} & names)
        stage_source = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('def publish_writing_preparation(', stage_source)
        self.assertIn('publish_stage_bundle(payload', stage_source)
        self.assertIn('publish=publish_writing_preparation', app_source)

    def test_context_and_import_reports_require_l3_publishers(self):
        context = (ROOT / 'workflow_context.py').read_text(encoding='utf-8')
        writing = (ROOT / 'writing.py').read_text(encoding='utf-8')
        controller = (ROOT / 'workflow_context_controller.py').read_text(encoding='utf-8')
        stage = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        app = (ROOT / 'app.py').read_text(encoding='utf-8')
        desktop = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('def instruction(project, stage, data=None, *, publish=None):', context)
        self.assertIn('项目接续进度需要由 L3 注入发布器', context)
        self.assertNotIn('from agent.core import read, save', context)
        self.assertIn('def import_project(root,json_file,*,gateway=None,publish_report=None):', writing)
        self.assertIn('项目导入报告需要由 L3 注入发布器', writing)
        self.assertIn('def request_stage_instruction(', controller)
        self.assertIn('def publish_writing_context(', controller)
        self.assertIn('def import_writing_project(', stage)
        self.assertIn('request_stage_instruction(project,stage,data)', desktop)
        self.assertIn('import_writing_project(self.root,file)', app)


if __name__ == '__main__':
    unittest.main()
