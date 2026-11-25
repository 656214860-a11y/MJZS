# -*- coding: utf-8 -*-
"""UX-REPLY-AREA：第 2–13 页「过程与回话区」的分阶段 JSONL 记录层（domain/stage_reply_log.py）。

覆盖卡面接口契约：按阶段落盘 ``<项目>/对话记录/<阶段键>.jsonl``、每行带
``schema_version``、经注入发布器原子写回；打开页仅尾部反向定位读最近 200 条
（不一次全量读入），更早记录按字节游标分页；无总条数上限；纯记录隔离——
任何发给模型的 prompt/上下文构造不得读取 ``对话记录/*.jsonl``。
"""
import json
import tempfile
import unittest
from pathlib import Path

from agent.core import save_text
from contract import pet_bus
from domain import stage_reply_log


class StageLogPathTests(unittest.TestCase):
    def test_path_is_project_reply_folder_per_stage(self):
        root = Path('X:/proj')
        path = stage_reply_log.stage_log_path(root, 'storyboard')
        self.assertEqual(path.parent.name, stage_reply_log.FOLDER)
        self.assertEqual(path.name, 'storyboard.jsonl')

    def test_every_production_stage_gets_a_log(self):
        for stage in pet_bus.STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(
                    stage_reply_log.stage_log_path(Path('X:/p'), stage).name,
                    stage + '.jsonl')

    def test_unknown_or_unsafe_stage_rejected(self):
        for bad in ('', 'notastage', '../escape', 'a/b', 'a\\b', '.', '..'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    stage_reply_log.stage_log_path(Path('X:/p'), bad)


class AppendAndTailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()

    def _append(self, stage, i, kind='progress'):
        return stage_reply_log.append_record(
            self.root, stage, {'kind': kind, 'text': '记录%d' % i}, publish=save_text)

    def test_append_stamps_schema_version_and_timestamp(self):
        record = self._append('storyboard', 0)
        self.assertIsInstance(record, dict)
        self.assertEqual(record.get('schema_version'), stage_reply_log.SCHEMA_VERSION)
        self.assertTrue(record.get('at'))
        path = stage_reply_log.stage_log_path(self.root, 'storyboard')
        lines = [line for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row.get('schema_version'), stage_reply_log.SCHEMA_VERSION)
        self.assertEqual(row.get('kind'), 'progress')
        self.assertEqual(row.get('text'), '记录0')

    def test_records_are_per_stage_files(self):
        self._append('storyboard', 0)
        self._append('assets', 1)
        storyboard, _ = stage_reply_log.read_tail(self.root, 'storyboard')
        assets, _ = stage_reply_log.read_tail(self.root, 'assets')
        self.assertEqual([r.get('text') for r in storyboard], ['记录0'])
        self.assertEqual([r.get('text') for r in assets], ['记录1'])

    def test_invalid_kind_and_missing_publisher_degrade(self):
        bad = stage_reply_log.append_record(
            self.root, 'storyboard', {'kind': 'bogus', 'text': 'x'}, publish=save_text)
        self.assertIsNone(bad, '未登记的记录种类拒绝落盘')
        without = stage_reply_log.append_record(
            self.root, 'storyboard', {'kind': 'progress', 'text': 'x'})
        self.assertIsNone(without, '未注入发布器只降级，不阻断发送链')
        self.assertEqual(stage_reply_log.read_tail(self.root, 'storyboard'), ([], 0))

    def test_read_tail_missing_and_empty_file(self):
        self.assertEqual(stage_reply_log.read_tail(self.root, 'storyboard'), ([], 0))
        path = stage_reply_log.stage_log_path(self.root, 'storyboard')
        path.parent.mkdir(parents=True)
        path.write_bytes(b'')
        self.assertEqual(stage_reply_log.read_tail(self.root, 'storyboard'), ([], 0))

    def test_tail_returns_last_200_in_order_and_cursor(self):
        total = stage_reply_log.TAIL_LIMIT + 50
        for i in range(total):
            self._append('storyboard', i)
        records, cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        self.assertEqual(len(records), stage_reply_log.TAIL_LIMIT)
        self.assertEqual(records[0].get('text'), '记录%d' % (total - stage_reply_log.TAIL_LIMIT))
        self.assertEqual(records[-1].get('text'), '记录%d' % (total - 1))
        self.assertGreater(cursor, 0, '还有更早记录时游标非零')

    def test_read_before_pages_back_to_file_head(self):
        total = stage_reply_log.TAIL_LIMIT + 50
        for i in range(total):
            self._append('storyboard', i)
        _records, cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        earlier, cursor = stage_reply_log.read_before(self.root, 'storyboard', cursor)
        self.assertEqual(len(earlier), 50)
        self.assertEqual(earlier[0].get('text'), '记录0')
        self.assertEqual(earlier[-1].get('text'), '记录49')
        self.assertEqual(cursor, 0, '已到文件头')
        earlier, cursor = stage_reply_log.read_before(self.root, 'storyboard', cursor)
        self.assertEqual((earlier, cursor), ([], 0))

    def test_read_before_cursor_in_middle_of_page(self):
        for i in range(90):
            self._append('storyboard', i)
        records, cursor = stage_reply_log.read_tail(self.root, 'storyboard', limit=40)
        self.assertEqual(len(records), 40)
        self.assertEqual(records[-1].get('text'), '记录89')
        earlier, cursor = stage_reply_log.read_before(self.root, 'storyboard', cursor, limit=40)
        self.assertEqual(len(earlier), 40)
        self.assertEqual(earlier[0].get('text'), '记录10')
        earlier, cursor = stage_reply_log.read_before(self.root, 'storyboard', cursor, limit=40)
        self.assertEqual(len(earlier), 10)
        self.assertEqual(earlier[0].get('text'), '记录0')
        self.assertEqual(cursor, 0)

    def test_bad_lines_and_garbage_head_are_tolerated(self):
        path = stage_reply_log.stage_log_path(self.root, 'storyboard')
        path.parent.mkdir(parents=True)
        with open(path, 'wb') as handle:
            handle.write(b'{"kind":"progress","text":"broken\n')  # 未闭合 JSON
            handle.write(b'\xff\xfe not utf8 line\n')
        for i in range(3):
            self._append('storyboard', i)
        records, cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        self.assertEqual([r.get('text') for r in records], ['记录0', '记录1', '记录2'])
        self.assertEqual(cursor, 0, '坏行同窗口一并消费完（解码侧丢弃），没有更早分页')

    def test_no_total_cap_beyond_two_pages(self):
        total = stage_reply_log.TAIL_LIMIT * 2 + 37
        for i in range(total):
            stage_reply_log.append_record(
                self.root, 'storyboard', {'kind': 'user', 'text': 'm%d' % i},
                publish=save_text)
        seen = []
        records, cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        while records:
            seen = [r.get('text') for r in records] + seen
            records, cursor = stage_reply_log.read_before(self.root, 'storyboard', cursor)
        self.assertEqual(len(seen), total)
        self.assertEqual(seen[0], 'm0')
        self.assertEqual(seen[-1], 'm%d' % (total - 1))


class PromptIsolationTests(unittest.TestCase):
    """纯记录隔离守护：记录层只被回话区消费，任何 prompt/上下文构造不读它。"""

    def test_only_reply_area_imports_stage_reply_log(self):
        from tests.architecture._scan import module_scan_files, resolved_module_import_rows
        offenders = []
        for path in module_scan_files():
            imported = {name for _line, name in resolved_module_import_rows(path)}
            if 'stage_reply_log' in imported and path.stem != 'stage_reply_area':
                offenders.append(path.name)
        self.assertEqual(offenders, [],
                         '对话记录只能被 ui/stage_reply_area 消费：' + ', '.join(offenders))

    def test_records_do_not_change_prompt_construction(self):
        """写入/修改阶段记录后，发送链构造的技能 prompt 逐字不变。"""
        import desktop_shared_send as shared_send
        before = shared_send._skill_prompt('分镜技法', Path('x') / '分镜技法.skill.md', '做三版')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(3):
                stage_reply_log.append_record(
                    root, 'storyboard',
                    {'kind': 'user', 'text': '私有标记%d' % i}, publish=save_text)
            after = shared_send._skill_prompt('分镜技法', Path('x') / '分镜技法.skill.md', '做三版')
        self.assertEqual(before, after)
        self.assertNotIn('私有标记', after)


if __name__ == '__main__':
    unittest.main()
