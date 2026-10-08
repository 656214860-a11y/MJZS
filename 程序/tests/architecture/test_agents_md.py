"""AGENTS、地图与架构文档不得漂移于运行时阶段和静态门禁。"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import pet_bus
from tests.architecture._scan import ROOT
from tests.architecture._layers import LAYERS
from tests.architecture.test_path_authority import _WHITELIST as PATH_AUTHORITIES
from tests.architecture.test_remove_authority import _WHITELIST as REMOVE_AUTHORITIES


AGENTS = ROOT / 'AGENTS.md'
PROJECT_MAP = ROOT / 'PROJECT_MAP.md'
ARCHITECTURE = ROOT / 'architecture.md'
GITIGNORE = ROOT.parent / '.gitignore'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    following = re.search(r'^## ', text[start + len(heading):], re.MULTILINE)
    end = start + len(heading) + following.start() if following else len(text)
    return text[start:end]


def _stage_counts(text: str) -> set[int]:
    return {int(count) for count in re.findall(r'(\d+)\s*(?:个制作)?阶段', text)}


class AgentsMdConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agents = _read(AGENTS)

    def test_contract_round_whitelist_matches_authorized_l0_scope(self) -> None:
        section = self.agents.split('### 3.4 契约轮', 1)[1].split('### 3.5', 1)[0]
        clause = section.split('- 只改 ', 1)[1].split('。', 1)[0]
        modules = set(re.findall(r'`([a-z_]+)`', clause))
        self.assertEqual(modules, {'pet_bus', 'script_contract', 'asset_contract',
                                  'stage_layout', 'storyboard_paths', 'hollmwood_rules'})
        self.assertEqual({module: LAYERS[module] for module in modules},
                         dict.fromkeys(modules, 0))
        self.assertIn('不动 L1 以上', section)
        self.assertIn('跑全量自检', section)

    def test_workflow_stage_count_matches_bus(self) -> None:
        matched = re.search(r'工作流：(\d+) 个制作阶段', self.agents)
        self.assertIsNotNone(matched)
        self.assertEqual(int(matched.group(1)), len(pet_bus.STAGES))

    def test_broadcaster_stage_denominator_matches_bus(self) -> None:
        section = _section(self.agents, '## 6. 进度播报前缀')
        matched = re.search(r'【阶段 X/(\d+)】', section)
        self.assertIsNotNone(matched)
        self.assertEqual(int(matched.group(1)), len(pet_bus.STAGES))

    def test_authority_table_modules_exist(self) -> None:
        section = _section(self.agents, '### 2.2 权威源（唯一真源）')
        expected = {
            'pet_bus', 'stage_parallel', 'skill_registry', 'stage_layout',
            'storyboard_paths', 'script_contract', 'asset_contract', 'model_pool',
            'file_cache', 'asset_thumbs', 'hash_backend', 'stage_handler_registry',
            'ui_plugin_registry', 'stage_path_service', 'stage_completion_service',
            'storage_maintenance',
        }
        mentioned = set(re.findall(r'`([a-z_]+)(?:\.[A-Za-z_()]+)?`', section))
        self.assertTrue(expected <= mentioned, expected - mentioned)
        missing = sorted(name for name in expected if not (ROOT / f'{name}.py').is_file())
        self.assertEqual(missing, [], 'AGENTS 2.2 引用的模块不存在：' + ', '.join(missing))

    def test_delete_authority_contract_matches_remove_guard(self) -> None:
        section = _section(self.agents, '### 2.3 新增结构硬约束（第 118 期起）')
        clause = re.search(r'14\. \*\*删除唯一权威\*\*：(.*?)(?=\n\d+\.|\Z)', section, re.S)
        self.assertIsNotNone(clause)
        self.assertIn('storage_maintenance.recycle_paths()', clause.group(1))
        self.assertIn('storage_maintenance', REMOVE_AUTHORITIES)

    def test_path_authority_contract_matches_path_guard(self) -> None:
        section = _section(self.agents, '### 2.2 权威源（唯一真源）')
        path_row = next(line for line in section.splitlines() if line.startswith('| 路径'))
        documented = set(re.findall(r'`([a-z_]+)', path_row))
        self.assertEqual(documented, PATH_AUTHORITIES)

    def test_new_test_location_rule_matches_root(self) -> None:
        section = _section(self.agents, '### 2.3 新增结构硬约束（第 118 期起）')
        self.assertIn('新测试一律放 `tests/`', section)
        root_tests = sorted(path.name for path in ROOT.glob('test_*.py'))
        self.assertEqual(root_tests, [], '根目录仍有应迁入 tests/ 的测试：' + ', '.join(root_tests))

    def test_three_documents_agree_on_stage_count(self) -> None:
        expected = {len(pet_bus.STAGES)}
        for path in (AGENTS, PROJECT_MAP, ARCHITECTURE):
            self.assertEqual(_stage_counts(_read(path)), expected, path.name)

    def test_desktop_route_documentation_matches_current_contract(self) -> None:
        architecture = _read(ARCHITECTURE)
        project_map = _read(PROJECT_MAP)
        source = _read(ROOT / 'workflow_settings.py')
        self.assertNotIn('不参与 API 自动抢占', architecture)
        self.assertIn('GPT/Anthropic API', architecture)
        self.assertIn('本机程序可启动', architecture)
        self.assertIn('启动失败才按兼容 API 回退', architecture)
        self.assertIn('GPT/Anthropic API', project_map)
        self.assertIn("{'GPT': 'codex', 'Anthropic': 'claude'}", source)

    def test_architecture_guard_list_matches_actual_test_files(self) -> None:
        section = _section(self.agents, '当前架构门禁清单')
        documented = set(re.findall(r'`(test_[a-z0-9_]+\.py)`', section))
        actual = {path.name for path in (ROOT / 'tests' / 'architecture').glob('test_*.py')}
        self.assertEqual(documented, actual,
                         'AGENTS 架构门禁清单必须与实际测试文件集合完全相等')

    def test_gitignore_covers_runtime_and_secret_boundaries(self) -> None:
        """版本控制兼容轮：必排除项缺一即红，防止用户数据或凭据进入暂存区。"""
        patterns = {line.strip() for line in _read(GITIGNORE).splitlines()
                    if line.strip() and not line.lstrip().startswith('#')}
        required = {
       '/程序/private/', '/程序/logs/', '/程序/data/', '**/__pycache__/',
       '**/*.py[cod]', '/程序/pycache/', '**/工作流任务/', '**/回收站/', '/升级备份/',
            '**/*.bak_*', '/程序/配置/宠物/', '/程序/projects.json',
            '/程序/desktop_settings.json', '/程序/config.json', '**/.env', '**/*.dpapi',
        }
        self.assertTrue(required <= patterns, required - patterns)
