# -*- coding: utf-8 -*-
"""合并门禁的欠账分支：同 HEAD 红冷却中放行合并（合并提交是解锁冷却的唯一途径），其余欠账态仍报红。

背景（2026-11-16 死锁）：后台全量红后 ``red_cooldown`` 对同 HEAD 永久抑制补跑，而合并出口门禁
要求「欠账时必须有在跑全量或绿凭据」——两边互相等待，只有手动 ``--run`` 能解开。本文件用 mock
驱动 ``test_round_baselines`` 的欠账判据，钉住「cooling=='head' 放行、其余仍红」的契约。
暂缓开关（auto-full-safe-hold.json）生效期间欠账项同样放行：到点由等待者自动补跑，欠账照记。
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(PROGRAM / 'tests'))

import run_selftests  # noqa: E402
from tests.architecture import test_round_baselines as gate  # noqa: E402

METHOD = 'test_full_safe_all_is_required_after_eight_source_rounds'


def drive(cooling='', *, source_rounds=10, running=False, receipt=None, participating=False,
          hold=0.0):
    """以给定欠账状态驱动门禁方法；断言失败以 AssertionError 抛出。"""
    case = gate.RoundBaselineTests(METHOD)
    with mock.patch.object(gate, '_latest_result_number', return_value=100), \
         mock.patch.object(run_selftests, 'load_layer_document',
                           return_value={'last_full_safe_all_round': 90,
                                         'full_safe_verified_trees': []}), \
         mock.patch.object(run_selftests, 'is_master_checkout', return_value=True), \
         mock.patch.object(run_selftests, 'source_rounds_since', return_value=source_rounds), \
         mock.patch.object(run_selftests, 'risk_overdue_since', return_value=False), \
         mock.patch.object(run_selftests, 'auto_full_running', return_value=running), \
         mock.patch.object(run_selftests, 'verified_tree_record', return_value=receipt), \
         mock.patch.object(run_selftests, 'content_tree', return_value='tree'), \
         mock.patch.object(run_selftests, 'participating_full_safe_run', return_value=participating), \
         mock.patch.object(gate.auto_full_safe, 'current_cooling', return_value=cooling), \
         mock.patch.object(gate.auto_full_safe, 'hold_until', return_value=hold):
        case.test_full_safe_all_is_required_after_eight_source_rounds()


class MergeGateDebtTests(unittest.TestCase):
    def test_same_head_red_cooling_allows_the_merge(self):
        # 死锁态：required＋同 HEAD 已红冷却。放行合并让 HEAD 前进，冷却降级为 'time'，
        # required 下 post-commit 自动补跑在新 HEAD 上重测——这正是解锁路径。
        drive(cooling='head')

    def test_time_cooldown_still_blocks(self):
        # 'time' 冷却有 4 小时上限且机制正在补跑，不属于死锁态，保持报红。
        with self.assertRaises(AssertionError):
            drive(cooling='time')

    def test_no_cooldown_still_blocks(self):
        with self.assertRaises(AssertionError):
            drive(cooling='')

    def test_an_active_hold_allows_the_merge(self):
        # 暂缓生效：欠账照记、到点由等待者自动补跑，门禁的欠账项不报红（用户 2026-11-22 批准）。
        drive(hold=1.0, cooling='time')
        drive(hold=1.0, cooling='')

    def test_running_full_allows(self):
        drive(running=True)

    def test_tree_receipt_allows(self):
        drive(receipt={'tree': 'abc', 'round': 99})

    def test_participating_full_run_allows(self):
        drive(participating=True)

    def test_not_required_passes_before_cooling_is_consulted(self):
        drive(cooling='head', source_rounds=1)


if __name__ == '__main__':
    unittest.main()
