# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from pathlib import Path

import script_workspace_service as workspace
from contract import project_stages
from skip_reasons import PLATFORM_DIRECTORY_LINK
from script_workspace_service import (batch_selected_script_paths, discover_script_documents,
                                      ensure_script_workspace,
                                      iter_script_document_rows,
                                      renamed_script_path, rename_script_document, script_deletion_selection,
                                      script_document_rows, script_structure_documents,
                                      selected_script_paths, selected_workspace_document)


class ScriptWorkspaceServiceTests(unittest.TestCase):
    def test_structure_signature_detects_same_size_overwrite_and_source_change(self):
        from unittest import mock
        from script_workspace_service import ScriptStructureDocuments, script_structure_signature
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.md'
            source.write_bytes(b'old')
            documents = ScriptStructureDocuments(root, root, source, root / 'output.md', (source,), ())
            with mock.patch('script_workspace_service.script_structure_documents', return_value=documents):
                before = script_structure_signature(root)
                stat = source.stat()
                source.write_bytes(b'new')
                os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                self.assertNotEqual(before, script_structure_signature(root))
                source.unlink()
                self.assertNotEqual(before, script_structure_signature(root))

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

    def test_regular_files_skip_resolve_but_symlinks_outside_are_excluded(self):
        """REQ-S01-01：发现路径只对符号链接做 resolve 越界检查，普通文件不付代价。

        真实大项目实测：逐文件 resolve() 占发现总耗时 53.5%（4098 次调用约 287ms），
        是剧本准备页分批加载时反复卡顿的唯一热点。普通文件按构造在写作根内，
        只对符号链接补一次 resolve 即可守住安全边界。
        """
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            writing.mkdir(parents=True, exist_ok=True)
            draft = writing / 'script_raw.md'
            draft.write_text('场景 1：室内\n小明：开始。', encoding='utf-8')
            folder = writing / 'DeepSeek' / 'Flash' / '创意_20261011' / '项目剧本'
            folder.mkdir(parents=True)
            normal = folder / '正常剧本.md'
            normal.write_text('场景 1：室内\n小红：开始。', encoding='utf-8')
            outside_dir = Path(temp) / 'outside_dir'
            outside_dir.mkdir(exist_ok=True)
            outside_target = outside_dir / 'external.md'
            outside_target.write_text('外部剧本', encoding='utf-8')
            link = folder / '符号链接.md'
            try:
                link.symlink_to(outside_target, target_is_directory=False)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest(PLATFORM_DIRECTORY_LINK + '：符号链接')

            rows = {row.path.name for row in discover_script_documents(temp)}
            self.assertIn('正常剧本.md', rows)
            self.assertIn('script_raw.md', rows)
            self.assertNotIn('符号链接.md', rows, '指向写作根外的符号链接必须被排除')

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
            for invalid in ('', '   '):
                with self.subTest(invalid=invalid):
                    draft.write_text(invalid, encoding='utf-8')
                    self.assertEqual([formal], [row.path for row in discover_script_documents(temp)])
            # 「只收自然语言剧本」闸门已删除：非空工作稿不论内容形态都照常展示。
            for visible in ('{"shots": []}', '# 结构化剧本\n角色档案'):
                with self.subTest(visible=visible):
                    draft.write_text(visible, encoding='utf-8')
                    self.assertEqual({draft, formal},
                                     {row.path for row in discover_script_documents(temp)})

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

    def test_all_published_batch_layouts_and_unsafe_entries(self):
        """历史 ``创意_*``、``Provider/创意_*``、``Provider/Model/创意_*`` 三种布局都列出；
        读不出文本的剧本不抛错。逐文件 resolve() 只对真实符号链接做，
        普通文件不付代价；这里用真实符号链接替代 mock 守住安全边界。
        """
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            (writing / '输入' / '故事创意_目录.md').mkdir(parents=True)
            top = writing / '创意_20260901' / '项目剧本' / '历史.md'
            middle = writing / 'Provider' / '创意_20260902' / '项目设定' / '中层.md'
            deep = writing / 'Provider' / 'Model' / '创意_20260903' / '项目剧本' / '深层.md'
            hidden_file = deep.parent / '越界文件.md'
            for path in (top, middle, deep):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('x', encoding='utf-8')
            deep.write_bytes(b'\xff\xfe\xfa')
            (writing / 'script_raw.md').write_text('场景 1：室内\n小明：开始。', encoding='utf-8')
            # 真实符号链接指向写作根外部
            outside = Path(temp) / 'outside_target.md'
            outside.write_text('外部文件', encoding='utf-8')
            try:
                hidden_file.symlink_to(outside, target_is_directory=False)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest(PLATFORM_DIRECTORY_LINK + '：符号链接')

            names = {row.path.name for row in discover_script_documents(temp)}
            self.assertEqual({'历史.md', '中层.md', '深层.md', 'script_raw.md'}, names)

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
            with self.assertRaisesRegex(ValueError, '请先选择'):
                batch_selected_script_paths(temp, [one, two], set())

    def test_rename_path_validates_source_name_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            writing = project_stages.writing(temp)
            source = writing / '创意_20260926' / '项目剧本' / '原名.md'
            occupied = source.with_name('已存在.md')
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('x', encoding='utf-8')
            occupied.write_text('x', encoding='utf-8')

            # R3131（Q3）：命名校验改用 L0 命名中心——首尾空格不再被静默裁掉，
            # 而是明确拒绝（Windows 会静默去尾空格，静默裁剪会让用户以为名字没变）。
            self.assertEqual(source.with_name('新名.md'), renamed_script_path(temp, source, '新名.md'))
            self.assertEqual(source, renamed_script_path(temp, source, source.name))
            with self.assertRaisesRegex(ValueError, '首尾不能有空格'):
                renamed_script_path(temp, source, ' 新名.md ')
            with self.assertRaisesRegex(ValueError, '不能包含'):
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


