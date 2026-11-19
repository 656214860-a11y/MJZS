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
import json, os, struct, subprocess, sys, tempfile, time, unittest, zlib
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


class WorkerResetTests(unittest.TestCase):
    """收后台进程时不许把「没收掉」吞掉：先 terminate，再 kill，实在收不掉要报出来。"""

    def setUp(self):
        self.original = (asset_thumbs._WORKER, asset_thumbs._WORKER_AT, asset_thumbs._WORKER_BAD)
        self.addCleanup(self.restore)

    def restore(self):
        asset_thumbs._WORKER, asset_thumbs._WORKER_AT, asset_thumbs._WORKER_BAD = self.original

    def test_reset_worker_kills_and_reaps_a_worker_that_ignores_terminate(self):
        class Stubborn:
            def __init__(self):
                self.killed = False
                self.waits = 0

            def terminate(self):
                pass

            def poll(self):
                return None

            def kill(self):
                self.killed = True

            def wait(self, timeout=None):
                self.waits += 1
                if self.waits == 1:
                    raise subprocess.TimeoutExpired('worker', timeout)
                return 0

        worker = Stubborn()
        asset_thumbs._WORKER = worker
        self.assertTrue(asset_thumbs.reset_worker(), '收掉进程后必须返回成功')
        self.assertTrue(worker.killed, 'terminate 等不到退出就要升级到 kill')
        self.assertIsNone(asset_thumbs._WORKER)

    def test_reset_worker_reports_when_the_process_cannot_be_reaped(self):
        class Unreapable:
            def terminate(self):
                pass

            def poll(self):
                return None

            def kill(self):
                pass

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired('worker', timeout)

        asset_thumbs._WORKER = Unreapable()
        with self.assertLogs('asset_thumbs', level='WARNING') as logs:
            self.assertFalse(asset_thumbs.reset_worker(), '收不掉必须让调用方知道')
        self.assertTrue(any('未能在' in line for line in logs.output), logs.output)
        self.assertIsNone(asset_thumbs._WORKER)


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
        # 收尾口（addCleanup 后进先出，故注册在 CACHE_ROOT 还原之后、TemporaryDirectory 清目录之前）：
        # 先撤下本拍待收任务、取消轮询定时器，再 terminate+wait 收掉后台进程。否则后台进程可能仍按着
        # cache/jobs/*.json 在读，临时目录清理会撞上 WinError 32「另一个程序正在使用此文件」。
        self.addCleanup(asset_thumbs.reset_worker)
        self.addCleanup(asset_thumbs.forget)

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
        from env_test_support import patched_env
        patched_env(self, DEEPSEEK_API_KEY='must-not-reach-thumbnail-worker')
        asset_thumbs.reset_worker()
        self.assertTrue(asset_thumbs._ensure_worker())
        self.assertNotIn('DEEPSEEK_API_KEY', captured)


