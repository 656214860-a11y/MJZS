# -*- coding: utf-8 -*-
"""分镜文件读缓存自检：同一个文件在一次页面重排里只解析一次。运行：python test_file_cache.py"""
import ast, hashlib, json, os, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import file_cache, storyboard_files, storyboard_selection


def write_episode(path, episode_id, shots):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"episode_id": episode_id, "title": "测试",
            "shots": [{"id": sid, "title": sid} for sid in shots]}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class FileDigestTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()

    def test_streaming_digest_matches_sha256_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "big.bin"
            payload = b"x" * (1024 * 1024 * 3 + 7)
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertEqual(file_cache.file_digest(path), expected)
            with patch.object(Path, "open", side_effect=AssertionError("缓存命中后不应再打开文件")):
                self.assertEqual(file_cache.file_digest(path), expected)

    def test_digest_refreshes_after_content_change_and_invalidate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "media.mp4"
            path.write_bytes(b"first")
            first = file_cache.file_digest(path)
            path.write_bytes(b"second")
            self.assertNotEqual(file_cache.file_digest(path), first)
            file_cache.invalidate(path)
            self.assertEqual(file_cache.file_digest(path), hashlib.sha256(b"second").hexdigest())


class ReadJsonTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()

    def test_unchanged_file_is_parsed_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_episode(Path(td) / "a.json", "EP001", ["SH001"])
            first = file_cache.read_json(path)
            with patch.object(file_cache.json, "loads", side_effect=AssertionError("重新解析了")):
                second = file_cache.read_json(path)
            self.assertEqual(first, second)

    def test_rewrite_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_episode(Path(td) / "a.json", "EP001", ["SH001"])
            first = file_cache.read_json(path)
            write_episode(path, "EP002", ["SH001", "SH002"])
            second = file_cache.read_json(path)
            self.assertIsNot(first, second)
            self.assertEqual(second["episode_id"], "EP002")

    def test_lifecycle_events_evict_all_cached_representations(self):
        """发布、回收和外部覆盖均走显式事件，不依赖页面刷新。"""
        with tempfile.TemporaryDirectory() as td:
            path = write_episode(Path(td) / 'a.json', 'EP001', ['SH001'])
            file_cache.read_json(path)
            file_cache.read_bytes(path)
            self.assertTrue(file_cache.published(path))
            self.assertFalse(file_cache.published(path))

            path.write_text('外部文本', encoding='utf-8')
            file_cache.read_text(path, encoding='utf-8')
            self.assertTrue(file_cache.externally_overwritten(path))

            moved = Path(td) / 'recycle' / 'a.json'
            moved.parent.mkdir()
            moved.write_text('{}', encoding='utf-8')
            file_cache.read_json(moved)
            self.assertTrue(file_cache.recycled(((path, moved),)))

    def test_same_content_rewrite_reuses_parsed_json_by_hash(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_episode(Path(td) / "a.json", "EP001", ["SH001"])
            first = file_cache.read_json(path)
            stamp = path.stat().st_mtime_ns
            path.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
            os.utime(path, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
            with patch.object(file_cache.json, "loads", side_effect=AssertionError("重新解析了")):
                self.assertEqual(file_cache.read_json(path), first)

    def test_missing_file_raises_and_drops_entry(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_episode(Path(td) / "a.json", "EP001", ["SH001"])
            file_cache.read_json(path)
            path.unlink()
            with self.assertRaises(OSError):
                file_cache.read_json(path)

    def test_text_preview_reuses_unchanged_file_and_reloads_after_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'preview.md'
            path.write_text('第一稿', encoding='utf-8')
            first = file_cache.read_text(path, encoding='utf-8')
            second = file_cache.read_text(path, encoding='utf-8')
            self.assertIs(first, second)
            path.write_text('第二稿内容更长', encoding='utf-8')
            self.assertEqual(file_cache.read_text(path, encoding='utf-8'), '第二稿内容更长')

    def test_same_content_rewrite_reuses_text_and_bytes_by_hash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'preview.md'
            path.write_text('相同内容', encoding='utf-8')
            text = file_cache.read_text(path, encoding='utf-8')
            raw = file_cache.read_bytes(path)
            stamp = path.stat().st_mtime_ns
            path.write_text('相同内容', encoding='utf-8')
            os.utime(path, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
            self.assertIs(file_cache.read_text(path, encoding='utf-8'), text)
            self.assertIs(file_cache.read_bytes(path), raw)

    def test_script_text_byte_cache_reuses_content_and_invalidates_after_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'script.md'
            path.write_text('第一版自然剧本', encoding='utf-8')
            from script_text_reader import script_text
            first = script_text(path)
            second = script_text(path)
            self.assertEqual(first, second)
            self.assertIs(file_cache.read_bytes(path), file_cache.read_bytes(path))
            path.write_text('第二版自然剧本，内容更长', encoding='utf-8')
            self.assertEqual(script_text(path), '第二版自然剧本，内容更长')

    def test_catalog_and_preview_share_one_parse_per_file(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"
            folder = project / "storyboard" / "分镜拆分"
            first = write_episode(folder / "EP001_分镜.json", "EP001", ["SH001"])
            second = write_episode(folder / "EP002_分镜.json", "EP002", ["SH001", "SH002"])
            calls = [0]
            original = file_cache.json.loads

            def counting(raw):
                calls[0] += 1
                return original(raw)

            file_cache.json.loads = counting
            try:
                entries = storyboard_files.catalog(project, "storyboard")
                for entry in entries:
                    storyboard_files.content_preview(entry["path"])
            finally:
                file_cache.json.loads = original
            self.assertEqual(len(entries), 2)
            self.assertEqual(calls[0], 2, "目录与预览应各文件只解析一次")


class RepeatReadTests(unittest.TestCase):
    """一次页面重排里会被问很多遍的东西：只解析一次，但写入后立刻能看到新内容。"""

    def setUp(self):
        file_cache.clear()

    def count_reads(self):
        counts = [0]
        original = file_cache.json.loads

        def counting(raw):
            counts[0] += 1
            return original(raw)

        file_cache.json.loads = counting
        self.addCleanup(setattr, file_cache.json, "loads", original)
        return counts

    def test_prefs_parses_ui_settings_once_and_reloads_after_write(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"; project.mkdir()
            path = project / "ui_settings.json"
            path.write_text(json.dumps({"adopted_storyboards": []}), encoding="utf-8")
            counts = self.count_reads()
            for _ in range(5):
                self.assertEqual(storyboard_selection.prefs(project)["adopted_storyboards"], [])
            self.assertEqual(counts[0], 1, "ui_settings.json 在 5 次读取里被解析了 %d 次" % counts[0])
            path.write_text(json.dumps({"adopted_storyboards": ["storyboard/分镜拆分/EP001_分镜.json"]}), encoding="utf-8")
            self.assertEqual(storyboard_selection.prefs(project)["adopted_storyboards"],
                             ["storyboard/分镜拆分/EP001_分镜.json"])
            self.assertEqual(counts[0], 2)

    def test_produced_scripts_reuses_given_entries(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"
            folder = project / "storyboard" / "分镜拆分"
            write_episode(folder / "EP001_分镜.json", "EP001", ["SH001"])
            calls = [0]
            original = storyboard_files.catalog

            def counting(project_arg, kind):
                calls[0] += 1
                return original(project_arg, kind)

            storyboard_files.catalog = counting
            self.addCleanup(setattr, storyboard_files, "catalog", original)
            entries = storyboard_files.catalog(project, "storyboard")
            calls[0] = 0
            storyboard_files.produced_scripts(project, entries)
            self.assertEqual(calls[0], 0, "已经算过分镜目录时不该再走一遍目录")
            storyboard_files.produced_scripts(project)
            self.assertEqual(calls[0], 1)

    def test_legacy_script_source_resolves_to_current_structured_script(self):
        """目录迁移后，旧 JSON 的 writing/script.md 不应令制作状态和自动采用失效。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            natural = project / '01剧本准备' / '项目_自然剧本_EP001_20260926.md'
            natural.parent.mkdir(parents=True)
            natural.write_text('# 第01集', encoding='utf-8')
            from script_contract import canonical_structured_script_path, structure_script
            structured = canonical_structured_script_path(project)
            structured.parent.mkdir(parents=True)
            structured.write_text(
                structure_script('# 第01集\n\n角色：测试角色\n\n场景：测试场景',
                                 source_name=natural.relative_to(project).as_posix()),
                encoding='utf-8')
            board = project / '03初步分镜' / '分镜拆分' / 'EP001_测试_分镜.json'
            write_episode(board, 'EP001', ['SH001'])
            payload = file_cache.read_json(board)
            payload['source_script'] = 'writing/script.md'
            board.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            file_cache.clear()

            self.assertEqual(storyboard_files.produced_scripts(project), {structured.resolve()})
            self.assertEqual(storyboard_selection.source_script_error(project, board), '')

    def test_orphaned_draft_is_not_offered_after_source_was_removed(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            board = write_episode(project / '03初步分镜' / '分镜拆分' / 'EP001_测试_分镜.json',
                                  'EP001', ['SH001'])
            payload = file_cache.read_json(board)
            payload['source_script'] = '02剧本结构/结构剧本/已删除_结构剧本_正稿_20260927.md'
            board.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            file_cache.clear()
            self.assertEqual(storyboard_files.catalog(project, 'storyboard'), [])

    def test_lineaged_final_is_hidden_when_its_structured_script_is_deleted(self):
        """定稿追溯结构剧本，不能追溯已被归档的工作 JSON。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            source = project / '02剧本结构' / '结构剧本' / 'p_结构剧本_正稿_20260927.md'
            source.parent.mkdir(parents=True)
            source.write_text('# 结构剧本', encoding='utf-8')
            final = write_episode(project / '06分镜定稿' / '分镜' /
                                  'EP001_分镜定稿_20260927' / 'episode.json', 'EP001', ['SH001'])
            from artifact_lineage import record
            record(project, final, source, 'final_storyboard')
            self.assertEqual([entry['path'] for entry in storyboard_files.catalog(project, 'storyboard')],
                             [final.resolve()])
            source.unlink(); file_cache.clear()
            self.assertEqual(storyboard_files.catalog(project, 'storyboard'), [])

    def test_stale_final_stays_visible_and_is_tagged_source_changed(self):
        """原稿同路径内容变了只标过期，不隐藏、不覆盖用户成品。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            source = project / '02剧本结构' / '结构剧本' / 'p_结构剧本_正稿_20260927.md'
            source.parent.mkdir(parents=True)
            source.write_text('# 结构剧本', encoding='utf-8')
            final = write_episode(project / '06分镜定稿' / '分镜' /
                                  'EP001_分镜定稿_20260927' / 'episode.json', 'EP001', ['SH001'])
            from artifact_lineage import record
            record(project, final, source, 'final_storyboard')
            source.write_text('# 结构剧本（用户改过）', encoding='utf-8')
            file_cache.clear()
            entries = storyboard_files.catalog(project, 'storyboard')
            self.assertEqual([entry['path'] for entry in entries], [final.resolve()])
            self.assertIn('来源已变更', entries[0]['title'])

    def test_final_lineage_prefers_stable_structured_script_over_working_json(self):
        """REQ-S07-21：定稿血缘追溯到稳定的结构剧本，而不是会被退役的分镜工作 JSON。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            source = project / '02剧本结构' / '结构剧本' / 'p_结构剧本_正稿_20260927.md'
            source.parent.mkdir(parents=True)
            source.write_text('# 结构剧本', encoding='utf-8')
            draft = write_episode(project / '03初步分镜' / '分镜文档' / 'EP001_测试_分镜.json',
                                  'EP001', ['SH001'])
            payload = file_cache.read_json(draft)
            payload['source_script'] = source.relative_to(project).as_posix()
            draft.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            import storyboard_final
            self.assertEqual(storyboard_final._lineage_source(project, draft), source.resolve())


class SharedCacheWriteTests(unittest.TestCase):
    """read_json 每次返回新拷贝（R1853 起）：读—改—写路径改了也不会污染缓存。"""

    def setUp(self):
        file_cache.clear()

    def write_prefs(self, project, data):
        (project / "ui_settings.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_prefs_is_a_fresh_copy_of_the_cached_object(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"; project.mkdir()
            self.write_prefs(project, {"adopted_storyboards": []})
            first = storyboard_selection.prefs(project)
            self.assertEqual(first, file_cache.read_json(project / "ui_settings.json"))
            self.assertIsNot(first, file_cache.read_json(project / "ui_settings.json"))

    def test_remember_many_keeps_prior_snapshot_intact(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"; project.mkdir()
            self.write_prefs(project, {"storyboard_files": ["storyboard/分镜拆分/EP001_分镜.json"]})
            second = write_episode(project / "storyboard" / "分镜拆分" / "EP002_分镜.json", "EP002", ["SH001"])
            before = storyboard_selection.prefs(project)
            storyboard_files.remember_many(project, "storyboard", [second])
            self.assertEqual(before["storyboard_files"], ["storyboard/分镜拆分/EP001_分镜.json"],
                             "remember_many 就地改写了 read_json 的共享缓存对象")
            after = storyboard_selection.prefs(project)
            self.assertEqual(after["storyboard_files"], ["storyboard/分镜拆分/EP002_分镜.json"])
            self.assertEqual(after["storyboard_file"], "storyboard/分镜拆分/EP002_分镜.json")

    def test_selected_many_sees_values_written_by_remember_many(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"; project.mkdir()
            self.write_prefs(project, {})
            ep = write_episode(project / "storyboard" / "分镜拆分" / "EP001_分镜.json", "EP001", ["SH001"])
            self.assertEqual(storyboard_files.selected_many(project, "storyboard"), [])
            storyboard_files.remember_many(project, "storyboard", [ep])
            self.assertEqual(storyboard_files.selected_many(project, "storyboard"), [ep.resolve()])

    def test_sync_structured_script_selects_canonical_output_before_existing_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"; project.mkdir()
            old = project / "writing" / "第02集.md"
            old.parent.mkdir(parents=True, exist_ok=True); old.write_text("# 原剧本", encoding="utf-8")
            structured = project / "writing" / "script.md"
            structured.write_text("# 结构化剧本\n## 角色档案\n## 分场剧本", encoding="utf-8")
            self.write_prefs(project, {"storyboard_scripts": ["writing/第02集.md"]})
            self.assertEqual(storyboard_files.sync_structured_script(project),
                             [structured.resolve(), old.resolve()])
            self.assertEqual(storyboard_files.selected_many(project, "script"),
                             [structured.resolve(), old.resolve()])

    def test_focus_keeps_prior_snapshot_intact(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"
            write_episode(project / "storyboard" / "分镜拆分" / "EP001_分镜.json", "EP001", ["SH001"])
            second = write_episode(project / "storyboard" / "分镜拆分" / "EP002_分镜.json", "EP002", ["SH002"])
            self.write_prefs(project, {"adopted_storyboards": ["storyboard/分镜拆分/EP001_分镜.json",
                                                               "storyboard/分镜拆分/EP002_分镜.json"],
                                       "frame_json": "storyboard/分镜拆分/EP001_分镜.json"})
            before = storyboard_selection.prefs(project)
            storyboard_selection.focus(project, second)
            self.assertEqual(before["frame_json"], "storyboard/分镜拆分/EP001_分镜.json",
                             "focus 就地改写了 read_json 的共享缓存对象")
            self.assertEqual(storyboard_selection.prefs(project)["frame_json"],
                             "storyboard/分镜拆分/EP002_分镜.json")

    def test_remove_keeps_prior_snapshot_intact(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"
            first = write_episode(project / "storyboard" / "分镜拆分" / "EP001_分镜.json", "EP001", ["SH001"])
            second = write_episode(project / "storyboard" / "分镜拆分" / "EP002_分镜.json", "EP002", ["SH002"])
            self.write_prefs(project, {"adopted_storyboards": ["storyboard/分镜拆分/EP001_分镜.json",
                                                               "storyboard/分镜拆分/EP002_分镜.json"],
                                       "frame_json": "storyboard/分镜拆分/EP002_分镜.json"})
            before = storyboard_selection.prefs(project)
            remaining = storyboard_selection.remove(project, [second])
            self.assertEqual(before["adopted_storyboards"], ["storyboard/分镜拆分/EP001_分镜.json",
                                                             "storyboard/分镜拆分/EP002_分镜.json"],
                             "remove 就地改写了 read_json 的共享缓存对象")
            self.assertEqual(remaining, [first.resolve()])
            self.assertEqual(storyboard_selection.prefs(project)["frame_json"],
                             "storyboard/分镜拆分/EP001_分镜.json")


class SharedCacheSourceGuardTests(unittest.TestCase):
    """源码守卫：read_json 的结果是共享对象，谁要改就得先取副本，不能就地写。"""

    SHARED_READERS = {"prefs", "_prefs", "read_json"}
    COPY_READERS = {"writable_prefs", "_writable_prefs", "dict"}
    MUTATORS = {"pop", "setdefault", "update", "clear"}

    @staticmethod
    def called(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def unsafe_writes(self, tree):
        """返回 [(函数, 变量, 写法)]：变量来自共享读取，却被就地改写。"""
        found = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            shared, copied = set(), set()
            for node in ast.walk(func):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    name = self.called(node.value)
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if name in self.SHARED_READERS:
                                shared.add(target.id)
                            if name in self.COPY_READERS:
                                copied.add(target.id)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                                and target.value.id in shared and target.value.id not in copied):
                            found.append((func.name, target.value.id, "下标写入"))
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in self.MUTATORS and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in shared and node.func.value.id not in copied):
                    found.append((func.name, node.func.value.id, node.func.attr))
        return found

    def test_shared_readers_are_not_mutated_in_place(self):
        program = Path(HERE).parent
        for name in ("storyboard_selection.py", "storyboard_files.py"):
            tree = ast.parse((program / name).read_text(encoding="utf-8"))
            self.assertEqual(self.unsafe_writes(tree), [],
                             "%s 就地改写了 read_json 的共享缓存对象" % name)

    def test_guard_detects_the_regression_it_is_meant_to_catch(self):
        sample = ast.parse("def f(p):\n    data = prefs(p)\n    data['k'] = 1\n")
        self.assertEqual(self.unsafe_writes(sample), [("f", "data", "下标写入")])
        safe = ast.parse("def f(p):\n    data = writable_prefs(p)\n    data['k'] = 1\n")
        self.assertEqual(self.unsafe_writes(safe), [])


class ReadJsonSharedTests(unittest.TestCase):
    """read_json_shared：命中走无锁快路径，但文件一变必须读到新内容。"""
    def setUp(self):
        file_cache.clear()

    def test_unchanged_file_skips_lock_and_changed_file_is_reread(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a.json"
            path.write_text(json.dumps({"v": 1}), encoding="utf-8")
            self.assertEqual(file_cache.read_json_shared(path), {"v": 1})
            with patch.object(file_cache, "_locked_json_shared", side_effect=AssertionError("命中不应再加锁")):
                self.assertEqual(file_cache.read_json_shared(path), {"v": 1})
            path.write_text(json.dumps({"v": 22}), encoding="utf-8")
            self.assertEqual(file_cache.read_json_shared(path), {"v": 22})

    def test_missing_or_broken_file_raises_like_read_json(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(OSError):
                file_cache.read_json_shared(Path(td) / "none.json")
            bad = Path(td) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                file_cache.read_json_shared(bad)


if __name__ == "__main__":
    unittest.main()
