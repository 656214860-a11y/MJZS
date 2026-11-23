# -*- coding: utf-8 -*-
"""stage_config：没有项目时读阶段配置不得把 None 当缓存键，否则之后任何保存都会在失效缓存时崩。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import stage_config
import skill_registry
import workflow_settings


class EmptyProjectCacheTests(unittest.TestCase):
    def test_reading_without_project_leaves_no_none_key_behind(self):
        stage_config.get(None, 'keyframe')
        stage_config.get('', 'keyframe')
        for cache in (stage_config._SYNCHRONIZE_CACHE, stage_config._GET_CACHE):
            self.assertNotIn(None, cache)

    def test_saving_after_reading_without_project_still_works(self):
        stage_config.get(None, 'keyframe')
        with tempfile.TemporaryDirectory() as folder:
            stage_config.put(Path(folder), 'keyframe', model='')
            self.assertTrue(stage_config.path(Path(folder)).exists())


class _FakeSkill:
    """注册表条目的最小口径：stage_config 只读 name／stage／deprecated。"""

    def __init__(self, name, stage, deprecated=False):
        self.name = name
        self.stage = stage
        self.deprecated = deprecated


class _FakeRegistry:
    """put 与发送门禁用到的注册表口径：按名查、按阶段列、禁用名单。"""

    def __init__(self, skills=(), disabled=()):
        self._skills = {item.name: item for item in skills}
        self._disabled = set(disabled)

    def getAll(self):
        return list(self._skills.values())

    def getByStage(self, stage):
        return [item for item in self._skills.values() if item.stage == stage]

    def getById(self, sid):
        return self._skills.get(str(sid or ''))

    def canonical_id(self, sid):
        return str(sid or '').strip()

    def disabled_names(self):
        return set(self._disabled)


class StageConfigSkillPreservationTests(unittest.TestCase):
    """FIX-AUD-SKILL-STAGECFG（审查 AUD-SKILL D7）：``put`` 的任何保存都不得静默丢弃
    落盘配置里失效／已禁用的 SKILL 引用——发送门禁 ``validate_selected_skills`` 靠
    ``skill_config.json`` 原始 ``skills`` 列表报「未加载／已禁用」，保存时抹掉等于绕过门禁。"""

    def _project_with_stale_refs(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        project = Path(folder.name)
        stage_config.path(project).write_text(json.dumps({
            'script': {'model': 'auto',
                       'skills': ['script-skill', 'disabled-skill', 'ghost-skill']},
            'video': {'model': 'auto', 'skills': ['ghost-video-skill']},
        }, ensure_ascii=False), encoding='utf-8')
        return project

    def _registry(self):
        return _FakeRegistry(
            [_FakeSkill('script-skill', 'script'), _FakeSkill('video-skill', 'video')],
            disabled=('disabled-skill',))

    def test_save_without_skill_changes_keeps_stale_references_on_disk(self):
        """只改模型的保存：失效／已禁用引用要留在落盘配置里，供发送门禁报错。"""
        project = self._project_with_stale_refs()
        reg = self._registry()
        stage_config.put(project, 'script', model='gpt-4o', registry=reg)
        saved = json.loads(stage_config.path(project).read_text(encoding='utf-8'))
        self.assertEqual(saved['script']['skills'],
                         ['script-skill', 'disabled-skill', 'ghost-skill'])
        self.assertEqual(saved['video']['skills'], ['ghost-video-skill'])
        # 读取视图照旧清洗：get() 仍只见有效项，面板口径不变。
        self.assertEqual(stage_config.get(project, 'script', registry=reg)['skills'],
                         ['script-skill'])

    def test_explicit_skill_selection_remains_the_way_to_clear_stale_references(self):
        """显式重存勾选列表＝用户重新确认：不在新列表里的失效引用才移除。"""
        project = self._project_with_stale_refs()
        reg = self._registry()
        stage_config.put(project, 'script', skills=['script-skill'], registry=reg)
        saved = json.loads(stage_config.path(project).read_text(encoding='utf-8'))
        self.assertEqual(saved['script']['skills'], ['script-skill'])
        # 没被显式改写的阶段仍保留失效引用。
        self.assertEqual(saved['video']['skills'], ['ghost-video-skill'])

    def test_send_gate_still_reports_the_preserved_references(self):
        """无关阶段的保存之后，已禁用／未加载报错路径照常拦截发送。"""
        project = self._project_with_stale_refs()
        reg = self._registry()
        stage_config.put(project, 'keyframe', model='auto', registry=reg)
        with mock.patch.object(skill_registry, 'default_registry', return_value=reg):
            with self.assertRaises(ValueError) as ctx:
                workflow_settings.validate_selected_skills(project, 'script')
        self.assertIn('已禁用', str(ctx.exception))
        self.assertIn('disabled-skill', str(ctx.exception))
        stage_config.path(project).write_text(json.dumps({
            'script': {'model': 'auto', 'skills': ['ghost-skill', 'disabled-skill']},
        }, ensure_ascii=False), encoding='utf-8')
        with mock.patch.object(skill_registry, 'default_registry', return_value=reg):
            with self.assertRaises(ValueError) as ctx:
                workflow_settings.validate_selected_skills(project, 'script')
        self.assertIn('未加载', str(ctx.exception))
        self.assertIn('ghost-skill', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
