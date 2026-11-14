"""总控包导入：自包含总控包（清单＋主控包）复制进 00全流程SKILL 并合并进内置总控清单。

REQ-S01-81 「浏览本地」导入自包含总控包：预检、可视化确认、复制包、合并 presets、刷新下拉。
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import master_import_service
import workflow_settings


def _write_skill(path, name, body='# 正文\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\nname: %s\n---\n%s' % (name, body), encoding='utf-8')
    return path


class MasterImportServiceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.program = Path(temp.name) / '程序'
        self.manifest = self.program / 'skills' / '00全流程SKILL' / '总控.json'
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self.manifest.write_text(json.dumps({'version': 1, 'presets': {}}, ensure_ascii=False),
                                 encoding='utf-8')
        # 让导入落在临时 program 里，不碰真机 总控.json。
        self._patch = mock.patch.object(workflow_settings, 'MASTER_MANIFEST', self.manifest)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(lambda: workflow_settings.refresh_workflow_presets(force=True))

    def _registry(self, names=()):
        return SimpleNamespace(getAll=lambda: [SimpleNamespace(name=name) for name in names])

    def _package(self, name, skills, locks):
        """造一个自包含总控包目录：清单 总控.json + 主控 SKILL.md。"""
        root = self.program / '_src' / name
        root.mkdir(parents=True, exist_ok=True)
        _write_skill(root / 'SKILL.md', name)
        manifest = {'version': 1, 'presets': {name: {
            'package': 'SKILL.md',
            'stage_skills': skills,
            'locks': locks,
        }}}
        (root / '总控.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
        return root / '总控.json'

    def test_plan_and_perform_import_registers_a_master(self):
        source = self._package('我的总控', {'script': ['pipeline-script-preparation']},
                               ['aspect_ratio'])
        registry = self._registry(['pipeline-script-preparation'])
        plan = master_import_service.plan_import(source, self.program, registry)
        self.assertIn('我的总控', plan['rows'])
        self.assertEqual(plan['problems'], [])

        result = master_import_service.perform_import(plan, self.program)
        self.assertIn('我的总控', result['names'])
        # 包被复制进 00全流程SKILL，清单合并并重写了 package 相对路径。
        self.assertTrue((self.manifest.parent / '我的总控' / 'SKILL.md').is_file())
        merged = json.loads(self.manifest.read_text(encoding='utf-8'))
        preset = merged['presets']['我的总控']
        self.assertEqual(preset['stage_skills']['script'], ['pipeline-script-preparation'])
        self.assertTrue(preset['package'].endswith('00全流程SKILL/我的总控/SKILL.md'))
        self.assertEqual(preset['locks'], ['aspect_ratio'])
        # 刷新后预设表可见。
        workflow_settings.refresh_workflow_presets(force=True)
        self.assertIn('我的总控', workflow_settings.WORKFLOW_PRESETS)

    def test_missing_package_is_blocked(self):
        source = self.program / '_src' / '缺包' / '总控.json'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps({'presets': {'缺包': {
            'package': '不存在/SKILL.md', 'stage_skills': {}, 'locks': []}}},
            ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(master_import_service.ImportBlocked):
            master_import_service.plan_import(source, self.program, self._registry())

    def test_unregistered_skill_is_a_soft_problem_not_hard_block(self):
        source = self._package('软问题', {'video': ['没有这个']}, [])
        plan = master_import_service.plan_import(source, self.program, self._registry())
        self.assertTrue(any('不在注册表里' in p for p in plan['problems']))
        self.assertIn('软问题', plan['rows'])

    def test_unknown_lock_is_a_soft_problem(self):
        source = self._package('坏锁', {}, ['不存在锁'])
        plan = master_import_service.plan_import(source, self.program, self._registry())
        self.assertTrue(any('未登记的制作锁' in p for p in plan['problems']))


if __name__ == '__main__':
    unittest.main()
