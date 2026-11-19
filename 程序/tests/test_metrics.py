# -*- coding: utf-8 -*-
"""I14 结构化指标自检：维度白名单/哈希、query 聚合、保留期清理、导出快照。

运行：python -B run_selftests.py -k metrics
"""
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import infra.metrics as metrics

_INSERT = ("INSERT INTO daily(day,name,dims,count,total,vmin,vmax) VALUES(?,?,?,?,?,?,?)")


class MetricsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(metrics, 'DIR', self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        with metrics._buf_lock:
            metrics._buf.clear()
            metrics._dropped.clear()
            metrics._dropped.update({'name': 0, 'dim': 0, 'overflow': 0})
            metrics._flush_pending[0] = False
            metrics._last_cleanup_day[0] = ''
        # 抑制 60s 自动落盘的执行器异步提交，测试一律走同步 metrics.flush()
        metrics._last_flush[0] = time.monotonic()

    def tearDown(self):
        with metrics._buf_lock:
            metrics._buf.clear()

    def _raw_lines(self, day=None):
        day = day or datetime.now().strftime('%Y%m%d')
        path = self.tmp / ('raw-%s.jsonl' % day)
        if not path.is_file():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding='utf-8').splitlines() if line.strip()]


class DimensionWhitelistTests(MetricsCase):
    """I14-1：白名单外维度名被拒绝；路径样值被哈希处理。"""

    def test_unknown_dimension_name_is_dropped_and_counted(self):
        metrics.counter('m.test', provider='h1', evil_dim='x', stage='video')
        metrics.flush()
        lines = self._raw_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['d'], {'provider': 'h1', 'stage': 'video'})
        self.assertNotIn('evil_dim', lines[0]['d'])
        self.assertEqual(metrics.dropped_counts()['dim'], 1)

    def test_path_like_value_is_hashed_not_stored(self):
        metrics.counter('m.test', project=r'D:\Users\me\我的项目', stage='video')
        metrics.counter('m.test', provider='D:\\secret\\dir\\file.txt')
        metrics.flush()
        lines = self._raw_lines()
        project_dim = lines[0]['d']['project']
        provider_dim = lines[1]['d']['provider']
        self.assertNotIn('我的项目', project_dim)
        self.assertNotIn('secret', provider_dim)
        self.assertNotIn('/', provider_dim)
        self.assertNotIn('\\', provider_dim)
        # project 恒哈希：即使值是安全形态也不存原文
        metrics.counter('m.test', project='plainname')
        metrics.flush()
        last = self._raw_lines()[-1]
        self.assertNotEqual(last['d']['project'], 'plainname')
        self.assertEqual(len(last['d']['project']), 16)

    def test_invalid_metric_name_is_dropped(self):
        metrics.counter('BAD NAME!', provider='h1')
        metrics.counter('', provider='h1')
        metrics.counter('ok.name-1_x', provider='h1')
        metrics.flush()
        lines = self._raw_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['n'], 'ok.name-1_x')
        self.assertEqual(metrics.dropped_counts()['name'], 2)


class QueryAggregationTests(MetricsCase):
    """I14-2：query 按 provider/stage/outcome 聚合次数、p50、p95。"""

    def test_query_groups_counts_and_percentiles(self):
        for value in (10.0, 20.0, 30.0, 40.0):
            metrics.observe('http.request', value, provider='api.a.com',
                            stage='video', outcome='ok')
        metrics.observe('http.request', 100.0, provider='api.b.com',
                        stage='video', outcome='error', error_code='E-NET-UNREACHABLE')
        metrics.counter('http.request', provider='api.a.com', stage='video', outcome='ok')
        metrics.flush()
        rows = metrics.query('http.request', group_by=('provider', 'outcome'))
        self.assertEqual(len(rows), 2)
        by_provider = {row['group']['provider']: row for row in rows}
        a = by_provider['api.a.com']
        self.assertEqual(a['count'], 5)          # 4 observe + 1 counter
        self.assertEqual(a['observed'], 4)
        self.assertAlmostEqual(a['p50'], 25.0, places=1)
        self.assertAlmostEqual(a['p95'], 38.5, places=1)
        self.assertAlmostEqual(a['total'], 100.0)
        b = by_provider['api.b.com']
        self.assertEqual(b['count'], 1)
        self.assertEqual(b['p50'], 100.0)
        self.assertEqual(b['group']['outcome'], 'error')

    def test_query_stage_and_since_filter(self):
        old = time.time() - 3 * 86400
        metrics.observe('stage.run', 5.0, stage='assets', outcome='ok')
        metrics.flush()
        day = datetime.now().strftime('%Y%m%d')
        path = self.tmp / ('raw-%s.jsonl' % day)
        path.write_text(path.read_text(encoding='utf-8') +
                        json.dumps({'t': old, 'n': 'stage.run', 'k': 'o', 'v': 9.0,
                                    'd': {'stage': 'assets', 'outcome': 'ok'}},
                                   ensure_ascii=False) + '\n', encoding='utf-8')
        rows = metrics.query('stage.run', group_by=('stage',))
        self.assertEqual(rows[0]['count'], 2)
        rows = metrics.query('stage.run', group_by=('stage',), since='2999-01-01')
        self.assertEqual(rows, [])
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        rows = metrics.query('stage.run', group_by=('stage',), since=yesterday)
        self.assertEqual(rows[0]['count'], 1)   # 3 天前事件被 since 滤掉

    def test_query_merges_sqlite_days_without_raw(self):
        # 造一个 20 天前的 sqlite 日汇总行（raw 已过期删除）
        metrics.observe('old.metric', 1.0, stage='x')
        metrics.flush()
        old_day = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
        db = sqlite3.connect(str(self.tmp / 'summary.sqlite'), timeout=5)
        db.execute(_INSERT, (old_day, 'old.metric',
                             json.dumps({'stage': 'x'}, sort_keys=True), 7, 7.0, 1.0, 1.0))
        db.commit()
        db.close()
        rows = metrics.query('old.metric', group_by=('stage',))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['count'], 8)   # sqlite 7 + 当日 raw 1
        self.assertAlmostEqual(rows[0]['p50'], 1.0)  # 分位只来自 raw observe


