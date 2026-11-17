# -*- coding: utf-8 -*-
"""SKILL 体系自检：注册表、阶段配置、预算、模型路由、工具表、编排器、阶段面板、三虎集成、
create-skill.js 生成器。运行：python -B test_skills.py

这些用例盯着规格里的两条硬话：**SKILL 不绑定模型**（模型由 ModelRouter 按能力／成本／可用性挑）
与 **11 个阶段都有统一的模型 + SKILL 面板**；另外每一条集成都要求「出问题只记一笔，不许把手
上的活带崩」。
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import tkinter as tk
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)  # legacy test fixtures are imported by their bare module name
os.chdir(PROGRAM)

import model_pool
import model_router
import pet_agent
import pet_bus
import pet_ui
import skill_budget
import skill_orchestrator
import skill_note_render
import skill_panel
import skill_registry
import skill_tools
import stage_config

NODE = shutil.which('node')
GENERATOR = Path(PROGRAM) / 'scripts' / 'create-skill.js'
SKILL_TEMPLATE = """---
name: %(name)s
displayName: %(display)s
description: 自检用的 SKILL
stage: %(stage)s
capabilities: [structured-output]
preferredModels: []
fallbackModels: []
tools: [%(tool)s]
dependsOn: [%(depends)s]
conflictsWith: [%(conflicts)s]
parallelizable: true
paid: %(paid)s
input: [projectId]
output: [ok]
constraints: [自检]
feedback:
  - onProgress: 更新三虎进度
  - onError: 异常处理
  - onComplete: 通知并推进阶段
examples:
  - 用户："跑一下" → run()
---

## 说明

自检用的最小 SKILL。
"""


def write_skill(root, name, stage='剧本准备', display='', tool='', depends='', conflicts='', paid='false'):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (name + '.skill.md')
    path.write_text(SKILL_TEMPLATE % {'name': name, 'display': display or name, 'stage': stage,
                                      'tool': tool, 'depends': depends, 'conflicts': conflicts,
                                      'paid': paid}, encoding='utf-8')
    return path


def _walk_widgets(widget):
    """深度优先产出 widget 及其全部后代（面板行是 Frame 套 Label）。"""
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


class FakeSkill(object):
    """SKILL 的属性是只读的（注册表里读出来的那一份谁都不许改），替身只用来看路由怎么挑。"""

    name = 'probe'
    displayName = '探针'
    description = ''
    stage = 'keyframe'
    capabilities = ()
    preferredModels = ()
    fallbackModels = ()
    tools = ()
    dependsOn = ()
    conflictsWith = ()
    parallelizable = True
    paid = False

    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeAdapter(model_router.ModelAdapter):
    """假服务商：密钥永远在，用来把「挑模型」那几步钉死。"""

    provider = 'fake'
    key_env = 'FAKE_API_KEY'
    models = {'fake-cheap': {'capabilities': ('structured-output',), 'cost': 1},
              'fake-smart': {'capabilities': ('reasoning', 'long-context'), 'cost': 3}}

    def credential(self):
        return 'fake-key'

    def endpoint(self):
        return 'http://127.0.0.1/fake/chat/completions'


class RegistryTests(unittest.TestCase):
    def test_skill_distribution_matches_the_split_script_flow(self):
        """验收：既有 SKILL 保留，并为 13 个阶段各登记一个全流程编排 SKILL。"""
        reg = skill_registry.default_registry()
        reg.scan(force=True)
        self.assertEqual(reg.count(), 73)
        self.assertEqual(len(reg.stages()), 13)
        expected_by_stage = {
            'script': 6, 'script_structure': 5, 'storyboard': 6, 'animatic': 1, 'assets': 6,
            'continuity': 6, 'final': 6, 'keyframe': 6, 'previs': 7,
            'video': 5, 'audio': 6, 'edit': 7, 'delivery': 6,
        }
        self.assertEqual(set(expected_by_stage), set(pet_bus.STAGES))
        for stage in pet_bus.STAGES:
            self.assertEqual(len(reg.getByStage(stage)), expected_by_stage[stage], stage)

    def test_pipeline_stage_skills_are_recursively_discovered_with_strong_dependencies(self):
        """阶段专属文件在子目录中发现，依赖只能指向已登记的上游管线 SKILL。"""
        from architecture.test_pipeline_stage_io_contract import PIPELINE_DEPENDENCIES
        reg = skill_registry.default_registry()
        self.assertEqual({name: reg.getById(name).dependsOn for name in PIPELINE_DEPENDENCIES},
                         PIPELINE_DEPENDENCIES)
        self.assertTrue(all(len(reg.getByStage(stage)) >= 1 for stage in pet_bus.STAGES))

    def test_registry_is_clean(self):
        reg = skill_registry.default_registry()
        reg.scan(force=True)
        self.assertEqual(reg.problems(), [])
        for note in reg.warnings():
            self.assertIn('子模块', note)

    def test_frontmatter_round_trips(self):
        item = skill_registry.default_registry().getById('firstframe-batch')
        self.assertEqual(item.displayName, '首帧批量生成')
        self.assertEqual(item.stage, 'keyframe')
        self.assertTrue(item.paid)
        self.assertEqual([key for row in item.feedback for key in row],
                         ['onProgress', 'onError', 'onComplete'])
        self.assertEqual(len(item.examples), 3)
        self.assertTrue(all('→' in row for row in item.examples))
        self.assertEqual(item.tools, ['firstframe.batchGenerate'])
        self.assertEqual(item.dependsOn, ['storyboard-prompt-render'])

    def test_lookup_by_id_and_stage(self):
        reg = skill_registry.default_registry()
        self.assertIsNone(reg.getById('没有这个'))
        names = [item.name for item in reg.getByStage('assets')]
        self.assertEqual(sorted(names), ['asset-auto-fill', 'asset-candidate-wall', 'asset-copyright-filter',
                                         'asset-dedupe', 'asset-visual-rank', 'pipeline-assets'])
        order = [item.name for item in reg.getAll()]
        self.assertEqual(order, sorted(order, key=lambda name: pet_bus.STAGES.index(reg.getById(name).stage)))

    def test_hot_reload_picks_up_a_new_file_without_restart(self):
        """阶段目录中新增文件免重启：再查一次就该进表。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '05资产管理SKILL'
            write_skill(stage_dir, 'probe-one', stage='资产管理')
            reg = skill_registry.Registry(root=root)
            self.assertEqual([item.name for item in reg.getAll()], ['probe-one'])
            write_skill(stage_dir, 'probe-two', stage='资产管理')
            # 常规查询允许短 TTL；阶段配置主动打开仍以 force 立即发现变更。
            reg.scan(force=True)
            self.assertEqual(sorted(item.name for item in reg.getAll()), ['probe-one', 'probe-two'])

    def test_root_manifest_is_migrated_and_non_stage_directories_are_not_scanned(self):
        """旧根目录文件受控归档；00 全流程包不因含 .skill.md 而进入阶段候选。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '01 剧本准备SKILL'
            stage_dir.mkdir(parents=True)
            legacy = write_skill(root, 'legacy-script', stage='剧本准备')
            flow = write_skill(root / '00全流程SKILL', 'whole-flow', stage='剧本准备')
            reg = skill_registry.Registry(root=root)

            expected = stage_dir / legacy.name
            self.assertEqual(reg.getById('legacy-script').path, expected)
            self.assertFalse(legacy.exists())
            self.assertTrue(expected.is_file())
            self.assertIsNone(reg.getById('whole-flow'))
            self.assertTrue(flow.is_file())

    def test_hot_reload_tracks_add_and_delete_inside_stage_directory(self):
        """阶段目录内的真实增删不能被 skills 根目录缓存遮住。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '01 剧本准备SKILL'
            stage_dir.mkdir(parents=True)
            reg = skill_registry.Registry(root=root)

            self.assertEqual(reg.files(), [])
            before_add = reg.fingerprint()
            before_add_key = reg._directory_cache_key
            probe = write_skill(stage_dir, 'probe-stage-file', stage='剧本准备')
            reg.scan(force=True)
            self.assertIn(probe, reg.files())
            after_add = reg.fingerprint(force=True)
            self.assertNotEqual(after_add, before_add)
            self.assertNotEqual(reg._directory_cache_key, before_add_key)
            after_add_key = reg._directory_cache_key
            self.assertIn('probe-stage-file', [item.name for item in reg.getAll()])

            probe.unlink()
            reg.scan(force=True)
            self.assertNotIn(probe, reg.files())
            after_delete = reg.fingerprint(force=True)
            self.assertNotEqual(after_delete, after_add)
            self.assertNotEqual(reg._directory_cache_key, after_add_key)
            self.assertNotIn('probe-stage-file', [item.name for item in reg.getAll()])

    def test_stage_package_registers_one_total_entry_and_hot_reloads(self):
        """阶段目录的外部包以一个入口登记；之后新放入的包无需重启即可发现。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '01 剧本准备SKILL'
            package = stage_dir / '外部编剧包'
            package.mkdir(parents=True)
            source = package / 'SKILL.md'
            source.write_text('# 外部编剧包\n\n用于验证总入口。', encoding='utf-8')
            nested = package / '内部子技能' / 'SKILL.md'
            nested.parent.mkdir()
            nested.write_text('# 不应单独出现', encoding='utf-8')
            write_skill(package, '包内重复清单', stage='剧本准备')

            reg = skill_registry.Registry(root=root)
            entry = reg.getById('外部编剧包')
            self.assertIsNotNone(entry)
            self.assertEqual(entry.stage, 'script')
            self.assertEqual(entry.displayName, '外部编剧包')
            self.assertEqual(entry.path, source)
            self.assertEqual([item.name for item in reg.getByStage('script')], ['外部编剧包'])
            self.assertIsNone(reg.getById('包内重复清单'))
            self.assertEqual(reg.problems(), [])

            later_package = stage_dir / '后放入的 SKILL 包'
            later_package.mkdir()
            (later_package / 'SKILL.md').write_text('# 后放入的 SKILL 包', encoding='utf-8')
            reg.scan(force=True)
            self.assertEqual([item.name for item in reg.getByStage('script')],
                             ['后放入的 SKILL 包', '外部编剧包'])

    def test_unchanged_directory_reuses_file_cache_without_rglob(self):
        """常规查询只 stat skills 根目录，不能再次递归扫描整棵树。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            write_skill(root / '05资产管理SKILL', 'probe-one', stage='资产管理')
            reg = skill_registry.Registry(root=root)
            self.assertEqual([item.name for item in reg.getAll()], ['probe-one'])

            calls = []
            path_type = type(reg.root)
            original_rglob = path_type.rglob

            def record_rglob(path, pattern):
                calls.append((path, pattern))
                return original_rglob(path, pattern)

            with mock.patch.object(path_type, 'rglob', new=record_rglob):
                self.assertEqual(reg.getById('probe-one').name, 'probe-one')
                self.assertEqual([item.name for item in reg.getAll()], ['probe-one'])
            self.assertEqual(calls, [])

    def test_fresh_queries_reuse_the_fingerprint_during_the_ttl(self):
        """启动期多控件查询不得反复构造文件键；面板强刷另有覆盖。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            write_skill(root / '05资产管理SKILL', 'probe-one', stage='资产管理')
            reg = skill_registry.Registry(root=root)
            reg.scan(force=True)
            calls = []
            original = reg._file_cache_key
            def counted():
                calls.append(1)
                return original()
            with mock.patch.object(reg, '_file_cache_key', side_effect=counted):
                for _ in range(40):
                    reg.getById('probe-one')
            self.assertEqual(calls, [])

    def test_numbered_stage_directory_classifies_an_unlabelled_skill(self):
        """01—12 文件夹是归类依据，漏写 stage 不会让新 SKILL 从阶段配置中消失。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            path = write_skill(root / '07分镜定稿SKILL', 'prompt-render-probe', stage='')
            reg = skill_registry.Registry(root=root)
            item = reg.getById('prompt-render-probe')
            self.assertEqual(item.stage, 'final')
            self.assertEqual([skill.name for skill in reg.getByStage('final')], ['prompt-render-probe'])
            self.assertEqual(reg.problems(), [])

    def test_a_temp_program_does_not_blank_out_the_default_registry(self):
        """第 44 期：注册表按目录分开缓存。

        原先只留「最后用到的那一份」：谁先拿一个临时 program 调一次 default_registry()，
        之后不带参数的那一版（＝程序目录）就跟着变成临时的那一份空的——界面勾选框、阶段
        默认值、编排器找 SKILL 会整片空掉。自检里就是这么串起来的：一个进程跑好几路工作单元，
        临时目录先出现，后面几路就红了。
        """
        real = skill_registry.default_registry()
        real.scan(force=True)
        self.assertEqual(real.count(), 73)
        with tempfile.TemporaryDirectory() as td:
            program = Path(td) / '程序'
            write_skill(program / 'skills' / '05资产管理SKILL', 'probe-one', stage='资产管理')
            other = skill_registry.default_registry(program)
            self.assertEqual([item.name for item in other.getAll()], ['probe-one'])
            self.assertIs(skill_registry.default_registry(), real, '不带参数仍是程序目录那一份')
            self.assertEqual(skill_registry.default_registry().count(), 73)
        self.assertEqual([item.name for item in skill_registry.default_registry().getByStage('keyframe')],
                         ['firstframe-auto-fill', 'firstframe-batch', 'firstframe-quality',
                          'firstframe-retry', 'firstframe-thumbnail', 'pipeline-keyframe'])


    def test_broken_skill_is_reported_not_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            write_skill(root, 'bad-stage', stage='没这个阶段')
            text = (root / 'bad-stage.skill.md').read_text(encoding='utf-8')
            stage_dir = root / '05资产管理SKILL'
            stage_dir.mkdir(parents=True)
            (stage_dir / 'self-dep.skill.md').write_text(
                text.replace('name: bad-stage', 'name: self-dep')
                    .replace('stage: 没这个阶段', 'stage: 资产管理')
                    .replace('dependsOn: []', 'dependsOn: [self-dep]'), encoding='utf-8')
            reg = skill_registry.Registry(root=root)
            problems = '；'.join(reg.problems())
            self.assertIn('阶段', problems)
            self.assertIn('自己', problems)

    def test_capability_outside_the_list_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            path = write_skill(root / '05资产管理SKILL', 'weird-cap', stage='资产管理')
            path.write_text(path.read_text(encoding='utf-8').replace(
                'capabilities: [structured-output]', 'capabilities: [telepathy]'), encoding='utf-8')
            reg = skill_registry.Registry(root=root)
            self.assertIn('telepathy', '；'.join(reg.problems()))


