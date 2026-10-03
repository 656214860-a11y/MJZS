# -*- coding: utf-8 -*-
"""资产缩略图（第 52 期第 3 条）：读文件头算抽点倍数、缓存复用、Tk 解不开就退回文字。

Round 1 起多两条路：磁盘缓存（private/缩略图）与后台解码进程。用例跟着改口径——
界面线程那一拍不再整张解图，先在页面上摆一个**同尺寸的空盒子**；后台进程把图解好、写进
磁盘缓存，界面线程那一拍（update）再把真图**就地贴进**这个盒子。下面这几条盯住新口径：
那一拍绝不整张解图、盒子的尺寸与成品严丝合缝、落地之后像素真的贴进了盒子、小图落在磁盘上、
第二次打开当拍就有图、后台进程不可用时也绝不在当前 UI 拍同步解。

运行：python test_asset_thumbs.py
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import os, struct, sys, tempfile, time, unittest, zlib
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import asset_thumbs


def png(width, height, color=(10, 20, 30)):
    """造一张真能解码的 PNG（纯标准库，写法与程序里那套一致）。"""
    raw = b"\x00" + bytes(color) * width
    raw = raw * height

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    return (asset_thumbs.PNG_MAGIC
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def colors(image, count=4):
    """抽几个点的颜色：判「盒子里的像素是不是真贴进去了」。"""
    width, height = int(image.width()), int(image.height())
    out = []
    for index in range(count):
        x = min(width - 1, index * max(1, width // count))
        y = min(height - 1, index * max(1, height // count))
        out.append(tuple(image.get(x, y)))
    return out


PICTURE = [(10, 20, 30)] * 4


class SizeTests(unittest.TestCase):
    def test_png_size_reads_the_header(self):
        self.assertEqual(asset_thumbs.png_size(png(600, 400)), (600, 400))

    def test_something_that_is_not_a_picture_has_no_size(self):
        self.assertIsNone(asset_thumbs.png_size(asset_thumbs.PNG_MAGIC))
        self.assertIsNone(asset_thumbs.png_size(b"not an image at all"))
        self.assertIsNone(asset_thumbs.gif_size(asset_thumbs.PNG_MAGIC))

    def test_gif_size_reads_the_logical_screen(self):
        head = b"GIF89a" + struct.pack("<HH", 320, 240) + b"\x00" * 4
        self.assertEqual(asset_thumbs.gif_size(head), (320, 240))

    def test_image_size_needs_a_readable_file(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "a.png"; good.write_bytes(png(64, 32))
            self.assertEqual(asset_thumbs.image_size(good), (64, 32))
            self.assertIsNone(asset_thumbs.image_size(Path(td) / "没这个文件.png"))
            bad = Path(td) / "b.png"; bad.write_bytes(asset_thumbs.PNG_MAGIC)
            self.assertIsNone(asset_thumbs.image_size(bad))

    def test_factor_never_enlarges_and_never_passes_the_target(self):
        self.assertEqual(asset_thumbs.factor(1000, 500, 72), 14)
        self.assertEqual(asset_thumbs.factor(71, 70, 72), 1, "比目标还小的图不许放大")
        self.assertEqual(asset_thumbs.factor(72, 72, 72), 1, "正好等于目标也不缩")
        self.assertEqual(asset_thumbs.factor(73, 73, 72), 2, "超一点就抽一半")
        self.assertEqual(asset_thumbs.factor(0, 0, 72), 1)

    def test_the_empty_box_is_exactly_as_big_as_the_finished_thumbnail(self):
        """Round 1：空盒子按 subsample 的**向上取整**算（400/6 → 67，不是 66），差一格就露边。"""
        with tempfile.TemporaryDirectory() as td:
            big = Path(td) / "big.png"; big.write_bytes(png(400, 200))
            self.assertEqual(asset_thumbs.placeholder_size(big, 72), (67, 34))
            square = Path(td) / "square.png"; square.write_bytes(png(1024, 1024))
            self.assertEqual(asset_thumbs.placeholder_size(square, 36), (36, 36))
            small = Path(td) / "small.png"; small.write_bytes(png(30, 20))
            self.assertEqual(asset_thumbs.placeholder_size(small, 72), (30, 20),
                             "比目标还小的图不缩，盒子就是原尺寸")

    def test_no_size_no_box(self):
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "broken.png"; broken.write_bytes(asset_thumbs.PNG_MAGIC)
            self.assertIsNone(asset_thumbs.placeholder_size(broken), "读不出尺寸就不摆盒子")
            self.assertIsNone(asset_thumbs.placeholder_size(Path(td) / "没有.png"))


class QueueLimitTests(unittest.TestCase):
    def test_full_background_queue_defers_without_starting_another_job(self):
        original_limit = asset_thumbs.QUEUE_LIMIT
        original_pending = dict(asset_thumbs._PENDING)
        self.addCleanup(setattr, asset_thumbs, 'QUEUE_LIMIT', original_limit)
        self.addCleanup(lambda: (asset_thumbs._PENDING.clear(),
                                 asset_thumbs._PENDING.update(original_pending)))
        asset_thumbs.QUEUE_LIMIT = 1
        asset_thumbs._PENDING['already-queued'] = {'path': Path('one.png')}
        result = asset_thumbs.request(None, ('root', 'new'), Path('new.png'), 36, 1, 'new-token')
        self.assertIsNone(result)
        self.assertEqual(set(asset_thumbs._PENDING), {'already-queued'})


class ThumbnailTests(unittest.TestCase):
    """Round 1 的口径：这一拍只登记任务 ＋ 摆一个空盒子，图由后台进程造好、落地之后贴上。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk(); self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / "cache"          # 自检不碰真缓存那本账
        self.root = Path(self.tmp.name) / "images"; self.root.mkdir()
        original = asset_thumbs.CACHE_ROOT
        asset_thumbs.CACHE_ROOT = self.cache
        asset_thumbs.forget()
        asset_thumbs.reset_worker()                         # 换了缓存目录，后台进程按新的起
        self.addCleanup(setattr, asset_thumbs, "CACHE_ROOT", original)

    def test_result_poll_checks_a_bounded_batch_of_pending_jobs(self):
        """长列表滚动时，单个 Tk tick 不能为全部待处理缩略图反复做磁盘检查。"""
        old_limit = asset_thumbs.RESULTS_PER_TICK
        old_load = asset_thumbs._load_cached
        old_worker = asset_thumbs._WORKER
        old_cursor = asset_thumbs._PENDING_CURSOR
        self.addCleanup(setattr, asset_thumbs, "RESULTS_PER_TICK", old_limit)
        self.addCleanup(setattr, asset_thumbs, "_load_cached", old_load)
        self.addCleanup(setattr, asset_thumbs, "_WORKER", old_worker)
        self.addCleanup(setattr, asset_thumbs, "_PENDING_CURSOR", old_cursor)
        asset_thumbs.forget()
        asset_thumbs.RESULTS_PER_TICK = 2
        calls = []

        class Worker:
            def poll(self):
                return None

        asset_thumbs._WORKER = Worker()
        for token in ("one", "two", "three"):
            asset_thumbs._PENDING[token] = {
                "master": self.win, "path": self.root / (token + ".png"),
                "size": 36, "stamp": 1, "key": ("root", token), "at": time.monotonic(),
            }

        def miss(master, token):
            calls.append(token)
            return "miss", None

        asset_thumbs._load_cached = miss
        asset_thumbs.update(self.win)
        self.assertEqual(len(calls), 2, "一次结果轮询只允许检查固定上限的 pending 项")
        self.addCleanup(asset_thumbs.forget)
        self.addCleanup(asset_thumbs.reset_worker)

    def write(self, name, data):
        path = self.root / name; path.write_bytes(data)
        return path

    def grab(self, path, size=72):
        """取这一格的图：先登记（当拍拿到一个空盒子），等落地之后再取一次真的。"""
        image = asset_thumbs.thumbnail(self.win, path, size)
        if asset_thumbs.pending():
            self.assertTrue(asset_thumbs.settle(self.win, seconds=60), "后台任务没能落地")
            image = asset_thumbs.thumbnail(self.win, path, size)
        return image

    def cached_pngs(self):
        return sorted(self.cache.glob("*.png"))

    def test_the_ui_thread_hands_the_decoding_to_the_background_process(self):
        """这一拍不许整张解图：把 build() 换成会炸的，照样交出任务与空盒子。"""
        path = self.write("big.png", png(400, 200))
        real = asset_thumbs.build

        def boom(*args, **kwargs):
            raise AssertionError("界面线程上不该整张解图")

        asset_thumbs.build = boom
        self.addCleanup(setattr, asset_thumbs, "build", real)
        box = asset_thumbs.thumbnail(self.win, path, 72)
        self.assertEqual(asset_thumbs.pending(), 1, "任务已经交给后台进程")
        self.assertIsNotNone(asset_thumbs._WORKER, "后台进程起来了")
        self.assertIsNotNone(box, "这一拍先摆一个空盒子，页面不必等图")
        self.assertEqual((box.width(), box.height()), (67, 34), "盒子与成品严丝合缝")
        asset_thumbs.build = real
        self.assertTrue(asset_thumbs.settle(self.win, seconds=60))
        self.assertEqual(colors(box), PICTURE, "落地之后真图贴进了页面上那个盒子")

    def test_the_finished_thumbnail_is_painted_into_the_box_on_the_page(self):
        """正题：页面上先摆的那个盒子，落地之后必须真被贴上——不然用户永远看白框。"""
        path = self.write("big.png", png(400, 200))
        box = asset_thumbs.thumbnail(self.win, path, 72)
        self.assertIsNotNone(box)
        self.assertNotEqual(colors(box), PICTURE, "还没造好的时候盒子里不是那张图")
        self.assertTrue(asset_thumbs.settle(self.win, seconds=60))
        self.assertEqual(colors(box), PICTURE, "图到了原地贴上，页面一行都不用改")

    def test_a_big_png_comes_back_as_a_small_thumbnail(self):
        path = self.write("big.png", png(400, 200))
        image = self.grab(path)
        self.assertIsNotNone(image)
        self.assertLessEqual(max(image.width(), image.height()), 72, "长边不超过 72")
        self.assertGreaterEqual(max(image.width(), image.height()), 36, "也别缩成一小点")
        self.assertAlmostEqual(image.width() / image.height(), 2.0, delta=0.15, msg="比例别走样")

    def test_a_small_png_is_not_enlarged(self):
        path = self.write("small.png", png(30, 20))
        image = self.grab(path)
        self.assertEqual((image.width(), image.height()), (30, 20))

    def test_the_second_open_reads_the_disk_cache_without_waiting(self):
        """Round 1 的正题：造好的小图落在磁盘上，内存清掉之后再开一次，当拍就出图。"""
        path = self.write("big.png", png(400, 200))
        first = self.grab(path)
        self.assertIsNotNone(first)
        self.assertEqual(len(self.cached_pngs()), 1, "小图落进了磁盘缓存")
        asset_thumbs.forget()                              # 只清内存，磁盘那一份留着
        started = time.perf_counter()
        again = asset_thumbs.thumbnail(self.win, path, 72)
        spent = (time.perf_counter() - started) * 1000
        self.assertIsNotNone(again, "第二次打开当拍就有图（不用等后台）")
        self.assertEqual(asset_thumbs.pending(), 0, "磁盘命中的不该再排队")
        self.assertEqual((again.width(), again.height()), (first.width(), first.height()))
        self.assertEqual(colors(again), PICTURE, "从磁盘读回来的就是那张小图")
        self.assertLess(spent, 100, "读一张小图不该拖住界面（实测 %.1f ms）" % spent)

    def test_without_a_background_process_the_ui_beat_does_not_decode_a_large_picture(self):
        """后台不可用时，Tk 当前拍不能同步解整图；页面先保留文字，避免可见卡顿。"""
        asset_thumbs._WORKER_BAD = True                    # 就当这一趟会话里它已经不可用
        path = self.write("big.png", png(400, 200))
        with mock.patch.object(asset_thumbs, '_build_here', side_effect=AssertionError('不应在 UI 线程解码')):
            image = asset_thumbs.thumbnail(self.win, path, 72)
        self.assertIsNone(image, "后台不可用时先保留文字，避免阻塞当前 UI 回调")
        self.assertEqual(asset_thumbs.pending(), 0, "没有后台进程就不排队")
        self.assertEqual(len(self.cached_pngs()), 0, "UI 当前拍不应同步写出缩略图缓存")

    def test_the_same_picture_is_only_built_once(self):
        path = self.write("same.png", png(200, 100))
        first = self.grab(path)
        self.assertIs(first, asset_thumbs.thumbnail(self.win, path, 72), "同一张图只造一次")
        os.utime(path, (0, 0))                    # 换了改动时间，缓存就该作废
        second = asset_thumbs.thumbnail(self.win, path, 72)
        self.assertIsNot(first, second, "换过的图要重新造")
        self.assertEqual(asset_thumbs.pending(), 1, "换了时间戳就重新排一条任务")

    def test_the_least_recently_used_thumbnail_is_dropped_first(self):
        """第 64 期任务 8：挤掉的必须是「最久没看的」，不是「最早造的」。

        先进先出会把天天在看的那几张挤出去（再看又得整张解码），这一条盯住这一点：
        把 a 重新看一遍之后，再来的新图应该挤掉 b，a 留着。
        """
        original = asset_thumbs.LIMIT
        asset_thumbs.LIMIT = 2
        self.addCleanup(setattr, asset_thumbs, "LIMIT", original)
        names = ("a.png", "b.png", "c.png")
        a_path, b_path, c_path = [self.write(name, png(60, 40)) for name in names]
        a = self.grab(a_path)
        b = self.grab(b_path)
        self.assertIs(a, asset_thumbs.thumbnail(self.win, a_path, 72), "再看一遍算「刚用过」")
        c = self.grab(c_path)                     # 满了，该挤掉最久没看的
        self.assertIs(a, asset_thumbs.thumbnail(self.win, a_path, 72), "刚看过的 a 还在")
        self.assertIs(c, asset_thumbs.thumbnail(self.win, c_path, 72), "新来的 c 也在")
        self.assertIsNot(b, asset_thumbs.thumbnail(self.win, b_path, 72), "最久没看的 b 被挤掉了")

    def test_what_tk_cannot_read_falls_back_to_nothing(self):
        broken = self.write("broken.png", asset_thumbs.PNG_MAGIC)
        self.assertIsNone(self.grab(broken), "解不开就没图可给（盒子也摆不出来）")
        self.assertIsNone(self.grab(Path(self.tmp.name) / "没有.png"))
        self.assertEqual(len(sorted(self.cache.glob("*.none"))), 1, "解不开的那一张落一份记号")
        self.assertEqual(asset_thumbs.pending(), 0, "记过号之后不再反复去试")

    def test_forget_cancels_the_pending_interface_timer(self):
        path = self.write("timer.png", png(60, 40))
        asset_thumbs.thumbnail(self.win, path, 72)
        self.assertIsNotNone(asset_thumbs._PUMP_ID, "有后台任务时应登记轮询定时器")
        asset_thumbs.forget()
        self.assertIsNone(asset_thumbs._PUMP_ID, "清理缓存时必须取消轮询定时器")

    def test_destroy_cleanup_cancels_the_pending_interface_timer(self):
        path = self.write("destroy-timer.png", png(60, 40))
        asset_thumbs.thumbnail(self.win, path, 72)
        self.assertIsNotNone(asset_thumbs._PUMP_ID)
        self.assertTrue(getattr(self.win, '_asset_thumbs_pump_cleanup_bound', False))
        asset_thumbs._disarm(self.win)
        self.assertIsNone(asset_thumbs._PUMP_ID,
                          "窗口销毁前必须取消缩略图轮询，不能留下 Tcl lambda")

    def test_thumbnail_worker_does_not_inherit_model_credentials(self):
        """纯图片缓存子进程没有调用模型的理由，不能拿到父进程里的 Key。"""
        original = asset_thumbs.subprocess.Popen
        captured = {}

        class Process:
            def poll(self):
                return None

        def start(*args, **kwargs):
            captured.update(kwargs.get('env') or {})
            return Process()

        asset_thumbs.subprocess.Popen = start
        self.addCleanup(setattr, asset_thumbs.subprocess, 'Popen', original)
        old = os.environ.get('DEEPSEEK_API_KEY')
        os.environ['DEEPSEEK_API_KEY'] = 'must-not-reach-thumbnail-worker'
        self.addCleanup(lambda: os.environ.pop('DEEPSEEK_API_KEY', None) if old is None
                        else os.environ.__setitem__('DEEPSEEK_API_KEY', old))
        asset_thumbs.reset_worker()
        self.assertTrue(asset_thumbs._ensure_worker())
        self.assertNotIn('DEEPSEEK_API_KEY', captured)


if __name__ == "__main__":
    unittest.main(verbosity=2)
