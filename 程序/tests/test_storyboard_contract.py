# -*- coding: utf-8 -*-
"""storyboard_contract.rules() 的助手校验指令契约（R3230 诊断 D1／轮 1 修复）。

提示词让模型把给出的目录加入 ``sys.path`` 后 ``from writing import
validate_episode`` 自检；目录或模块名算错时模型会 import 失败并跳过校验，
分镜 JSON 就未经助手校验落盘。断言检验 rules() 输出的行为，不比对源码字符串。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests.architecture._scan import ROOT
from contract import storyboard_contract


def _emitted_sys_path(text):
    """解析「将 <目录> 加入 Python 模块搜索路径」给出的目录；缺席时返回 None。"""
    matched = re.search(r'将 (.+?) 加入 Python 模块搜索路径', text)
    return Path(matched.group(1)) if matched else None


def _emitted_imports(text):
    """取 sys.path 指令之后、校验调用之前的 import 语句原文（模型照抄的部分）。"""
    tail = text.split('加入 Python 模块搜索路径，', 1)
    if len(tail) != 2:
        return ''
    head = tail[1].split('validate_episode(', 1)[0]
    return ';'.join(part.strip() for part in head.split(';') if part.strip())


class StoryboardRulesValidationTests(unittest.TestCase):
    def test_rules_point_at_a_directory_that_really_has_writing_py(self):
        text = storyboard_contract.rules()
        directory = _emitted_sys_path(text)
        self.assertIsNotNone(directory, 'rules() 必须给出校验器模块的搜索目录')
        self.assertTrue((directory / 'writing.py').is_file(),
                        f'提示词给出的目录下不存在 writing.py：{directory}')
        self.assertEqual(directory, Path(storyboard_contract.__file__).resolve().parents[1],
                         '校验器在程序/ 根，提示词的 sys.path 目录必须是它')
        self.assertIn('validate_episode', text)

    def test_validation_imports_resolve_from_the_emitted_directory(self):
        """模型照提示词做：把给出的目录加进 sys.path 后提示词里的 import 都必须成功。"""
        text = storyboard_contract.rules()
        directory = _emitted_sys_path(text)
        imports = _emitted_imports(text)
        self.assertIsNotNone(directory, 'rules() 必须给出校验器模块的搜索目录')
        self.assertTrue(imports, 'rules() 必须给出可执行的 import 指令')
        script = (f'import sys;sys.path.insert(0, {str(directory)!r});'
                  f'{imports};print("ok")')
        # cwd 必须离开 程序/：模拟模型在自己项目目录里只按提示词加的目录导入，
        # 否则 cwd 隐含的 程序/ 会掩盖错误路径（旧代码恰好靠这个巧合假绿）。
        done = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script],
                              cwd=str(ROOT.parent), capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=120)
        self.assertEqual(done.returncode, 0,
                         f'提示词给出的导入在子进程失败：{done.stderr.strip()[-400:]}')
        self.assertIn('ok', done.stdout)

    def test_validation_block_is_omitted_when_writing_py_is_missing(self):
        """校验器文件不存在时 rules() 不写校验指令（不误导模型去 import 一个缺失模块）。"""
        real_is_file = Path.is_file

        def fake_is_file(self):
            if self.name == 'writing.py':
                return False
            return real_is_file(self)

        with mock.patch.object(Path, 'is_file', fake_is_file):
            text = storyboard_contract.rules()
        self.assertNotIn('validate_episode', text)
        self.assertNotIn('加入 Python 模块搜索路径', text)
        self.assertNotIn('助手校验函数', text)


if __name__ == '__main__':
    unittest.main()