class BudgetTests(unittest.TestCase):
    def test_reservations_survive_restart_and_unknown_does_not_refund(self):
        with tempfile.TemporaryDirectory() as td:
            budget = skill_budget.Budget(project=td, config={'images_per_project': 2})
            self.assertTrue(budget.reserve('one', 'images', 2)[0])
            again = skill_budget.Budget(project=td, config={'images_per_project': 2})
            self.assertFalse(again.reserve('two', 'images', 1)[0])
            again.finish('one')
            self.assertEqual(again.remaining('images'), 0)
            again.finish('one', completed=True)
            again.finish('one', completed=True)
            self.assertEqual(again.used('images'), 2)

    def test_concurrent_budget_reservations_do_not_overspend(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as td:
            budgets = [skill_budget.Budget(project=td, config={'images_per_project': 1}) for _ in range(2)]
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda i: budgets[i].reserve(str(i), 'images')[0], range(2)))
            self.assertEqual(sum(results), 1)
            restored = skill_budget.Budget(project=td, config={'images_per_project': 1})
            self.assertEqual(restored.reserved('images'), 1)

    def test_not_submitted_releases_but_duplicate_id_stays_blocked(self):
        budget = skill_budget.Budget(config={'images_per_project': 1})
        self.assertTrue(budget.reserve('one', 'images')[0])
        budget.finish('one', not_submitted=True)
        self.assertEqual(budget.remaining('images'), 1)
        self.assertFalse(budget.reserve('one', 'images')[0])
        self.assertTrue(budget.reserve('two', 'images')[0])

    def test_corrupt_budget_does_not_reset_to_free_quota(self):
        with tempfile.TemporaryDirectory() as td:
            path = skill_budget.budget_path(td); path.parent.mkdir(parents=True)
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):skill_budget.Budget(project=td)

    def test_defaults_are_the_three_hard_limits(self):
        self.assertEqual(skill_budget.limits(), {'tokens_per_day': 2000000, 'images_per_project': 200,
                                                 'videos_per_project': 100})

    def test_config_can_override_only_those_three(self):
        got = skill_budget.limits({'images_per_project': 5, '别的': 7, 'videos_per_project': 'x'})
        self.assertEqual(got['images_per_project'], 5)
        self.assertEqual(got['videos_per_project'], 100)
        self.assertNotIn('别的', got)

    def test_images_counter_and_check(self):
        with tempfile.TemporaryDirectory() as td:
            budget = skill_budget.Budget(project=td, config={'images_per_project': 2})
            self.assertEqual(budget.used('images'), 0)
            self.assertEqual(budget.check('images', 1), (True, '生图（每项目） 还剩 2'))
            budget.spend('images', 2)
            self.assertFalse(budget.check('images', 1)[0])
            self.assertTrue(budget.over('images'))
            again = skill_budget.Budget(project=td, config={'images_per_project': 2})
            self.assertEqual(again.used('images'), 2)

    def test_tokens_are_read_from_the_pet_ledger(self):
        import pet_llm
        ledger = pet_llm.Ledger()
        ledger.record('deepseek-v4-flash', {'prompt_tokens': 10, 'completion_tokens': 5})
        budget = skill_budget.Budget(ledger=ledger)
        self.assertEqual(budget.used('tokens'), 15)
        self.assertEqual(budget.limit('tokens'), 2000000)
        budget.spend('tokens', 3)             # Token 那本自己不记：还是台账说了算
        self.assertEqual(budget.used('tokens'), 15)
class StageConfigTests(unittest.TestCase):
    def test_get_reuses_project_configuration_until_a_write_invalidates_it(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'video', model='qwen-max', skills=[])
            with mock.patch.object(stage_config, 'read_json', wraps=stage_config.read_json) as read:
                self.assertEqual(stage_config.get(td, 'video')['model'], 'qwen-max')
                self.assertEqual(stage_config.get(td, 'video')['model'], 'qwen-max')
                self.assertLessEqual(read.call_count, 2)
            stage_config.put(td, 'video', model='gpt-4o', skills=[])
            self.assertEqual(stage_config.get(td, 'video')['model'], 'gpt-4o')
    def test_script_stage_defaults_include_the_imported_script_skills(self):
        """01 阶段总入口与常规 SKILL 都会自动成为剧本准备阶段的默认可选项。"""
        with tempfile.TemporaryDirectory() as td:
            entry = stage_config.get(td, 'script')
            expected = [item.name for item in skill_registry.default_registry().getByStage('script')
                        if not item.deprecated]
            self.assertEqual(entry['skills'], expected)

    def test_default_entry_is_auto_plus_every_active_stage_skill(self):
        with tempfile.TemporaryDirectory() as td:
            entry = stage_config.get(td, 'keyframe')
            self.assertEqual(entry['model'], 'auto')
            self.assertEqual(entry['skills'], ['firstframe-auto-fill', 'firstframe-batch', 'firstframe-quality',
                          'firstframe-retry', 'firstframe-thumbnail', 'pipeline-keyframe'])

    def test_put_get_round_trip_cleans_junk(self):
        """第 43 期：模型那一栏不再照写死的清单过滤——池子是权威，存进来的 id 原样留着。

        抹成「自动」等于把用户的选择吃掉（模型管理里新加的模型就是这么丢的）；真发不出去时由
        路由说清「指定的模型 X 现在用不了」，而不是在这儿悄悄改掉。SKILL 那一栏照旧去重去假。
        """
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'video', model='我的本地模型',
                             skills=['video-quality-check', 'video-quality-check', '不存在'])
            entry = stage_config.get(td, 'video')
            self.assertEqual(entry['model'], '我的本地模型')
            self.assertEqual(entry['skills'], ['video-quality-check'])
            self.assertEqual(stage_config.load(td)['video']['skills'], ['video-quality-check'])

    def test_get_syncs_missing_and_misfiled_skills_to_their_directory_stage(self):
        """失效选择保留供发送阻断；重分类的有效 SKILL 仍归入正确阶段。"""
        with tempfile.TemporaryDirectory() as td:
            stage_config.path(td).write_text(json.dumps({
                'storyboard': {'model': 'auto', 'skills': ['storyboard-prompt-render', 'gone-skill']}
            }, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(stage_config.get(td, 'storyboard')['skills'], [])
            self.assertEqual(stage_config.get(td, 'final')['skills'], ['storyboard-prompt-render'])
            saved = json.loads(stage_config.path(td).read_text(encoding='utf-8'))
            self.assertEqual(saved['storyboard']['skills'], ['gone-skill'])
            import workflow_settings
            with self.assertRaisesRegex(ValueError, '已勾选的 SKILL 未加载'):
                workflow_settings.validate_selected_skills(td, 'storyboard')
            self.assertEqual(saved['final']['skills'], ['storyboard-prompt-render'])

    def test_reset_restores_the_default(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'audio', model='qwen-max', skills=[])
            self.assertEqual(stage_config.get(td, 'audio')['skills'], [])
            stage_config.reset(td, 'audio')
            entry = stage_config.get(td, 'audio')
            self.assertEqual(entry['model'], 'auto')
            self.assertEqual(entry['skills'], ['pipeline-audio-subtitle', 'subtitle-auto-align',
                          'subtitle-format-export', 'voice-emotion-check', 'voice-tts-synthesis'])

    def test_legacy_skill_id_is_migrated_to_its_active_replacement(self):
        """合并只收敛执行入口；旧项目写过的 id 仍能无感读回。"""
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'audio', skills=['voice-multi-character', 'voice-tts-synthesis'])
            self.assertEqual(stage_config.get(td, 'audio')['skills'], ['voice-tts-synthesis'])

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                stage_config.get(td, '没有这个阶段')

    def test_problems_finds_a_broken_file(self):
        """第 28 期：配置读不出来也要报——面板惄惄退回默认值，用户会以为自己的勾选丢了。"""
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_config.problems(td), [], '还没有配置＝没问题')
            stage_config.path(td).write_text('{不是 JSON', encoding='utf-8')
            found = stage_config.problems(td)
            self.assertTrue(found, '坏文件要报出来')
            self.assertIn(stage_config.CONFIG_NAME, found[0])
            stage_config.path(td).write_text('[不是对象]', encoding='utf-8')
            self.assertTrue(stage_config.problems(td), '形状不对也要报')
            stage_config.path(td).unlink()
            self.assertEqual(stage_config.problems(td), [], '删掉了就当没配置过')

    def test_program_wide_model_api_is_absent(self):
        """用户决策：阶段模型不再有程序级兜底。"""
        names = vars(stage_config)
        self.assertNotIn('set_' + 'global' + '_model', names)
        self.assertNotIn('global' + '_model', names)


