"""Execute each actual result-check/unpack sequence, without Tk construction."""
import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock
from service_contract import SystemError, success


class StageWorkspaceCallerTests(unittest.TestCase):
    def test_six_callers_guard_before_unpacking(self):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        found = []
        for node in ast.walk(tree):
            for _, statements in ast.iter_fields(node):
                if not isinstance(statements, list):
                    continue
                for index, statement in enumerate(statements):
                    if not isinstance(statement, ast.Assign):
                        continue
                    call = statement.value
                    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id in {'ensure_audio_workspace', 'ensure_storyboard_workspace',
                                                 'ensure_editing_workspace', 'ensure_delivery_workspace'}):
                        continue
                    found.append(call.func.id)
                    block = statements[index:index + 3]
                    self.assertIsInstance(block[1], ast.If)
                    self.assertIsInstance(block[2], ast.Assign)
                    code = compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(block), type_ignores=[])), str(source), 'exec')
                    data = {'ensure_storyboard_workspace': Path('storyboard'),
                            'ensure_audio_workspace': (Path('audio'), Path('subtitles')),
                            'ensure_editing_workspace': (Path('editing'),),
                            'ensure_delivery_workspace': (Path('delivery'), Path('exports'))}[call.func.id]
                    targets = [n.id for n in ast.walk(block[2].targets[0]) if isinstance(n, ast.Name)]
                    for ok in (False, True):
                        with self.subTest(line=statement.lineno, ok=ok):
                            result = success(data) if ok else SystemError('初始化失败')
                            env = {'self': Mock(), call.func.id: Mock(return_value=result)}
                            if ok:
                                exec(code, env)
                                expected = (data,) if isinstance(data, Path) else data
                                self.assertEqual(expected, tuple(env[name] for name in targets))
                            else:
                                with self.assertRaisesRegex(ValueError, '初始化失败'):
                                    exec(code, env)
                                self.assertTrue(all(name not in env for name in targets))
        self.assertCountEqual(found, ['ensure_storyboard_workspace', 'ensure_audio_workspace',
                                     'ensure_audio_workspace', 'ensure_editing_workspace',
                                     'ensure_delivery_workspace', 'ensure_delivery_workspace'])
