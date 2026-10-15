"""截图基线工具的纯逻辑（PNG 读写、差异度量）；真实抓屏是手动命令，不进自动门禁。"""
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import ui_snapshot  # noqa: E402


class UiSnapshotToolTests(unittest.TestCase):
    def test_png_round_trip(self):
        rgb = bytes((x * 7 + y * 3) % 256 for y in range(5) for x in range(12))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.png'
            ui_snapshot.write_png(path, 4, 5, rgb)
            self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(ui_snapshot.read_png(path), (4, 5, rgb))

    def test_diff_metric(self):
        self.assertEqual(ui_snapshot.mean_abs_diff(b'\x00\x00', b'\x00\x00'), 0)
        self.assertEqual(ui_snapshot.mean_abs_diff(b'\x00\x00', b'\x0a\x0a'), 10)
        self.assertEqual(ui_snapshot.mean_abs_diff(b'\x00', b'\x00\x00'), 255.0)

    def test_committed_baseline_is_a_valid_png(self):
        width, height, rgb = ui_snapshot.read_png(ui_snapshot.BASELINES / 'runtime_dialog.png')
        self.assertGreater(width, 300)
        self.assertEqual(len(rgb), width * height * 3)
        self.assertGreater(len(set(rgb[:20000])), 2)  # 不是纯色空白


if __name__ == '__main__':
    unittest.main()