class RouterTests(unittest.TestCase):
    def skill(self, name='firstframe-batch', **overrides):
        real = skill_registry.default_registry().getById(name)
        fields = {key: getattr(real, key) for key in (
            'name', 'displayName', 'stage', 'capabilities', 'preferredModels', 'fallbackModels',
            'tools', 'dependsOn', 'conflictsWith', 'parallelizable', 'paid')}
        fields.update(overrides)
        return FakeSkill(**fields)

    def router(self, budget=None):
        return model_router.ModelRouter(adapters=[FakeAdapter()], budget=budget)

    def test_choices_are_the_five_panel_options(self):
        self.assertEqual([value for value, _label in model_router.CHOICES],
                         ['auto', 'gpt-4o', 'qwen-max', 'deepseek-v4-pro', 'deepseek-v4-flash'])
        self.assertEqual(model_router.label_of('deepseek-v4-flash'), 'DeepSeek Flash')
        self.assertEqual(model_router.label_of('没登记'), '没登记')

    def test_spend_kind_follows_the_tools(self):
        self.assertEqual(model_router.spend_kind(self.skill('firstframe-batch')), 'images')
        self.assertEqual(model_router.spend_kind(self.skill('video-batch-submit')), 'videos')
        self.assertEqual(model_router.spend_kind(self.skill('script-structured-generation')), 'tokens')

    def test_override_is_single_then_project(self):
        router = self.router()
        self.assertEqual(router.override({'model': 'fake-cheap', 'projectModel': 'fake-smart'})[0], 'fake-cheap')
        self.assertEqual(router.override({'projectModel': 'fake-smart', 'legacyDefault': 'fake-cheap'})[0], 'fake-smart')
        self.assertEqual(router.override({'legacyDefault': 'fake-smart'}), ('', ''))
        self.assertEqual(router.override({'model': 'auto'}), ('', ''))

    def test_select_uses_the_skill_preference_first(self):
        item = self.skill('firstframe-batch', preferredModels=['fake-smart'], capabilities=[], fallbackModels=[])
        choice = self.router().select(item, {})
        self.assertTrue(choice.ok)
        self.assertEqual(choice.model, 'fake-smart')
        self.assertIn('preferredModels', choice.reason)

    def test_select_matches_a_capability_when_nothing_is_preferred(self):
        item = self.skill('firstframe-batch', preferredModels=['没有这个'], capabilities=['reasoning'],
                          fallbackModels=['fake-cheap'])
        choice = self.router().select(item, {})
        self.assertEqual(choice.model, 'fake-smart')
        self.assertIn('reasoning', choice.reason)

    def test_select_falls_back_then_gives_up_with_a_reason(self):
        item = self.skill('firstframe-batch', preferredModels=[], capabilities=[], fallbackModels=['fake-cheap'])
        self.assertEqual(self.router().select(item, {}).model, 'fake-cheap')
        choice = model_router.ModelRouter(adapters=[]).select(item, {})
        self.assertFalse(choice.ok)
        self.assertIn('没有可用模型', choice.reason)

    def test_select_stops_when_the_budget_is_gone(self):
        with tempfile.TemporaryDirectory() as td:
            budget = skill_budget.Budget(project=td, config={'images_per_project': 1})
            budget.spend('images', 1)
            item = self.skill('firstframe-batch', preferredModels=['fake-smart'])
            choice = self.router(budget=budget).select(item, {})
            self.assertFalse(choice.ok)
            self.assertIn('生图', choice.reason)

    def test_model_is_not_bound_to_the_skill(self):
        """SKILL 不绑定模型：同一份 SKILL，用户三级覆盖换谁就是谁。"""
        item = self.skill('script-structured-generation')
        router = self.router()
        self.assertEqual(router.select(item, {'model': 'fake-cheap'}).model, 'fake-cheap')
        self.assertEqual(router.select(item, {'projectModel': 'fake-smart'}).model, 'fake-smart')


class ToolTests(unittest.TestCase):
    def test_every_tool_in_the_registry_is_known(self):
        reg = skill_registry.default_registry()
        names = [tool for item in reg.getAll() for tool in item.tools]
        self.assertEqual(skill_tools.missing(names), [])
        self.assertTrue(skill_tools.ready_names())
        self.assertTrue(skill_tools.page_names())

    def test_page_tool_says_which_page(self):
        with self.assertRaises(skill_tools.ToolNeedsPage) as ctx:
            skill_tools.call('firstframe.batchGenerate', {'project': '.'})
        self.assertIn('首帧管理', ctx.exception.title())
        self.assertEqual(skill_tools.status_of('firstframe.batchGenerate'), 'page')

    def test_missing_input_is_not_a_missing_tool(self):
        with self.assertRaises(skill_tools.ToolNeedsInput):
            skill_tools.call('storyboard.validate', {})

    def test_unknown_tool_is_reported(self):
        self.assertEqual(skill_tools.status_of('没有这个工具'), 'missing')
        with self.assertRaises(skill_tools.ToolMissing):
            skill_tools.call('没有这个工具', {})

    def test_ready_tools_actually_run(self):
        with tempfile.TemporaryDirectory() as td:
            episode = {'episode_id': 'EP001', 'title': 'T',
                       'shots': [{'id': 'SH001', 'title': '镜头', 'duration': 4, 'characters': [],
                                  'location': 'LOC', 'frame': 'frames/SH001.png', 'video_prompt': '画面',
                                  'frame_prompt': '窗边的猫', 'dialogue': []}]}
            report = skill_tools.call('storyboard.validate', {'project': td, 'episode': episode})
            self.assertTrue(report['ok'], report)
            self.assertEqual(report['shot_count'], 1)
            self.assertTrue(skill_tools.call('asset.copyrightFilter', {'project': td, 'episode': episode})['ok'])
            manifest = skill_tools.call('delivery.exportManifest', {'project': td, 'episode': episode})
            self.assertTrue(Path(manifest['manifest']).is_file())
            self.assertTrue(skill_tools.call('subtitle.align', {'project': td, 'episode': episode})['ok'])

    def test_injected_replacements_win(self):
        calls = []
        context = {'tools': {'storyboard.validate': lambda ctx: calls.append(ctx) or {'ok': True,
                                                                                     'shot_count': 7}}}
        out = skill_tools.call('storyboard.validate', context)
        self.assertEqual(out['shot_count'], 7)
        self.assertEqual(len(calls), 1)
