# -*- coding: utf-8 -*-
"""模型产出进入文件名、阶段写盘与清单的结构不变量＋注入对抗（T4／T10）。

口径：模型产出的标题、正文与清单数据都是**不可信输入**。本文件只钉三条可判定的边界：

* 命名：产出里的路径分隔符、控制字符与超长文本不得改变落盘位置，也不得逃出阶段目录；
* 写盘：结构剧本的来源必须在本项目内，空正文不得发布，目标路径不由正文内容决定；
* 清单：编号重复／缺失必须可被检出，宽松读取与严格读取的差别不得被抹平。

不联网、不调模型、不用 Tk。
"""
import json
import tempfile
import unittest
from pathlib import Path

import script_contract as contract
import script_manifest_schema as schema
import stage_path_service
from agent.core import read, read_json


ILLEGAL_IN_NAME = ('<', '>', ':', '"', '/', '\\', '|', '?', '*')


class FileNameInjectionTests(unittest.TestCase):
    """模型给的标题进入文件名时必须被收成一个安全片段。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'p'
        self.root.mkdir(parents=True)

    def name(self, content):
        return contract.stage_file_name(self.root, '结构剧本', content)

    def test_path_separators_cannot_split_or_escape_the_name(self):
        for content in ('../../escape', 'a/b/c', '..\\..\\win', 'C:/abs', 'C:\\abs', '~/home'):
            name = self.name(content)
            self.assertEqual(Path(name).name, name, name)
            self.assertNotIn('..', name, content)
            for bad in ('/', '\\', ':'):
                self.assertNotIn(bad, name, (content, name))

    def test_windows_illegal_characters_are_replaced(self):
        name = self.name('a<b>c:d"e|f?g*h')
        for bad in ILLEGAL_IN_NAME + ('\x00', '\x1f', '\n', '\r', '\t'):
            self.assertNotIn(bad, name, (bad, name))

    def test_control_characters_and_newlines_never_reach_the_name(self):
        name = self.name('标题\n第二行\x00\x1b[31m红色')
        for bad in ('\n', '\r', '\x00', '\x1b'):
            self.assertNotIn(bad, name, name)
        # 控制字节被收掉后剩下的 "[31m" 只是普通文字；关键是文件名仍能被受控命名解析认出。
        self.assertIsNotNone(contract.stage_file_info(self.root / name), name)

    def test_over_long_title_is_capped(self):
        name = self.name('长' * 200)
        self.assertEqual(name.count('长'), 80, name)

    def test_empty_or_symbol_only_title_falls_back(self):
        for content in ('', '   ', '...', '__', '  . _ '):
            self.assertIn('内容', self.name(content), content)

    def test_sanitized_name_is_still_a_controlled_stage_file(self):
        for content in ('../../escape', '雨夜修伞', 'a:b*c?d'):
            name = self.name(content)
            info = contract.stage_file_info(self.root / name)
            self.assertIsNotNone(info, name)
            self.assertEqual(info['file_type'], '结构剧本', (content, info))

    def test_real_path_stays_inside_the_project(self):
        target = self.root / self.name('../../escape')
        self.assertTrue(target.resolve().is_relative_to(self.root.resolve()), str(target))


class StructuredScriptWriteTests(unittest.TestCase):
    """结构剧本写盘：来源受限、空正文不发布、目标路径与正文无关。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'p'
        self.root.mkdir(parents=True)
        self.script_dir = stage_path_service.write_dir(self.root, 'script')
        self.script_dir.mkdir(parents=True, exist_ok=True)
        contract.canonical_structured_script_path(self.root).parent.mkdir(parents=True, exist_ok=True)
        self.source = self.script_dir / '自然剧本_测试_20260101.md'
        self.source.write_text('林青：你终于来了。', encoding='utf-8')

    def test_source_outside_the_project_is_rejected(self):
        outside = self.base / 'outside.md'
        outside.write_text('外部剧本', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            contract.write_structured_script(self.root, source=outside)
        self.assertIn('剧本来源必须位于当前项目的 writing 目录', str(caught.exception))

    def test_missing_source_file_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            contract.write_structured_script(self.root, source=self.root / '不存在.md')
        self.assertIn('未找到可读取的剧本原稿', str(caught.exception))

    def test_blank_body_is_not_published(self):
        target = contract.canonical_structured_script_path(self.root)
        with self.assertRaises(ValueError) as caught:
            contract.write_structured_script(self.root, content='   \n  ', source=self.source)
        self.assertIn('结构剧本正文不能为空', str(caught.exception))
        self.assertFalse(target.exists(), str(target))

    def test_target_does_not_depend_on_the_body(self):
        body = '正文里写着 ../../escape 和 C:\\Windows\\x 与 ../' * 3
        target = contract.write_structured_script(self.root, content=body, source=self.source)
        self.assertEqual(Path(target), contract.canonical_structured_script_path(self.root))
        self.assertTrue(Path(target).resolve().is_relative_to(self.root.resolve()), str(target))
        self.assertEqual(Path(target).read_text(encoding='utf-8'), body)

    def test_rendered_body_is_used_when_content_is_none(self):
        target = contract.write_structured_script(self.root, source=self.source)
        text = Path(target).read_text(encoding='utf-8')
        self.assertTrue(text.strip())
        self.assertIn('林青', text)

    def test_publisher_receives_the_target_and_a_non_blank_predicate(self):
        seen = {}

        def publisher(target, rendered, accepts, update_index):
            seen['target'] = Path(target)
            seen['rendered'] = rendered
            seen['accepts'] = accepts
            seen['published'] = accepts(rendered)

        contract.write_structured_script(self.root, content='正文', source=self.source, publisher=publisher)
        self.assertEqual(seen['target'], contract.canonical_structured_script_path(self.root))
        self.assertTrue(seen['target'].resolve().is_relative_to(self.root.resolve()))
        self.assertEqual(seen['rendered'], '正文')
        self.assertTrue(seen['published'])
        self.assertFalse(seen['accepts']('   '))
        self.assertFalse(seen['accepts']('\n'))
        self.assertTrue(seen['accepts']('x'))


class ManifestStructureInvariantsTests(unittest.TestCase):
    """清单编号与补缺：重复／缺失必须报出，补缺不得改动入参。"""

    def test_duplicate_ids_inside_one_manifest_are_reported(self):
        manifests = {'character_manifest.json': {'items': [{'character_id': 'CHAR_001'},
                                                          {'character_id': 'CHAR_001'}]}}
        problems = schema.duplicate_ids(manifests)
        self.assertTrue(problems)
        self.assertFalse(schema.unique_ids(manifests))
        self.assertTrue(any('CHAR_001' in row for row in problems), problems)

    def test_ids_clashing_across_manifests_are_reported(self):
        manifests = {'character_manifest.json': {'items': [{'character_id': 'CHAR_001'}]},
                     'prop_manifest.json': {'items': [{'prop_id': 'CHAR_001'}]}}
        self.assertTrue(schema.duplicate_ids(manifests))

    def test_missing_id_is_reported_not_silently_accepted(self):
        problems = schema.duplicate_ids({'scene_manifest.json': {'items': [{'name': '屋顶'}]}})
        self.assertTrue(problems)
        self.assertTrue(any('还没有编号' in row for row in problems), problems)

    def test_unique_ids_pass(self):
        manifests = {'character_manifest.json': {'items': [{'character_id': 'CHAR_001'}]},
                     'scene_manifest.json': {'items': [{'scene_id': 'LOC_001'}]}}
        self.assertEqual(schema.duplicate_ids(manifests), [])
        self.assertTrue(schema.unique_ids(manifests))

    def test_normalize_fills_defaults_and_leaves_the_input_alone(self):
        item = {'name': '林青'}
        filled = schema.normalize('character', item, 3)
        self.assertNotIn('character_id', item)
        self.assertEqual(filled['character_id'], schema.new_id('character', 3))
        self.assertEqual(sorted(filled['physical_features']), sorted(schema.PHYSICAL_KEYS))
        self.assertEqual(filled['name'], '林青')

    def test_normalize_rejects_non_dict_items(self):
        for value in ('文本', 3, None, ['a']):
            self.assertIsNone(schema.normalize('character', value), value)

    def test_manifest_wrapper_keeps_header_and_drops_junk_rows(self):
        built = schema.manifest('scene', [{'name': '屋顶'}, '不是条目', 7])
        self.assertEqual(built['manifest'], 'scene_manifest.json')
        self.assertEqual(built['kind'], 'scene')
        self.assertEqual(len(built['items']), 1)
        self.assertEqual(built['items'][0]['scene_id'], 'LOC_001')


class StrictVersusLenientReadTests(unittest.TestCase):
    """宽松读取与严格读取的差别是既有契约：坏文件不得被静默当成空数据。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.broken = Path(self.temp.name) / 'broken.json'
        self.broken.write_text('{"a": 1', encoding='utf-8')

    def test_strict_read_raises_on_broken_json(self):
        with self.assertRaises(json.JSONDecodeError):
            read(self.broken)

    def test_lenient_read_returns_the_default_on_broken_json(self):
        sentinel = {'d': 1}
        self.assertEqual(read_json(self.broken, sentinel), sentinel)
        self.assertIsNone(read_json(self.broken))

    def test_lenient_read_returns_the_default_when_the_file_is_absent(self):
        self.assertEqual(read_json(Path(self.temp.name) / '无此文件.json', 'fallback'), 'fallback')


if __name__ == '__main__':
    unittest.main()