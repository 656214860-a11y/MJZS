# -*- coding: utf-8 -*-
"""媒体探测自检：判断 PNG / 取首帧尺寸只读 8~24 字节文件头，不把整帧读进内存。运行：python test_media.py"""
import base64, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import agent.media, writing

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AGN2YCkAAAAAElFTkSuQmCC")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 60
NOT_PNG = b"hello, this is not an image at all" * 4


def spy_reads(target):
    calls = []
    real_open = open

    def spy(path, *args, **kwargs):
        handle = real_open(path, *args, **kwargs)
        if os.fspath(path) == os.fspath(target):
            inner = handle.read

            def read(size=-1):
                calls.append(size)
                return inner(size)

            handle.read = read
        return handle

    return mock.patch("builtins.open", new=spy), calls


class HeaderReadTests(unittest.TestCase):
    """文件头助手要能判定、能取尺寸，而且只读文件头那点字节。"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.png = Path(self.dir.name) / "SH001.png"
        self.png.write_bytes(PNG_1X1)
        self.big = Path(self.dir.name) / "big.png"
        self.big.write_bytes(PNG_1X1 + b"\x00" * (1 << 20))  # 1MB 尾巴：旧实现会整份读进来

    def test_is_png_accepts_real_png(self):
        self.assertTrue(agent.media.is_png(self.png))

    def test_is_png_rejects_other_bytes(self):
        for blob in (JPEG, NOT_PNG, b"", PNG_1X1[:7]):
            path = Path(self.dir.name) / "other.bin"
            path.write_bytes(blob)
            self.assertFalse(agent.media.is_png(path), blob[:8])

    def test_is_png_reads_only_8_bytes(self):
        patcher, calls = spy_reads(self.big)
        with patcher:
            self.assertTrue(agent.media.is_png(self.big))
        self.assertEqual(calls, [8])

    def test_png_size_reads_ihdr_of_real_png(self):
        self.assertEqual(agent.media.png_size(self.big), (1, 1))

    def test_png_size_reads_only_24_bytes(self):
        patcher, calls = spy_reads(self.big)
        with patcher:
            self.assertEqual(agent.media.png_size(self.big), (1, 1))
        self.assertEqual(calls, [24])

    def test_png_size_honours_ihdr_values(self):
        path = Path(self.dir.name) / "sized.png"
        path.write_bytes(agent.media.PNG_SIGNATURE + b"\x00\x00\x00\rIHDR"
                         + (1280).to_bytes(4, "big") + (720).to_bytes(4, "big"))
        self.assertEqual(agent.media.png_size(path), (1280, 720))

    def test_png_size_rejects_non_png(self):
        path = Path(self.dir.name) / "not.png"
        path.write_bytes(NOT_PNG)
        with self.assertRaises(ValueError) as caught:
            agent.media.png_size(path)
        self.assertIn("PNG", str(caught.exception))

    def test_png_size_rejects_truncated_header(self):
        path = Path(self.dir.name) / "short.png"
        path.write_bytes(PNG_1X1[:8] + b"\x00" * 4)  # 只有签名，IHDR 不完整
        with self.assertRaises(ValueError) as caught:
            agent.media.png_size(path)
        self.assertIn("尺寸", str(caught.exception))

    def test_png_size_rejects_zero_dimensions(self):
        path = Path(self.dir.name) / "zero.png"
        path.write_bytes(agent.media.PNG_SIGNATURE + b"\x00" * 8 + b"\x00" * 8)
        with self.assertRaises(ValueError) as caught:
            agent.media.png_size(path)
        self.assertIn("尺寸", str(caught.exception))


class ValidateFirstFrameTests(unittest.TestCase):
    """剧本校验改用文件头判断首帧，结论与旧的整份读取保持一致。"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / "frames").mkdir()
        self.assets = {"CHAR_001": {}, "LOC_001": {}}

    def episode(self):
        return {"episode_id": "EP001", "title": "测试集", "shots": [
            {"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"],
             "location": "LOC_001", "frame": "frames/SH001.png",
             "video_prompt": "画面与对白要求", "dialogue": []}]}

    def test_real_png_first_frame_passes(self):
        (self.root / "frames" / "SH001.png").write_bytes(PNG_1X1)
        result = writing.validate_episode(self.episode(), self.root, self.assets)
        self.assertEqual(result["shot_count"], 1)

    def test_non_png_first_frame_is_rejected(self):
        (self.root / "frames" / "SH001.png").write_bytes(NOT_PNG)
        with self.assertRaises(ValueError) as caught:
            writing.validate_episode(self.episode(), self.root, self.assets)
        self.assertIn("首帧不是有效PNG", str(caught.exception))

    def test_missing_first_frame_stays_a_warning(self):
        result = writing.validate_episode(self.episode(), self.root, self.assets)
        self.assertEqual(result["shot_count"], 1)
        self.assertTrue(any("首帧尚未制作" in w for w in result["warnings"]), result["warnings"])