class RetentionCleanupTests(MetricsCase):
    """I14-3：超过保留期的原始文件与汇总行被清理；清理随后台落盘执行。"""

    def test_expired_raw_file_and_summary_rows_are_removed(self):
        # 20 天前 raw 文件（>14 天保留期）应被删；sqlite 20 天行（<180 天）应保留、
        # sqlite 200 天行（>180 天）应删。
        old_day = (datetime.now() - timedelta(days=20)).strftime('%Y%m%d')
        old_iso = old_day[:4] + '-' + old_day[4:6] + '-' + old_day[6:]
        ancient_iso = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
        (self.tmp / ('raw-%s.jsonl' % old_day)).write_text(
            json.dumps({'t': 0, 'n': 'old.metric', 'k': 'c', 'd': {}},
                       ensure_ascii=False) + '\n', encoding='utf-8')
        metrics.observe('new.metric', 1.0)
        metrics.flush()   # 首次 flush 建 sqlite 并触发当日清理
        db = sqlite3.connect(str(self.tmp / 'summary.sqlite'), timeout=5)
        try:
            db.execute(_INSERT, (old_iso, 'keep.metric', '{}', 3, 3.0, 1.0, 1.0))
            db.execute(_INSERT, (ancient_iso, 'keep.metric', '{}', 3, 3.0, 1.0, 1.0))
            db.commit()
        finally:
            db.close()
        # 清理每日至多一次：重置当日标记后再 flush 验证删除生效
        metrics._last_cleanup_day[0] = ''
        metrics.observe('new.metric', 2.0)
        metrics.flush()
        self.assertFalse((self.tmp / ('raw-%s.jsonl' % old_day)).exists())
        db = sqlite3.connect(str(self.tmp / 'summary.sqlite'), timeout=5)
        try:
            days = {row[0] for row in db.execute(
                'SELECT day FROM daily WHERE name=?', ('keep.metric',))}
        finally:
            db.close()
        self.assertIn(old_iso, days)          # 20 天 < 180 天，保留
        self.assertNotIn(ancient_iso, days)    # 200 天 > 180 天，删除

    def test_counter_alone_does_not_run_cleanup(self):
        # 清理只在后台落盘路径执行：打点本身不扫目录（规则 33 启动路径零扫描）
        metrics.counter('m.test')
        self.assertFalse((self.tmp / 'summary.sqlite').exists())


class ExportSnapshotTests(MetricsCase):
    """接入 diagnostic_capture.export() 的快照形态。"""

    def test_snapshot_shape_and_no_paths(self):
        metrics.counter('m.test', provider='h1', project=r'D:\secret\proj')
        snap = metrics.export_snapshot()
        self.assertIn('totals', snap)
        self.assertIn('m.test', snap['totals'])
        self.assertIn('dimensions', snap)
        self.assertNotIn('D:\\', json.dumps(snap, ensure_ascii=False))
        self.assertNotIn('secret', json.dumps(snap, ensure_ascii=False))

    def test_flush_is_idempotent_and_buffer_drains(self):
        for _ in range(5):
            metrics.counter('m.batch', stage='s')
        metrics.flush()
        with metrics._buf_lock:
            self.assertEqual(len(metrics._buf), 0)
        lines = self._raw_lines()
        self.assertEqual(len(lines), 5)
        # 再 flush 不重复写
        metrics.flush()
        self.assertEqual(len(self._raw_lines()), 5)


if __name__ == '__main__':
    unittest.main()
