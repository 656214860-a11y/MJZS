# -*- coding: utf-8 -*-
"""自然语言原稿到结构化 Markdown 的契约回归。"""
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import script_contract as contract

RAW = '''第 1 集
场景 1：夜，旧书店内
林小满：把旧怀表交给我。
陆时：先离开这里。
道具：旧怀表
林小满愤怒地望向门口。
'''


class ScriptStructureTests(unittest.TestCase):
    def test_structure_keeps_the_required_archives_and_scene_fields(self):
        text = contract.structure_script(RAW)
        for heading in ('## 角色档案', '## 场景档案', '## 道具档案', '## 分场剧本'):
            self.assertIn(heading, text)
        self.assertIn('### 林小满', text)
        self.assertIn('### 陆时', text)
        self.assertIn('旧怀表', text)
        self.assertIn('- 出场角色：林小满、陆时', text)
        self.assertIn('- 情绪基调：林小满愤怒地望向门口。', text)

    def test_empty_raw_is_rejected(self):
        with self.assertRaises(ValueError):
            contract.structure_script('  \n')

    def test_write_only_creates_script_md_and_keeps_raw_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writing = root / 'writing'
            writing.mkdir()
            source = writing / contract.RAW_SCRIPT_NAME
            source.write_text(RAW, encoding='utf-8')
            target = contract.write_structured_script(root)
            self.assertEqual(target, contract.canonical_structured_script_path(root))
            self.assertRegex(target.name, r'^%s_结构剧本_本地_\d{8}\.md$' % root.name)
            self.assertEqual(source.read_text(encoding='utf-8'), RAW)
            self.assertIn('## 分场剧本', target.read_text(encoding='utf-8'))

    def test_missing_raw_is_rejected_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                contract.write_structured_script(root)
            self.assertFalse(contract.canonical_structured_script_path(root).exists())

    def test_failed_publication_does_not_record_lineage(self):
        """发布未落盘时不得留下指向不存在结构稿的血缘记录。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'writing' / contract.RAW_SCRIPT_NAME
            source.parent.mkdir(parents=True)
            source.write_text(RAW, encoding='utf-8')
            with patch('agent.core.save_text', side_effect=OSError('disk full')):
                with patch('contract.artifact_lineage.record') as record:
                    with self.assertRaisesRegex(OSError, 'disk full'):
                        contract.write_structured_script(root)
            record.assert_not_called()

    def test_multiple_model_drafts_require_explicit_adoption_and_pin_content(self):
        """REQ-S01-21：多份自然稿并存时必须由用户明确采用一份，不按时间自动采用。"""
        from stage_execution_service import adopt_natural_script
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / '01剧本准备' / '甲' / '模型甲' / '创意_20261011' / '项目剧本' / '甲.md'
            second = root / '01剧本准备' / '乙' / '模型乙' / '创意_20261011' / '项目剧本' / '乙.md'
            first.parent.mkdir(parents=True); second.parent.mkdir(parents=True)
            first.write_text(RAW, encoding='utf-8')
            second.write_text(RAW + '\n另一版结尾。', encoding='utf-8')
            self.assertIsNone(contract.resolve_script_source(root))
            adopt_natural_script(root, first)
            self.assertEqual(contract.resolve_script_source(root), first)
            second.write_text(RAW + '\n再次更新的另一版。', encoding='utf-8')
            self.assertEqual(contract.resolve_script_source(root), first)
            first.write_text(RAW + '\n已修改采用版本。', encoding='utf-8')
            self.assertIsNone(contract.resolve_script_source(root))
            adopt_natural_script(root, first)
            self.assertEqual(contract.resolve_script_source(root), first)
            first.unlink()
            self.assertIsNone(contract.resolve_script_source(root))

    def test_adopted_natural_script_is_the_only_baseline(self):
        """定稿之后，另一份更新的草稿不能成为结构阶段或续写基准。"""
        from stage_execution_service import adopt_natural_script
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            adopted = root / '01剧本准备' / '甲' / '模型甲' / '创意_20261011' / '项目剧本' / '甲.md'
            newer = root / '01剧本准备' / '乙' / '模型乙' / '创意_20261011' / '项目剧本' / '乙.md'
            adopted.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            adopted.write_text(RAW, encoding='utf-8')
            newer.write_text(RAW + '\n另一版结尾。', encoding='utf-8')
            adopt_natural_script(root, adopted)
            newer.write_text(RAW + '\n再次更新的另一版。', encoding='utf-8')
            self.assertEqual(contract.script_baseline_path(root), adopted)
            adopted.write_text(RAW + '\n已修改采用版本。', encoding='utf-8')
            self.assertIsNone(contract.script_baseline_path(root))

    def test_downloaded_script_from_preparation_is_used_when_script_raw_is_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            downloaded = root / 'writing' / '创意_20260926' / '项目_EP001_20260926.md'
            downloaded.parent.mkdir(parents=True)
            downloaded.write_text(RAW, encoding='utf-8')
            self.assertEqual(contract.resolve_script_source(root), downloaded)
            rendered = contract.write_structured_script(root).read_text(encoding='utf-8')
            self.assertIn('来源：`writing/创意_20260926/项目_EP001_20260926.md`', rendered)
            self.assertIn('## 分场剧本', rendered)

    def test_internal_script_raw_is_not_shown_or_used_as_a_natural_script(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            produced = root / 'writing' / '创意_20260926' / 'script_raw.md'
            produced.parent.mkdir(parents=True)
            produced.write_text(RAW, encoding='utf-8')
            self.assertEqual(contract.natural_script_paths(root), ())
            self.assertIsNone(contract.resolve_script_source(root))

    def test_current_script_stage_wins_over_an_identical_writing_legacy_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / '摄像头3_20260926'
            current = root / '01剧本准备' / 'Anthropic' / '模型' / '创意_20260926' / '摄像头3_自然剧本_第01集_20260926.md'
            legacy = root / 'writing' / 'Anthropic' / '模型' / '创意_20260926' / current.name
            current.parent.mkdir(parents=True); legacy.parent.mkdir(parents=True)
            current.write_text(RAW, encoding='utf-8'); legacy.write_text(RAW, encoding='utf-8')
            self.assertEqual(contract.natural_script_paths(root), (current,))
            self.assertEqual(contract.stage_file_name(root, '自然剧本', '第01集', at=0),
                             '摄像头3_自然剧本_第01集_19700101.md')

    def test_stage_file_info_is_the_single_parser_for_current_and_legacy_names(self):
        current = contract.stage_file_info('摄像头_3_自然剧本_第01集_20260927.md')
        self.assertEqual(current['project'], '摄像头_3')
        self.assertEqual(current['file_type'], '自然剧本')
        self.assertEqual(current['content'], '第01集')
        self.assertEqual(current['reason'], '四段式文件名中的文件类型段')
        legacy = contract.stage_file_info('摄像头3_EP001_20260927.md')
        self.assertEqual(legacy['file_type'], '自然剧本')
        self.assertEqual(legacy['format'], 'legacy-episode')
        self.assertEqual(contract.stage_file_info('brief_raw.md'), None)

    def test_provider_model_saved_script_is_used_when_script_raw_is_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            downloaded = (root / 'writing' / 'DeepSeek' / 'DeepSeek V4 Flash' /
                          '创意_20260926' / '项目_EP001_20260926.md')
            downloaded.parent.mkdir(parents=True)
            downloaded.write_text(RAW, encoding='utf-8')
            self.assertEqual(contract.resolve_script_source(root), downloaded)
            rendered = contract.write_structured_script(root).read_text(encoding='utf-8')
            self.assertIn('来源：`writing/DeepSeek/DeepSeek V4 Flash/创意_20260926/项目_EP001_20260926.md`', rendered)

    def test_project_script_category_is_visible_even_when_file_name_has_no_script_marker(self):
        """剧本准备页的“项目剧本”目录是自然剧本的受控分类，不能只靠文件名猜类型。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = (root / '01剧本准备' / 'DeepSeek' / '模型' / '创意_20260926'
                      / '项目剧本' / '第一集.md')
            source.parent.mkdir(parents=True)
            source.write_text(RAW, encoding='utf-8')

            self.assertEqual(contract.natural_script_paths(root), (source,))
            self.assertEqual(contract.resolve_script_source(root), source)

    def test_structure_output_is_hidden_when_its_recorded_natural_script_is_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / '01剧本准备' / 'DeepSeek' / 'DeepSeek V4 Flash' / '创意_20260926' / '项目_自然剧本_EP001_20260926.md'
            source.parent.mkdir(parents=True)
            source.write_text(RAW, encoding='utf-8')
            target = contract.write_structured_script(root, source=source)
            self.assertEqual(contract.structured_script_paths(root), (target,))
            lineage = json.loads((target.parent / '产物来源关系.json').read_text(encoding='utf-8'))
            self.assertEqual(lineage['entries'][0]['artifact_type'], '结构剧本')
            self.assertEqual(lineage['entries'][0]['source'],
                             '01剧本准备/DeepSeek/DeepSeek V4 Flash/创意_20260926/项目_自然剧本_EP001_20260926.md')
            source.unlink()
            self.assertEqual(contract.structured_script_paths(root), ())

    def test_stage_execution_runs_the_existing_template_and_writes_output(self):
        from types import SimpleNamespace
        import stage_exec
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            writing = root / 'writing'
            writing.mkdir()
            (writing / contract.RAW_SCRIPT_NAME).write_text(RAW, encoding='utf-8')
            run = stage_exec.run(SimpleNamespace(root=root, errors=[], bus=None, app=None), 'script_structure')
            self.assertTrue(run['ok'])
            self.assertTrue(contract.canonical_structured_script_path(root).is_file())
            self.assertEqual(len(run['results']), 6)

    def test_stage_execution_reads_downloaded_preparation_script(self):
        from types import SimpleNamespace
        import stage_exec
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            downloaded = root / 'writing' / '创意_20260926' / '项目_EP001_20260926.md'
            downloaded.parent.mkdir(parents=True)
            downloaded.write_text(RAW, encoding='utf-8')
            run = stage_exec.run(SimpleNamespace(root=root, errors=[], bus=None, app=None), 'script_structure')
            self.assertTrue(run['ok'])
            self.assertTrue(contract.canonical_structured_script_path(root).is_file())

    def test_editor_reports_missing_profile_and_writer_rebuilds_it(self):
        structured = contract.structure_script(RAW).replace('- 物理特征：', '- 特征：', 1)
        review = contract.review_structured_script(RAW, structured)
        self.assertFalse(review['approved'])
        self.assertTrue(any('物理特征' in note for note in review['feedback']))
        repaired = contract.revise_structured_script(RAW, review['feedback'])
        self.assertTrue(contract.review_structured_script(RAW, repaired)['approved'])

    def test_editor_blocks_conflicting_prop_dimensions_in_raw(self):
        raw = RAW + '\n道具：怀表（直径3厘米）\n道具：怀表（直径5厘米）\n'
        review = contract.review_structured_script(raw, contract.structure_script(raw))
        self.assertFalse(review['approved'])
        with self.assertRaises(ValueError):
            contract.revise_structured_script(raw, review['feedback'])


