# -*- coding: utf-8 -*-
"""R3110（任务书 P2）：剧本改名的命名校验、原子替换与索引同步。

覆盖：非法字符／Windows 保留名／尾点空格／超长名被 L0 命名中心拦下并给可读原因；
改名后文件内容按新路径可读（缓存已失效）、旧路径不再命中；改名后项目文件索引同步；
目标已存在时返回可读的用户错误。
"""
import hashlib
import json
import os
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

from contract import project_stages
import script_workspace_service as service
from file_cache import read_text
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


class RenameIntegrityTests(unittest.TestCase):
    def _source(self, tmp):
        root, folder = _project(tmp)
        source = folder / '旧名.md'
        source.write_bytes('正文\r\n原样'.encode('utf-8'))
        return root, folder, source

    def test_extension_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, source = self._source(tmp)
            result = service.rename_script_document(root, source, '新名.docx')
            self.assertFalse(result.ok)
            self.assertIn('扩展名', result.reason)
            self.assertTrue(source.exists())

    def test_adoption_and_confirmation_references_follow_rename(self):
        from agent.core import save
        import script_contract
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            stage = project_stages.writing(root)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            relative = source.relative_to(stage).as_posix()
            state = {'documents': [{'path': relative, 'confirmed': True, 'sha256': 'keep'}],
                     'revision': {'documents': [{'path': relative, 'confirmed': False}],
                                  'source_path': relative},
                     'snapshots': [{'path': relative, 'snapshot': '确认快照/留存.md',
                                    'sha256': 'keep', 'confirmed_at': '保持'}]}
            save(stage / 'preparation_state.json', state)
            selection = script_contract.natural_script_selection_path(root)
            save(selection, {'path': source.relative_to(root).as_posix(), 'sha256': digest})
            before = source.read_bytes()
            result = service.rename_script_document(root, source, '新名.md')
            self.assertTrue(result.ok, result.reason)
            target = folder / '新名.md'
            expected = json.loads(json.dumps(state, ensure_ascii=False).replace('旧名.md', '新名.md'))
            self.assertEqual(json.loads((stage / 'preparation_state.json').read_text('utf-8')), expected)
            self.assertEqual(script_contract.resolve_script_source(root), target)
            self.assertEqual(target.read_bytes(), before)

    def test_unknown_settings_reference_blocks_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, source = self._source(tmp)
            (root / 'ui_settings.json').write_text(json.dumps({'unknown': str(source)}), 'utf-8')
            result = service.rename_script_document(root, source, '新名.md')
            self.assertFalse(result.ok)
            self.assertIn('引用', result.reason)
            self.assertTrue(source.exists())

    def test_reference_write_failure_rolls_back_bytes_and_file(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            state = project_stages.writing(root) / 'preparation_state.json'
            save(state, {'documents': [{'path': source.relative_to(state.parent).as_posix(),
                                       'confirmed': True}]})
            before = state.read_bytes(), source.read_bytes()
            with patch('agent.core.save', side_effect=OSError('故障注入')):
                result = service.rename_script_document(root, source, '新名.md')
            self.assertFalse(result.ok)
            self.assertEqual((state.read_bytes(), source.read_bytes()), before)
            self.assertFalse((folder / '新名.md').exists())

    def test_competing_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            target = folder / '新名.md'
            real_link = os.link
            def compete(src, dst, *args, **kwargs):
                if Path(dst) == target:
                    target.write_bytes(b'competitor')
                return real_link(src, dst, *args, **kwargs)
            with patch('os.link', side_effect=compete):
                result = service.rename_script_document(root, source, target.name)
            self.assertFalse(result.ok)
            self.assertTrue(source.exists())
            self.assertEqual(target.read_bytes(), b'competitor')

    def test_project_and_source_junctions_are_rejected(self):
        import _winapi
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            alias = Path(tmp) / '联接项目'
            _winapi.CreateJunction(str(root), str(alias))
            try:
                relative = source.relative_to(root)
                result = service.rename_script_document(alias, alias / relative, '新名.md')
                self.assertFalse(result.ok)
                self.assertIn('联接', result.reason)
                inner = project_stages.writing(root) / '联接来源'
                _winapi.CreateJunction(str(folder), str(inner))
                try:
                    result = service.rename_script_document(root, inner / source.name, '新名.md')
                    self.assertFalse(result.ok)
                    self.assertIn('联接', result.reason)
                finally:
                    inner.rmdir()
                self.assertTrue(source.exists())
            finally:
                alias.rmdir()

    def test_source_symlink_is_rejected_even_inside_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            alias = folder / '链接.md'
            alias.symlink_to(source)
            result = service.rename_script_document(root, alias, '新名.md')
            self.assertFalse(result.ok)
            self.assertIn('符号链接', result.reason)
            self.assertTrue(source.exists())
            self.assertTrue(alias.is_symlink())

    def test_late_reference_failure_restores_earlier_published_record(self):
        from agent import core
        import script_contract
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            stage = project_stages.writing(root)
            state = stage / 'preparation_state.json'
            selection = script_contract.natural_script_selection_path(root)
            core.save(state, {'documents': [{'path': source.relative_to(stage).as_posix(),
                                            'confirmed': True, 'sha256': 'unchanged'}]})
            core.save(selection, {'path': source.relative_to(root).as_posix(), 'sha256': 'unchanged'})
            before = {path: path.read_bytes() for path in (source, state, selection)}
            real_save = core.save
            calls = []
            def fail_second(path, data):
                calls.append(path)
                if len(calls) == 2:
                    raise OSError('第二份引用落盘失败')
                return real_save(path, data)
            with patch('agent.core.save', side_effect=fail_second):
                result = service.rename_script_document(root, source, '新名.md')
            self.assertFalse(result.ok)
            self.assertEqual(len(calls), 2)
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)
            self.assertFalse((folder / '新名.md').exists())

    def test_index_runtime_failure_does_not_undo_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, folder, source = self._source(tmp)
            with patch('infra.file_index.update', side_effect=RuntimeError('缓存故障')):
                result = service.rename_script_document(root, source, '新名.md')
            self.assertTrue(result.ok, result.reason)
            self.assertEqual((folder / '新名.md').read_bytes(), '正文\r\n原样'.encode('utf-8'))


class ProjectMediaRenameTests(unittest.TestCase):
    def test_unreferenced_media_can_be_renamed_without_changing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / '11配音与字幕' / '音频' / '旧名.wav'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'RIFF-original')
            result = service.rename_project_file(root, source, '新名.wav')
            self.assertTrue(result.ok, result.reason)
            self.assertEqual(result.data.read_bytes(), b'RIFF-original')
            self.assertFalse(source.exists())

    def test_unknown_media_reference_blocks_change_and_preserves_both(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / '10视频生成' / 'assets' / 'clip.mp4'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'video')
            save(root / 'ui_settings.json', {'media_path': '10视频生成/assets/clip.mp4'})
            result = service.rename_project_file(root, source, 'other.mp4')
            self.assertFalse(result.ok)
            self.assertTrue(source.is_file())
            self.assertFalse(source.with_name('other.mp4').exists())


if __name__ == '__main__':
    unittest.main()