class MediaThumbTests(unittest.TestCase):
    """任务书 M4：视频封面帧／音频波形——缓存命中、失效、ffmpeg 缺失、旁路记录、真 Tk 几何。"""

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
        self.cache = Path(self.tmp.name) / "cache"; self.cache.mkdir()
        self.root = Path(self.tmp.name) / "media"; self.root.mkdir()
        original = asset_thumbs.CACHE_ROOT
        asset_thumbs.CACHE_ROOT = self.cache
        asset_thumbs.forget()
        asset_thumbs.reset_worker()
        self.addCleanup(setattr, asset_thumbs, "CACHE_ROOT", original)
        self.addCleanup(asset_thumbs.reset_worker)
        self.addCleanup(asset_thumbs.forget)

    def media(self, name):
        path = self.root / name; path.write_bytes(b'fake-media-bytes')
        return path

    def token(self, path, size=72):
        return asset_thumbs.cache_key(path, asset_thumbs.file_stamp(path), size)

    def no_real_worker(self):
        """本组用例手工扮演后台进程：不让真 worker 抢跑 jobs 目录。"""
        original = asset_thumbs._ensure_worker
        asset_thumbs._ensure_worker = lambda: True
        self.addCleanup(setattr, asset_thumbs, "_ensure_worker", original)

    def test_media_kind_uses_file_index_suffixes(self):
        self.assertEqual(asset_thumbs.media_kind(self.media('clip.mp4')), 'video')
        self.assertEqual(asset_thumbs.media_kind(self.media('voice.mp3')), 'audio')
        self.assertIsNone(asset_thumbs.media_kind(self.media('cover.png')))
        self.assertIsNone(asset_thumbs.media_kind(self.media('notes.md')))

    def test_media_geometry_is_the_fixed_canvas_ffmpeg_produces(self):
        self.assertEqual(asset_thumbs.media_geometry('video', 72), (72, round(72 * 9 / 16)))
        self.assertEqual(asset_thumbs.media_geometry('audio', 72), (72, 72 // 3))
        width, height = asset_thumbs.media_geometry('video', 36)
        self.assertEqual((width, height), (36, round(36 * 9 / 16)))

    def test_file_stamp_changes_on_size_or_mtime(self):
        path = self.media('clip.mp4')
        first = asset_thumbs.file_stamp(path)
        path.write_bytes(b'fake-media-bytes-more')
        self.assertNotEqual(first, asset_thumbs.file_stamp(path), '大小变了签名要变')
        second = asset_thumbs.file_stamp(path)
        os.utime(path, (0, 0))
        self.assertNotEqual(second, asset_thumbs.file_stamp(path), 'mtime 变了签名也要变')

    def test_media_thumbnail_miss_queues_job_and_puts_an_empty_box(self):
        self.no_real_worker()
        clip = self.media('clip.mp4')
        box = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertIsNotNone(box)
        self.assertEqual(asset_thumbs.pending(), 1, '媒体任务登记进后台队列')
        self.assertEqual((box.width(), box.height()), asset_thumbs.media_geometry('video', 72))
        token = self.token(clip)
        spec = asset_thumbs.read_json(self.cache / 'jobs' / (token + '.json'))
        self.assertEqual(spec['kind'], 'video', '任务要带媒体类型给后台分流')
        self.assertIn('ffmpeg', spec, '显式配置透传字段要在任务里（可为空串）')
        self.assertIn('ffprobe', spec)

    def test_media_cover_lands_in_the_box_in_place(self):
        """后台把封面写进磁盘缓存后，界面上那个空盒就地贴上真图。"""
        self.no_real_worker()
        clip = self.media('clip.mp4')
        box = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertNotEqual(colors(box), PICTURE, '还没造好时是空盒')
        asset_thumbs.save_bytes(asset_thumbs.cache_file(self.token(clip)),
                                png(*asset_thumbs.media_geometry('video', 72)))
        asset_thumbs.update(self.win)
        self.assertEqual(asset_thumbs.pending(), 0)
        self.assertEqual(colors(box), PICTURE, '封面到了就贴进同一个盒子')

    def test_second_read_hits_cache_without_ffmpeg(self):
        """二次读取命中磁盘缓存、不排队不调用 ffmpeg（任务书 M4 验收）。"""
        clip = self.media('clip.mp4')
        asset_thumbs.save_bytes(asset_thumbs.cache_file(self.token(clip)), png(72, 40))
        image = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertIsNotNone(image)
        self.assertEqual(asset_thumbs.pending(), 0, '缓存命中不该再排任务')
        asset_thumbs.forget()
        again = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertIsNotNone(again, '内存清掉后磁盘缓存当拍出图')
        self.assertEqual(asset_thumbs.pending(), 0)

    def test_replaced_file_requests_a_fresh_cover(self):
        """文件被替换（mtime 或大小变化）后重新排队生成（任务书 M4 验收）。"""
        self.no_real_worker()
        clip = self.media('clip.mp4')
        asset_thumbs.media_thumbnail(self.win, clip, 72)
        old = self.token(clip)
        clip.write_bytes(b'replaced-media')
        asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertNotEqual(old, self.token(clip), '内容变了要换一个缓存键')
        self.assertEqual(asset_thumbs.pending(), 2, '新旧键各排一条')

    def test_missing_ffmpeg_writes_blank_and_shows_placeholder(self):
        """ffmpeg 缺失：后台落 .none 记号，界面给占位图不阻断（任务书 M4 验收）。"""
        clip = self.media('clip.mp4')
        token = self.token(clip)
        real = asset_thumbs.tool_path
        asset_thumbs.tool_path = lambda *args, **kwargs: None
        self.addCleanup(setattr, asset_thumbs, "tool_path", real)
        asset_thumbs._media_job(clip, 72, token, 'video', {})
        self.assertTrue(asset_thumbs.blank_mark(token).is_file(), 'ffmpeg 缺失落 .none 记号')
        image = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertIsNotNone(image, '损坏／缺 ffmpeg 也要给占位图，不让列表留白')
        self.assertEqual((image.width(), image.height()), asset_thumbs.media_geometry('video', 72))

    def test_worker_media_writes_cover_and_info_sidecar(self):
        """后台媒体任务：封面 PNG 与时长／分辨率旁路记录同键落盘（任务书 M4）。"""
        clip = self.media('clip.mp4')
        token = self.token(clip)
        info_json = json.dumps({'streams': [{'width': 1920, 'height': 1080}],
                                'format': {'duration': '12.345'}}).encode()
        cover = png(*asset_thumbs.media_geometry('video', 72))

        def fake_run(args, **_kwargs):
            if 'ffprobe' in str(args[0]):
                return subprocess.CompletedProcess(args, 0, stdout=info_json, stderr=b'')
            return subprocess.CompletedProcess(args, 0, stdout=cover, stderr=b'')

        self.addCleanup(setattr, asset_thumbs, "tool_path",
                        asset_thumbs.tool_path)
        asset_thumbs.tool_path = lambda name, **kw: 'D:/fake/' + name
        self.addCleanup(setattr, asset_thumbs, "run_process", asset_thumbs.run_process)
        asset_thumbs.run_process = fake_run
        asset_thumbs._media_job(clip, 72, token, 'video', {})
        self.assertTrue(asset_thumbs.cache_file(token).is_file(), '封面落进磁盘缓存')
        self.assertEqual(asset_thumbs.media_info(clip, 72),
                         {'width': 1920, 'height': 1080, 'duration': 12.345},
                         '时长与分辨率由旁路记录提供')

    def test_damaged_media_writes_blank_and_placeholder_shows(self):
        """文件损坏：ffmpeg 出不了图时落 .none，界面给占位图（任务书 M4 验收）。"""
        clip = self.media('clip.mp4')
        token = self.token(clip)

        def failing_run(args, **_kwargs):
            return subprocess.CompletedProcess(args, 1, stdout=b'', stderr=b'error')

        self.addCleanup(setattr, asset_thumbs, "tool_path", asset_thumbs.tool_path)
        asset_thumbs.tool_path = lambda name, **kw: 'D:/fake/' + name
        self.addCleanup(setattr, asset_thumbs, "run_process", asset_thumbs.run_process)
        asset_thumbs.run_process = failing_run
        asset_thumbs._media_job(clip, 72, token, 'video', {})
        self.assertTrue(asset_thumbs.blank_mark(token).is_file())
        image = asset_thumbs.media_thumbnail(self.win, clip, 72)
        self.assertIsNotNone(image, '损坏文件也要给占位图')

    def test_deadline_lands_placeholder_and_late_cover_still_replaces(self):
        """后台超时：先落占位图、任务继续等；封面迟到仍原位贴上真图。"""
        self.no_real_worker()

        class LiveWorker:
            def poll(self):
                return None

        old_worker = asset_thumbs._WORKER
        asset_thumbs._WORKER = LiveWorker()             # worker 活着只是慢：任务继续等
        self.addCleanup(setattr, asset_thumbs, "_WORKER", old_worker)
        clip = self.media('clip.mp4')
        box = asset_thumbs.media_thumbnail(self.win, clip, 72)
        token = self.token(clip)
        asset_thumbs._PENDING[token]['at'] = time.monotonic() - asset_thumbs.JOB_DEADLINE - 1
        asset_thumbs.update(self.win)
        self.assertEqual(asset_thumbs.pending(), 1, '媒体任务不在界面线程做 ffmpeg，继续等后台')
        self.assertNotEqual(colors(box), PICTURE, '占位图不是封面内容')
        asset_thumbs.save_bytes(asset_thumbs.cache_file(token),
                                png(*asset_thumbs.media_geometry('video', 72)))
        asset_thumbs.update(self.win)
        self.assertEqual(asset_thumbs.pending(), 0)
        self.assertEqual(colors(box), PICTURE, '迟到的封面仍就地贴上')

    def test_prefetch_media_only_queues_media_files(self):
        self.no_real_worker()
        clip = self.media('clip.mp4'); voice = self.media('voice.mp3')
        self.media('notes.md'); self.media('cover.png')
        with mock.patch.object(asset_thumbs._prefetch, 'schedule',
                               return_value=True) as schedule:
            count = asset_thumbs.prefetch_media(self.win, sorted(self.root.iterdir()))
        self.assertEqual(count, 2, '只有视频／音频进队列')
        self.assertEqual(asset_thumbs.pending(), 2)
        schedule.assert_called_once()          # I22：媒体文件另投一条 io 池暖缓存任务


if __name__ == "__main__":
    unittest.main(verbosity=2)