class ExtractionProvenanceTests(unittest.TestCase):
    """O17：本地规则提取要标出处与待确认，结构合法不等于制作信息齐全。"""

    def test_structure_is_labelled_as_local_rules_not_a_model(self):
        text = contract.structure_script(RAW)
        self.assertIn('本地规则提取（未调用模型）', text)
        self.assertIn('结构合法不等于制作信息齐全', text)
        from types import SimpleNamespace
        import stage_exec
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'writing').mkdir()
            (root / 'writing' / contract.RAW_SCRIPT_NAME).write_text(RAW, encoding='utf-8')
            run = stage_exec.run(SimpleNamespace(root=root, errors=[], bus=None, app=None), 'script_structure')
        details = ' '.join(str(row.get('detail', '')) for row in run['results'])
        self.assertIn('未调用模型', details)
        self.assertNotIn('Writer 已提取', details)

    def test_untagged_dialogue_and_unknown_props_keep_pending_status(self):
        raw = '场景 1：夜，空房间\n门被风吹开。\n道具：旧钥匙\n'
        text = contract.structure_script(raw)
        self.assertIn('待确认（原稿本场未出现“人物名：对白”标签）', text)
        self.assertIn('请人工补充角色档案', text)
        self.assertIn('- 旧钥匙：尺寸、材质、持有者待确认（来源：原稿声明）。', text)

    def test_alias_and_cross_episode_id_keep_source(self):
        raw = '场景 1：日，教室\n林小满，又名小满，是班长。\n林小满：我来了。\n'
        first = contract.structure_script(raw, source_name='第01集.md')
        second = contract.structure_script(raw, source_name='第09集.md')
        self.assertIn('- 别名：小满（来源：原稿声明）', first)
        ids = [line for line in first.splitlines() if line.startswith('- 跨集 ID：')]
        self.assertEqual(ids, [line for line in second.splitlines() if line.startswith('- 跨集 ID：')])
        self.assertRegex(ids[0], r'^- 跨集 ID：char-[0-9a-f]{8}（程序按角色名生成')

    def test_flashback_scene_is_marked_pending(self):
        raw = '场景 1：夜，雨中\n这是三年前的回忆。\n林小满：那次你说过会回来。\n'
        text = contract.structure_script(raw)
        self.assertIn('- 时间线：回忆／闪回（待确认：原稿未逐场标注，仅按关键词识别）', text)

    def test_same_name_conflicting_features_are_flagged(self):
        raw = ('场景 1：日，教室\n小李：我十八岁。\n\n'
               '场景 2：夜，街头\n小李：三十岁的男人独自站着。\n')
        text = contract.structure_script(raw)
        self.assertIn('- 同名提醒：原稿中「小李」在不同场次特征不一致，可能是同名不同人（待确认）。', text)

    def test_rule_review_requires_provenance_but_accepts_pending_fields(self):
        text = contract.structure_script(RAW)
        self.assertTrue(contract.review_structured_script(RAW, text)['approved'])
        without_id = text.replace('- 跨集 ID：', '- 编号：', 1)
        review = contract.review_structured_script(RAW, without_id)
        self.assertFalse(review['approved'])
        self.assertTrue(any('跨集 ID' in note for note in review['feedback']))


