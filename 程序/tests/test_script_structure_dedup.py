# -*- coding: utf-8 -*-
"""REQ-S02-33/34：同源结构剧本去重、旧份回收与厂商命名。

V1（G1）：同一来源只显示最新一份，重新生成时旧同源份进回收站，不同来源各保留一份，
无来源记录的历史稿不被回收。V2（G2）：本地规则生成文件名含「本地」，经模型生成含厂商名，
旧「_正稿_」文件仍被识别。
"""
import tempfile
import unittest
from datetime import datetime as _real_datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import contract.script_contract as contract
from contract.stage_path_service import write_dir


def _natural_script(root, name='自然剧本_测试_20260101.md',
                    text='第 1 集\n场景 1：夜\n林青：你来了。\n'):
    folder = write_dir(root, 'script')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    return path


def _patch_now(stamp):
    fake = SimpleNamespace(now=lambda: _real_datetime.fromtimestamp(stamp),
                           fromtimestamp=_real_datetime.fromtimestamp)
    return patch.object(contract, 'datetime', fake)


def _recycle(root):
    def supersede(paths):
        from storage_maintenance import recycle_paths
        recycle_paths(root, list(paths), '重新生成同源结构剧本，回收旧份')
    return supersede


class SameSourceDedupTests(unittest.TestCase):
    def test_same_source_keeps_only_the_latest(self):
        """REQ-S02-33：同一原稿两次生成（内容略有差异）只显示最新一份。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            with _patch_now(_real_datetime(2026, 10, 20, 12, 0, 0).timestamp()):
                contract.write_structured_script(root, source=source)
            # 同一原稿略微改动后重新生成，产出内容不同但来源相同。
            source.write_text(source.read_text(encoding='utf-8') + '\n新增一句对白。', encoding='utf-8')
            with _patch_now(_real_datetime(2026, 10, 21, 12, 0, 0).timestamp()):
                latest = contract.write_structured_script(root, source=source)
            self.assertEqual(contract.structured_script_paths(root), (latest,))

    def test_regenerate_recycles_the_old_same_source_copy(self):
        """REQ-S02-33：重新生成同源结构剧本时，旧份进回收站，可恢复。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            with _patch_now(_real_datetime(2026, 10, 20, 12, 0, 0).timestamp()):
                old = contract.write_structured_script(root, source=source)
            with _patch_now(_real_datetime(2026, 10, 21, 12, 0, 0).timestamp()):
                latest = contract.write_structured_script(root, source=source, supersede=_recycle(root))
            self.assertEqual(contract.structured_script_paths(root), (latest,))
            self.assertFalse(old.exists(), '旧同源份应已移入回收站')
            from storage_maintenance import recycle_base
            recycle = recycle_base(root)
            self.assertTrue(any(p.name == old.name for p in recycle.rglob('*.md')),
                            '回收站里应能找到旧同源份')

    def test_two_different_sources_each_keep_one(self):
        """REQ-S02-33：两份不同原稿各保留一份，不被同源去重误合并。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = _natural_script(root, '甲_自然剧本_20260101.md',
                                    '第 1 集\n场景 1：夜\n甲：来了。\n')
            second = _natural_script(root, '乙_自然剧本_20260101.md',
                                     '第 1 集\n场景 1：日\n乙：走了。\n')
            with _patch_now(_real_datetime(2026, 10, 20, 12, 0, 0).timestamp()):
                one = contract.write_structured_script(root, source=first)
            with _patch_now(_real_datetime(2026, 10, 21, 12, 0, 0).timestamp()):
                two = contract.write_structured_script(root, source=second)
            self.assertEqual(set(contract.structured_script_paths(root)), {one, two})

    def test_history_without_lineage_is_not_recycled(self):
        """REQ-S02-33：无来源记录的历史结构稿不被回收，也不被同源去重抹掉。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            structure_dir = write_dir(root, 'structure') / contract.STRUCTURED_SCRIPT_DIR
            structure_dir.mkdir(parents=True, exist_ok=True)
            history = structure_dir / '旧_结构剧本_正稿_20260101.md'
            history.write_text('# 结构化剧本\n## 角色档案\n## 分场剧本\n旧正文\n', encoding='utf-8')
            with _patch_now(_real_datetime(2026, 10, 21, 12, 0, 0).timestamp()):
                target = contract.write_structured_script(root, source=source, supersede=_recycle(root))
            self.assertTrue(history.exists(), '无来源记录的历史稿不得被回收')
            self.assertIn(history, contract.structured_script_paths(root))
            self.assertIn(target, contract.structured_script_paths(root))


class StructuredScriptNamingTests(unittest.TestCase):
    def test_local_rules_use_the_local_segment(self):
        """REQ-S02-34：本地规则生成的结构剧本文件名含「本地」。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            with _patch_now(_real_datetime(2026, 10, 22, 12, 0, 0).timestamp()):
                target = contract.write_structured_script(root, source=source)
            self.assertIn('_结构剧本_本地_', target.name)

    def test_model_generation_uses_the_vendor_segment(self):
        """REQ-S02-34：经模型生成时文件名含厂商名。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _natural_script(root)
            with _patch_now(_real_datetime(2026, 10, 22, 12, 0, 0).timestamp()):
                target = contract.write_structured_script(root, source=source, vendor='Anthropic')
            self.assertIn('_结构剧本_Anthropic_', target.name)

    def test_vendor_name_is_sanitized(self):
        """REQ-S02-34：厂商名走现有文件名净化，不引入路径分隔符。"""
        name = contract.structured_script_file_name(Path('p'), content='Anthropic/C<x>:d')
        for bad in ('/', '\\', '<', '>', ':', '"', '|', '?', '*'):
            self.assertNotIn(bad, name)

    def test_legacy_zheng_gao_files_still_recognized(self):
        """REQ-S02-34：旧「_正稿_」文件仍被识别并显示，不批量改名。"""
        name = '摄影侠_结构剧本_正稿_20261021.md'
        self.assertTrue(contract.is_structured_script_file_name(Path(name)))
        info = contract.stage_file_info(name)
        self.assertEqual(info['file_type'], '结构剧本')
        self.assertEqual(info['content'], '正稿')


if __name__ == '__main__':
    unittest.main()
