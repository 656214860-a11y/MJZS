# -*- coding: utf-8 -*-
"""日报／周报自检：归一键、规则建议、渲染确定性、落盘与同日覆盖、周汇总口径。运行：python test_pet_report.py"""
import calendar, json, os, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import pet_llm, pet_report, pet_state
from unittest.mock import patch
from pet_bus import STAGES

AT = calendar.timegm((2026, 9, 20, 4, 0, 0, 0, 0, 0))          # 北京时间 2026-09-20 12:00
DAY = '2026-09-20'
KEYS = ['counts', 'day', 'done_stages', 'failures', 'notices', 'percent', 'project', 'stage',
        'stage_name', 'stages', 'timings', 'tokens', 'total_stages']
COUNT_KEYS = ['adopted', 'assets', 'frames', 'ready_assets', 'scripts', 'shots', 'storyboards']
TOKEN_KEYS = ['budget', 'cached', 'completion', 'entries', 'flash_entries', 'flash_share', 'hit_rate',
              'prompt', 'today']


class FakeLedger:
    """只提供 gather 真正用到的两样东西：entries 与 today_tokens。"""

    def __init__(self, entries=None, today=0, broken=False):
        self.entries = entries or []
        self._today = today
        self.broken = broken

    def today_tokens(self, at=None):
        if self.broken:
            raise RuntimeError('台账坏了')
        return self._today


def entry(prompt, cached, tier='flash', completion=10):
    return {'prompt_tokens': prompt, 'completion_tokens': completion, 'cached_tokens': cached, 'tier': tier}


def project_in(td):
    proj = Path(td) / 'p'
    proj.mkdir(parents=True, exist_ok=True)
    return proj


