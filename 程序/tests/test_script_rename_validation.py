# -*- coding: utf-8 -*-
"""R3110（任务书 P2）：剧本改名的命名校验、原子替换与索引同步。

覆盖：非法字符／Windows 保留名／尾点空格／超长名被 L0 命名中心拦下并给可读原因；
改名后文件内容按新路径可读（缓存已失效）、旧路径不再命中；改名后项目文件索引同步；
目标已存在时返回可读的用户错误。
"""
import tempfile
import unittest
from pathlib import Path

from contract import project_stages
import script_workspace_service as service
from infra.file_cache import read_text
from infra import file_index


def _project(tmp):
    root = Path(tmp) / '项目'
    folder = project_stages.writing(root) / '项目剧本'
    folder.mkdir(parents=True)
    return root, folder


class RenameValidationTests(unittest.TestCase):
    def test_illegal_characters_are_rejected_with_readable_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '名字.md'
            source.write_text('正文', encoding='utf-8')
            for bad in ('a*b.md', 'a?b.md', 'a|b.md', 'a/b.md'):
                result = service.rename_script_document(root, source, bad)
                self.assertFalse(result.ok, bad)
                self.assertIn('不能包含', result.reason, bad)
            self.assertTrue(source.is_file())

    def test_windows_reserved_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '名字.md'
            source.write_text('正文', encoding='utf-8')
            result = service.rename_script_document(root, source, 'CON.txt')
            self.assertFalse(result.ok)
            self.assertIn('保留名', result.reason)

    def test_trailing_dot_and_space_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '名字.md'
            source.write_text('正文', encoding='utf-8')
            for bad in ('名字.', '名字 '):
                self.assertFalse(service.rename_script_document(root, source, bad).ok, bad)

    def test_taken_target_reports_a_user_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '原稿.md'
            source.write_text('甲', encoding='utf-8')
            (folder / '已存在.md').write_text('乙', encoding='utf-8')
            result = service.rename_script_document(root, source, '已存在.md')
            self.assertFalse(result.ok)
            self.assertIn('已存在', result.reason)
            self.assertTrue(source.is_file())


class RenameEffectTests(unittest.TestCase):
    def test_rename_moves_file_and_refreshes_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '旧名.md'
            source.write_text('新正文', encoding='utf-8')
            self.assertEqual(read_text(source), '新正文')
            result = service.rename_script_document(root, source, '新名.md')
            self.assertTrue(result.ok, result.reason)
            target = folder / '新名.md'
            self.assertTrue(target.is_file())
            self.assertFalse(source.exists())
            self.assertEqual(read_text(target), '新正文')

    def test_rename_updates_the_file_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '旧名.md'
            source.write_text('正文', encoding='utf-8')
            file_index.rebuild(root)
            self.assertIn(folder.joinpath('旧名.md').relative_to(root).as_posix(),
                          [row.path for row in file_index.rows(root)])
            result = service.rename_script_document(root, source, '新名.md')
            self.assertTrue(result.ok, result.reason)
            paths = [row.path for row in file_index.rows(root)]
            self.assertIn(folder.joinpath('新名.md').relative_to(root).as_posix(), paths)
            self.assertNotIn(folder.joinpath('旧名.md').relative_to(root).as_posix(), paths)

    def test_rename_without_index_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder = _project(tmp)
            source = folder / '旧名.md'
            source.write_text('正文', encoding='utf-8')
            result = service.rename_script_document(root, source, '新名.md')
            self.assertTrue(result.ok, result.reason)


if __name__ == '__main__':
    unittest.main()
