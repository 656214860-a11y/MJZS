# -*- coding: utf-8 -*-
"""R3128（任务书 P3，Q11）：全局素材库目录的登记与读取。

覆盖：默认落在 ``<程序>/配置/素材库.json``；写入后可读回；未设置／文件损坏／内容非法
一律返回 ``None``（调用方据此提示用户先设置）；空目录拒绝写入。
"""
import tempfile
import unittest
from pathlib import Path

import infra.file_index as file_index


class GlobalDirConfigTests(unittest.TestCase):
    def test_default_path_lives_under_program_config(self):
        path = file_index.global_config_path()
        self.assertEqual(path.parent.name, '配置')
        self.assertEqual(path.name, '素材库.json')

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / '程序'
            library = Path(tmp) / '素材库'
            file_index.save_global_dir(library, program=program)
            self.assertEqual(file_index.read_global_dir(program=program), library)

    def test_unset_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(file_index.read_global_dir(program=Path(tmp) / '程序'))

    def test_corrupt_config_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / '程序'
            path = file_index.global_config_path(program)
            path.parent.mkdir(parents=True)
            path.write_text('{坏', encoding='utf-8')
            self.assertIsNone(file_index.read_global_dir(program=program))

    def test_blank_value_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / '程序'
            from agent.core import save
            save(file_index.global_config_path(program), {'library_dir': '   '})
            self.assertIsNone(file_index.read_global_dir(program=program))

    def test_blank_library_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                file_index.save_global_dir('', program=Path(tmp) / '程序')


if __name__ == '__main__':
    unittest.main()
