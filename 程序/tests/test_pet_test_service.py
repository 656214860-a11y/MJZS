import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pet_test_service
import pet_agent
import pet_performance_service


class PetTestServiceTests(unittest.TestCase):
    def test_chat_rule_routes_incremental_test_as_free_local_action(self):
        plan = pet_agent.route('运行增量自检 3 次')
        self.assertEqual(plan['intent'], 'test')
        self.assertEqual(pet_agent.action_for(plan), 'stage.inspect')

    def test_chat_rule_routes_performance_check_as_free_local_action(self):
        plan = pet_agent.route('运行优化检查')
        self.assertEqual(plan['intent'], 'performance')
        self.assertEqual(pet_agent.action_for(plan), 'stage.inspect')

    def test_chat_rule_routes_long_list_check_separately(self):
        plan = pet_agent.route('运行长列表优化检查')
        self.assertEqual(plan['intent'], 'performance_list')
        self.assertEqual(pet_agent.action_for(plan), 'stage.inspect')

    def test_help_mentions_the_safe_local_check_commands(self):
        self.assertIn('运行增量自检', pet_agent.REPLIES['help'])
        self.assertIn('运行优化检查', pet_agent.REPLIES['help'])

    def test_repeat_count_has_safe_default_and_cap(self):
        self.assertEqual(pet_test_service.repeat_count('运行增量自检'), 1)
        self.assertEqual(pet_test_service.repeat_count('跑 3 次测试'), 3)
        self.assertEqual(pet_test_service.repeat_count('跑 999 次测试'), 20)

    def test_run_incremental_records_rate_and_failure_names(self):
        outputs = iter((
            SimpleNamespace(returncode=0, stdout='Ran 4 tests\nOK'),
            SimpleNamespace(returncode=1, stdout='FAIL: test_demo (tests.test_demo.Case)\nRan 4 tests'),
        ))
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / '项目'
            result = pet_test_service.run_incremental(
                folder, project, '跑 2 次测试', at=12,
                invoke=lambda _args, _cwd: next(outputs))
            self.assertEqual(result['item']['passed'], 1)
            self.assertEqual(result['item']['total'], 2)
            self.assertEqual(result['failures'], ['test_demo'])
            saved = pet_test_service.read_json(pet_test_service.ledger_path(project), {})
            self.assertEqual(saved['runs'][0]['success_rate'], 0.5)

    def test_poll_incremental_finishes_and_records_without_raw_log(self):
        with tempfile.TemporaryDirectory() as folder:
            output = tempfile.TemporaryFile(mode='w+b')
            output.write(b'Ran 2 tests\nOK')
            output.flush()
            session = {'program': Path(folder), 'command': ['python'],
                       'process': SimpleNamespace(poll=lambda: 0, returncode=0),
                       'output': output, 'repeats': 1, 'runs': []}
            result = pet_test_service.poll_incremental(session, Path(folder) / 'project', at=9)
            self.assertFalse(result['running'])
            self.assertEqual(result['item']['success_rate'], 1.0)
            self.assertNotIn('Ran 2 tests', str(result['item']))

    def test_start_incremental_uses_explicit_incremental_cli(self):
        seen = {}
        def popen(args, **kwargs):
            seen['args'], seen['cwd'] = args, kwargs['cwd']
            return SimpleNamespace()
        session = pet_test_service.start_incremental(
            'C:/program', '运行增量自检 2 次', executable='python-test', popen=popen)
        try:
            self.assertEqual(seen['args'], ['python-test', 'run_selftests.py', '--incremental'])
            self.assertEqual(session['repeats'], 2)
            self.assertEqual(Path(seen['cwd']), Path('C:/program'))
        finally:
            session['output'].close()

    def test_performance_compare_only_reports_over_forty_percent_duration_regression(self):
        baseline = {'start': {'ready_total_ms': 100, 'rows': 300}, 'memory': {'after_start_mb': 50}}
        current = {'start': {'ready_total_ms': 141, 'rows': 600}, 'memory': {'after_start_mb': 90}}
        with tempfile.TemporaryDirectory() as folder:
            result = pet_performance_service.compare_and_record(folder, baseline, current, at=7)
            self.assertEqual(result['slowdowns'], [{'metric': 'start.ready_total_ms', 'ratio': 1.41}])
            self.assertEqual(result['text'], '优化检查：start.ready_total_ms 比基准慢 41%')
            saved = pet_performance_service.read_json(
                Path(folder) / '工作流任务' / '宠物' / '优化.json', {})
            self.assertEqual(saved['runs'][0]['count'], 1)
            self.assertNotIn('rows', str(saved))

    def test_startup_check_uses_project_report_then_polls_comparison(self):
        seen = {}
        with tempfile.TemporaryDirectory() as folder:
            program, project = Path(folder) / '程序', Path(folder) / '项目'
            script = program / '维护记录' / '基准脚本'
            script.mkdir(parents=True)
            (script / pet_performance_service.SCRIPT_NAME).write_text('', encoding='utf-8')
            (script / pet_performance_service.BASELINE_NAME).write_text(
                '{"start": {"ready_total_ms": 100}}', encoding='utf-8')
            def popen(args, **kwargs):
                seen['args'], seen['cwd'] = args, kwargs['cwd']
                return SimpleNamespace(poll=lambda: 0, returncode=0)
            session = pet_performance_service.start_startup_check(
                program, project, executable='python-test', popen=popen)
            session['output'].write(b'ok')
            session['output'].flush()
            session['current'].write_text('{"start": {"ready_total_ms": 150}}', encoding='utf-8')
            result = pet_performance_service.poll_startup_check(session, at=4)
            self.assertEqual(seen['args'][1:3], [str(script / pet_performance_service.SCRIPT_NAME), 'start'])
            self.assertIn('--output', seen['args'])
            self.assertEqual(result['slowdowns'][0]['metric'], 'start.ready_total_ms')

    def test_long_list_check_uses_its_own_script_and_project_report(self):
        seen = {}
        with tempfile.TemporaryDirectory() as folder:
            program, project = Path(folder) / '程序', Path(folder) / '项目'
            scripts = program / '维护记录' / '基准脚本'
            scripts.mkdir(parents=True)
            (scripts / pet_performance_service.LONG_LIST_SCRIPT_NAME).write_text('', encoding='utf-8')
            (scripts / pet_performance_service.LONG_LIST_BASELINE_NAME).write_text('{}', encoding='utf-8')
            def popen(args, **kwargs):
                seen['args'] = args
                return SimpleNamespace()
            session = pet_performance_service.start_long_list_check(program, project, popen=popen)
            try:
                self.assertEqual(seen['args'][1], str(scripts / pet_performance_service.LONG_LIST_SCRIPT_NAME))
                self.assertEqual(session['current'].name, pet_performance_service.LONG_LIST_BASELINE_NAME)
            finally:
                session['output'].close()

    def test_failed_performance_process_does_not_write_output_to_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            output = tempfile.TemporaryFile(mode='w+b')
            output.write(b'sensitive diagnostic details')
            output.flush()
            project = Path(folder) / '项目'
            session = {'process': SimpleNamespace(poll=lambda: 1, returncode=1), 'output': output,
                       'project': project, 'baseline': Path(folder) / 'baseline.json',
                       'current': Path(folder) / 'current.json'}
            result = pet_performance_service.poll_startup_check(session)
            self.assertTrue(result['failed'])
            self.assertIn('优化检查运行失败', result['text'])
            self.assertFalse((project / '工作流任务' / '宠物' / '优化.json').exists())

    def test_performance_compare_tolerates_missing_or_non_duration_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            result = pet_performance_service.compare_and_record(
                folder, {'memory': {'after_start_mb': 50}}, {'rows': {'count': 100}}, at=5)
            self.assertEqual(result['slowdowns'], [])
            self.assertIn('未发现超过 40% 的耗时退化', result['text'])
