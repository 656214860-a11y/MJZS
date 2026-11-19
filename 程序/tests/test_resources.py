# -*- coding: utf-8 -*-
"""infra/resources.py 资源感知测试（I15／L1-Q12 验收）。

- I15-2：无 NVIDIA 驱动／pynvml 缺失时 vram 字段为 'unavailable'，不抛异常；
- I15-3：ensure_free 空间不足抛 StorageError（E-IO-WRITE），detail 带
  required_bytes／available_bytes；
- I15-4：import infra.resources 不导入 psutil／pynvml（启动关键路径零成本）；
- 限额学习：429＋Retry-After 推导 rpm，与配置 rpm 取小。
"""
import builtins
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import infra.resources as resources
from contract.infra_errors import StorageError

REAL_PURELIB = Path(sysconfig.get_paths()["purelib"])
PSUTIL_PRESENT = (REAL_PURELIB / "psutil").exists() or (REAL_PURELIB / "psutil.py").exists()


class SnapshotTests(unittest.TestCase):
    def test_snapshot_field_shape(self):
        snap = resources.snapshot()
        self.assertIn("collected_at", snap)
        for key in ("memory", "disk", "disk_io", "network", "vram"):
            self.assertIn(key, snap)
        if PSUTIL_PRESENT:
            self.assertIsInstance(snap["memory"], dict)
            for field in ("total", "available", "used", "percent"):
                self.assertIn(field, snap["memory"])
            self.assertIsInstance(snap["disk_io"], dict)
            self.assertIsInstance(snap["network"], dict)
        else:
            for key in ("memory", "disk_io", "network"):
                self.assertEqual(snap[key], "unavailable")
        self.assertIsInstance(snap["disk"], dict)
        for field in ("path", "total", "used", "free"):
            self.assertIn(field, snap["disk"])

    def test_snapshot_disk_follows_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = resources.snapshot(path=tmp)
            self.assertEqual(Path(snap["disk"]["path"]).resolve(), Path(tmp).resolve())
            self.assertGreater(snap["disk"]["free"], 0)

    def test_snapshot_vram_never_raises(self):
        # I15-2：无论 pynvml 是否存在、nvmlInit 是否失败，vram 字段降级不抛。
        snap = resources.snapshot()
        self.assertTrue(snap["vram"] == "unavailable"
                        or isinstance(snap["vram"], dict))
        if isinstance(snap["vram"], dict):
            for field in ("total_mb", "used_mb", "free_mb"):
                self.assertIn(field, snap["vram"])

    def test_snapshot_vram_unavailable_when_nvml_fails(self):
        # I15-2：模拟 pynvml 导入失败（等价于无驱动/无模块）→ 'unavailable'。
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "pynvml":
                raise ImportError("no driver")
            return real_import(name, *args, **kwargs)

        with mock.patch.object(builtins, "__import__", blocked):
            self.assertEqual(resources._vram(), "unavailable")

    def test_snapshot_psutil_absent_degrades(self):
        # psutil 缺失时内存/磁盘IO/网络降级 'unavailable'，磁盘仍由 stdlib 提供。
        with mock.patch.object(resources, "_psutil", return_value=None):
            snap = resources.snapshot()
        self.assertEqual(snap["memory"], "unavailable")
        self.assertEqual(snap["disk_io"], "unavailable")
        self.assertEqual(snap["network"], "unavailable")
        self.assertIsInstance(snap["disk"], dict)
        # vram 与 psutil 无关：只断言字段存在且形态合法（GPU 实时值不可比对）。
        self.assertTrue(snap["vram"] == "unavailable" or isinstance(snap["vram"], dict))


class EnsureFreeTests(unittest.TestCase):
    def test_ensure_free_accepts_small_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            usage = resources.ensure_free(tmp, 1)
            self.assertIsInstance(usage, tuple)
            self.assertGreaterEqual(len(usage), 3)

    def test_ensure_free_accepts_nonexistent_nested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b" / "c.bin"
            usage = resources.ensure_free(target, 1)
            self.assertGreater(usage.free, 0)

    def test_ensure_free_rejects_oversized_request(self):
        # I15-3：空间不足 → StorageError(E-IO-WRITE)，detail 带所需/可用字节。
        with tempfile.TemporaryDirectory() as tmp:
            probe = resources._probe_for(tmp)
            available = shutil.disk_usage(probe).free
            with self.assertRaises(StorageError) as ctx:
                resources.ensure_free(tmp, available + 1)
            exc = ctx.exception
            self.assertEqual(exc.code, "E-IO-WRITE")
            self.assertIsInstance(exc, OSError)
            self.assertEqual(exc.detail["required_bytes"], available + 1)
            self.assertEqual(exc.detail["available_bytes"], available)
            self.assertIn("probe", exc.detail)


class RateLearningTests(unittest.TestCase):
    def setUp(self):
        with resources._RATE_LOCK:
            resources._LEARNED.clear()

    tearDown = setUp

    def test_retry_after_derives_rpm(self):
        resources.note_rate_limited("api.example.com", 30)
        self.assertEqual(resources.learned_rpm("api.example.com"), 2.0)

    def test_effective_rpm_takes_min_with_configured(self):
        resources.note_rate_limited("api.example.com", 30)  # 学习 2 rpm
        self.assertEqual(resources.effective_rpm("api.example.com", 10), 2.0)
        self.assertEqual(resources.effective_rpm("api.example.com", 1), 1.0)
        self.assertEqual(resources.effective_rpm("api.example.com", None), 2.0)
        self.assertIsNone(resources.effective_rpm("other.example.com", None))

    def test_bare_429_halves_learned(self):
        resources.note_rate_limited("api.example.com", 30)  # 学习 2 rpm
        resources.note_rate_limited("api.example.com")  # 裸 429：减半→1，取 min 得 1
        self.assertEqual(resources.learned_rpm("api.example.com"), 1.0)
        with resources._RATE_LOCK:
            resources._LEARNED.clear()
        resources.note_rate_limited("api.example.com")  # 裸 429：60/2=30
        self.assertEqual(resources.learned_rpm("api.example.com"), 30.0)
        resources.note_rate_limited("api.example.com")  # 再减半：15
        self.assertEqual(resources.learned_rpm("api.example.com"), 15.0)

    def test_learned_ttl_expires(self):
        base = 1000.0
        resources.note_rate_limited("api.example.com", 30, now=base)
        self.assertEqual(resources.learned_rpm("api.example.com", now=base + 1), 2.0)
        self.assertIsNone(resources.learned_rpm("api.example.com",
                                               now=base + resources._LEARNED_TTL + 1))

    def test_hosts_are_independent_and_case_insensitive(self):
        resources.note_rate_limited("API.Example.COM", 60)
        self.assertEqual(resources.learned_rpm("api.example.com"), 1.0)
        self.assertIsNone(resources.learned_rpm("other.example.com"))


class LazyImportTests(unittest.TestCase):
    def test_module_import_does_not_load_psutil_or_pynvml(self):
        # I15-4：在干净子进程里 import infra.resources，psutil/pynvml 不得进 sys.modules。
        code = (
            "import sys; sys.path.insert(0, '.');"
            "import infra.resources;"
            "assert 'psutil' not in sys.modules, 'psutil leaked';"
            "assert 'pynvml' not in sys.modules, 'pynvml leaked';"
            "print('lazy-ok')"
        )
        proc = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0,
                         proc.stderr or proc.stdout)
        self.assertIn("lazy-ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()
