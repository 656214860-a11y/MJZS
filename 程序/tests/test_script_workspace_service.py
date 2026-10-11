# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path

import project_stages
from script_workspace_service import (batch_selected_script_paths, discover_script_documents,
                                      ensure_script_workspace,
                                      iter_script_document_rows,
                                      renamed_script_path, rename_script_document, script_deletion_selection,
                                      script_document_rows, script_structure_documents,
                                      selected_script_paths, selected_workspace_document)


class ScriptWorkspaceServiceTests(unittest.TestCase):
    def test_legacy_model_versions_display_provider_without_changing_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = (project_stages.writing(temp) / 'DeepSeek' / 'DeepSeek V4 Flash'
                      / '创意_20261010' / '项目设定')
            folder.mkdir(parents=True)
            for suffix in ('', '(1)', '(2)'):
                path = folder / ('摄影侠_项目设定_DeepSeek V4 Flash' + suffix + '_20261010.md')
                path.write_text('设定正文', encoding='utf-8')
            for rows in (script_document_rows(temp), tuple(iter_script_document_rows(temp))):
                self.assertEqual(len(rows), 3)
                self.assertEqual({row.name for row in rows}, {
                    '摄影侠_项目设定_DeepSeek' + suffix + '_20261010.md'
                    for suffix in ('', '(1)', '(2)')})
                for row in rows:
                    self.assertIn('DeepSeek V4 Flash', Path(row.item_id).name)
                    self.assertEqual(Path(row.item_id).read_text(encoding='utf-8'), '设定正文')

    def test_custom_document_name_is_not_rewritten(self):
        from script_workspace_service import _document_display_name
        path = Path('DeepSeek/DeepSeek V4 Flash/创意_20261010/项目设定/用户命名.md')
        self.assertEqual(_document_display_name(path), '用户命名.md')

    def test_agent_internal_draft_is_visible_without_canonical_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            path = project_stages.writing(temp) / 'script_raw.md'
            path.parent.mkdir(parents=True)
            content = '\n'.join('## 第%d集\n场景 1：室内\n小明：开始。' % n for n in range(1, 11))
            path.write_text(content, encoding='utf-8')
            row, = script_document_rows(temp)
            self.assertEqual(('script', str(path)), (row.category, row.item_id))
            self.assertEqual('script_raw.md（内部工作稿）', row.name)
            self.assertEqual(content, path.read_text(encoding='utf-8'))

    def test_published_identical_draft_is_hidden_without_deleting_internal_file(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            draft = writing / 'script_raw.md'
            formal = (writing / 'DeepSeek' / 'DeepSeek V4 Flash' / '创意_20261011'
                      / '项目剧本' / '摄影侠_自然剧本_DeepSeek_20261011.md')
            formal.parent.mkdir(parents=True)
            content = '场景 1：室内\n小明：开始。'
            draft.write_text(content, encoding='utf-8')
            formal.write_text(content + '\n', encoding='utf-8')
            for rows in (script_document_rows(temp), tuple(iter_script_document_rows(temp))):
                self.assertEqual([str(formal)], [row.item_id for row in rows])
                self.assertEqual(formal.name, rows[0].name)
            self.assertEqual(content, draft.read_text(encoding='utf-8'))

    def test_internal_draft_does_not_replace_formal_script_or_accept_wrong_stage(self):
        import script_contract
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            draft = writing / script_contract.RAW_SCRIPT_NAME
            formal = writing / 'GPT' / 'Codex' / '创意_20261007' / '项目剧本' / '正式剧本.md'
            formal.parent.mkdir(parents=True)
            formal.write_text('场景 1：公园\n小明：开始。', encoding='utf-8')
            draft.write_text('场景 2：室内\n小明：结束。', encoding='utf-8')
            self.assertEqual({draft, formal}, {row.path for row in discover_script_documents(temp)})
            self.assertEqual(formal, script_contract.resolve_script_source(temp))
            self.assertNotIn(draft, script_contract.natural_script_paths(temp))
            for invalid in ('', '   ', '{"shots": []}', '# 结构化剧本\n角色档案'):
                with self.subTest(invalid=invalid):
                    draft.write_text(invalid, encoding='utf-8')
                    self.assertEqual([formal], [row.path for row in discover_script_documents(temp)])

    def test_internal_draft_resolving_outside_stage_is_not_shown(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            writing.mkdir(parents=True)
            draft = writing / 'script_raw.md'
            draft.write_text('场景 1：室内', encoding='utf-8')
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                if path == draft:
                    return Path(temp) / 'outside.md'
                return original(path, *args, **kwargs)
            with patch.object(Path, 'resolve', resolve):
                self.assertEqual((), discover_script_documents(temp))

    def test_ensure_workspace_creates_only_the_script_stage_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '新项目'

            result = ensure_script_workspace(project)
            self.assertTrue(result.ok)
            writing = result.data

            self.assertEqual(project_stages.writing(project), writing)
            self.assertTrue(writing.is_dir())

    def test_discovers_only_creative_category_documents_in_newest_order(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            old = writing / 'DeepSeek' / 'Flash' / '创意_20260926' / '项目剧本' / '旧剧本.md'
            new = writing / 'DeepSeek' / 'Flash' / '创意_20260926' / '项目设定' / '新设定.txt'
            ignored = writing / '其他目录' / '项目剧本' / '不应显示.md'
            for path, stamp in ((old, 1000), (new, 2000), (ignored, 3000)):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('x', encoding='utf-8')
                os.utime(path, (stamp, stamp))
            (new.parent / '附件.pdf').write_text('x', encoding='utf-8')

            rows = discover_script_documents(temp)

            self.assertEqual(['新设定.txt', '旧剧本.md'], [row.path.name for row in rows])
            self.assertEqual(['setting', 'script'], [row.category for row in rows])
            self.assertTrue(rows[0].relative_path.startswith('DeepSeek/Flash/创意_'))

    def test_uploaded_creative_is_shown_as_project_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = project_stages.writing(temp) / '输入' / '故事创意_20260929_120000.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('上传创意', encoding='utf-8')

            row, = discover_script_documents(temp)

            self.assertEqual(('setting', '故事创意_20260929_120000.md'), (row.category, row.path.name))

    def test_missing_writing_directory_is_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual((), discover_script_documents(Path(temp)))

    def test_document_rows_are_stable_ui_data_without_tk_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            path = project_stages.writing(temp) / 'Provider' / 'Model' / '创意_20260926' / '项目剧本' / '一.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x', encoding='utf-8')
            os.utime(path, (0, 0))

            row, = script_document_rows(temp)
            self.assertEqual(('script', str(path), '一.md', '01-01'),
                             (row.category, row.item_id, row.name, row.modified_label))

    def test_incremental_rows_do_not_require_a_full_catalog_before_first_row(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            first = writing / '输入' / '故事创意_20260929_120000.md'
            later = writing / 'Provider' / 'Model' / '创意_20260926' / '项目剧本' / '二.md'
            for path in (first, later):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('x', encoding='utf-8')

            rows = iter_script_document_rows(temp)
            row = next(rows)

            self.assertEqual('setting', row.category)
            self.assertEqual(first.name, row.name)
            self.assertIsInstance(row.modified_at, float)

    def test_structure_documents_list_current_and_legacy_without_silently_adopting(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            current = project / '01剧本准备' / '新剧本.md'
            legacy = project_stages.writing(project) / '旧剧本.md'
            current.parent.mkdir(parents=True, exist_ok=True)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            current.write_text('场景 1', encoding='utf-8')
            legacy.write_text('场景 旧', encoding='utf-8')
            os.utime(legacy, (1000, 1000))
            os.utime(current, (2000, 2000))

            result = script_structure_documents(project)
            self.assertIsNone(result.source)
            self.assertEqual((current, legacy), result.source_documents)
            self.assertEqual(project / '01剧本准备', result.source_directory)
            self.assertEqual(project / '02剧本结构', result.output_directory)

    def test_workspace_document_selection_stays_with_visible_existing_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            visible = Path(temp) / '可见.md'
            hidden = Path(temp) / '不可见.md'
            visible.write_text('x', encoding='utf-8')
            hidden.write_text('x', encoding='utf-8')

            self.assertEqual(visible.resolve(), selected_workspace_document([visible], visible))
            with self.assertRaisesRegex(ValueError, '请先选择'):
                selected_workspace_document([visible], None)
            with self.assertRaisesRegex(ValueError, '已不存在'):
                selected_workspace_document([visible], hidden)

    def test_selected_paths_stay_in_current_writing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            kept = writing / '创意_20260926' / '项目剧本' / '可操作.md'
            outside = Path(temp) / '项目外.md'
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_text('x', encoding='utf-8')
            outside.write_text('x', encoding='utf-8')

            self.assertEqual((kept.resolve(),), selected_script_paths(temp, [kept], require_files=True))
            with self.assertRaisesRegex(ValueError, '当前剧本目录'):
                selected_script_paths(temp, [outside], require_files=True)

    def test_selected_paths_require_existing_files_for_batch_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = project_stages.writing(temp) / '创意_20260926' / '项目剧本' / '已移走.md'
            with self.assertRaisesRegex(ValueError, '已移动'):
                selected_script_paths(temp, [missing], require_files=True)

    def test_batch_selection_prefers_checks_then_current_highlight(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            one = writing / '创意_20260926' / '项目剧本' / '一.md'
            two = one.with_name('二.md')
            one.parent.mkdir(parents=True, exist_ok=True)
            one.write_text('x', encoding='utf-8')
            two.write_text('x', encoding='utf-8')

            self.assertEqual((two.resolve(),),
                             batch_selected_script_paths(temp, [one, two], {str(two)}, [one]))
            self.assertEqual((one.resolve(),),
                             batch_selected_script_paths(temp, [one, two], set(), [one]))
            with self.assertRaisesRegex(ValueError, '请先勾选'):
                batch_selected_script_paths(temp, [one, two], set())

    def test_rename_path_validates_source_name_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            source = writing / '创意_20260926' / '项目剧本' / '原名.md'
            occupied = source.with_name('已存在.md')
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('x', encoding='utf-8')
            occupied.write_text('x', encoding='utf-8')

            self.assertEqual(source.with_name('新名.md'), renamed_script_path(temp, source, ' 新名.md '))
            self.assertEqual(source, renamed_script_path(temp, source, source.name))
            with self.assertRaisesRegex(ValueError, '文件名不能为空'):
                renamed_script_path(temp, source, 'bad/name.md')
            with self.assertRaisesRegex(ValueError, '已存在'):
                renamed_script_path(temp, source, occupied.name)

    def test_rename_document_persists_only_validated_workspace_target(self):
        with tempfile.TemporaryDirectory() as temp:
            source = project_stages.writing(temp) / '创意_20260926' / '项目剧本' / '原名.md'
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('内容', encoding='utf-8')

            result = rename_script_document(temp, source, '新名.md')
            self.assertTrue(result.ok)
            target = result.data

            self.assertEqual(source.with_name('新名.md'), target)
            self.assertFalse(source.exists())
            self.assertEqual('内容', target.read_text(encoding='utf-8'))

    def test_deletion_selection_marks_only_complete_checked_set_as_all_files(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            one = writing / '创意_20260926' / '项目剧本' / '一.md'
            two = one.with_name('二.md')
            one.parent.mkdir(parents=True, exist_ok=True)
            one.write_text('x', encoding='utf-8')
            two.write_text('x', encoding='utf-8')

            all_selected = script_deletion_selection(temp, [one, two], {str(one), str(two)})
            partial = script_deletion_selection(temp, [one, two], {str(one)})
            self.assertTrue(all_selected.deletes_all)
            self.assertEqual((one.resolve(), two.resolve()), all_selected.paths)
            self.assertFalse(partial.deletes_all)
