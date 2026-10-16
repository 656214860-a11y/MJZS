# -*- coding: utf-8 -*-
"""O10：大媒体发布必须按块复制，峰值内存不随文件大小增长。"""
import hashlib
import tempfile
import tracemalloc
import unittest
from pathlib import Path

from agent.core import save_file
from stage_execution_service import collect_download_inbox, register_download_inbox


SIZE = 16 * 1024 * 1024
PEAK_LIMIT = 5 * 1024 * 1024


def _payload(size=SIZE):
    block = bytes(range(256)) * 4096                      # 1 MiB 周期块，便于核对内容
    return block * (size // len(block)) + block[: size % len(block)]


class StreamingPublishTests(unittest.TestCase):
    def test_save_file_does_not_materialize_media(self):
        data = _payload()
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.mp4"; source.write_bytes(data)
            target = Path(td) / "项目" / "C01.mp4"
            tracemalloc.start()
            digest = save_file(target, source)
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())
            self.assertEqual(target.stat().st_size, len(data))
            self.assertEqual(target.read_bytes(), data)
            self.assertLess(peak, PEAK_LIMIT, "复制 %d 字节时峰值内存 %d 字节" % (len(data), peak))

    def test_digest_mismatch_keeps_previous_target(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.mp4"; source.write_bytes(b"new-payload")
            target = Path(td) / "C01.mp4"; target.write_bytes(b"old")
            with self.assertRaises(ValueError):
                save_file(target, source, digest="0" * 64)
            self.assertEqual(target.read_bytes(), b"old")

    def test_download_inbox_collects_large_media_without_buffering(self):
        data = _payload()
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "项目"; project.mkdir()
            downloads = Path(td) / "下载"; downloads.mkdir()
            target = project / "07视频生成" / "SH001.mp4"
            register_download_inbox(project, "输出：" + str(target))
            (downloads / "SH001.mp4").write_bytes(data)
            tracemalloc.start()
            done = collect_download_inbox(project, downloads=downloads)
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(done, [target])
            self.assertEqual(target.stat().st_size, len(data))
            self.assertLess(peak, PEAK_LIMIT, "收回 %d 字节时峰值内存 %d 字节" % (len(data), peak))


if __name__ == "__main__":
    unittest.main(verbosity=2)
