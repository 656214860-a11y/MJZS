import os
import tempfile
import unittest
from pathlib import Path

from infra import file_cache


class FileCacheBoundsTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_same_stat_external_rewrites_and_replacement(self):
        path = self.root / 'data.json'
        path.write_bytes(b'{"v":1}')
        for index in range(32):
            previous, version = (1, 2) if index % 2 == 0 else (2, 1)
            digest = file_cache.file_digest(path)
            self.assertEqual(file_cache.read_json_shared(path), {'v': previous})
            stamp = path.stat().st_mtime_ns
            replace = index == 31
            target = self.root / 'replacement' if replace else path
            target.write_bytes(b'{"v":%d}' % version)
            os.utime(target, ns=(stamp, stamp))
            if replace:
                target.replace(path)
            with self.subTest(index=index):
                self.assertEqual(path.stat().st_mtime_ns, stamp)
                self.assertEqual(file_cache.read_json_shared(path), {'v': version})
                self.assertNotEqual(file_cache.file_digest(path), digest)

    def test_entry_limits_at_100_and_1000(self):
        for index in range(1000):
            path = self.root / f'{index}.json'
            path.write_bytes(b'{}')
            file_cache.read_json_shared(path)
            file_cache.file_digest(path)
            if index in (99, 999):
                with self.subTest(count=index + 1):
                    self.assertLess(len(file_cache._CACHE), 100)
                    self.assertLess(len(file_cache._DIGEST_CACHE), 100)

    def test_oversize_json_and_aggregate_byte_budget(self):
        paths = [self.root / f'large-{index}.json' for index in range(4)]
        for path in paths:
            path.write_bytes(b'"' + b'x' * (3 * 1024 * 1024) + b'"')
            self.assertEqual(len(file_cache.read_json_shared(path)), 3 * 1024 * 1024)
        self.assertEqual(len(file_cache._CACHE), 2)
        self.assertGreater(file_cache._CACHE.weight, 6 * 1024 * 1024)
        self.assertLessEqual(file_cache._CACHE.weight, file_cache._CONTENT_BUDGET)
        self.assertNotIn(file_cache._key(paths[0]), file_cache._CACHE)

        path = self.root / 'huge.json'
        payload = b'x' * file_cache._CONTENT_BUDGET
        path.write_bytes(b'"' + payload + b'"')
        self.assertEqual(len(file_cache.read_json(path)), len(payload))
        self.assertEqual(len(file_cache.read_text(path)), len(payload) + 2)
        self.assertEqual(len(file_cache.read_bytes(path)), len(payload) + 2)
        self.assertFalse(file_cache.invalidate(path))
        self.assertEqual(len(file_cache._CACHE), 2)

    def test_invalid_json_and_deleted_paths_drop_entries(self):
        path = self.root / 'data.json'
        path.write_bytes(b'{}')
        file_cache.read_json_shared(path)
        path.write_bytes(b'invalid')
        with self.assertRaises(ValueError):
            file_cache.read_json_shared(path)
        self.assertFalse(file_cache.invalidate(path))

        file_cache.file_digest(path)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            file_cache.file_digest(path)
        self.assertFalse(file_cache.invalidate(path))

    def test_parallel_reads_and_explicit_invalidation_during_miss(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        path = self.root / 'data.json'
        path.write_bytes(b'{}')
        file_cache.read_json_shared(path)
        cache = file_cache._DIGEST_CACHE
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(file_cache.file_digest, [path] * 32))
            self.assertEqual(len(set(results)), 1)
        self.assertEqual(len(cache), 1)

        original = file_cache._weight
        for evict in (lambda: file_cache.externally_overwritten(path), file_cache.clear):
            file_cache.invalidate(path)
            entered, resume = Event(), Event()

            def pause(*args):
                entered.set()
                if not resume.wait(5):
                    raise TimeoutError('test barrier')
                return original(*args)

            with ThreadPoolExecutor(max_workers=1) as pool, patch.object(file_cache, '_weight', pause):
                read = pool.submit(file_cache.file_digest, path)
                try:
                    self.assertTrue(entered.wait(5))
                    evict()
                finally:
                    resume.set()
                self.assertEqual(read.result(5), results[0])
            self.assertEqual(len(cache), 0)
            self.assertEqual(cache.weight, 0)

    def test_replacement_between_data_and_signature_is_retried(self):
        from unittest.mock import patch

        path = self.root / 'data.json'
        replacement = self.root / 'replacement.json'
        path.write_bytes(b'{"previous":true}')
        replacement.write_bytes(b'{"replacement":true}')
        signature = file_cache._signature
        calls = 0

        def replace_on_validation(candidate):
            nonlocal calls
            calls += 1
            if calls == 2:
                replacement.replace(path)
            return signature(candidate)

        with patch.object(file_cache, '_signature', replace_on_validation):
            self.assertEqual(file_cache.read_json(path), {'replacement': True})
        self.assertEqual(file_cache.read_json_shared(path), {'replacement': True})

    def test_unavailable_strong_signature_never_serves_cached_value(self):
        from unittest.mock import patch

        path = self.root / 'data.json'
        path.write_bytes(b'{"v":1}')
        self.assertEqual(file_cache.read_json_shared(path), {'v': 1})
        digest = file_cache.file_digest(path)
        with patch.object(file_cache, '_signature', return_value=None):
            path.write_bytes(b'{"v":2}')
            self.assertEqual(file_cache.read_json_shared(path), {'v': 2})
            self.assertNotEqual(file_cache.file_digest(path), digest)