class OrchestratorTests(unittest.TestCase):
    def orchestrator(self, **kwargs):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        return skill_orchestrator.default_orchestrator(project=holder.name, **kwargs)

    def test_expand_pulls_dependencies_in_stage_order(self):
        orch = self.orchestrator()
        names = orch.expand(['storyboard-pacing-check'])
        self.assertEqual(names, ['script-structured-generation', 'storyboard-pacing-check',
                                 'storyboard-shot-generation'])

    def test_build_dag_layers_are_topological(self):
        orch = self.orchestrator()
        dag = orch.buildDAG(orch.expand(['edit-multi-format-export']))
        self.assertEqual(dag['problems'], [])
        placed = {}
        for index, layer in enumerate(dag['layers']):
            for name in layer:
                placed[name] = index
        for name, index in placed.items():
            for dep in orch.skill(name).dependsOn:
                if dep in placed:
                    self.assertLess(placed[dep], index, '%s 比它的依赖先跑' % name)

    def test_build_dag_reports_a_cycle_instead_of_hanging(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '05资产管理SKILL'
            write_skill(stage_dir, 'ring-a', stage='资产管理', depends='ring-b')
            write_skill(stage_dir, 'ring-b', stage='资产管理', depends='ring-a')
            orch = skill_orchestrator.Orchestrator(registry=skill_registry.Registry(root=root))
            dag = orch.buildDAG(['ring-a', 'ring-b'])
            self.assertEqual(len(dag['layers']), 1)
            self.assertIn('成环', '；'.join(dag['problems']))

    def test_validate_catches_unknown_conflict_and_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            stage_dir = root / '05资产管理SKILL'
            write_skill(stage_dir, 'pair-a', stage='资产管理', conflicts='pair-b')
            write_skill(stage_dir, 'pair-b', stage='资产管理')
            reg = skill_registry.Registry(root=root)
            orch = skill_orchestrator.Orchestrator(registry=reg)
            self.assertIn('不认识的 SKILL', '；'.join(orch.validate(['没有这个'])['errors']))
            self.assertIn('互斥', '；'.join(orch.validate(['pair-a', 'pair-b'])['errors']))
            self.assertTrue(orch.validate(['pair-a', 'pair-b'])['missing_deps'] == [])

    def test_validate_writes_a_budget_event_when_the_quota_is_gone(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe('budget.exceeded', seen.append)
        budget = skill_budget.Budget(config={'images_per_project': 1})
        budget.spend('images', 1)
        orch = skill_orchestrator.Orchestrator(budget=budget, bus=bus)
        check = orch.validate(['firstframe-batch'], {})
        self.assertFalse(check['ok'])
        bus.pump()
        self.assertEqual([item['budget'] for item in seen], ['images'])

    def test_run_reports_page_and_input_without_calling_them_failures(self):
        orch = self.orchestrator()
        run = orch.run(['storyboard-pacing-check'], {'project': '.'})
        self.assertTrue(run['ok'])
        self.assertEqual(run['failed'], [])
        statuses = set(row['status'] for row in run['results'])
        self.assertTrue({'page', 'input'} & statuses, statuses)
        self.assertIn('要您回页面', run['text'])

    def test_before_step_persists_a_recoverable_checkpoint(self):
        orch = self.orchestrator()
        stage = type('Stage', (), {'id': 'assets'})()
        step = type('Step', (), {'index': 3, 'name': '生成缺失的正典板'})()

        checkpoint = orch.before_step(stage, step)
        saved = json.loads((Path(orch.project) / 'sanhu_project_status.json').read_text(encoding='utf-8'))

        self.assertEqual(checkpoint['stage'], 'assets')
        self.assertEqual(checkpoint['step'], 3)
        self.assertEqual(checkpoint['completed_steps'], [1, 2])
        self.assertEqual(saved['checkpoint'], checkpoint)

    def test_execute_writes_checkpoint_before_running_a_skill(self):
        orch = self.orchestrator()
        orch.execute('asset-visual-rank', {'project': '.'})
        saved = json.loads((Path(orch.project) / 'sanhu_project_status.json').read_text(encoding='utf-8'))

        self.assertEqual(saved['current_stage'], 'assets')
        self.assertEqual(saved['checkpoint']['stage'], 'assets')
        self.assertGreaterEqual(saved['checkpoint']['step'], 1)

    def test_recovery_broadcasts_and_continues_from_interrupted_step(self):
        orch = self.orchestrator()
        stage = type('Stage', (), {'id': 'assets'})()
        step = type('Step', (), {'index': 3, 'name': '生成缺失的正典板'})()
        orch.before_step(stage, step)
        messages = []

        resumed = orch.recover_from_checkpoint(lambda _prompt: '继续', messages.append)

        self.assertEqual(resumed, 3)
        self.assertEqual(messages[0], '【恢复】检测到中断')
        self.assertIn('步骤 3/4：生成缺失的正典板', messages[1])
        self.assertIn('[继续/跳过/重做]', messages[2])
        resumed_skill = orch.registry.getByStage('assets')[resumed - 1].name
        orch.run([resumed_skill], {'project': '.'})
        saved = json.loads((Path(orch.project) / 'sanhu_project_status.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['checkpoint']['step'], 3)

    def test_paid_skill_waits_for_a_nod(self):
        orch = self.orchestrator()
        run = orch.run(['firstframe-batch'], {'project': '.', 'at': NOON})
        self.assertEqual([row['skill'] for row in run['pending']], ['firstframe-batch'])
        self.assertFalse(run['pending'][0]['queued'])
        self.assertIn('要花钱', run['pending'][0]['detail'])
        self.assertIn('等您点头', run['text'])

    def test_quiet_hours_queue_the_confirmation_instead_of_bubbling(self):
        """23:00-07:00 免打扰：付费确认先排队，不弹气泡。"""
        bus = pet_bus.Bus()
        bubbles = []
        bus.subscribe('notify.aggregate', lambda item: bubbles.append(item['text']))
        orch = self.orchestrator(bus=bus)
        run = orch.run(['firstframe-batch'], {'project': '.', 'at': MIDNIGHT})
        self.assertTrue(run['pending'][0]['queued'])
        self.assertIn('排上队', orch.pending_confirmations()[0]['text'])
        bus.pump()
        self.assertFalse([text for text in bubbles if '要花钱' in text])

    def test_confirm_all_approves_and_the_next_run_goes_through(self):
        orch = self.orchestrator()
        orch.run(['firstframe-batch'], {'project': '.', 'at': NOON})
        rows = orch.confirm_all(True)
        self.assertEqual([row['skill'] for row in rows], ['firstframe-batch'])
        self.assertEqual(orch.pending_confirmations(), [])
        self.assertIn('firstframe-batch', orch.approved)
        again = orch.run(['firstframe-batch'], {'project': '.', 'at': NOON})
        self.assertEqual(again['pending'], [])
        self.assertTrue(again['ok'])

    def test_retry_only_retries_the_failures(self):
        calls = []

        def boom(ctx):
            calls.append('boom')
            raise RuntimeError('这一步炸了')

        orch = self.orchestrator()
        first = orch.run(['firstframe-batch'], {'project': '.', 'confirm': True, 'at': NOON,
                                                'tools': {'firstframe.batchGenerate': boom}})
        self.assertIn('firstframe-batch', first['failed'])
        self.assertEqual(calls, ['boom'])
        again = first.retry_failed({'project': '.', 'confirm': True, 'at': NOON, 'tools': {}})
        self.assertEqual(again['retried'], ['firstframe-batch'])
        self.assertEqual(again['failed'], [])
        # 重跑时依赖会连带展开（幂等），但那一步坏活只重试了一次
        self.assertEqual(calls, ['boom'])

    def test_run_reports_events_for_the_ui(self):
        bus = pet_bus.Bus()
        kinds = []
        bus.subscribe('*', lambda item: kinds.append(item['kind']))
        self.orchestrator(bus=bus).run(['storyboard-pacing-check'], {'project': '.'})
        bus.pump()
        self.assertIn('stage.started', kinds)
        self.assertIn('notify.aggregate', kinds)
        self.assertNotIn('stage.completed', kinds,
                         '分镜仅在 JSON 已生成、校验并采用后由自动采用轮询完成阶段')

    def test_skill_done_without_a_verified_artifact_never_completes_a_stage(self):
        """工具返回 done 不得把资产等后续阶段误报为完成。"""
        bus = pet_bus.Bus()
        kinds = []
        bus.subscribe('*', lambda item: kinds.append(item['kind']))
        self.orchestrator(bus=bus).run(['firstframe-batch'],
                                       {'project': '.', 'confirm': True, 'at': NOON})
        bus.pump()
        self.assertNotIn('stage.completed', kinds)

    def test_describe_is_human_readable(self):
        orch = self.orchestrator()
        text = orch.describe({'results': [{'skill': 'a', 'name': '结构化剧本生成', 'status': 'done'},
                                          {'skill': 'b', 'name': '镜头链生成', 'status': 'failed'}],
                              'errors': [], 'problems': []})
        self.assertIn('成了 1 个', text)
        self.assertIn('结构化剧本生成', text)
        self.assertIn('没成 1 个', text)

def _beijing_hour_stamp(stamp, hour):
    """北京时间 hour 点的真实时间戳（beijing() 给的是 +8h 的平移值，要减回来）。"""
    import pet_llm
    local = pet_llm.beijing(stamp)
    return local - (local % 86400) + hour * 3600 - 8 * 3600


NOON = 1789900000.0                          # 随便一个正向时间戳（正午前后）
MIDNIGHT = _beijing_hour_stamp(NOON, 1)      # 北京时间 01:00：落在免打扰窗口里


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        class Fake(object):
            pass

        self.desktop = Fake()
        self.desktop.win = self.win
        self.desktop.root = Path(self.tmp.name) / 'p'
        self.desktop.root.mkdir(parents=True, exist_ok=True)
        # 预设落在 program 下：自检给一个临时程序目录，
        # 别往真机的 配置\SKILL\ 里写试验用的东西（上一版就把一个厫名预设写进去了）。
        self.desktop.app = Path(self.tmp.name) / '程序'
        self.desktop.app.mkdir(parents=True, exist_ok=True)
        self.desktop.status = self.tk.StringVar(master=self.win, value='')

    def test_imported_package_hint_only_appears_for_api_models(self):
        """外部包总入口在 API 模型下必须明确提示，桌面与普通 SKILL 均不提示。"""
        imported = skill_registry.Skill({'name': 'external-package',
                                         skill_registry.IMPORTED_PACKAGE_FLAG: True})
        normal = skill_registry.Skill({'name': 'ordinary-skill'})
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        panel.skills = [imported]
        panel.vars = {imported.name: self.tk.BooleanVar(master=self.win, value=True)}
        # R2862：面板模型选择器已删，model_id() 改读项目配置；提示逻辑不变。
        stage_config.put(self.desktop.root, 'script', model='deepseek-v4-pro')
        self.assertIn('外部包总入口', panel.refresh_external_package_hint())
        self.assertIn('外部包总入口', panel.external_package_hint.cget('text'))
        stage_config.put(self.desktop.root, 'script', model='chatgpt-desktop')
        self.assertEqual(panel.refresh_external_package_hint(), '')
        panel.skills = [normal]
        stage_config.put(self.desktop.root, 'script', model='deepseek-v4-pro')
        self.assertEqual(panel.refresh_external_package_hint(), '')

    def test_stage_panel_uses_compact_aligned_rows_and_short_hints(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        def descendants(widget):
            return [child for item in widget.winfo_children()
                    for child in [item] + descendants(item)]
        labels = [child for child in descendants(panel) if str(child.winfo_class()) == 'TLabel']
        widths = {label.cget('text'): label.cget('width') for label in labels}
        # R2862：预设／总控／模型选择行已删，只剩 SKILL 标签与制作锁入口。
        self.assertNotIn('预设', widths)
        self.assertNotIn('厂商', widths, '厂商／模型下拉已拆到按钮右侧的两级选择器')
        self.assertEqual(widths['SKILL'], 10)
        self.assertIn('确认保存本页', panel.state.cget('text'))
        self.assertEqual(skill_panel.EXTERNAL_PACKAGE_API_HINT,
                         '外部包总入口：桌面引擎可完整执行；API 仅传入入口。')

    def test_stage_panel_controls_and_dropdowns_share_the_standard_font(self):
        """标签、勾选、分组标题及下拉显示/弹出项不可各走一套字体。"""
        from tkinter import ttk
        from ui_tokens import COMBOBOX_FONT, FONTS
        from ui_widgets import setup_styles

        setup_styles(self.win)
        style = ttk.Style(self.win)
        expected = style.lookup('TCombobox', 'font')
        self.assertEqual(FONTS['body'], FONTS['caption'])
        self.assertEqual(COMBOBOX_FONT, FONTS['body'])
        self.assertTrue(expected)
        for name in ('TLabel', 'TCheckbutton', 'TLabelframe.Label'):
            self.assertEqual(style.lookup(name, 'font'), expected, name)

    def test_stage_of_page_covers_the_production_pages(self):
        self.assertEqual([skill_panel.stage_of_page(index) for index in range(len(pet_bus.STAGES))],
                         list(pet_bus.STAGES))
        self.assertEqual(skill_panel.stage_of_page(len(pet_bus.STAGES)), '')

    def test_stage_for_accepts_legacy_flow_names(self):
        self.assertEqual(skill_panel.stage_for('writing'), 'script')
        self.assertEqual(skill_panel.stage_for('frames'), 'keyframe')
        self.assertEqual(skill_panel.stage_for('audio'), 'audio')
        self.assertEqual(skill_panel.stage_for('没有这个'), '没有这个')

    def test_the_dropdown_keeps_all_saved_api_models_for_every_stage(self):
        """统一配置保存的模型不因能力标签被隐藏，阶段配置都应能手动选择。"""
        import stage_model_picker
        previs = stage_model_picker.StageModelPicker(self.win, self.desktop, 'previs')
        data = model_pool.upsert(model_pool.raw(self.desktop.app),
                                 {'label': 'GPT-6', 'model': 'gpt-6',
                                  'base_url': 'https://api.openai.com/v1',
                                  'capabilities': ['vision']})
        model_pool.store(data, self.desktop.app)
        skill_panel.refresh_all()
        displays = previs.labels()
        self.assertIn('GPT-6', displays,
                      '保存后应立刻刷新已打开选择器的模型目录（仅模型名，不带供应商前缀）')
        for provider, options in previs.groups.items():
            for _model_id, label in options:
                self.assertNotIn('%s · %s' % (provider, label), displays,
                                 'REQ-S01-82：选择器项只显示模型名称')
        previs.model.set('GPT-6')
        previs.choose_model()
        self.assertEqual(stage_config.get(self.desktop.root, 'previs')['model'], 'gpt-6',
                         '选好立即写进项目配置')
        previs.destroy()

    def test_a_custom_provider_name_is_the_stage_vendor_group(self):
        """阶段配置的「厂商」一级目录应使用 API 统一配置填写的自定义 Provider。"""
        data = model_pool.upsert(model_pool.raw(self.desktop.app),
                                 {'label': '我的 GPT', 'model': 'my-gpt',
                                  'provider': '我的厂商'})
        model_pool.store(data, self.desktop.app)
        groups = skill_panel.grouped_model_choices(self.desktop, 'script')
        self.assertIn('我的厂商', groups)
        self.assertIn(('my-gpt', '我的 GPT'), groups['我的厂商'])

    def test_stage_button_text_is_fixed_and_picker_follows_it(self):
        """R2942：页面级「阶段配置」按钮＋模型下拉框已删；模型选择收进共享输入框的
        StageModelPicker 下拉框按钮——按钮文案即当前模型名，点击弹菜单列表而非模态窗。"""
        import stage_model_picker
        from tkinter import ttk
        stage_config.put(self.desktop.root, 'script', model='deepseek-v4-flash')
        self.assertFalse(hasattr(skill_panel, 'stage_button'), '页面级阶段配置按钮工厂已删')
        self.assertFalse(hasattr(stage_model_picker, 'stage_button_for'), '按钮工厂已删')
        self.assertFalse(hasattr(stage_model_picker, 'attach_stage_pickers'), '选择器补挂入口已删')
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'script')
        self.addCleanup(picker.destroy)
        picker.pack(side='left')
        self.assertIsInstance(picker.models, ttk.Button, '模型选择器是无外框下拉按钮，不是弹窗')
        self.assertEqual(picker.model_id(), 'deepseek-v4-flash')
        self.assertIn('DeepSeek', picker.model.get())
        self.assertNotIn(' · ', picker.model.get(),
                         'REQ-S01-82：选择器当前项只显示模型名称，不带供应商前缀')

    def test_model_picker_popup_renders_rows_and_stays_on_screen(self):
        """R3111 回归：徽标行 padx 误用元组曾让 ``_fill_popup`` 抛 TclError——
        浮层残留在默认位置（屏幕顶）且内容空白。开层必须建出模型行、几何落在屏内。"""
        import stage_model_picker
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'script')
        self.addCleanup(picker.destroy)
        self.addCleanup(picker._close_popup)
        picker.pack(side='left')
        # 注入带推理徽标的假条目：徽标 Label 的 padx 是本次崩溃点，真实空池没有徽标行。
        picker._items = [('m1', '模型甲'), ('m2', '模型乙')]
        picker._by_display = {'模型甲': 'm1', '模型乙': 'm2'}
        picker._capable = {'m1'}
        picker.model.set('模型甲')
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.update()
        picker.toggle_popup()
        self.win.update_idletasks()
        self.win.update()
        top = picker._popup
        self.assertIsNotNone(top)
        self.assertTrue(top.winfo_exists())

        def labels(widget):
            out = []
            for child in widget.winfo_children():
                if child.winfo_class() == 'Label':
                    out.append(child)
                out.extend(labels(child))
            return out

        texts = {str(label.cget('text')) for label in labels(top)}
        self.assertIn('模型甲', texts)
        self.assertIn('模型乙', texts)
        self.assertTrue(any(text.startswith('推理·') for text in texts),
                        '推理徽标行必须渲染出来')
        screen_h = self.win.winfo_screenheight()
        self.assertGreater(top.winfo_reqheight(), 0)
        self.assertLess(top.winfo_reqheight(), screen_h)
        self.assertGreaterEqual(top.winfo_rooty(), 0)
        self.assertLessEqual(top.winfo_rooty() + top.winfo_height(), screen_h + 2)

    def test_add_menu_model_entry_opens_the_manager_and_reverts(self):
        """REQ-S01-91：「添加模型…」移到共享输入框「＋」下拉；模型池仍只有模型管理
        这一扇门，模型选择器浮层不再保留添加尾项。"""
        import desktop_shared_input, pet_models_ui, stage_model_picker
        opened = []
        pet = object()
        self.desktop.pet = pet
        real = pet_models_ui.open_manager
        pet_models_ui.open_manager = lambda target: opened.append(target)
        self.addCleanup(setattr, pet_models_ui, 'open_manager', real)
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'keyframe')
        self.addCleanup(picker.destroy)
        spec = picker._popup_spec()
        self.assertFalse(any(row['kind'] == 'add' for row in spec),
                         '模型浮层不再保留「+ 添加模型…」尾项')
        box = desktop_shared_input.SharedStageInput(
            self.win, desktop=self.desktop, stage='keyframe',
            options={'on_send': None})
        self.addCleanup(box.destroy)
        box.pack()
        self.win.update_idletasks()
        picker.set_model('qwen-max')
        picker.choose_model()
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['model'], 'qwen-max')
        # 「＋」下拉的「添加模型…」走同一扇门，当前选择不被重置。
        box.open_add_menu()
        self.win.update_idletasks()
        rows = [w for w in _walk_widgets(box.add_panel)
                if isinstance(w, self.tk.Label)]
        labels = {str(w.cget('text')): w for w in rows}
        self.assertIn('添加模型…', labels)
        target = labels['添加模型…']
        # 合成真实单击（映射窗口＋控件中心坐标），与 test_cell_menu 同法。
        self.win.deiconify()
        self.win.update()
        x, y = target.winfo_width() // 2, target.winfo_height() // 2
        target.event_generate('<Button-1>', x=x, y=y,
                              rootx=target.winfo_rootx() + x,
                              rooty=target.winfo_rooty() + y)
        self.win.update()
        self.assertEqual(opened, [pet], '模型池只有模型管理这一扇门')
        self.assertEqual(picker.model_id(), 'qwen-max')

    def test_set_model_label_syncs_provider_and_model_by_display_name(self):
        """REQ-S01-80：目录条点某模型，按显示名把单级下拉切到同一模型，返回 model id；找不到或空值不改动。"""
        import stage_model_picker
        model_pool.upsert(model_pool.raw(self.desktop.app),
                          {'label': 'Qwen-Max', 'model': 'qwen-max',
                           'provider': '阿里云', 'key_env': 'X'})
        skill_panel.refresh_all()
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'keyframe')
        self.addCleanup(picker.destroy)
        # 命中：显示名一致 → 选择器切到该模型名（仅名称，不带供应商前缀），返回 model id
        self.assertEqual(picker.set_model_label('Qwen-Max'), 'qwen-max')
        self.assertEqual(picker.model_id(), 'qwen-max')
        self.assertEqual(picker.model.get(), 'Qwen-Max',
                         'REQ-S01-82：选择器当前项只显示模型名称')
        self.assertIn('qwen-max', picker._by_display.values())
        # 找不到的显示名：返回 None，当前选择不动
        before_model = picker.model.get()
        self.assertIsNone(picker.set_model_label('不存在的模型名'))
        self.assertEqual(picker.model.get(), before_model)
        # 空值/空白：返回 None，不动
        self.assertIsNone(picker.set_model_label(''))
        self.assertIsNone(picker.set_model_label('   '))

    def test_confirming_script_model_saves_and_refreshes_history_without_sending(self):
        window = tk.Toplevel(self.win)
        self.desktop.refresh_script_chat_for_selected_model = mock.Mock()
        stage_config.put(self.desktop.root, 'script', model='deepseek-v4-flash')
        panel = skill_panel.Panel(window, self.desktop, 'script')
        panel.confirm_button.invoke()
        self.desktop.refresh_script_chat_for_selected_model.assert_called_once_with()
        self.assertEqual(stage_config.get(self.desktop.root, 'script')['model'], 'deepseek-v4-flash')
        self.assertFalse(window.winfo_exists())

    def test_a_saved_api_model_is_not_dropped_by_capability_tags(self):
        """模型池里的 API 模型由用户决定用途，不能因能力标签自动改回自动。"""
        stage_config.put(self.desktop.root, 'previs', model='qwen-max')
        panel = skill_panel.Panel(self.win, self.desktop, 'previs')
        self.assertEqual(panel.model_id(), 'qwen-max')
        self.assertEqual(stage_config.get(self.desktop.root, 'previs')['model'], 'qwen-max')
        panel.destroy()

    def test_a_production_model_of_another_stage_is_dropped(self):
        """第 58 期第 5 条：预设可以跨阶段套用——别的阶段的生产模型套过来也要撤掉。"""
        stage_config.put(self.desktop.root, 'script', model='Seedream 5.0 Pro')
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.assertEqual(stage_config.get(self.desktop.root, 'script')['model'], 'auto')
        # R2862：面板模型选择器已删；跨阶段生产模型仍可经 stage_config 写入并被面板保留。
        stage_config.put(self.desktop.root, 'keyframe', model='Seedream 5.0 Pro')
        keyframe = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['model'], 'Seedream 5.0 Pro',
                         '首帧那一步自己的生产模型照旧选得中、存得下')
        panel.destroy(); keyframe.destroy()

    def test_a_hand_written_model_id_stays(self):
        """池里没有的 id 是用户自己填的：不替他判死，照旧留着。"""
        stage_config.put(self.desktop.root, 'previs', model='my-local-model')
        panel = skill_panel.Panel(self.win, self.desktop, 'previs')
        self.assertEqual(panel.model_id(), 'my-local-model')
        self.assertEqual(stage_config.get(self.desktop.root, 'previs')['model'], 'my-local-model')

    def test_saving_writes_project_skill_config(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        panel.vars['firstframe-quality'].set(False)
        panel.save()
        entry = stage_config.get(self.desktop.root, 'keyframe')
        # R2862：面板不再有模型选择器，保存时模型保持项目里已存的值（新项目即「自动」）。
        self.assertEqual(entry['model'], 'auto')
        self.assertEqual(entry['skills'], ['firstframe-auto-fill', 'firstframe-batch', 'firstframe-retry',
                                            'firstframe-thumbnail', 'pipeline-keyframe'])
        self.assertTrue(stage_config.path(self.desktop.root).is_file())

    def test_check_all_and_reset(self):
        """恢复默认入口回归；SKILL 批量操作仍是唯一的全选入口。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.assertFalse(hasattr(panel, 'check_all'), '面板上的「全选」接口一并删掉')
        self.assertTrue(hasattr(panel, 'reset_defaults'))
        # R2862：「恢复默认」按钮随预设行删除，reset_defaults 保留为可编程入口。
        self.assertFalse(hasattr(panel, 'restore_defaults_button'))
        for name in panel.vars:
            panel.vars[name].set(False)
        self.assertEqual(panel.selected(), [])
        panel.save()
        stage_config.reset(self.desktop.root, 'keyframe')
        panel.load()
        self.assertEqual(len(panel.selected()), 6)
        self.assertEqual(panel.model_id(), 'auto')

    def test_every_stage_has_a_panel(self):
        for stage in pet_bus.STAGES:
            panel = skill_panel.Panel(self.win, self.desktop, stage)
            expected = sum(not item.deprecated
                           for item in skill_registry.default_registry().getByStage(stage))
            self.assertEqual(len(panel.vars), expected, stage)
            self.assertEqual(panel.stage, stage)
            panel.destroy()

    def test_confirm_saves_current_page_configuration_and_is_in_bottom_action_bar(self):
        """确认在底部动作条，预设行不承担关闭窗口的责任。"""
        window = tk.Toplevel(self.win)
        stage_config.put(self.desktop.root, 'keyframe', model='qwen-max')
        panel = skill_panel.Panel(window, self.desktop, 'keyframe', compact=False)
        panel.pack()
        panel.vars['firstframe-quality'].set(False)
        self.win.update_idletasks()
        self.assertEqual(panel.confirm_button.master, panel.bottom_bar)
        row_children = list(panel.bottom_bar.winfo_children())
        self.assertFalse(any(child.cget('text') == '执行' for child in row_children
                             if str(child.winfo_class()) in ('TButton', 'Button')))
        self.assertEqual(panel.confirm_button.cget('text'), '确认并关闭')
        self.assertEqual(panel.confirm_button.pack_info()['side'], 'right')
        panel.confirm()
        entry = stage_config.get(self.desktop.root, 'keyframe')
        self.assertEqual(entry['model'], 'qwen-max')
        self.assertNotIn('firstframe-quality', entry['skills'])
        self.assertFalse(window.winfo_exists())

    def test_open_for_page_maps_the_page_to_its_stage(self):
        panel = skill_panel.open_for_page(self.desktop, pet_bus.STAGES.index('keyframe'))
        self.assertEqual(panel.stage, 'keyframe')
        panel.winfo_toplevel().destroy()

    def test_the_panel_shows_the_skill_markdown(self):
        """R2916：面板内联说明区已删除——说明改由共享输入框技能列表的悬停卡片提供。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.assertEqual([box.cget('text') for box in panel.registered_boxes.values()],
                         [skill_panel.registered_skill_checkbox_label(item) for item in panel.skills],
                         '勾选框必须显示注册表中的用户可见名称，不能退化为通用 SKILL.md 文件名')
        self.assertIsNone(panel.note_list, '说明目录已随 R2916 删除')
        self.assertIsNone(panel.note_text, '说明正文已随 R2916 删除')
        self.assertEqual(panel.note_items, [], '说明条目列表已清空')
        panel.destroy()

    def test_skill_notes_resize_with_the_stage_panel(self):
        """R2916：说明区已删除——窗口伸缩时阶段配置与底栏仍正确重排。"""
        self.win.deiconify()
        self.win.geometry('1200x800')
        self.win.update_idletasks()
        panel = skill_panel.open_for_page(self.desktop, 0)
        window = panel.winfo_toplevel()
        self.addCleanup(window.destroy)
        self.assertIsNone(panel.note_list, '说明目录已随 R2916 删除')
        self.assertIsNone(panel.note_text, '说明正文已随 R2916 删除')
        window.geometry('880x690')
        window.update()
        self.assertEqual(panel.reason.winfo_manager(), '')
        window.geometry('880x600')
        window.update()
        window.geometry('880x900')
        window.update()
        window.geometry('800x460')
        window.update()
        self.assertTrue(panel.bottom_bar.winfo_ismapped())
        window.destroy()

    def test_note_text_reads_the_body_and_survives_an_empty_skill(self):
        skill = skill_registry.default_registry().getById('firstframe-batch')
        text = skill_panel.note_text(skill)
        self.assertIn(str(skill.displayName), text)
        self.assertIn(str(skill.description), text)
        self.assertIn('## 说明', text, '正文（frontmatter 之后的 MD）要带上')
        self.assertEqual(skill_panel.note_text(None), '')

    def test_markdown_document_prefers_case_insensitive_sibling_readme(self):
        """README（任意大小写）始终优先于同目录 SKILL.md。"""
        with tempfile.TemporaryDirectory() as folder:
            skill = Path(folder) / 'SKILL.md'
            skill.write_text('# SKILL 说明', encoding='utf-8')
            (Path(folder) / 'readme.MD').write_text('# README 说明\n\n内容', encoding='utf-8')
            self.assertEqual(skill_panel.markdown_document(skill), '# README 说明\n\n内容')

    def test_markdown_document_falls_back_to_sibling_skill(self):
        """README 缺失时，说明区回退到同目录 SKILL.md。"""
        with tempfile.TemporaryDirectory() as folder:
            skill = Path(folder) / 'SKILL.md'
            skill.write_text('# SKILL 说明', encoding='utf-8')
            self.assertEqual(skill_panel.markdown_document(skill), '# SKILL 说明')

    def test_the_skill_manage_dropdown_has_the_single_grid_actions(self):
        """面板只有阶段注册网格；旧引擎档清单不再生成第二套勾选框。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        panel.layout_skill_controls()
        self.assertEqual(panel.flow_skill_label.cget('text'), 'SKILL')
        self.assertIs(panel.flow_skill_label.master, panel.skill_action_row, 'SKILL 标签必须留在操作栏左侧')
        self.assertEqual(list(panel.skill_action_row.winfo_children())[1].cget('values'),
                     skill_panel.MANAGE_LABELS)
        self.assertFalse(hasattr(panel, 'delete_skill_button'))
        self.assertEqual(panel.skill_action.get(), '请选择')
        with mock.patch.object(panel, 'check_all_skills') as check_all:
            self.assertEqual(panel.choose_skill_action(), '')
        check_all.assert_not_called()
        self.assertEqual([label for label, _path in skill_panel.flow_skill_choices('frames')],
                         ['图像生成'])
        self.assertFalse(hasattr(panel, 'flow_vars'))
        self.assertEqual(len(panel.registered_boxes), len(panel.skills))
        panel.destroy()

    def test_flow_skill_choices_ignore_codex_home(self):
        """固定预设候选只能来自程序内置 skills，不能随 CODEX_HOME 覆盖。"""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with mock.patch.dict(os.environ, {'CODEX_HOME': str(home)}):
                choices = skill_panel.flow_skill_choices('frames')
        self.assertTrue(choices)
        self.assertTrue(all(not Path(path).is_relative_to(home) for _label, path in choices))
        self.assertTrue(all(Path(path).is_relative_to(skill_panel.skill_registry.default_root())
                            for _label, path in choices))

    def test_the_skill_boxes_and_notes_follow_registry_order(self):
        """注册 SKILL 勾选沿用注册表返回顺序；R2916：说明区已删除（悬停卡片替代）。"""
        audio = skill_panel.Panel(self.win, self.desktop, 'audio')
        expected = [item.name for item in audio.registry.getByStage('audio') if not item.deprecated]
        self.assertEqual([item.name for item in audio.skills], expected)
        self.assertIsNone(audio.note_list, '说明目录已随 R2916 删除')
        self.assertEqual(audio.note_items, [], '说明条目列表已清空')
        self.assertEqual(list(audio.registered_boxes), expected,
                         '勾选框与说明目录必须使用同一注册表返回顺序')
        audio.destroy()
        delivery = skill_panel.Panel(self.win, self.desktop, 'delivery')
        self.assertEqual([item.name for item in delivery.skills],
                         [item.name for item in delivery.registry.getByStage('delivery') if not item.deprecated])
        delivery.destroy()

    def test_legacy_engine_skill_list_is_read_only_and_not_rendered(self):
        """旧引擎档仍可读取，但只会在提示词末尾消费，面板不再画第二套框。"""
        folder = Path(self.tmp.name) / '我的分镜'; folder.mkdir()
        mine = folder / 'SKILL.md'; mine.write_text('# 我的分镜', encoding='utf-8')
        skill_panel.set_flow_skills(self.desktop.root, 'frames', [str(mine)])
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        self.assertEqual(skill_panel.flow_skill_value(self.desktop.root, 'frames'), ['我的分镜/SKILL.md'])
        self.assertFalse(hasattr(panel, 'flow_vars'))
        self.assertNotIn('我的分镜', [box.cget('text') for box in panel.registered_boxes.values()])

    def test_skill_action_dropdown_deletes_then_resets_to_all(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        with mock.patch.object(panel, 'delete_checked_skills', return_value=['recycled']) as deleted:
            panel.skill_action.set(skill_panel.MANAGE_DELETE)
            self.assertEqual(panel.choose_skill_action(), ['recycled'])
        deleted.assert_called_once_with()
        self.assertEqual(panel.skill_action.get(), skill_panel.MANAGE_ALL)

    def test_skill_controls_flow_into_action_row_and_scroll_policy(self):
        """勾选框按注册表顺序流式排进操作行；超过十项提供滚动。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        panel.layout_skill_controls()
        self.assertTrue(panel.skill_controls)
        # 勾选框直接排在操作行里，不再用三列网格。
        self.assertEqual(panel.flow_skill_row, panel.skill_action_row)
        self.assertTrue(all(widget.master is panel.flow_skill_row for widget in panel.skill_controls))
        self.assertTrue(all(widget.winfo_manager() != 'grid' for widget in panel.skill_controls))
        self.assertTrue(panel.uses_skill_scrollbar(11))
        self.assertFalse(panel.uses_skill_scrollbar(10))
        clipped = panel.skill_label('名称' * 20, limit=12)
        self.assertTrue(clipped.endswith('...'))
        self.assertEqual(len(clipped), 12)

    def test_stage_panel_skill_display_keeps_chinese_and_aigc_name(self):
        self.assertEqual(skill_panel.chinese_skill_display('全流程AIGC·剧本'), '全流程AIGC·剧本')
        self.assertEqual(skill_panel.chinese_skill_display('Drama 分镜'), '分镜')
        self.assertEqual(skill_panel.chinese_skill_display('TTS 配音合成'), '配音合成')
        self.assertEqual(skill_panel.chinese_skill_display('我的分镜/SKILL.md'), '我的分镜')
        self.assertEqual(skill_panel.chinese_skill_display('【我的-分镜】 01'), '我的分镜')
        self.assertEqual(skill_panel.chinese_skill_display('custom-skill'), '自定义技能')
        self.assertEqual(skill_panel.skill_checkbox_label('D:/任意/目录/【我的-分镜】.skill.md'), '我的分镜')
        skill = type('Skill', (), {'displayName': '全流程AIGC·剧本', 'name': 'pipeline-script-preparation',
                                   'path': 'D:/skills/01/SKILL.md'})()
        self.assertEqual(skill_panel.registered_skill_checkbox_label(skill), '全流程AIGC·剧本')

    def test_note_selection_focuses_the_matching_skill_checkbox(self):
        """R2916：说明目录已删除——面板不再有说明↔勾选框的联动。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        self.assertIsNone(panel.note_list, '说明目录已随 R2916 删除')
        self.assertEqual(panel.note_items, [], '说明条目列表已清空')
        self.assertIsNone(panel.note_text, '说明正文已随 R2916 删除')

    def test_delete_checked_program_skill_recycles_it_and_refreshes_the_panel(self):
        """删除按钮只能把程序 skills/ 的 .skill.md 移到程序回收站，并立即刷新。"""
        program = Path(self.tmp.name) / '删除测试程序'
        target = write_skill(program / 'skills' / '08首帧管理SKILL',
                             'temporary-delete', stage='keyframe')
        registry = skill_registry.Registry(root=program / 'skills')
        registry.scan(force=True)
        with mock.patch.object(skill_panel, '__file__', str(program / 'skill_panel.py')):
            with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
                with mock.patch.object(skill_panel, 'confirm', return_value=True):
                    panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
                    self.addCleanup(panel.destroy)
                    panel.vars['temporary-delete'].set(True)
                    records = panel.delete_checked_skills()

        self.assertTrue(records)
        self.assertFalse(target.exists(), '源文件应从 skills/ 消失')
        self.assertTrue(any((program / '工作流任务' / '回收站').rglob('temporary-delete.skill.md')),
                        '回收副本必须在程序回收站，不能留在 skills/')
        self.assertNotIn('temporary-delete', panel.vars, '删除成功后面板应立即刷新')
        reopened = skill_registry.Registry(root=program / 'skills')
        reopened.scan(force=True)
        self.assertNotIn('temporary-delete', [item.name for item in reopened.getAll()],
                         '重新建立注册表（模拟重启）后，被删 SKILL 也不得复活')

    def test_referenced_program_skill_requires_confirmation_before_deleting(self):
        """仍被项目配置引用时必须先确认；确认后才可回收，不改项目配置。"""
        program = Path(self.tmp.name) / '引用删除测试程序'
        target = write_skill(program / 'skills' / '08首帧管理SKILL',
                             'referenced-delete', stage='keyframe')
        registry = skill_registry.Registry(root=program / 'skills')
        registry.scan(force=True)
        (self.desktop.root / 'skill_config.json').write_text(
            json.dumps({'script': {'skills': ['referenced-delete']}}, ensure_ascii=False), encoding='utf-8')
        with mock.patch.object(skill_panel, '__file__', str(program / 'skill_panel.py')):
            with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
                with mock.patch.object(skill_panel, 'confirm', return_value=False) as confirm:
                    panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
                    self.addCleanup(panel.destroy)
                    panel.vars['referenced-delete'].set(True)
                    self.assertEqual(panel.delete_checked_skills(), [])
                    self.assertIn('仍被当前项目 skill_config.json 引用', confirm.call_args.args[2])

        self.assertTrue(target.exists(), '用户取消时不得删除')
        with mock.patch.object(skill_panel, '__file__', str(program / 'skill_panel.py')):
            with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
                with mock.patch.object(skill_panel, 'confirm', return_value=True):
                    records = panel.delete_checked_skills()
        self.assertTrue(records, '引用提示确认后应进入既有回收服务')
        self.assertFalse(target.exists())

    def test_missing_legacy_engine_skill_remains_noninteractive(self):
        """旧清单不迁移、不清空；即使路径失效也不会在面板复活为勾选框。"""
        missing = Path(self.tmp.name) / '已删除分镜' / 'SKILL.md'
        skill_panel.set_flow_skills(self.desktop.root, 'frames', [str(missing)])
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        self.assertFalse(hasattr(panel, 'flow_vars'))
        self.assertEqual(skill_panel.flow_skill_paths(self.desktop.root, 'frames'), [])

    def registered_package_registry(self, package='外部包总入口'):
        """建立一份临时外部包注册表，模拟已注册又被工作流保存的同一路径。"""
        program = Path(self.tmp.name) / '双源渲染程序'
        source = program / 'skills' / '01剧本准备SKILL' / package / 'SKILL.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('---\nname: %s\n---\n# %s\n' % (package, package), encoding='utf-8')
        registry = skill_registry.Registry(root=program / 'skills')
        registry.scan(force=True)
        return source, registry

    def test_registered_legacy_flow_skill_has_one_stage_checkbox(self):
        """同源旧路径只由阶段注册表渲染一次，旧字段不提供可编辑副本。"""
        source, registry = self.registered_package_registry()
        skill_panel.set_flow_skills(self.desktop.root, 'writing', [str(source)])
        with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
            self.addCleanup(panel.destroy)
            resolved = str(source.resolve())
            boxes = [box for box in panel.flow_skill_row.winfo_children()
                     if getattr(box, '_skill_path', '') == resolved]
            self.assertEqual(len(boxes), 1,
                             '同一 resolve 路径只能由注册表或流程来源之一渲染')
            self.assertFalse(hasattr(panel, 'flow_vars'))

    def test_legacy_engine_skill_is_preserved_for_cli_consumption(self):
        """读取旧清单不写回、不清空，CLI 仍由 workflow_settings 消费。"""
        source, registry = self.registered_package_registry('持久化外部包')
        skill_panel.set_flow_skills(self.desktop.root, 'writing', [str(source)])
        with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
            self.addCleanup(panel.destroy)
            panel.load()
        saved = skill_panel.flow_skill_paths(self.desktop.root, 'writing')
        self.assertIn(str(source.resolve()), [str(Path(path).resolve()) for path in saved],
                      '隐藏仅用于去重显示，不得从工作流设置写回清单丢失')

    def test_unregistered_legacy_skill_does_not_get_a_second_checkbox(self):
        """仅存在于旧流程设置的路径保持只读，面板无第二个勾选框。"""
        program = Path(self.tmp.name) / '未注册流程程序'
        registry = skill_registry.Registry(root=program / 'skills')
        registry.scan(force=True)
        source = Path(self.tmp.name) / '未注册外部包' / 'SKILL.md'
        source.parent.mkdir()
        source.write_text('# 未注册 SKILL', encoding='utf-8')
        skill_panel.set_flow_skills(self.desktop.root, 'writing', [str(source)])
        with mock.patch.object(skill_panel.skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
            self.addCleanup(panel.destroy)
            self.assertFalse(hasattr(panel, 'flow_vars'))
            self.assertNotIn(str(source.resolve()),
                             [getattr(box, '_skill_path', '') for box in panel.registered_boxes.values()])

    def test_stage_skill_actions_never_write_legacy_engine_list(self):
        """阶段网格的全选/取消仅写 skill_config，旧 flows.*.skills 保持原值。"""
        source = Path(self.tmp.name) / '旧引擎' / 'SKILL.md'; source.parent.mkdir(); source.write_text('# x', encoding='utf-8')
        skill_panel.set_flow_skills(self.desktop.root, 'frames', [str(source)])
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        panel.skill_action.set(skill_panel.MANAGE_NONE)
        panel.choose_skill_action()
        self.assertEqual(skill_panel.flow_skill_paths(self.desktop.root, 'frames'), [str(source)])
        self.assertEqual(panel.selected(), [])

    def test_restore_defaults_requires_confirmation(self):
        real = skill_panel.confirm
        skill_panel.confirm = lambda *args, **kwargs: False
        self.addCleanup(setattr, skill_panel, 'confirm', real)
        stage_config.put(self.desktop.root, 'keyframe', model='qwen-max')
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.assertIsNone(panel.reset_defaults())
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['model'], 'qwen-max')

    def test_restore_defaults_resets_only_the_current_stage(self):
        real = skill_panel.confirm
        skill_panel.confirm = lambda *args, **kwargs: True
        self.addCleanup(setattr, skill_panel, 'confirm', real)
        stage_config.put(self.desktop.root, 'keyframe', model='qwen-max')
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        panel.vars['firstframe-quality'].set(False)
        panel.save()
        entry = panel.reset_defaults()
        self.assertEqual(entry['model'], 'auto')
        self.assertTrue(panel.vars['firstframe-quality'].get())
        self.assertIn('制作锁未改变', panel.state.cget('text'))

    def test_add_skill_action_uses_the_file_picker(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        with mock.patch('ui_dialogs.filedialog.askopenfilename', return_value='') as picker:
            panel.skill_action.set(skill_panel.MANAGE_ADD)
            self.assertIsNone(panel.choose_skill_action())
        picker.assert_called_once()
        self.assertEqual(panel.skill_action.get(), skill_panel.MANAGE_ALL)

    def test_stage_label_names_the_stage(self):
        """第 30 期第 8 条：下拉框那一列的名字（面板抬头还是「阶段配置 · 08 首帧管理」）。"""
        self.assertEqual(skill_panel.stage_label('keyframe'), '08 首帧管理')
        self.assertEqual(skill_panel.stage_label('没有这个'), '没有这个')
        self.assertEqual(skill_panel.panel_title('keyframe'), '阶段配置 · 08 首帧管理')

    def test_the_panel_stays_on_the_stage_of_the_page(self):
        """第 33 期第 3 条：抬头那个「阶段」下拉撤掉——每页的按钮只配自己那一个阶段。"""
        from tkinter import ttk
        panel = skill_panel.open_for_page(self.desktop, 0)
        self.assertEqual(panel.stage, 'script')
        window = panel.winfo_toplevel()
        self.addCleanup(window.destroy)

        def walk(widget):
            found = []
            for child in widget.winfo_children():
                found.append(child)
                found.extend(walk(child))
            return found

        pickers = [w for w in walk(window)
                   if isinstance(w, ttk.Combobox) and '08 首帧管理' in list(w.cget('values'))]
        self.assertEqual(pickers, [], '面板里不再有切到别的阶段的入口')
        texts = [str(w.cget('text')) for w in walk(window) if isinstance(w, ttk.Label)]
        self.assertIn('阶段配置 · 01 剧本准备', texts, '抬头写的就是本页那一阶段的标题')
        self.assertEqual(window.title(), '阶段配置 · 01 剧本准备')
        # 首帧管理页自己那颗按钮进去，开的还是它自己那一个阶段
        other = skill_panel.open_for_page(self.desktop, pet_bus.STAGES.index('keyframe'))
        self.addCleanup(other.winfo_toplevel().destroy)
        self.assertEqual(other.stage, 'keyframe')
        self.assertEqual(other.winfo_toplevel().title(), '阶段配置 · 08 首帧管理')
        self.assertEqual(len([w for w in walk(other.winfo_toplevel())
                               if isinstance(w, skill_panel.Panel)]), 1, '一次只开一块面板')

    def test_stage_config_window_covers_its_main_window(self):
        self.win.deiconify()
        self.win.geometry('1200x800+0+0')
        self.win.update_idletasks()
        panel = skill_panel.open_for_page(self.desktop, 0)
        window = panel.winfo_toplevel()
        self.addCleanup(window.destroy)
        window.update_idletasks()
        self.assertEqual(window.winfo_width(), self.win.winfo_width(),
                         'R2411：阶段配置弹窗尺寸＝主界面（覆盖，像切换页面）')
        self.assertEqual(window.winfo_height(), self.win.winfo_height())
        self.assertTrue(all(window.resizable()))
        window.geometry('1250x850')
        window.update_idletasks()
        self.assertEqual((window.winfo_width(), window.winfo_height()), (1250, 850))
        window.geometry('400x300')
        window.update_idletasks()
        from ui_tokens import STAGE_PANEL_LAYOUT
        min_width = min(STAGE_PANEL_LAYOUT['min_width'], self.win.winfo_screenwidth())
        min_height = min(STAGE_PANEL_LAYOUT['min_height'], self.win.winfo_screenheight())
        self.assertGreaterEqual(window.winfo_width(), min_width)
        self.assertGreaterEqual(window.winfo_height(), min_height)

    def test_the_report_splits_done_from_needs_the_page(self):
        """第 30 期第 7 条：两个都「得回页面按」时，不再报「成了 2 个」。"""
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        run = {'results': [
            {'skill': 'firstframe-batch', 'status': skill_orchestrator.PAGE, 'ok': True,
             'name': '批量首帧', 'page': 4, 'pageTitle': '08 首帧管理',
             'detail': '这一步得回「08 首帧管理」页面上按'},
            {'skill': 'firstframe-quality', 'status': skill_orchestrator.PAGE, 'ok': True,
             'name': '首帧质检', 'page': 4, 'pageTitle': '08 首帧管理',
             'detail': '这一步得回「08 首帧管理」页面上按'}],
            'failed': [],
            'text': '这一批 2 个 SKILL：成了 0 个，等您点头 0 个，没成 0 个。'}
        panel.report(run)
        self.assertEqual(panel.state.cget('text'), '做完了 0 个，2 个要回页面按，没成 0 个')
        reason = panel.reason.cget('text')
        self.assertIn('不算做完', reason, '得说清「为什么不算做完」')
        self.assertIn('08 首帧管理', reason)
        self.assertIn('批量首帧', reason)

    def test_the_report_counts_a_real_finish_and_a_failure(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        run = {'results': [
            {'skill': 'firstframe-batch', 'status': skill_orchestrator.DONE, 'ok': True, 'name': '做完了的'},
            {'skill': 'firstframe-quality', 'status': skill_orchestrator.FAILED, 'ok': False,
             'name': '没成的', 'detail': '工具炸了'}],
            'failed': ['firstframe-quality'], 'text': '这一批 2 个 SKILL。'}
        panel.report(run)
        self.assertEqual(panel.state.cget('text'), '做完了 1 个，0 个要回页面按，没成 1 个')
        self.assertEqual(panel.reason.cget('text'), '', '没有「要回页面按」的就不写那一行')

    def test_input_rows_are_explained_as_missing_files(self):
        panel = skill_panel.Panel(self.win, self.desktop, 'keyframe')
        self.addCleanup(panel.destroy)
        run = {'results': [
            {'skill': 'firstframe-batch', 'status': skill_orchestrator.INPUT, 'ok': True,
             'name': '要分镜的', 'detail': '还没采用分镜 JSON'}],
            'failed': [], 'text': ''}
        panel.report(run)
        self.assertEqual(panel.state.cget('text'), '做完了 0 个，1 个要回页面按，没成 0 个')
        self.assertIn('还缺您手上的文件', panel.reason.cget('text'))
        self.assertIn('还没采用分镜 JSON', panel.reason.cget('text'))

    def test_waiting_reason_is_empty_without_rows(self):
        self.assertEqual(skill_panel.waiting_reason([]), '')
        self.assertEqual(skill_panel.waiting_reason(None), '')


class PetIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from test_pet_ui import FakeDesktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeDesktop(self.tk, __import__('tkinter.ttk', fromlist=['ttk']), self.win)
        project = Path(self.tmp.name) / 'p'
        (project / 'episode').mkdir(parents=True)
        (project / 'episode' / 'episode.json').write_text(json.dumps(
            {'episode_id': 'EP001', 'title': 'T', 'shots': []}), encoding='utf-8')
        self.fake.root = project
        self.pet = pet_ui.attach(self.fake, autostart=False)
        self.asked = []
        self.pet.asker = lambda title, text: self.asked.append((title, text)) or True
        # run_skill 的手动模板门禁会打开真实对话框；单元测试须明确提供用户选择，
        # 否则隐藏的 Tk 根窗口会让 ask_string 永久等待。
        self.pet.template_choice = lambda text: '确认'

    def test_natural_language_can_name_a_skill(self):
        plan = pet_agent.route('把首帧批量生成跑一下')
        self.assertEqual(plan['intent'], 'skill')
        self.assertEqual(plan['stage'], 'keyframe')
        self.assertEqual(plan['params']['skills'], ['firstframe-batch'])
        self.assertEqual(pet_agent.action_for(plan), 'skill.run')

    def test_execute_selected_means_the_current_stage(self):
        plan = pet_agent.route('执行选中', context={'stage': 'final'})
        self.assertEqual(plan['intent'], 'skill')
        self.assertEqual(plan['stage'], 'final')
        self.assertEqual(plan['params']['skills'], [])

    def test_plain_talk_is_not_a_skill_order(self):
        self.assertIsNone(pet_agent.match_skill('你在干什么呀'))
        self.assertIsNone(pet_agent.match_skill('首帧管理那一页在哪'))
        self.assertIsNone(pet_agent.match_skill('不用跑首帧批量生成'))

    def test_stage_question_still_routes_to_the_page(self):
        self.assertEqual(pet_agent.route('首帧管理那一页在哪')['intent'], 'goto')

    def test_run_skill_reports_through_the_pet(self):
        result = self.pet.run_skill({'stage': 'storyboard', 'params': {'skills': []}})
        self.assertTrue(result)
        self.assertEqual(result, self.pet.notice)

    def test_run_skill_says_so_when_nothing_is_checked(self):
        stage_config.put(self.fake.root, 'keyframe', model='auto', skills=[])
        result = self.pet.run_skill({'stage': 'keyframe', 'params': {'skills': []}})
        self.assertIn('取消勾选', result)

    def test_run_skill_without_a_project_says_so(self):
        self.fake.root = None
        result = self.pet.run_skill({'stage': 'keyframe', 'params': {'skills': []}})
        self.assertIn('项目', result)

    def test_settle_paid_asks_once_and_carries_on(self):
        orch = skill_panel.build_orchestrator(self.fake, self.fake.root)
        context = {'project': str(self.fake.root), 'at': NOON}
        run = orch.run(['firstframe-batch'], context)
        self.assertTrue(run['pending'])
        out = self.pet.settle_paid(orch, run, list(run['pending']), context)
        self.assertEqual(len(self.asked), 1)
        self.assertIn('首帧批量生成', self.asked[0][1])
        self.assertIn('firstframe-batch', orch.approved)
        self.assertNotIn('firstframe-batch', out['failed'])


    def test_match_model_reads_the_five_aliases(self):
        self.assertEqual(pet_agent.match_model('这次用 GPT 跑'), 'gpt-4o')
        self.assertEqual(pet_agent.match_model('换 Qwen 试试'), 'qwen-max')
        self.assertEqual(pet_agent.match_model('用通义千问'), 'qwen-max')
        self.assertEqual(pet_agent.match_model('切到 deepseek pro'), 'deepseek-v4-pro')
        self.assertEqual(pet_agent.match_model('换成 flash'), 'deepseek-v4-flash')

    def test_match_model_does_not_mistake_profile_for_pro(self):
        self.assertEqual(pet_agent.match_model('看看 profile 里的设置'), '')
        self.assertEqual(pet_agent.match_model(''), '')

    def test_a_named_model_rides_along_with_the_skill_plan(self):
        plan = pet_agent.route('用 Qwen 把首帧批量生成跑一下')
        self.assertEqual(plan['intent'], 'skill')
        self.assertEqual(plan['params']['skills'], ['firstframe-batch'])
        self.assertEqual(plan['params']['model'], 'qwen-max')


class GeneratorTests(unittest.TestCase):
    def run_generator(self, args, stdin=None):
        if NODE is None:
            self.skipTest(MISSING_NODE)
        # 第 63 期：生成器缺参数时会问一句（readline 等一行）。原来 input=None 表示「继承调用方的
        # stdin」，整跑从后台起来时那根管子一直不关，它就死等 90 秒——同一份代码前台跑绿、后台跑红。
        # 这里统一喂空串：等于「把 stdin 合上」，生成器拿到 EOF 就用默认值往下走。
        done = subprocess.run([NODE, str(GENERATOR)] + args, input='' if stdin is None else stdin,
                              capture_output=True, text=True, encoding='utf-8', cwd=HERE, timeout=90)
        return done.returncode, done.stdout or '', done.stderr or ''

    def test_generates_a_spec_compliant_skill_file(self):
        with tempfile.TemporaryDirectory() as td:
            code, out, err = self.run_generator(
                ['--name', 'self-check-skill', '--display', '自检 SKILL', '--description', '生成器自检',
                 '--stage', '首帧管理', '--capabilities', 'structured-output, reasoning',
                 '--tools', 'firstframe.batchGenerate', '--depends', 'firstframe-batch',
                 '--input', 'scope', '--output', 'submitted', '--constraints', '付费前确认',
                 '--examples', '用户："补首帧" → batch()', '--paid', '--dir', td])
            self.assertEqual(code, 0, err)
            self.assertIn('已生成', out)
            self.assertTrue((Path(td) / 'self-check-skill.skill.md').is_file())
            (Path(td) / '08首帧管理SKILL').mkdir()
            reg = skill_registry.Registry(root=td)
            reg.scan(force=True)
            self.assertEqual(reg.problems(), [])
            item = reg.getById('self-check-skill')
            self.assertEqual(item.stage, 'keyframe')
            self.assertEqual(item.displayName, '自检 SKILL')
            self.assertTrue(item.paid)
            self.assertTrue(item.parallelizable)
            self.assertEqual(item.capabilities, ['structured-output', 'reasoning'])
            self.assertEqual([key for row in item.feedback for key in row],
                             ['onProgress', 'onError', 'onComplete'])
            self.assertIn('三虎', json.dumps(item.feedback, ensure_ascii=False))

    def test_asks_questions_and_accepts_piped_answers(self):
        with tempfile.TemporaryDirectory() as td:
            answers = '\n'.join(['demo-skill', '演示 SKILL', '一句话说明', '资产管理', 'reasoning',
                                 'asset.demo', '', 'scope', 'saved', '不落库', 'n', 'n', '']) + '\n'
            code, out, err = self.run_generator(['--dir', td], stdin=answers)
            self.assertEqual(code, 0, err)
            (Path(td) / '05资产管理SKILL').mkdir()
            item = skill_registry.Registry(root=td).getById('demo-skill')
            self.assertEqual(item.displayName, '演示 SKILL')
            self.assertEqual(item.stage, 'assets')
            self.assertEqual(item.capabilities, ['reasoning'])
            self.assertFalse(item.paid)

    def test_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            args = ['--name', 'twice-skill', '--display', 'x', '--stage', '资产管理', '--yes', '--dir', td]
            self.assertEqual(self.run_generator(args)[0], 0)
            code, out, err = self.run_generator(args)
            self.assertEqual(code, 3)
            self.assertIn('已经有这个 SKILL', err)
            self.assertEqual(self.run_generator(args + ['--force'])[0], 0)

    def test_rejects_a_bad_id_or_capability(self):
        with tempfile.TemporaryDirectory() as td:
            code, out, err = self.run_generator(['--name', 'Bad Name', '--display', 'x', '--stage',
                                                 '资产管理', '--yes', '--dir', td])
            self.assertEqual(code, 2)
            self.assertIn('小写字母', err)
            code, out, err = self.run_generator(['--name', 'ok-name', '--display', 'x', '--stage',
                                                 '资产管理', '--capabilities', 'telepathy', '--yes', '--dir', td])
            self.assertEqual(code, 2)
            self.assertIn('telepathy', err)


if __name__ == '__main__':
    unittest.main()