class PngCompleteTests(unittest.TestCase):
    """首帧批次每 1.5 秒轮询一次：只看头尾判断 PNG 是否完整，不整图读进来。"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.png = Path(self.dir.name) / "SH001.png"
        self.png.write_bytes(PNG_1X1)
        self.huge = Path(self.dir.name) / "huge.png"
        self.huge.write_bytes(PNG_1X1[:-12] + b"\x00" * (1 << 20) + PNG_1X1[-12:])

    def test_complete_png_is_accepted(self):
        self.assertTrue(agent.media.png_complete(self.png))
        self.assertTrue(agent.media.png_complete(self.huge))

    def test_truncated_png_is_rejected(self):
        path = Path(self.dir.name) / "half.png"
        path.write_bytes(PNG_1X1[:-12])
        self.assertFalse(agent.media.png_complete(path))

    def test_unfinished_png_is_rejected(self):
        path = Path(self.dir.name) / "writing.png"
        path.write_bytes(PNG_1X1 + b"\x00" * 32)
        self.assertFalse(agent.media.png_complete(path))

    def test_non_png_is_rejected(self):
        path = Path(self.dir.name) / "not.png"
        path.write_bytes(NOT_PNG)
        self.assertFalse(agent.media.png_complete(path))

    def test_tiny_and_missing_files_are_rejected(self):
        small = Path(self.dir.name) / "tiny.png"
        small.write_bytes(PNG_1X1[:8])
        self.assertFalse(agent.media.png_complete(small))
        self.assertFalse(agent.media.png_complete(Path(self.dir.name) / "missing.png"))

    def test_only_head_and_tail_are_read(self):
        patcher, calls = spy_reads(self.huge)
        with patcher:
            self.assertTrue(agent.media.png_complete(self.huge))
        self.assertEqual(calls, [8, 4])


class ImageContentOkTests(unittest.TestCase):
    """导入候选验真只读文件头尾：PNG/JPG/WEBP 各认签名与收尾，读不动或后缀不认一律 False。"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)

    def _write(self, name, blob):
        path = self.root / name
        path.write_bytes(blob)
        return path

    def test_accepts_png(self):
        self.assertTrue(agent.media.image_content_ok(self._write("ok.png", PNG_1X1)))

    def test_rejects_broken_png(self):
        truncated = self._write("half.png", PNG_1X1[:-12])
        fake = self._write("fake.png", NOT_PNG)
        self.assertFalse(agent.media.image_content_ok(truncated))
        self.assertFalse(agent.media.image_content_ok(fake))

    def test_accepts_jpg(self):
        blob = b"\xff\xd8\xff\xe0" + b"\x00" * 60 + b"\xff\xd9"
        self.assertTrue(agent.media.image_content_ok(self._write("ok.jpg", blob)))

    def test_rejects_broken_jpg(self):
        self.assertFalse(agent.media.image_content_ok(self._write("half.jpg", JPEG)))

    def test_accepts_webp(self):
        blob = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 16
        self.assertTrue(agent.media.image_content_ok(self._write("ok.webp", blob)))

    def test_rejects_broken_webp(self):
        blob = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 16
        self.assertFalse(agent.media.image_content_ok(self._write("wave.webp", blob)))

    def test_rejects_other_suffix(self):
        self.assertFalse(agent.media.image_content_ok(self._write("ok.gif", PNG_1X1)))

    def test_returns_false_on_oserror(self):
        path = self._write("ok.png", PNG_1X1)
        with mock.patch("builtins.open", side_effect=OSError("denied")):
            self.assertFalse(agent.media.image_content_ok(path))
        self.assertFalse(agent.media.image_content_ok(self.root / "missing.png"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
