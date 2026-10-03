"""Execute the actual four post-save UI branches without constructing Tk."""
import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from service_contract import SystemError, success


class AssetBatchSettingsCallerTests(unittest.TestCase):
    def branches(self):
        source = Path(__file__).resolve().parents[1] / 'asset_batch.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        branches = []
        for node in ast.walk(tree):
            for _, statements in ast.iter_fields(node):
                if not isinstance(statements, list):
                    continue
                for index, statement in enumerate(statements):
                    if not isinstance(statement, ast.Assign):
                        continue
                    call = statement.value
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id in {'save_settings', 'remove_model'}):
                        wrapper = ast.parse('def invoke():\n    pass\n')
                        wrapper.body[0].body = copy.deepcopy(statements[index:])
                        branches.append((statement.lineno, compile(ast.fix_missing_locations(wrapper), str(source), 'exec')))
        self.assertEqual(len(branches), 4, 'Every persistence caller must be exercised')
        return branches

    def environment(self, result):
        return dict(save_settings=Mock(return_value=result), remove_model=Mock(return_value=result),
                    project=object(), options={}, checks={}, model_key=Mock(return_value='id'),
                    values={'url': Mock(), 'model': Mock()}, model='old', modelbox=MagicMock(),
                    status=Mock(), app=Mock(), base=object(), items=[], win=Mock(),
                    _launch_skill_batch=Mock(return_value=True), stop=Mock(), done=Mock(),
                    run_batch=Mock(), events=Mock())

    def test_failure_stops_all_four_branches(self):
        for line, code in self.branches():
            with self.subTest(line=line):
                env = self.environment(SystemError('保存失败'))
                exec(code, env)
                env['invoke']()
                env['status'].set.assert_called_once_with('保存失败')
                env['values']['model'].set.assert_not_called()
                env['modelbox'].configure.assert_not_called()
                env['_launch_skill_batch'].assert_not_called()
                env['win'].destroy.assert_not_called()
                env['app'].launch_comfy.assert_not_called()
                env['app'].async_.assert_not_called()
                env['stop'].clear.assert_not_called()

    def test_success_preserves_all_four_continuations(self):
        continuations = []
        for line, code in self.branches():
            with self.subTest(line=line):
                env = self.environment(success({}))
                exec(code, env)
                env['invoke']()
                continuations.append((env['values']['model'].set.called,
                                      env['status'].set.called,
                                      env['win'].destroy.called,
                                      env['app'].async_.called))
        self.assertCountEqual(continuations, [(True, True, False, False),
                                              (False, True, False, False),
                                              (False, False, True, False),
                                              (False, False, False, True)])
