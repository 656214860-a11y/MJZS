"""轮次接续与最低验证基线不得因文档或测试迁移而倒退。"""
from __future__ import annotations

import importlib.util
import re
import json
import subprocess
import unittest

import smoke_test
import run_selftests
from tests.architecture._scan import ROOT

# scripts/ 不在包路径里；与 test_auto_full_safe 同法按文件装载，冷却判定仍只有 auto_full_safe 一份实现。
_AUTO_SPEC = importlib.util.spec_from_file_location(
    'auto_full_safe_for_round_baselines', ROOT / 'scripts' / 'auto_full_safe.py')
auto_full_safe = importlib.util.module_from_spec(_AUTO_SPEC)
_AUTO_SPEC.loader.exec_module(auto_full_safe)


STATUS = ROOT / 'project_status.md'
BASELINES = ROOT / '维护记录' / '测试分层基线.json'
RESULT_PATTERN = re.compile(r'tasks_round_(\d+)_result\.md$')
INVALID_TYPE_HEADING = re.compile(r'结构治理执行(?:轮)?|修复/结构治理轮|整理轮（结构治理执行）')


def _latest_result_number() -> int:
    numbers = [int(match.group(1)) for path in (ROOT / 'tasks_round').rglob('tasks_round_*_result.md')
               if (match := RESULT_PATTERN.search(path.name))]
    if not numbers:
        raise AssertionError('tasks_round 中没有结果报告')
    return max(numbers)


class RoundBaselineTests(unittest.TestCase):
    @staticmethod
    def _merge_in_progress() -> bool:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "-q", "--verify", "MERGE_HEAD"],
                             capture_output=True, text=True, timeout=15)
        return out.returncode == 0

    def test_round_number_continuous(self) -> None:
        """AGENTS 2.5 规则 27：状态轮次必须紧接最新结果报告。"""
        if self._merge_in_progress():
            # B1 新流程：merge --no-commit 后、领号写状态页前跑 exit-CI，
            # 此时「当前轮次==最新结果+1」结构上尚不成立；merge_round 在领号后提交前复核。
            self.skipTest("合并候选树：状态页轮次由 merge_round 领号后写入，提交前复核")
        text = STATUS.read_text(encoding='utf-8')
        matched = re.search(r'当前轮次：(\d+)', text)
        self.assertIsNotNone(matched, 'project_status.md 缺少当前轮次')
        self.assertEqual(int(matched.group(1)), _latest_result_number() + 1)

    def test_baseline_unchanged(self) -> None:
        """AGENTS 2.5 规则 29：默认冒烟 8 项，架构门禁不低于历史 14 项。"""
        self.assertEqual(len(smoke_test.ROUND_CHECKS[smoke_test.ROUND]), 8,
                         '默认冒烟基线必须保持 8/8')
        architecture_files = list((ROOT / 'tests' / 'architecture').glob('test_*.py'))
        self.assertGreaterEqual(len(architecture_files), 14,
                                '架构门禁不得低于历史 14/14 基线')

    def test_execution_is_not_an_independent_round_type(self) -> None:
        """AGENTS 3.3：执行仅可作为结构治理轮的子场景。"""
        headings = [
            f'{path}: {path.read_text(encoding="utf-8").splitlines()[0]}'
            for path in (ROOT / 'tasks_round').rglob('tasks_round_*_result.md')
        ]
        for line in STATUS.read_text(encoding='utf-8').splitlines():
            matched = re.match(r'- R\d+ ([^：]+)：', line)
            if matched:
                headings.append(f'{STATUS}: {matched.group(1)}')
        invalid = [heading for heading in headings if INVALID_TYPE_HEADING.search(heading)]
        self.assertEqual(invalid, [], '轮次标题或状态摘要不得把“执行”写成独立轮次类型')

    def test_full_safe_all_is_required_after_eight_source_rounds(self) -> None:
        """仅主干提交序列：累计 FULL_SAFE_ROUND_INTERVAL 个改过源码的轮次要求一次完整安全全量（文档／测试轮不计）。"""
        latest = _latest_result_number()
        baseline = run_selftests.load_layer_document()
        last_full = baseline['last_full_safe_all_round']
        if not run_selftests.full_safe_required(
                latest, last_full, run_selftests.is_master_checkout(),
                run_selftests.source_rounds_since(last_full, latest),
                run_selftests.risk_overdue_since(last_full, latest)):
            return
        if run_selftests.auto_full_running():
            return      # 后台已在补跑：不报红，也别手动再跑
        receipt = run_selftests.verified_tree_record(
            baseline.get('full_safe_verified_trees', []), run_selftests.content_tree())
        # A run cannot have its own success receipt before its tests finish.
        # Other processes still need an actual receipt, not report prose.
        # 同 HEAD 红冷却（'head'）是机制对相同内容树的确定性抑制：合并提交是唯一能推进 HEAD、
        # 让冷却降级为 'time'（required 下自动补跑）的途径，此时拦合并就是死锁（2026-11-16 事故）。
        cooling = auto_full_safe.current_cooling()
        self.assertTrue(receipt or run_selftests.participating_full_safe_run(latest)
                        or cooling == 'head',
                        f'R{latest} 欠一次完整安全全量。后台会自动补跑（post-commit 钩子触发），请勿手动全量；'
                        '进度见 程序/logs/auto_full_safe.log，或运行 scripts/auto_full_safe.py --status')

    def test_verified_tree_records_have_required_metadata(self) -> None:
        baseline = run_selftests.load_layer_document()
        records = baseline.get('full_safe_verified_trees', [])
        self.assertIsInstance(records, list)
        for record in records:
            self.assertTrue({'tree', 'round', 'seconds', 'at'} <= set(record))