class GatherTests(unittest.TestCase):
    def test_defaults_are_complete_and_empty(self):
        data = pet_report.gather()
        self.assertEqual(sorted(data), KEYS)
        self.assertEqual(sorted(data['tokens']), TOKEN_KEYS)
        self.assertEqual(sorted(data['counts']), COUNT_KEYS)
        self.assertEqual(sorted(data['counts']), sorted(pet_report.COUNT_KEYS))
        self.assertEqual(set(data['counts'].values()), {0})
        self.assertEqual(data['total_stages'], len(STAGES))
        self.assertEqual(data['tokens']['hit_rate'], 0.0)
        self.assertEqual(data['failures'], [])
        self.assertEqual(data['timings'], {'stages': {}, 'units': {}, 'rates': {}})
        self.assertEqual(data['notices'], {'sent': 0, 'pending': 0, 'recorded': 0})

    def test_token_totals_and_rates(self):
        ledger = FakeLedger([entry(100, 90), entry(100, 0, tier='pro')])
        data = pet_report.gather(ledger=ledger)
        tokens = data['tokens']
        self.assertEqual((tokens['prompt'], tokens['cached'], tokens['completion']), (200, 90, 20))
        self.assertEqual(tokens['entries'], 2)
        self.assertEqual(tokens['flash_entries'], 1)
        self.assertEqual(tokens['hit_rate'], 0.45)
        self.assertEqual(tokens['flash_share'], 0.5)

    def test_today_and_budget_come_from_inputs(self):
        data = pet_report.gather(ledger=FakeLedger([entry(10, 5)], today=1500), budget=2000)
        self.assertEqual(data['tokens']['today'], 1500)
        self.assertEqual(data['tokens']['budget'], 2000)

    def test_broken_ledger_does_not_raise(self):
        data = pet_report.gather(ledger=FakeLedger([entry(10, 5)], broken=True), budget=None)
        self.assertEqual(data['tokens']['today'], 0)
        self.assertEqual(data['tokens']['budget'], 0)

    def test_failures_and_stage_states_are_normalized(self):
        stages = {'keyframe': {'state': 'running'}, 'script': 'bad-shape'}
        data = pet_report.gather(failures=[{'stage': 'video', 'category': 'retryable', 'error': '超时', 'hint': '稍后重试'},
                                           'junk', {'stage': None}], stages=stages)
        self.assertEqual(len(data['failures']), 2)
        self.assertEqual(data['failures'][0]['hint'], '稍后重试')
        self.assertEqual(data['stages'], {'keyframe': 'running'})

    def test_notice_counts(self):
        data = pet_report.gather(notices={'sent': [1, 2], 'pending': [3], 'recorded': [4, 5, 6]})
        self.assertEqual(data['notices'], {'sent': 2, 'pending': 1, 'recorded': 3})

    def test_counts_are_normalized_and_filled_with_zero(self):
        data = pet_report.gather(counts={'shots': 12, 'frames': '7', 'junk': 99})
        self.assertEqual(data['counts']['shots'], 12)
        self.assertEqual(data['counts']['frames'], 7)
        self.assertEqual(data['counts']['assets'], 0)
        self.assertNotIn('junk', data['counts'])

    def test_broken_counts_do_not_raise(self):
        self.assertEqual(pet_report.gather(counts='乱写的')['counts']['shots'], 0)

    def test_day_key_follows_beijing(self):
        evening = calendar.timegm((2026, 9, 20, 12, 0, 0, 0, 0, 0))      # 北京 20:00
        midnight = calendar.timegm((2026, 9, 20, 18, 0, 0, 0, 0, 0))     # 北京次日 02:00
        self.assertEqual(pet_report.gather(at=evening)['day'], '2026-09-20')
        self.assertEqual(pet_report.gather(at=midnight)['day'], '2026-09-21')

    def test_project_name_is_used(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(pet_report.gather(project=project_in(td))['project'], 'p')


class AdviceTests(unittest.TestCase):
    def test_no_ledger_entries_says_so(self):
        items = pet_report.advice(pet_report.gather())
        self.assertTrue(any('还没有 Token 台账记录' in item for item in items), items)

    def test_low_hit_rate_points_at_the_prefix(self):
        items = pet_report.advice(pet_report.gather(ledger=FakeLedger([entry(1000, 100)])))
        self.assertTrue(any('缓存命中率' in item and '前缀' in item for item in items), items)

    def test_low_flash_share_points_at_pro(self):
        items = pet_report.advice(pet_report.gather(ledger=FakeLedger([entry(1000, 900, tier='pro')])))
        self.assertTrue(any('Flash 占比' in item for item in items), items)

    def test_healthy_ledger_has_no_rate_complaint(self):
        items = pet_report.advice(pet_report.gather(ledger=FakeLedger([entry(1000, 900)])))
        self.assertFalse(any('Flash 占比' in item or '缓存命中率' in item for item in items), items)

    def test_budget_over_threshold_mentions_off_peak(self):
        data = pet_report.gather(ledger=FakeLedger([entry(10, 9)], today=1700), budget=2000)
        self.assertTrue(any('23:00-07:00' in item for item in pet_report.advice(data)))

    def test_budget_below_threshold_is_silent(self):
        data = pet_report.gather(ledger=FakeLedger([entry(10, 9)], today=100), budget=2000)
        self.assertFalse(any('23:00-07:00' in item for item in pet_report.advice(data)))

    def test_failures_are_grouped_by_stage(self):
        data = pet_report.gather(failures=[{'stage': 'keyframe', 'error': '审核', 'hint': '换提示词'},
                                           {'stage': 'keyframe', 'error': '审核', 'hint': '换提示词'},
                                           {'stage': 'video', 'error': '超时'}])
        items = pet_report.advice(data)
        self.assertEqual(len([item for item in items if '首帧管理' in item]), 1)
        self.assertTrue(any('首帧管理 有 2 条' in item and '换提示词' in item for item in items), items)
        self.assertTrue(any('视频生成 有 1 条' in item for item in items), items)

    def test_unfinished_stages_are_named(self):
        data = pet_report.gather(progress={'done_stages': 3, 'total_stages': 10, 'stage_name': '首帧管理'})
        self.assertTrue(any('还有 7 个阶段没有收尾' in item and '首帧管理' in item for item in pet_report.advice(data)))

    def test_quiet_hours_notice(self):
        data = pet_report.gather(notices={'recorded': [1, 2], 'pending': [3]})
        items = pet_report.advice(data)
        self.assertTrue(any('免打扰' in item for item in items))
        self.assertTrue(any('攒在队列' in item for item in items))

    def test_all_clear(self):
        data = pet_report.gather(progress={'done_stages': 10, 'total_stages': 10, 'percent': 100.0},
                                 ledger=FakeLedger([entry(1000, 900)], today=10), budget=2000)
        self.assertEqual(len(pet_report.advice(data)), 1)
        self.assertIn('状态正常', pet_report.advice(data)[0])


class RenderTests(unittest.TestCase):
    def data(self):
        return pet_report.gather(progress={'percent': 42.5, 'done_stages': 4, 'total_stages': 10,
                                           'stage': 'keyframe', 'stage_name': '首帧管理'},
                                 ledger=FakeLedger([entry(1000, 900)], today=100), budget=2000,
                                 failures=[{'stage': 'video', 'error': '超时', 'hint': '稍后重试'}],
                                 notices={'sent': [1], 'pending': [], 'recorded': [2, 3]},
                                 stages={'script': {'state': 'success'}, 'keyframe': {'state': 'running'}},
                                 project=Path('D:/x/星空项目'), at=AT)

    def test_body_has_the_numbers(self):
        text = pet_report.render(self.data())
        for token in [DAY, '星空项目', '42.5%', '4／10 阶段', '首帧管理', '命中率 90%', 'Flash 占比 100%', '100／2000']:
            self.assertIn(token, text, token)
        self.assertIn('## 建议', text)

    def test_render_is_deterministic(self):
        self.assertEqual(pet_report.render(self.data()), pet_report.render(self.data()))

    def test_items_override_the_default_advice(self):
        text = pet_report.render(self.data(), items=['自定义建议'])
        self.assertIn('- 自定义建议', text)
        self.assertNotIn('稍后重试', text)

    def test_settled_stages_are_not_listed_as_open(self):
        text = pet_report.render(self.data())
        self.assertIn('没有收尾的阶段：首帧管理（running）', text)
        self.assertNotIn('剧本准备（success）', text)

    def test_material_counts_are_kept_out_of_the_body_when_absent(self):
        text = pet_report.render(self.data())
        self.assertNotIn('素材：', text)
        self.assertNotIn('还没补齐', text)

    def test_material_counts_render_one_line(self):
        data = self.data()
        data['counts'] = {'scripts': 2, 'storyboards': 3, 'adopted': 1, 'shots': 40, 'frames': 12,
                          'assets': 9, 'ready_assets': 4}
        text = pet_report.render(data)
        self.assertIn('素材：剧本 2 · 分镜 3（已采用 1）· 镜头 40 · 首帧 12 · 资产 9（已有图 4）', text)

    def test_missing_first_frames_become_an_actionable_suggestion(self):
        data = self.data()
        data['counts'] = {'shots': 40, 'frames': 12}
        self.assertIn('- 首帧 12／40 还没补齐', pet_report.render(data))

    def test_complete_first_frames_raise_no_suggestion(self):
        data = self.data()
        data['counts'] = {'shots': 40, 'frames': 40}
        self.assertNotIn('还没补齐', pet_report.render(data))


class WriteTests(unittest.TestCase):
    def data(self, day_at=AT, percent=42.5):
        return pet_report.gather(progress={'percent': percent, 'done_stages': 4, 'total_stages': 10},
                                 ledger=FakeLedger([entry(100, 90)], today=50), budget=1000,
                                 project=Path('p'), at=day_at)

    def test_write_creates_the_daily_file_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            path, summary = pet_report.write(proj, self.data())
            self.assertEqual(path.name, DAY + '.md')
            self.assertTrue(path.is_file())
            self.assertIn(DAY, path.read_text(encoding='utf-8'))
            self.assertEqual(len(pet_report.load_rows(proj)), 1)

    def test_same_day_is_overwritten_not_appended(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.write(proj, self.data(percent=10.0))
            pet_report.write(proj, self.data(percent=90.0))
            rows = pet_report.load_rows(proj)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['percent'], 90.0)

    def test_rows_stay_sorted_and_trimmed(self):
        rows = [{'day': '2026-09-18'}, {'day': '2026-09-20'}, {'day': '2026-09-19'}]
        merged = pet_report.merge_rows(rows, {'day': '2026-09-21'}, keep=3)
        self.assertEqual([row['day'] for row in merged], ['2026-09-19', '2026-09-20', '2026-09-21'])

    def test_broken_summary_file_is_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            path = pet_report.summary_path(proj)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{坏掉的 JSON', encoding='utf-8')
            self.assertEqual(pet_report.load_rows(proj), [])
            pet_report.write(proj, self.data())
            self.assertEqual(len(pet_report.load_rows(proj)), 1)

    def test_daily_helper_writes_and_returns(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            data, path = pet_report.daily(proj, progress={'percent': 5.0}, at=AT)
            self.assertEqual(data['day'], DAY)
            self.assertTrue(path.is_file())


class WeeklyTests(unittest.TestCase):
    def test_retention_uses_calendar_days_and_recycles_reports(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            folder = pet_report.report_dir(proj)
            folder.mkdir(parents=True)
            expired = ['2026-06-22.md', '周报-2026-06-15.md']
            retained = ['2026-06-23.md', '周报-2026-06-22.md',
                        '2026-06-22-notes.md', '2026-02-30.md']
            for name in expired + retained:
                (folder / name).write_text(name, encoding='utf-8')
            removed = pet_report.prune(proj, at=AT)
            self.assertEqual(sorted(p.name for p in removed), sorted(expired))
            self.assertEqual(sorted(p.name for p in folder.glob('*.md')), sorted(retained))
            from storage_maintenance import recycle_base, read_recycle_batch, restore_recycle_batch
            batch = next(recycle_base(proj).iterdir())
            self.assertEqual(len(read_recycle_batch(proj, batch)['items']), 2)
            restore_recycle_batch(proj, batch)
            for name in expired:
                self.assertEqual((folder / name).read_text(encoding='utf-8'), name)

    def test_sparse_summary_ages_out_without_waiting_for_ninety_rows(self):
        rows = [{'day': '2025-01-01'}, {'day': '2026-06-22'}, {'day': '2026-06-23'}]
        merged = pet_report.merge_rows(rows, {'day': DAY})
        self.assertEqual([r['day'] for r in merged], ['2026-06-23', DAY])

    def test_daily_custom_retention_and_unlimited_retention(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.daily(proj, at=AT - 4 * 86400)
            pet_report.daily(proj, at=AT, keep=0)
            self.assertTrue(pet_report.report_path(proj, '2026-09-16').exists())
            pet_report.daily(proj, at=AT, keep=3)
            self.assertFalse(pet_report.report_path(proj, '2026-09-16').exists())
            self.assertEqual([r['day'] for r in pet_report.load_rows(proj)], [DAY])

    def test_cleanup_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            folder = pet_report.report_dir(proj)
            folder.mkdir(parents=True)
            old = folder / '2025-01-01.md'
            old.write_text('retain on failure', encoding='utf-8')
            with patch('storage_maintenance.recycle_paths', side_effect=PermissionError('occupied')):
                self.assertEqual(pet_report.prune(proj, at=AT), [])
            self.assertTrue(old.exists())

    def test_weekly_also_prunes_sparse_summary(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.daily(proj, at=AT - 100 * 86400)
            pet_report.write_weekly(proj, at=AT)
            self.assertEqual(pet_report.load_rows(proj), [])
            self.assertTrue(pet_report.weekly_path(proj, DAY).exists())

    def test_rejected_recycle_and_invalid_dates_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            folder = pet_report.report_dir(proj)
            folder.mkdir(parents=True)
            for name in ['2025-01-01.md', '2025-99-99.md', '2025-99-99 (1).md']:
                (folder / name).write_text('preserve', encoding='utf-8')
            with patch('storage_maintenance.recycle_paths', return_value=[]):
                self.assertEqual(pet_report.prune(proj, at=AT), [])
            self.assertEqual(len(list(folder.glob('*.md'))), 3)

    def rows(self):
        days = ['2026-09-13', '2026-09-14', '2026-09-19', '2026-09-20', '2026-09-21']
        made = []
        for index, day in enumerate(days):
            made.append({'day': day, 'percent': float(index) * 10,
                         'tokens': {'prompt': 100, 'completion': 10, 'cached': 50, 'entries': 1, 'flash_entries': 1},
                         'failures': [{'stage': 'keyframe'}] if index > 1 else [],
                         'notices': {'sent': 1, 'pending': 0, 'recorded': 0}})
        return made

    def test_window_is_the_last_seven_days(self):
        picked = pet_report.weekly_rows(self.rows(), at=AT, days=7)
        self.assertEqual([row['day'] for row in picked], ['2026-09-14', '2026-09-19', '2026-09-20'])

    def test_totals_recompute_hit_rate_from_sums(self):
        totals = pet_report.weekly_totals(pet_report.weekly_rows(self.rows(), at=AT, days=7))
        self.assertEqual(totals['days'], 3)
        self.assertEqual((totals['prompt'], totals['cached']), (300, 150))
        self.assertEqual(totals['hit_rate'], 0.5)
        self.assertEqual(totals['failures'], 2)
        self.assertEqual(totals['failure_stages'], {'keyframe': 2})
        self.assertEqual(totals['first_day'], '2026-09-14')
        self.assertEqual(totals['last_day'], '2026-09-20')

    def test_empty_week_promises_nothing(self):
        totals = pet_report.weekly_totals([])
        self.assertEqual(totals['days'], 0)
        self.assertIn('本周还没有日报', pet_report.weekly_advice(totals)[0])
        self.assertIn('本周还没有日报', pet_report.render_weekly(totals))

    def test_failure_stage_advice_names_the_stage(self):
        items = pet_report.weekly_advice(pet_report.weekly_totals(self.rows()))
        self.assertTrue(any('首帧管理' in item for item in items), items)

    def test_render_weekly_lists_the_range_and_daily_progress(self):
        rows = pet_report.weekly_rows(self.rows(), at=AT, days=7)
        text = pet_report.render_weekly(pet_report.weekly_totals(rows), at=AT, rows=rows)
        self.assertIn('2026-09-14 ~ 2026-09-20', text)
        self.assertIn('每日进度：2026-09-14', text)

    def test_weekly_reads_what_daily_wrote(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            for offset in (4, 3):
                pet_report.daily(proj, progress={'percent': 20.0}, at=AT - offset * 86400)
            totals, text = pet_report.weekly(proj, at=AT)
            self.assertEqual(totals['days'], 2)
            self.assertIn('覆盖天数：2 天', text)
            path, _ = pet_report.write_weekly(proj, at=AT)
            # 第 21 期：周报按「本周周一」命名（一份周报一周只留一份），2026-09-20 是周日，本周一＝09-14。
            self.assertEqual(path.name, '周报-' + pet_report.week_key(DAY) + '.md')
            self.assertEqual(pet_report.week_key(DAY), '2026-09-14')
            self.assertTrue(path.is_file())

    def test_one_weekly_file_per_week(self):
        """第 21 期：同一个星期里写几次，盘上也只有一份（用户要的「每周只保存一份」）。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            named = []
            for offset in (3, 1, 0):
                path, _ = pet_report.write_weekly(proj, at=AT - offset * 86400)
                named.append(path.name)
            self.assertEqual(named, ['周报-2026-09-14.md'] * 3, '三次都落在同一份上')
            files = sorted(os.path.basename(item) for item in pet_report.report_dir(proj).glob('周报-*.md'))
            self.assertEqual(files, ['周报-2026-09-14.md'], '一周只有一份')

    def test_prune_deletes_extra_dailies_and_weeklies(self):
        """第 21 期：多余的日报／周报删掉——一天只留一份、一周只留一份，留最后写下去的那一份。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            folder = pet_report.report_dir(proj)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / '2026-09-20.md').write_text('正名', encoding='utf-8')
            (folder / '2026-09-20 (1).md').write_text('副本', encoding='utf-8')
            (folder / '周报-2026-09-14.md').write_text('本周正名', encoding='utf-8')
            for day in ('2026-09-17', '2026-09-19'):      # 同一周里按旧命名散落的几份
                (folder / ('周报-' + day + '.md')).write_text('旧命名', encoding='utf-8')
            removed = [item.name for item in pet_report.prune(proj, at=AT)]
            self.assertEqual(sorted(removed), ['2026-09-20 (1).md', '周报-2026-09-17.md', '周报-2026-09-19.md'])
            self.assertEqual(sorted(item.name for item in folder.glob('*.md')),
                             ['2026-09-20.md', '周报-2026-09-14.md'])
            self.assertEqual((folder / '2026-09-20.md').read_text(encoding='utf-8'), '正名')

    def test_prune_keeps_the_last_written_copy_when_the_name_is_not_canonical(self):
        """没有正名那份时留最新的一份，不能把一个星期的周报全删空。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            folder = pet_report.report_dir(proj)
            folder.mkdir(parents=True, exist_ok=True)
            older = folder / '周报-2026-09-17.md'
            newer = folder / '周报-2026-09-19.md'
            older.write_text('早', encoding='utf-8')
            newer.write_text('晚', encoding='utf-8')
            os.utime(str(older), (1000.0, 1000.0))
            os.utime(str(newer), (2000.0, 2000.0))
            pet_report.prune(proj, at=AT)
            self.assertEqual(sorted(item.name for item in folder.glob('周报-*.md')), ['周报-2026-09-19.md'])

    def test_a_bad_day_degrades_to_today_instead_of_crashing(self):
        """认不出来的日子不许把写报告这一步带崩：退回今天，照样给得出一个文件名。"""
        self.assertEqual(pet_report.as_day(DAY), DAY, '日期串原样用')
        self.assertEqual(pet_report.as_day(AT), DAY, '时间戳换成北京时间的日期')
        self.assertEqual(pet_report.week_key(DAY), '2026-09-14')
        self.assertEqual(len(pet_report.week_key('不是日期')), 10)

    def test_weekly_ignores_days_outside_the_window(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.daily(proj, progress={'percent': 1.0}, at=AT - 30 * 86400)
            pet_report.daily(proj, progress={'percent': 2.0}, at=AT)
            totals, _ = pet_report.weekly(proj, at=AT, days=7)
            self.assertEqual(totals['days'], 1)


    def test_counts_and_categories_come_from_the_rows(self):
        rows = [{'day': '2026-09-19', 'counts': {'shots': 10, 'frames': 1},
                 'failures': [{'stage': 'keyframe', 'category': 'timeout'},
                              {'stage': 'keyframe', 'category': 'content'}]},
                {'day': '2026-09-20', 'counts': {'shots': 12, 'frames': 5},
                 'failures': [{'stage': 'video', 'category': 'timeout'}]}]
        totals = pet_report.weekly_totals(rows)
        self.assertEqual(totals['counts']['shots'], 12, '取最近一天')
        self.assertEqual(totals['counts']['frames'], 5)
        self.assertEqual(totals['failure_categories'], {'timeout': 2, 'content': 1})

    def test_a_day_without_counts_does_not_erase_the_last_known_material(self):
        rows = [{'day': '2026-09-19', 'counts': {'shots': 12, 'frames': 5}},
                {'day': '2026-09-20', 'counts': {}}]
        self.assertEqual(pet_report.weekly_totals(rows)['counts']['shots'], 12)

    def test_render_weekly_shows_material_and_categories(self):
        totals = pet_report.weekly_totals([
            {'day': '2026-09-20',
             'counts': {'scripts': 2, 'storyboards': 3, 'adopted': 1, 'shots': 40, 'frames': 12,
                        'assets': 9, 'ready_assets': 4},
             'failures': [{'stage': 'keyframe', 'category': 'timeout'}]}])
        text = pet_report.render_weekly(totals)
        self.assertIn('素材（最近一天）：剧本 2 · 分镜 3（已采用 1）· 镜头 40 · 首帧 12 · 资产 9（已有图 4）', text)
        self.assertIn('失败分类：超时 1', text)

    def test_render_weekly_keeps_them_quiet_when_absent(self):
        text = pet_report.render_weekly(pet_report.weekly_totals(self.rows()))
        self.assertNotIn('素材（最近一天）', text)
        self.assertNotIn('失败分类：', text)

    def test_weekly_advice_names_the_top_category(self):
        totals = pet_report.weekly_totals([
            {'day': '2026-09-20',
             'failures': [{'stage': 'keyframe', 'category': 'content'},
                          {'stage': 'video', 'category': 'content'},
                          {'stage': 'video', 'category': 'timeout'}]}])
        items = pet_report.weekly_advice(totals)
        self.assertTrue(any('内容审核' in item and '2 次' in item for item in items), items)

    def test_weekly_reads_the_counts_daily_wrote(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.daily(proj, progress={'percent': 20.0}, at=AT, counts={'shots': 30, 'frames': 7})
            totals, text = pet_report.weekly(proj, at=AT)
            self.assertEqual(totals['counts']['shots'], 30)
            self.assertIn('镜头 30 · 首帧 7', text)


class TimingTests(unittest.TestCase):
    """阶段停留与平均单位耗时：日报写事实、周报取最近一天（累计量不能跨天相加）。"""

    def timings(self, **kwargs):
        payload = {'stages': {'keyframe': 600.0, 'assets': 120.0}, 'units': {'keyframe': 20, 'assets': 0},
                   'rates': {'keyframe': 30.0}}
        payload.update(kwargs)
        return payload

    def test_span_reads_like_a_duration(self):
        self.assertEqual(pet_report.span(0), '0:00')
        self.assertEqual(pet_report.span(37), '0:37')
        self.assertEqual(pet_report.span(600), '10:00')
        self.assertEqual(pet_report.span(3720), '1:02:00')

    def test_broken_seconds_are_zero_not_a_crash(self):
        for value in (None, '坏', True, -5, [1]):
            self.assertEqual(pet_report._seconds(value), 0.0, value)
            self.assertEqual(pet_report.span(value), '0:00', value)

    def test_normalize_drops_the_empty_and_the_zero(self):
        measured = pet_report.normalize_timings({'stages': {'keyframe': 600, 'assets': 0, '坏': '坏'},
                                                 'units': {'keyframe': 20, 'assets': 0},
                                                 'rates': {'keyframe': 30, 'assets': 0}})
        self.assertEqual(measured, {'stages': {'keyframe': 600.0}, 'units': {'keyframe': 20},
                                    'rates': {'keyframe': 30.0}})
        self.assertEqual(pet_report.normalize_timings(None), {'stages': {}, 'units': {}, 'rates': {}})
        self.assertEqual(pet_report.normalize_timings('坏'), {'stages': {}, 'units': {}, 'rates': {}})

    def test_gather_carries_the_measurements(self):
        data = pet_report.gather(timings=self.timings())
        self.assertEqual(data['timings']['stages'], {'keyframe': 600.0, 'assets': 120.0})
        self.assertEqual(data['timings']['rates'], {'keyframe': 30.0})

    def test_daily_report_writes_both_lines(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            data, path = pet_report.daily(proj, progress={'percent': 5.0}, at=AT, timings=self.timings())
            text = path.read_text(encoding='utf-8')
            self.assertIn('- 阶段停留：首帧管理 10:00 · 资产管理 2:00', text)
            self.assertIn('- 平均耗时：首帧管理 0:30/镜', text)
            self.assertEqual(data['timings']['units'], {'keyframe': 20})

    def test_a_report_without_measurements_says_nothing_about_time(self):
        text = pet_report.render(pet_report.gather(at=AT))
        self.assertNotIn('阶段停留', text)
        self.assertNotIn('平均耗时', text)

    def test_advice_names_the_slowest_stage(self):
        items = pet_report.advice(pet_report.gather(timings=self.timings()))
        self.assertTrue(any('耗时最长' in item and '首帧管理' in item and '10:00' in item for item in items), items)

    def test_advice_mentions_the_average_shot_cost(self):
        items = pet_report.advice(pet_report.gather(timings=self.timings()))
        self.assertTrue(any('平均单镜首帧耗时 0:30' in item for item in items), items)

    def test_no_rates_means_no_average_advice(self):
        items = pet_report.advice(pet_report.gather(timings={'stages': {'keyframe': 60}}))
        self.assertFalse(any('平均单镜' in item for item in items), items)

    def test_weekly_timings_take_the_most_recent_day(self):
        rows = [{'day': '2026-09-19', 'timings': {'stages': {'keyframe': 600}, 'units': {'keyframe': 20},
                                                  'rates': {'keyframe': 30}}},
                {'day': '2026-09-20', 'timings': {'stages': {'keyframe': 900, 'assets': 60},
                                                  'units': {'keyframe': 30},
                                                  'rates': {'keyframe': 30}}}]
        totals = pet_report.weekly_totals(rows)
        self.assertEqual(totals['timings']['stages'], {'keyframe': 900.0, 'assets': 60.0}, '累计量取最近一天，不能相加')

    def test_a_day_without_timings_keeps_the_last_known_measurement(self):
        rows = [{'day': '2026-09-19', 'timings': {'stages': {'keyframe': 600}}},
                {'day': '2026-09-20'}]
        self.assertEqual(pet_report.weekly_totals(rows)['timings']['stages']['keyframe'], 600.0)

    def test_render_weekly_shows_the_measurements(self):
        totals = pet_report.weekly_totals([{'day': '2026-09-20', 'timings': self.timings()}])
        text = pet_report.render_weekly(totals)
        self.assertIn('- 阶段停留（截至最近一天）：首帧管理 10:00 · 资产管理 2:00', text)
        self.assertIn('- 平均耗时（截至最近一天）：首帧管理 0:30/镜', text)

    def test_weekly_keeps_them_quiet_when_absent(self):
        text = pet_report.render_weekly(pet_report.weekly_totals([{'day': '2026-09-20'}]))
        self.assertNotIn('阶段停留', text)
        self.assertNotIn('平均耗时', text)

    def test_weekly_advice_names_the_weekly_bottleneck(self):
        totals = pet_report.weekly_totals([{'day': '2026-09-20', 'timings': self.timings()}])
        items = pet_report.weekly_advice(totals)
        self.assertTrue(any('整周耗时最长' in item and '首帧管理' in item for item in items), items)

    def test_weekly_reads_the_timings_daily_wrote(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_in(td)
            pet_report.daily(proj, progress={'percent': 20.0}, at=AT, timings=self.timings())
            totals, text = pet_report.weekly(proj, at=AT)
            self.assertEqual(totals['timings']['rates'], {'keyframe': 30.0})
            self.assertIn('阶段停留（截至最近一天）', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
