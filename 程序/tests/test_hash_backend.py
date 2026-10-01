# -*- coding: utf-8 -*-
"""hashlib 回退到内置实现（省掉启动时的 OpenSSL 常驻）。运行：python test_hash_backend.py

回退开关是**进程级**状态，不能在测试进程里拨（拨完这个进程的 hashlib 就换了实现），
所以每条用例都在子进程里跑，只回读它 print 的 JSON。
"""
import json, os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import hash_backend

PRELUDE = "import json,sys;sys.path.insert(0,%r);import hash_backend;" % ROOT
# 「OpenSSL 后端进来了没有」＝ _hashlib 在 sys.modules 里且不是那个占位 None。
LOADED = "sys.modules.get('_hashlib') is not None"


def run(code):
    """在子进程里跑：前置引好 hash_backend，再把最后一行 print 的 JSON 读回来。"""
    done = subprocess.run([sys.executable, "-B", "-c", PRELUDE + code],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    if done.returncode != 0:
        raise AssertionError("子进程失败：" + (done.stderr or "")[-800:])
    return json.loads(done.stdout.strip().splitlines()[-1])


class InstallTests(unittest.TestCase):
    def test_switch_happens_and_digests_stay_correct(self):
        data = run("ok=hash_backend.install()\n"
                   "import hashlib, io\n"
                   "print(json.dumps({'ok':ok,'loaded':%s,"
                   "'sha256':hashlib.sha256(b'abc').hexdigest(),"
                   "'md5':hashlib.md5(b'abc').hexdigest(),"
                   "'sha1':hashlib.sha1(b'abc').hexdigest(),"
                   "'blake2b':hashlib.blake2b(b'abc').hexdigest()[:16],"
                   "'file_digest':hashlib.file_digest(io.BytesIO(b'abc'),'sha256').hexdigest()}))" % LOADED)
        self.assertTrue(data["ok"], "内置实现齐备时应当切过去")
        self.assertFalse(data["loaded"], "切过去之后 OpenSSL 后端不该被加载")
        self.assertEqual(data["sha256"], hash_backend.SHA256_ABC)
        self.assertEqual(data["md5"], hash_backend.MD5_ABC)
        self.assertEqual(data["sha1"], hash_backend.SHA1_ABC)
        self.assertEqual(data["blake2b"], "ba80a53f981c4d0d", "blake2b 也得照旧算对")
        self.assertEqual(data["file_digest"], hash_backend.SHA256_ABC, "file_digest 走同一个后端")

    def test_late_install_steps_aside_when_openssl_is_already_loaded(self):
        data = run("import hashlib\n"
                   "print(json.dumps({'ok':hash_backend.install(),'loaded':%s}))" % LOADED)
        self.assertFalse(data["ok"], "已经 import 过 hashlib 就别再动它")
        self.assertTrue(data["loaded"], "这种情况下 OpenSSL 后端保持原样")

    def test_install_is_repeatable(self):
        data = run("first=hash_backend.install()\n"
                   "print(json.dumps({'first':first,'second':hash_backend.install(),'loaded':%s}))" % LOADED)
        self.assertTrue(data["first"])
        self.assertTrue(data["second"], "第二次调用不该翻车")
        self.assertFalse(data["loaded"], "开关还是「不可用」")

    def test_gives_up_when_the_builtin_modules_are_missing(self):
        data = run("hash_backend.builtins_ready=lambda:False\n"
                   "print(json.dumps({'ok':hash_backend.install(),'loaded':%s}))" % LOADED)
        self.assertFalse(data["ok"], "内置实现不在就照旧走 OpenSSL")
        self.assertFalse(data["loaded"], "没切过去就不该动 _hashlib")

    def test_rolls_back_when_the_fallback_computes_wrong(self):
        # 真跑一遍「算错」的分支：把已知答案改坏，install() 应当放开开关并返回 False。
        data = run("hash_backend.SHA256_ABC='00'\n"
                   "ok=hash_backend.install()\n"
                   "print(json.dumps({'ok':ok,'left':sys.modules.get('_hashlib','缺席')}))")
        self.assertFalse(data["ok"])
        self.assertEqual(data["left"], "缺席", "算错就要把开关摘掉")


class GuardTests(unittest.TestCase):
    """守卫：install() 只砍掉了 OpenSSL 独有的几个接口，全仓库不许有人用它们。"""

    OPENSSL_ONLY = ("pbkdf2_hmac", "scrypt", "algorithms_available")

    def sources(self):
        skip = {"hash_backend.py", "test_hash_backend.py"}       # 这两个文件里就是说明与守卫本身
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "运行环境")]
            for name in files:
                if name.endswith((".py", ".pyw")) and name not in skip:
                    yield os.path.join(base, name)

    def test_no_one_calls_the_openssl_only_apis(self):
        offenders = []
        for path in self.sources():
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for name in self.OPENSSL_ONLY:
                if name in text:
                    offenders.append(os.path.relpath(path, ROOT) + " → " + name)
        self.assertEqual(offenders, [],
                         "有代码用到了只有 OpenSSL 后端才有的接口，install() 必须先撤掉")

    def test_the_scan_actually_walks_the_program(self):
        scanned = [os.path.basename(p) for p in self.sources()]
        self.assertIn("desktop.py", scanned)
        self.assertIn("h3_launcher.pyw", scanned)
        self.assertGreater(len(scanned), 50, "扫到的文件太少，八成是目录 walk 写错了")


class LauncherTests(unittest.TestCase):
    def test_launcher_installs_the_backend_before_importing_hashlib(self):
        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:
            text = handle.read()
        statements = [line.strip() for line in text.splitlines()]
        self.assertIn("hash_backend.install()", statements, "启动脚本里得有这一句")
        self.assertLess(statements.index("hash_backend.install()"), statements.index("import queue"),
                        "切换必须先于应用服务导入，晚一步 OpenSSL 就可能已经进来了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
