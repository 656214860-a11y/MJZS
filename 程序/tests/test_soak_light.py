"""轻量 soak（阶段4 T7）：固定轮数反复走真实落盘生命周期，看状态与内存是否只涨不落。

默认 12 轮、三镜，跑在全量安全层，成本按实测记录（见 docs/process/联调测试出口基线.md §6）。
要跑更长的 3–5 分钟档就设 SOAK_MINUTES=4：轮数按墙上时间延长，观察值随之记录；
墙上时间只记观测、不设硬阈值，否则机器负载会被当成代码退化。
"""
import os
import shutil
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path

from agent.core import file_hash, read
from engine import Studio
from offline_recovery_fixture import missing_external_programs, prepare_project, scope
from skip_reasons import MISSING_FFMPEG

SHOTS = ('SH001', 'SH009', 'SH010')   # 只用替身不注入故障的镜号：soak 量的是稳态，不是恢复路径
ROUNDS = int(os.environ.get('SOAK_ROUNDS', '12'))
MINUTES = float(os.environ.get('SOAK_MINUTES', '0') or 0)
ROUND_SECONDS_LIMIT = 10        # 单轮上限：实测 1.3 秒，留约 7 倍余量；超限先查机器负载
GROWTH_KB_PER_ROUND = 128       # 稳态后每轮增幅上限：实测 21 KB，留约 6 倍余量（tracemalloc，非工作集）
# 每墙上秒约消耗 4.3 制作秒（3 镜 × 2 秒 / 1.4 秒）；额度必须显式放大，
# 否则长时间档测到的是「超过可用制作秒数」拦截，不是稳态（R1632 实测在约第 50 轮撞上）。
BUDGET_SECONDS = int(300 + MINUTES * 60 * 8)


class LightSoakTests(unittest.TestCase):
    """同一条项目反复提交／轮询／改稿，结果必须逐轮可预测。"""

    @classmethod
    def setUpClass(cls):
        if missing_external_programs():
            cls.skipTest(MISSING_FFMPEG)
        cls.tmp = Path(tempfile.mkdtemp(prefix='soak-light-'))
        cls.root = prepare_project(cls.tmp / 'project', SHOTS, budget_seconds=BUDGET_SECONDS)
        cls.round_seconds = []
        cls.round_versions = []
        cls.round_memory_kb = []
        tracing = tracemalloc.is_tracing()
        if not tracing:
            tracemalloc.start()
        deadline = time.monotonic() + MINUTES * 60
        with scope(cls.root):
            round_no = 0
            while round_no < ROUNDS or time.monotonic() < deadline:
                round_no += 1
                started = time.monotonic()
                studio = Studio(cls.root)
                for sid in SHOTS:
                    studio.submit(sid)
                    studio.poll(sid)
                    studio.review(sid, 'revise', 'OFFLINE SOAK round %d' % round_no)
                cls.round_seconds.append(round(time.monotonic() - started, 3))
                cls.round_versions.append({sid: len(studio.state()['shots'][sid]) for sid in SHOTS})
                cls.round_memory_kb.append(tracemalloc.get_traced_memory()[0] / 1024.0)
        cls.rounds = round_no
        if not tracing:
            tracemalloc.stop()
        cls.final = Studio(cls.root)
        for sid in SHOTS:            # 收尾采用：轮数由墙上时间决定，所以“最后一批”只能在循环后认，不能提前判。
            cls.final.review(sid, 'pass', 'OFFLINE SOAK final acceptance')
        cls.attempts = read(cls.root / 'offline-provider.json')['attempts']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_round_adds_exactly_one_version_and_submission_per_shot(self):
        """轮数、版本数、供应商提交数三者必须逐镜相等：丢一轮或多提交一次都算失败。"""
        self.assertEqual(self.rounds, len(self.round_versions))
        for sid in SHOTS:
            self.assertEqual(self.attempts[sid], self.rounds, sid)
            self.assertEqual(len(self.final.state()['shots'][sid]), self.rounds, sid)
            growth = [row[sid] for row in self.round_versions]
            self.assertEqual(growth, list(range(1, self.rounds + 1)), sid)

    def test_earlier_versions_stay_on_disk(self):
        """改稿只许追加：每一版的文件都还在，不能靠覆盖旧版换增长。"""
        versions = self.final.state()['shots']['SH001']
        paths = [Path(self.root / row['file']) if not Path(row['file']).is_absolute()
                 else Path(row['file']) for row in versions]
        missing = [str(path) for path in paths if not path.exists()]
        self.assertEqual(missing, [])
        self.assertEqual(len({file_hash(path) for path in paths}), 1,
                         '离线替身每轮给同一份合成源片，版本内容应逐字节相同')

    def test_no_round_exceeds_the_recorded_per_round_budget(self):
        worst = max(self.round_seconds)
        self.assertLessEqual(
            worst, ROUND_SECONDS_LIMIT,
            '最慢一轮 %.3f 秒超过记录上限 %d 秒（逐轮耗时：%s）——先确认机器负载，再查链路退化'
            % (worst, ROUND_SECONDS_LIMIT, self.round_seconds))

    def test_steady_state_memory_does_not_grow_per_round(self):
        """稳态口径：丢掉首轮预热，看后段每轮增幅，避免把一次性的初始化算成泄漏。"""
        samples = self.round_memory_kb
        self.assertGreaterEqual(len(samples), 3, '轮数太少，稳态增幅没有意义')
        per_round = (samples[-1] - samples[1]) / (len(samples) - 2)
        self.assertLessEqual(
            per_round, GROWTH_KB_PER_ROUND,
            '稳态每轮增长 %.1f KB 超过上限 %d KB（逐轮样本 KB：%s）'
            % (per_round, GROWTH_KB_PER_ROUND, [round(value, 1) for value in samples]))