def _cand(path, sha='x', fresh=False):
    return workspace.AdoptionCandidate(path=path, sha256=sha, fresh=fresh)


def _snap(kind='script', candidates=(), adopted='', state='none'):
    return workspace.AdoptionSnapshot(kind=kind, candidates=tuple(candidates),
                                      adopted=adopted, state=state)


def _judge_tuple(verdict):
    return (verdict.action, verdict.reason, verdict.path, verdict.prefer)


class AdoptionJudgeTests(unittest.TestCase):
    RAW = '第 1 集\n场景 1：夜\n甲：你好。\n'

    def _two_scripts(self, root):
        first = root / '01剧本准备' / '甲' / '模型甲' / '创意_20261011' / '项目剧本' / '甲.md'
        second = root / '01剧本准备' / '乙' / '模型乙' / '创意_20261011' / '项目剧本' / '乙.md'
        first.parent.mkdir(parents=True)
        second.parent.mkdir(parents=True)
        first.write_text(self.RAW, encoding='utf-8')
        second.write_text(self.RAW + '\n另一版结尾。', encoding='utf-8')
        return first, second

    def test_judge_table_with_picked(self):
        a, b = '甲.md', '乙.md'
        cands = (_cand(a), _cand(b, fresh=True))
        v = workspace.judge_adoption(_snap(candidates=cands, adopted=a, state='valid'), picked=a)
        self.assertEqual(('keep', 'valid', a, ''), _judge_tuple(v))
        v = workspace.judge_adoption(_snap(candidates=cands, adopted=a, state='changed'), picked=a)
        self.assertEqual(('adopt', 'picked', a, ''), _judge_tuple(v))
        v = workspace.judge_adoption(_snap(candidates=cands, adopted=a, state='valid'), picked=b)
        self.assertEqual(('ask', 'picked_other', '', b), _judge_tuple(v))
        self.assertEqual((a, b), v.choices)
        v = workspace.judge_adoption(_snap(candidates=cands, adopted=a, state='changed'), picked=b)
        self.assertEqual(('ask', 'picked_other', '', b), _judge_tuple(v))
        v = workspace.judge_adoption(_snap(candidates=cands, state='none'), picked=b)
        self.assertEqual(('adopt', 'picked', b, ''), _judge_tuple(v))
        v = workspace.judge_adoption(_snap(candidates=cands, adopted=a, state='missing'), picked=b)
        self.assertEqual(('adopt', 'picked', b, ''), _judge_tuple(v))

    def test_judge_table_without_picked(self):
        a, b, c = '甲.md', '乙.md', '丙.md'
        # 1 valid others empty
        v = workspace.judge_adoption(_snap(candidates=(_cand(a, fresh=True),), adopted=a, state='valid'))
        self.assertEqual(('keep', 'valid', a, ''), _judge_tuple(v))
        # 2 valid one other fresh
        v = workspace.judge_adoption(_snap(candidates=(_cand(a), _cand(b, fresh=True)), adopted=a, state='valid'))
        self.assertEqual(('adopt', 'fresh', b, ''), _judge_tuple(v))
        # 3 valid several fresh
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a), _cand(b, fresh=True), _cand(c, fresh=True)), adopted=a, state='valid'))
        self.assertEqual(('ask', 'several_fresh', '', a), _judge_tuple(v))
        self.assertEqual((a, b, c), v.choices)
        # 4 empty
        v = workspace.judge_adoption(_snap(state='none'))
        self.assertEqual(('none', 'empty', '', ''), _judge_tuple(v))
        # 5 one changed edited / only_changed
        v = workspace.judge_adoption(_snap(candidates=(_cand(a, fresh=True),), adopted=a, state='changed'))
        self.assertEqual(('adopt', 'edited', a, ''), _judge_tuple(v))
        v = workspace.judge_adoption(_snap(candidates=(_cand(a),), adopted=a, state='changed'))
        self.assertEqual(('adopt', 'only_changed', a, ''), _judge_tuple(v))
        # 6 one missing
        v = workspace.judge_adoption(_snap(candidates=(_cand(b),), adopted=a, state='missing'))
        self.assertEqual(('adopt', 'only_left', b, ''), _judge_tuple(v))
        # 7 one none
        v = workspace.judge_adoption(_snap(candidates=(_cand(a),), state='none'))
        self.assertEqual(('adopt', 'only', a, ''), _judge_tuple(v))
        # 8 changed A fresh others empty
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a, fresh=True), _cand(b)), adopted=a, state='changed'))
        self.assertEqual(('adopt', 'edited', a, ''), _judge_tuple(v))
        # 9 changed A fresh others nonempty
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a, fresh=True), _cand(b, fresh=True)), adopted=a, state='changed'))
        self.assertEqual(('ask', 'several_fresh', '', a), _judge_tuple(v))
        # 10 changed A not fresh
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a), _cand(b, fresh=True)), adopted=a, state='changed'))
        self.assertEqual(('ask', 'changed_outside', '', a), _judge_tuple(v))
        self.assertEqual((a, b), v.choices)
        # 11 missing one fresh
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(b, fresh=True), _cand(c)), adopted=a, state='missing'))
        self.assertEqual(('adopt', 'fresh', b, ''), _judge_tuple(v))
        # 12 missing other
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(b), _cand(c)), adopted=a, state='missing'))
        self.assertEqual(('ask', 'adopted_missing', '', ''), _judge_tuple(v))
        # 13 none one fresh
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a), _cand(b, fresh=True)), state='none'))
        self.assertEqual(('adopt', 'fresh', b, ''), _judge_tuple(v))
        # 14 none several fresh
        v = workspace.judge_adoption(_snap(
            candidates=(_cand(a, fresh=True), _cand(b, fresh=True)), state='none'))
        self.assertEqual(('ask', 'several_fresh', '', ''), _judge_tuple(v))
        # 15 none no fresh
        v = workspace.judge_adoption(_snap(candidates=(_cand(a), _cand(b)), state='none'))
        self.assertEqual(('ask', 'no_signal', '', ''), _judge_tuple(v))
        self.assertEqual((a, b), v.choices)

    def test_judge_boundaries(self):
        a, b = '甲.md', '乙.md'
        # 有效采用自己 fresh、别的不 fresh → keep
        v = workspace.judge_adoption(_snap(candidates=(_cand(a, fresh=True), _cand(b)), adopted=a, state='valid'))
        self.assertEqual(('keep', 'valid', a, ''), _judge_tuple(v))
        # 有效采用不在候选且没有候选 → keep
        v = workspace.judge_adoption(_snap(candidates=(), adopted=a, state='valid'))
        self.assertEqual(('keep', 'valid', a, ''), _judge_tuple(v))
        # picked 不在候选 → 同没传
        v = workspace.judge_adoption(
            _snap(candidates=(_cand(a), _cand(b)), state='none'), picked='不存在.md')
        self.assertEqual(('ask', 'no_signal', '', ''), _judge_tuple(v))

    def test_snapshot_four_states_and_invalid_record(self):
        from stage_execution_service import adopt_natural_script
        import contract.script_contract as script_contract
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = self._two_scripts(root)
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('none', snap.state)
            self.assertEqual('', snap.adopted)
            self.assertEqual(2, len(snap.candidates))
            adopt_natural_script(root, first)
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('valid', snap.state)
            self.assertEqual(first.relative_to(root).as_posix(), snap.adopted)
            first.write_text(self.RAW + '\n已改。', encoding='utf-8')
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('changed', snap.state)
            first.unlink()
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('missing', snap.state)
            path = script_contract.natural_script_selection_path(root)
            path.write_text(json.dumps({'path': '', 'sha256': '', 'reason': 'x'}), encoding='utf-8')
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('none', snap.state)
            self.assertEqual('', snap.adopted)

    def test_touches_only_content_written_by_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = self._two_scripts(root)
            touches = workspace.AdoptionTouches()
            touches.note(root, 'script', second, 'generate')
            snap = workspace.adoption_snapshot(root, 'script', touches=touches)
            by_path = {c.path: c for c in snap.candidates}
            self.assertTrue(by_path[second.relative_to(root).as_posix()].fresh)
            second.write_text(self.RAW + '\n应用外改。', encoding='utf-8')
            snap = workspace.adoption_snapshot(root, 'script', touches=touches)
            by_path = {c.path: c for c in snap.candidates}
            self.assertFalse(by_path[second.relative_to(root).as_posix()].fresh)

    def test_does_not_use_file_mtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = self._two_scripts(root)
            snap = workspace.adoption_snapshot(root, 'script')
            verdict = workspace.judge_adoption(snap)
            self.assertEqual('ask', verdict.action)
            os.utime(first, (1_700_000_000, 1_900_000_000))
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('ask', workspace.judge_adoption(snap).action)
            os.utime(second, (1_700_000_000, 2_000_000_000))
            os.utime(first, (1_700_000_000, 1_000_000_000))
            snap = workspace.adoption_snapshot(root, 'script')
            self.assertEqual('ask', workspace.judge_adoption(snap).action)

    def test_apply_adoption_calls_and_clears(self):
        touches = workspace.AdoptionTouches()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / '乙.md'
            target.write_text('x', encoding='utf-8')
            touches.note(root, 'script', target, 'edit')
            self.assertTrue(touches.seen(root, 'script'))
            calls = []

            def fake_adopt(project, path):
                calls.append((Path(project), Path(path)))

            adopt_v = workspace.AdoptionVerdict(
                kind='script', action='adopt', reason='only', path='乙.md', previous='')
            notice = workspace.apply_adoption(root, adopt_v, adopt=fake_adopt, touches=touches)
            self.assertEqual(1, len(calls))
            self.assertEqual(root.resolve(), calls[0][0].resolve())
            self.assertEqual((root / '乙.md').resolve(), calls[0][1].resolve())
            self.assertEqual(workspace.adoption_notice(adopt_v), notice)
            self.assertEqual(frozenset(), touches.seen(root, 'script'))

            for action in ('keep', 'ask', 'none'):
                calls.clear()
                v = workspace.AdoptionVerdict(kind='script', action=action, reason='x')
                self.assertEqual('', workspace.apply_adoption(root, v, adopt=fake_adopt))
                self.assertEqual([], calls)

            touches.note(root, 'script', target, 'edit')

            def boom(project, path):
                raise ValueError('no')

            with self.assertRaises(ValueError):
                workspace.apply_adoption(root, adopt_v, adopt=boom, touches=touches)
            self.assertTrue(touches.seen(root, 'script'))

    def test_end_to_end_with_real_adopt(self):
        from stage_execution_service import adopt_natural_script
        import contract.script_contract as script_contract
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = self._two_scripts(root)
            touches = workspace.AdoptionTouches()
            touches.note(root, 'script', second, 'edit')
            snap = workspace.adoption_snapshot(root, 'script', touches=touches)
            verdict = workspace.judge_adoption(snap)
            self.assertEqual(('adopt', 'fresh', second.relative_to(root).as_posix(), ''),
                             _judge_tuple(verdict))
            workspace.apply_adoption(root, verdict, adopt=adopt_natural_script, touches=touches)
            self.assertEqual(second.resolve(), script_contract.resolve_script_source(root).resolve())
            snap = workspace.adoption_snapshot(root, 'script', touches=touches)
            self.assertEqual('keep', workspace.judge_adoption(snap).action)
            second.write_text(self.RAW + '\n再改。', encoding='utf-8')
            touches.note(root, 'script', second, 'edit')
            snap = workspace.adoption_snapshot(root, 'script', touches=touches)
            verdict = workspace.judge_adoption(snap)
            self.assertEqual('edited', verdict.reason)
            self.assertEqual('adopt', verdict.action)
            workspace.apply_adoption(root, verdict, adopt=adopt_natural_script, touches=touches)
            self.assertEqual(second.resolve(), script_contract.resolve_script_source(root).resolve())

    def test_old_rule_untouched_when_ask(self):
        import contract.script_contract as script_contract
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._two_scripts(root)
            snap = workspace.adoption_snapshot(root, 'script')
            verdict = workspace.judge_adoption(snap)
            self.assertEqual('ask', verdict.action)
            self.assertFalse(script_contract.natural_script_selection_path(root).exists())
            self.assertIsNone(script_contract.resolve_script_source(root))

    def test_rejects_unknown_kinds_and_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._two_scripts(root)
            with self.assertRaisesRegex(ValueError, '剧本大纲'):
                workspace.adoption_snapshot(root, 'outline')
            with self.assertRaises(ValueError):
                workspace.adoption_snapshot(root, 'x')
            touches = workspace.AdoptionTouches()
            with self.assertRaises(ValueError):
                touches.note(root, 'script', root / 'no.md', 'guess')

    def test_notice_and_question_copy(self):
        a_rel = '01剧本准备/甲/模型甲/创意_20261011/项目剧本/甲.md'
        b_rel = '01剧本准备/乙/模型乙/创意_20261011/项目剧本/乙.md'
        only = workspace.AdoptionVerdict(kind='script', action='adopt', reason='only', path=a_rel)
        self.assertEqual('只有《甲》这一份自然剧本，已自动采用。', workspace.adoption_notice(only))
        fresh = workspace.AdoptionVerdict(
            kind='script', action='adopt', reason='fresh', path=b_rel, previous=a_rel)
        self.assertEqual(
            '已自动采用您刚生成或改过的《乙》。原来采用的是《甲》。'
            '要换一份，在文件面板里右键点「采用此剧本」。',
            workspace.adoption_notice(fresh))
        ask = workspace.AdoptionVerdict(
            kind='script', action='ask', reason='no_signal', choices=(a_rel, b_rel))
        self.assertEqual('有 2 份自然剧本，还没定用哪一份，下一阶段用哪一份？',
                         workspace.adoption_question(ask))
        for reason in ('only', 'only_left', 'fresh', 'edited', 'only_changed', 'picked'):
            v = workspace.AdoptionVerdict(kind='script', action='adopt', reason=reason, path=a_rel)
            text = workspace.adoption_notice(v)
            self.assertTrue(text)
            self.assertIn('甲', text)
        for reason in ('several_fresh', 'no_signal', 'changed_outside', 'adopted_missing', 'picked_other'):
            v = workspace.AdoptionVerdict(
                kind='script', action='ask', reason=reason, choices=(a_rel, b_rel),
                previous=a_rel, prefer=b_rel)
            self.assertTrue(workspace.adoption_question(v))