EPISODE_SCRIPT = '''# 第1集：雨夜来客

> 结构化剧本 · 《项目》第 1 集
> 来源：`%s`
> 整理日期：2026-11-22

---

## 一、本集信息

## 二、本集人物索引

## 四、分场结构

### 场景 1｜EP01-S01｜旧书店
林小满：把旧怀表交给我。
'''


class ModelWrittenStructureScriptTests(unittest.TestCase):
    """REQ-S02-21：按命名规则写进「结构剧本」目录的稿，正文按集排版也认。"""

    def project(self, folder):
        root = Path(folder).resolve() / '项目'
        source = (root / '01剧本准备' / 'Google' / 'Gemini desktop' / '创意_20261114' / '项目剧本'
                  / '项目_自然剧本_Google_20261114.md')
        source.parent.mkdir(parents=True)
        source.write_text(RAW, encoding='utf-8')
        return root, source

    def episode(self, root, source, name='项目_结构剧本_第01集_20261122.md', text=None):
        from contract.stage_path_service import write_dir
        folder = write_dir(root, 'structure') / contract.STRUCTURED_SCRIPT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(EPISODE_SCRIPT % source.relative_to(root).as_posix() if text is None else text,
                        encoding='utf-8')
        return path

    def test_episode_layout_in_structure_folder_is_recognised_and_listed(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            path = self.episode(root, source)
            self.assertTrue(contract.is_structured_script(path))
            self.assertEqual(contract.structured_script_paths(root), (path,))
            self.assertEqual(contract.structured_script_path(root), path)

    def test_structure_page_lists_the_model_written_script(self):
        from domain.script_workspace_service import script_structure_documents
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            path = self.episode(root, source)
            documents = script_structure_documents(root)
            self.assertEqual(documents.output_documents, (path,))
            self.assertEqual(documents.target, path)

    def test_each_episode_file_stays_listed(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            first = self.episode(root, source)
            second = self.episode(
                root, source, '项目_结构剧本_第02集_20261122.md',
                (EPISODE_SCRIPT % source.relative_to(root).as_posix()).replace('第1集', '第2集'))
            self.assertEqual(set(contract.structured_script_paths(root)), {first, second})

    def test_outline_source_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            path = self.episode(root, source,
                                text=EPISODE_SCRIPT % '01剧本准备/项目_项目大纲_Google_20261114.md')
            self.assertFalse(contract.is_structured_script(path))
            self.assertEqual(contract.structured_script_paths(root), ())

    def test_name_and_folder_are_both_required_and_blank_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            text = EPISODE_SCRIPT % source.relative_to(root).as_posix()
            notes = self.episode(root, source, '随手记.md', text)
            self.assertFalse(contract.is_structured_script(notes))
            outside = source.parent / '项目_结构剧本_第01集_20261122.md'
            outside.write_text(text, encoding='utf-8')
            self.assertFalse(contract.is_structured_script(outside))
            blank = self.episode(root, source, '项目_结构剧本_第03集_20261122.md', ' \n')
            self.assertFalse(contract.is_structured_script(blank))
            self.assertEqual(contract.structured_script_paths(root), ())

    def test_hidden_when_its_source_script_is_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            root, source = self.project(folder)
            path = self.episode(root, source)
            self.assertEqual(contract.structured_script_paths(root), (path,))
            source.unlink()
            self.assertEqual(contract.structured_script_paths(root), ())
            self.assertTrue(path.is_file())


class StructureDocumentRoleTests(unittest.TestCase):
    """REQ-S02-38：``_document_role`` 按两组剧本文档给面板点选分类；其余只读。"""

    def test_role_of_each_group_and_other_documents(self):
        from types import SimpleNamespace
        from desktop_script_pages import _document_role
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            natural = root / 'writing' / '剧本_甲.md'
            structured = root / '02剧本结构' / '结构剧本' / '项目_结构剧本_本地_20261124.md'
            other = root / '02剧本结构' / 'output' / '整理说明.md'
            structure = SimpleNamespace(source_documents=(natural,),
                                        output_documents=(structured,))
            self.assertEqual(_document_role(structure, natural), 'natural')
            self.assertEqual(_document_role(structure, structured), 'structured')
            self.assertIsNone(_document_role(structure, other),
                              '两组剧本之外的文档按只读处理')
            self.assertIsNone(_document_role(structure, None))
            self.assertIsNone(_document_role(structure, ''),
                              '空路径按只读处理')

    def test_role_matches_resolved_paths(self):
        """同一文件的等价路径写法（..／大小写无关与否依平台）仍判出同一角色。"""
        from types import SimpleNamespace
        from desktop_script_pages import _document_role
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            natural = root / 'writing' / '剧本_甲.md'
            structure = SimpleNamespace(source_documents=(natural,),
                                        output_documents=())
            self.assertEqual(_document_role(structure, natural.resolve()), 'natural')
            aliased = root / 'writing' / '..' / 'writing' / '剧本_甲.md'
            self.assertEqual(_document_role(structure, aliased), 'natural')


if __name__ == '__main__':
    unittest.main()
