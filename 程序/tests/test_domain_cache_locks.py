# -*- coding: utf-8 -*-
"""L2 领域服务层优化任务书轮 3（修复轮）：三个 L2 模块级缓存的并发加锁回归。

覆盖 ``domain.white_model_service`` 六个模块级缓存、``domain.idea_transcript``
的 ``_history_cache``、``domain.video_task_state`` 的 ``_OTHER_ACTIVE``：
多线程并发「写入/命中」与「清空/淘汰」混合操作，不得出现 KeyError／IndexError
等异常；缓存不变量（命中返回类型正确、清空后可重建、有界不超限）保持成立。

竞态窗口用「让出 GIL 的测试替身」确定性放大：dict／list／OrderedDict 子类
在临界区间 ``time.sleep``（会释放 GIL），加锁前对端清空／淘汰必然插入，
加锁后对端操作被同一把锁挡住，故先红后绿。
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.core import save as _core_save
from agent.core import save_text as _core_save_text
from contract.project_context import ProjectContext
from domain import idea_transcript, video_task_state
from domain import white_model_service as wm

_TRAP_SECONDS = 0.0005
_WHITE_MODEL_CACHES = ('_BLENDER_CACHE', '_WORKSPACE_CACHE', '_BASE_CACHE',
                       '_DIR_CACHE', '_SETTINGS_CACHE', '_VERSION_CACHE')


class _TrapContainsDict(dict):
    """``key in cache`` 判定命中后先让出 GIL，放大「判定→取值」竞态窗口。"""

    def __contains__(self, key):
        found = dict.__contains__(self, key)
        if found:
            time.sleep(_TRAP_SECONDS)
        return found


class _TrapBoolList(list):
    """``if cache`` 真值判定后先让出 GIL，放大「判空→取首元素」竞态窗口。"""

    def __bool__(self):
        result = list.__len__(self) > 0
        if result:
            time.sleep(_TRAP_SECONDS)
        return result


class _TrapSetDict(dict):
    """写入完成后先让出 GIL，放大「写入→回读校验」竞态窗口。"""

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        time.sleep(_TRAP_SECONDS)


class _TrapHistoryCache(OrderedDict):
    """``move_to_end``／``popitem`` 执行前先让出 GIL，放大「命中→置顶／淘汰」窗口。"""

    def move_to_end(self, key, last=True):
        time.sleep(_TRAP_SECONDS)
        return super().move_to_end(key, last)

    def popitem(self, last=True):
        time.sleep(_TRAP_SECONDS)
        return super().popitem(last=last)


class _Race:
    """收集 worker 异常：任何线程抛错都记进 errors，主线程统一断言。"""

    def __init__(self):
        self.errors = []
        self._lock = threading.Lock()

    def worker(self, fn, *args):
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001 - 并发回归要收集一切异常
            with self._lock:
                if len(self.errors) < 50:
                    self.errors.append('%s: %r' % (threading.current_thread().name, exc))

    def spawn(self, targets):
        threads = [threading.Thread(target=self.worker, args=(fn,), name='race-%d' % i,
                                    daemon=True)
                   for i, fn in enumerate(targets)]
        for thread in threads:
            thread.start()
        return threads

    def join(self, threads, timeout=60):
        for thread in threads:
            thread.join(timeout)
        alive = [thread.name for thread in threads if thread.is_alive()]
        self.assert_no_errors()
        if alive:
            raise AssertionError('并发用例线程未在限期内结束：%r' % alive)

    def assert_no_errors(self):
        if self.errors:
            raise AssertionError('并发操作抛出异常（%d 条）：\n%s'
                                 % (len(self.errors), '\n'.join(self.errors[:10])))


def _project_context(root):
    """最小 ProjectContext：L2 只校验类型并取 ``.root``，阶段解析器本用例用不到。"""
    root = Path(root)
    return ProjectContext.snapshot(root, lambda stage: root / stage)


def _chat_gateway():
    """idea_transcript 的最小注入网关：读 JSON + 原子发布（与 idea_chat_gateway 同口径）。"""
    return {'read_json': lambda path: json.loads(Path(path).read_text(encoding='utf-8')),
            'publish_json': _core_save,
            'publish_text': _core_save_text}


class WhiteModelCacheLockTests(unittest.TestCase):
    """``white_model_service`` 六个模块级缓存：并发读写 × ``_reset_caches`` 清空。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'proj'
        self.ws = self.root / 'ws'
        self.blender_exe = self.root / 'blender.exe'
        self.blender_exe.write_bytes(b'MZ-fake')
        settings = self.root / 'cfg' / 'white_model_settings.json'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({'workspace': str(self.ws)}), encoding='utf-8')
        env = {'LOCALAPPDATA': str(self.root / 'local'),
               'MANJU_WHITE_MODEL_SETTINGS': str(settings),
               'MANJU_WHITE_MODEL_WORKSPACE': str(self.ws),
               'MANJU_BLENDER_EXE': str(self.blender_exe)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ctx = _project_context(self.project)
        self.exe_pool = [Path('X:/Blender/blender_%d.exe' % i) for i in range(30)]
        self.sids = ['SHOT%03d' % i for i in range(12)]
        self._saved = {name: getattr(wm, name) for name in _WHITE_MODEL_CACHES}
        wm._BLENDER_CACHE = _TrapBoolList()
        for name in _WHITE_MODEL_CACHES[1:]:
            setattr(wm, name, _TrapContainsDict())

        def restore():
            for name, value in self._saved.items():
                setattr(wm, name, value)
        self.addCleanup(restore)
        candidates = patch.object(wm, 'blender_candidates', lambda: [self.blender_exe])
        candidates.start()
        self.addCleanup(candidates.stop)
        # 叶子数据源替身：竞态发生在六个模块级缓存的复合操作里，
        # ``_json_quiet``／``project_identity`` 只是喂数据的 IO 口（真实现会走
        # ``read_json``→``access()`` 的 OS 文件锁，并发下把用例拖到分钟级）。
        # 缓存的 get/set/clear 复合序列仍是被测模块的真实代码。
        quiet = patch.object(wm, '_json_quiet', lambda path: {})
        quiet.start()
        self.addCleanup(quiet.stop)
        identity = patch.object(wm, 'project_identity', lambda root: None)
        identity.start()
        self.addCleanup(identity.stop)

    @staticmethod
    def _fake_run(command, **kwargs):
        return SimpleNamespace(stdout=b'Blender 4.2.0\n\tbuild platform: Windows\n')

    @staticmethod
    def _reset():
        """「清空」一侧：优先走模块自带的锁内 reset 入口，未提供时退回裸清空。"""
        reset = getattr(wm, '_reset_caches', None)
        if callable(reset):
            reset()
            return
        for name in _WHITE_MODEL_CACHES:
            getattr(wm, name).clear()

    def test_concurrent_reads_and_resets(self):
        race = _Race()
        iters = 350

        def worker(wid):
            for i in range(iters):
                # 六个缓存各自的读写路径：设置／版本／成果目录／Blender／镜头目录。
                settings = wm.read_settings()
                if not isinstance(settings, dict):
                    raise AssertionError('read_settings 返回类型异常：%r' % type(settings))
                version = wm.blender_version(self.exe_pool[(i + wid) % len(self.exe_pool)],
                                             run=self._fake_run)
                if version not in ('', '4.2.0'):
                    raise AssertionError('blender_version 返回异常：%r' % version)
                target = wm.workspace()
                if not isinstance(target, Path):
                    raise AssertionError('workspace 返回类型异常：%r' % type(target))
                exe = wm.find_blender()
                if exe is not None and not isinstance(exe, Path):
                    raise AssertionError('find_blender 返回类型异常：%r' % type(exe))
                directory = wm.shot_directory(self.ctx, self.sids[(i + wid) % len(self.sids)],
                                              workspace_path=self.ws)
                if not directory.is_relative_to(self.ws.resolve()):
                    raise AssertionError('shot_directory 越出成果目录：%r' % directory)

        race_done = threading.Event()

        def clearer():
            # 清空侧让出 GIL：清得足够勤（毫秒级一次）仍能压住命中率，
            # 又不至于让两个空转线程把 worker 的 Python 临界区拖慢一个数量级。
            while not race_done.is_set():
                self._reset()
                time.sleep(0.001)

        threads = race.spawn([lambda w=wid: worker(w) for wid in range(6)]
                             + [clearer, clearer])
        for thread in threads[:6]:
            thread.join(60)
        stuck = [thread.name for thread in threads[:6] if thread.is_alive()]
        race_done.set()
        for thread in threads[6:]:
            thread.join(10)
        race.assert_no_errors()
        if stuck:
            raise AssertionError('worker 线程未在限期内结束：%r' % stuck)
        # 不变量：命中类型正确、清空后可重建、各缓存不超其上限。
        self.assertIsInstance(wm.read_settings(), dict)
        self.assertEqual(wm.blender_version(self.exe_pool[0], run=self._fake_run), '4.2.0')
        self.assertEqual(wm.workspace(), self.ws.resolve())
        self.assertEqual(wm.find_blender(), self.blender_exe)
        self.assertLessEqual(len(wm._SETTINGS_CACHE), 256)
        self.assertLessEqual(len(wm._VERSION_CACHE), 64)
        self.assertLessEqual(len(wm._BASE_CACHE), 1024)
        self.assertLessEqual(len(wm._DIR_CACHE), 1024)
        self.assertLessEqual(len(wm._WORKSPACE_CACHE), 1)
        self.assertLessEqual(len(wm._BLENDER_CACHE), 1)


class IdeaTranscriptCacheLockTests(unittest.TestCase):
    """``idea_transcript._history_cache``：并发读/写/命中 × LRU 淘汰与 pop。"""

    FILE_COUNT = 20  # > _HISTORY_CACHE_LIMIT(16)，保证淘汰持续发生

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.chat_dir = self.root / 'chat'
        self.chat_dir.mkdir()
        self.files = []
        for index in range(self.FILE_COUNT):
            path = self.chat_dir / ('c%02d.json' % index)
            path.write_text(json.dumps(
                {'messages': [{'role': 'user', 'text': '消息%d' % index,
                               'at': '2026-01-01 00:00:00'}]}, ensure_ascii=False),
                encoding='utf-8')
            self.files.append(path)
        self.missing = self.chat_dir / 'missing.json'
        self.ctx = _project_context(self.root / 'proj')
        self.gateway = _chat_gateway()
        self._saved_cache = idea_transcript._history_cache
        idea_transcript._history_cache = _TrapHistoryCache()

        def restore():
            idea_transcript._history_cache = self._saved_cache
        self.addCleanup(restore)
        # 预热：让全部文件进缓存，读线程立即进入「命中→move_to_end」路径。
        for path in self.files:
            idea_transcript._read_rows(path, self.gateway)

    def test_concurrent_reads_writes_and_evictions(self):
        race = _Race()
        iters = 800
        save_iters = 300

        def reader(wid):
            for i in range(iters):
                path = self.files[(i * 3 + wid) % self.FILE_COUNT]
                rows = idea_transcript._read_rows(path, self.gateway)
                if not isinstance(rows, list):
                    raise AssertionError('_read_rows 返回类型异常：%r' % type(rows))
                if i % 7 == 0:
                    # stat 失败分支：pop(path, None) 路径。
                    idea_transcript._read_rows(self.missing, self.gateway)

        def writer(wid):
            for i in range(save_iters):
                rows = [{'role': 'user', 'text': '写入%d-%d' % (wid, i)}]
                saved = idea_transcript.save_rows(self.ctx, rows, gateway=self.gateway)
                if not isinstance(saved, list):
                    raise AssertionError('save_rows 返回类型异常：%r' % type(saved))

        threads = race.spawn([lambda w=wid: reader(w) for wid in range(4)]
                             + [lambda w=wid: writer(w) for wid in range(2)])
        race.join(threads)
        race.assert_no_errors()
        # 不变量：命中返回完整行、缓存不超上限、清空后可重建。
        rows = idea_transcript._read_rows(self.files[0], self.gateway)
        self.assertTrue(rows and isinstance(rows[0], dict) and rows[0].get('text'))
        self.assertLessEqual(len(idea_transcript._history_cache),
                             idea_transcript._HISTORY_CACHE_LIMIT)
        idea_transcript._history_cache.clear()
        self.assertTrue(idea_transcript._read_rows(self.files[1], self.gateway))


class VideoTaskStateCacheLockTests(unittest.TestCase):
    """``video_task_state._OTHER_ACTIVE``：并发 get/clear/set（>64 键触发内部清空）。"""

    KEY_COUNT = 200  # > 64 上限，保证内部 clear 持续发生

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'p'
        (self.project / 'cloud_video').mkdir(parents=True)
        self.source = self.root / 'episode' / 'episode.json'
        self.source.parent.mkdir(parents=True)
        self.source.write_text(json.dumps({'shots': []}), encoding='utf-8')
        self.own_roots = [self.root / 'ws' / ('w%03d' % i) for i in range(self.KEY_COUNT)]
        self._saved_cache = video_task_state._OTHER_ACTIVE
        video_task_state._OTHER_ACTIVE = _TrapSetDict()

        def restore():
            video_task_state._OTHER_ACTIVE = self._saved_cache
        self.addCleanup(restore)

    def test_concurrent_other_active_ids(self):
        race = _Race()
        iters = 600

        def worker(wid):
            for i in range(iters):
                active = video_task_state._other_active_ids(
                    self.project, self.own_roots[(i * 7 + wid * 13) % self.KEY_COUNT],
                    self.source)
                if not isinstance(active, frozenset):
                    raise AssertionError('_other_active_ids 返回类型异常：%r' % type(active))

        threads = race.spawn([lambda w=wid: worker(w) for wid in range(6)])
        race.join(threads)
        race.assert_no_errors()
        # 不变量：返回 frozenset、缓存不超「64 上限 + 1」的封顶口径。
        active = video_task_state._other_active_ids(
            self.project, self.own_roots[0], self.source)
        self.assertIsInstance(active, frozenset)
        self.assertLessEqual(len(video_task_state._OTHER_ACTIVE), 65)


if __name__ == '__main__':
    unittest.main()
