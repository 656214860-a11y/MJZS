"""离线全链 E2E 自动收编（阶段4 T1）：10 镜＋故障矩阵＋真实编码与落盘。

把手工脚本 `维护记录/基准脚本/recovery_to_delivery_baseline.py` 的核心断言钉进自动套件：
一条真实临时项目跑完全链，全部用例共享这一次运行，只读同一份 result.json。
供应商仍是离线替身；这里证明的是代码路径与持久化事实，不是真实供应商可用性或人工验收。
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from agent.core import file_hash
from engine import read_edit_bundle
from offline_recovery_fixture import main, missing_external_programs
from skip_reasons import MISSING_FFMPEG

BUDGET_SECONDS = 150          # 观测口径：本机实测 32.5 秒，留约 4 倍余量；超此值先查负载再查链路
SHOT_IDS = ['SH%03d' % number for number in range(1, 11)]
EXPECTED_ATTEMPTS = {sid: (2 if sid in ('SH003', 'SH006', 'SH007') else 1) for sid in SHOT_IDS}
FAULT_KEYS = ('disconnect', '429', 'poll_timeout', 'process_restart', 'forced_termination',
              'cancelled', 'edit_while_running', 'partial_download')


class RecoveryDeliveryE2ETests(unittest.TestCase):
    """一次真实全链运行，四条互不重叠的结论。"""

    @classmethod
    def setUpClass(cls):
        if missing_external_programs():
            cls.skipTest(MISSING_FFMPEG)
        cls.tmp = Path(tempfile.mkdtemp(prefix='recovery-delivery-e2e-'))
        main(cls.tmp / 'fixture')
        cls.root = cls.tmp / 'fixture'
        cls.result = json.loads((cls.root / 'result.json').read_text(encoding='utf-8'))
        cls.faults = cls.result['faults']

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_no_shot_is_submitted_twice_and_adoption_is_not_replaceable(self):
        """提交次数矩阵：断网／429／取消／改稿各恢复一次，其余只提交一次。"""
        attempts = self.result['submissions']
        self.assertEqual(attempts, EXPECTED_ATTEMPTS,
                         '每镜提交次数是“不重复提交”的唯一凭据；变化即链路语义变化')
        self.assertEqual(self.result['shots'], len(SHOT_IDS))
        self.assertEqual(len(self.result['scope'].split('NOT real-provider')), 2,
                         'result.json 必须自带“非真实供应商／非人工验收”的范围声明')

    def test_fault_matrix_covers_every_recovery_path(self):
        """八类故障都要有命名证据，且恢复后任务编号与进程边界对得上。"""
        missing = [key for key in FAULT_KEYS if key not in self.faults]
        self.assertEqual(missing, [], '故障矩阵缺项')
        self.assertIn('提交连接中断', self.faults['disconnect'])
        self.assertIn('HTTP 429', self.faults['429'])
        self.assertIn('编号已保留', self.faults['poll_timeout'])
        self.assertIn('已取消', self.faults['cancelled'])
        self.assertIn('正在生成', self.faults['edit_while_running'])
        self.assertIn('下载中断', self.faults['partial_download'])
        restart, killed = self.faults['process_restart'], self.faults['forced_termination']
        self.assertEqual(restart['task_id'], killed['task_id'],
                         '强杀后跨进程恢复必须还是同一个任务编号')
        self.assertNotEqual(restart['pid'], killed['pid'])
        self.assertNotEqual(killed['exit_code'], 0)
        self.assertEqual(killed['recovered_task_id'], killed['task_id'])

    def test_deliverable_spec_bundle_and_quality_evidence(self):
        """成片：规格、剪辑清单顺序、改稿版本号、质检与摘要一致。"""
        spec = self.result['output_spec']
        self.assertEqual((spec['width'], spec['height'], spec['fps']), (1080, 1920, 25))
        self.assertEqual(self.result['qc']['errors'], [], '成片质检不允许有错')
        master = Path(self.result['master'])
        self.assertTrue(master.exists(), master)
        self.assertEqual(file_hash(master), self.result['sha256'])
        manifest = read_edit_bundle(master.parent)['manifest']
        self.assertEqual([row['shot'] for row in manifest], SHOT_IDS)
        self.assertEqual(manifest[6]['version'], 2, '改稿后交付的必须是第 2 版')
        self.assertRegex(self.result['head'], r'^[0-9a-f]{40}$')

    def test_runtime_stays_within_the_recorded_budget(self):
        """耗时口径：只作观测与退化报警，不当作性能承诺。"""
        seconds = self.result['seconds']
        self.assertGreater(seconds, 0)
        self.assertLessEqual(
            seconds, BUDGET_SECONDS,
            '全链耗时 %.1f 秒超出记录预算 %d 秒；先确认是本机负载还是链路退化，再决定是改口径还是修代码'
            % (seconds, BUDGET_SECONDS))