# -*- coding: utf-8 -*-
"""完整运行环境的静态守卫：启动 import 闭包必须在当前 runtime／源码中解析。

第 34 期裁掉的 58 个标准库模块现已随完整 Python 恢复，历史清单保留作回归覆盖，
不再要求物理缺失；平台专属或已废弃的私有模块不作为跨版本必需项。

1. 从 app.py 与 Blender 脚本出发，解析源码 import 闭包（包括函数体 import）。
   缺失只允许明确登记的 Blender 宿主模块，不忽略可选分支中的 ImportError。
2. 第三方模块必须列入 requirements.txt，并实际存在于当前 runtime 的 site-packages；
   不搜索 sys.path 或用户 site，不以白名单代替文件存在性检查。

解析口径：

* `import a.b`：`a` 是**单文件模块**时允许按属性算（`import os.path` 就是这个道理）；
  `a` 是**包**时 `a.b` 必须真有 `b.py`／`b/`——否则「重新 import 一个被裁掉的子模块」会被父包悄悄救活。
* `from X import Y`：`X.Y` 不存在时，只有当 `X` 自己的源码里确实定义了 `Y`（`def`／`class`／赋值／
  再导出）才算符号导入，否则一样算缺（`from tkinter import colorchooser` 在裁剪后必须红）。
"""
import ast
import io
import os
import re
import sys
import tempfile
import tokenize
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
# 闭包从程序目录解析；标准库必须以当前解释器为准。正式目录把「运行环境」放在
# 源码同级，但 Codex worktree 只检出源码，仍复用同一个受控解释器。
HERE = ROOT
PYTHON = sys.prefix
LIB = os.path.join(PYTHON, "Lib")
DLLS = os.path.join(PYTHON, "DLLs")
SITE_PACKAGES = os.path.join(LIB, "site-packages")
ENTRY = os.path.join(ROOT, "app.py")


def _requirements_imports(path):
    """只认显式 requirements 项；发行包名与导入名的例外也须明确登记。"""
    aliases = {"pillow": "PIL"}
    with open(path, encoding="utf-8") as handle:
        names = []
        for line in handle:
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*(?:\[|[<>=!~;]|$)", line.strip())
            if match:
                distribution = match.group(1).lower().replace("-", "_")
                names.append(aliases.get(distribution, distribution))
    return set(names)


THIRD_PARTY = _requirements_imports(os.path.join(ROOT, "requirements.txt"))

# 只在外宿主里存在的模块：本机 Python 解析不到是**正常**的，不算裁剪事故。
HOST_ONLY = {"bpy", "bpy_extras", "bmesh", "mathutils"}

# 在 Blender 宿主里跑的脚本：它们不在启动 import 闭包里（第 47 期白模页撤掉「制作进度」那一栏
# 以后，previs_progress.py 不再被哪个页面 import 了——它跟着白模批量任务复制进批次目录，交给
# Blender 里的 agent 用），但还是这个程序发货的一部分，一并走闭包。它们 import 的 bpy（还有
# mathutils）本来就解析不到：HOST_ONLY 这份放行名单就是为它们留的，别让它退化成空名单。
HOST_SCRIPTS = ("previs_progress.py", "blender_previs_template.py")

# 第 34 期的 58 项历史清单；完整 runtime 已恢复，不再作为禁入名单。
PRUNED = (
    "multiprocessing.managers asyncio.unix_events multiprocessing.pool trace modulefinder dbm wave "
    "compileall curses concurrent.interpreters multiprocessing.shared_memory fileinput "
    "multiprocessing.forkserver poplib symtable multiprocessing.resource_tracker timeit dbm.dumb "
    "tabnanny multiprocessing.heap pyclbr filecmp urllib.robotparser graphlib shelve "
    "concurrent.interpreters._queues zipapp rlcompleter curses.textpad _android_support "
    "multiprocessing.sharedctypes unittest.async_case curses.has_key pty multiprocessing.resource_sharer "
    "multiprocessing.dummy dbm.sqlite3 colorsys concurrent.interpreters._crossinterp tkinter.colorchooser "
    "multiprocessing.popen_fork nturl2path _apple_support multiprocessing.popen_forkserver "
    "multiprocessing.popen_spawn_posix tty tkinter.scrolledtext string.templatelib antigravity __hello__ "
    "__phello__ __phello__.spam dbm.gnu dbm.ndbm __phello__.ham.eggs __phello__.ham "
    # 第 34 期第 14 条：xml 包里只有 etree 与 parsers.expat 在用，dom／sax 整个包没人 import。
    "xml.dom xml.sax"
).split()

# 这些条目属于平台实现或旧版私有 API，不能因历史清单而强制其他平台／版本提供。
PLATFORM_OR_PRIVATE = {
    "asyncio.unix_events", "curses", "curses.textpad", "curses.has_key", "pty", "tty",
    "dbm.gnu", "dbm.ndbm", "_android_support", "_apple_support",
    "multiprocessing.forkserver", "multiprocessing.popen_fork",
    "multiprocessing.popen_forkserver", "multiprocessing.popen_spawn_posix",
    "concurrent.interpreters._queues", "concurrent.interpreters._crossinterp",
}

BUILTIN = set(sys.builtin_module_names)
_SOURCES = {}


def _parse(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return ast.parse(handle.read())
    except (SyntaxError, OSError):
        return None


def _read(path):
    if path not in _SOURCES:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                _SOURCES[path] = handle.read()
        except OSError:
            _SOURCES[path] = ""
    return _SOURCES[path]


def _locate(name):
    """严格定位：只认这个点分名**本身**，不替它找父包。返回 `(路径, 是不是包)`。

    认四种形态：带 `__init__.py` 的包、单文件 `.py`、没有 `__init__.py` 的**命名空间包**
    （`batch_frames_tool` 就是这一种，`keyframe_comfy.py` 那句 `import batch_frames_tool` 靠它才成立）、
    以及 `DLLs` 下的扩展模块（`_ssl.pyd` 之类）。
    """
    parts = name.split(".")
    rel = os.path.join(*parts)
    roots = [HERE, LIB]
    if parts[0] in THIRD_PARTY:
        roots.append(SITE_PACKAGES)
    for root in roots:
        init = os.path.join(root, rel, "__init__.py")
        if os.path.isfile(init):
            return init, True
        single = os.path.join(root, rel + ".py")
        if os.path.isfile(single):
            return single, False
        folder = os.path.join(root, rel)
        if os.path.isdir(folder) and any(item.endswith(".py") for item in os.listdir(folder)):
            return folder, True
    leaf = parts[-1]
    for candidate in (os.path.join(DLLS, leaf + ".pyd"), os.path.join(DLLS, leaf + ".dll"),
                      os.path.join(PYTHON, leaf + ".pyd"), os.path.join(PYTHON, leaf + ".dll")):
        if os.path.isfile(candidate):
            return candidate, False
    return None, False


def _resolve(name):
    """模块名 → 盘上的文件；找不到返回 None。单文件模块允许接属性（`import os.path`）。"""
    path, is_package = _locate(name)
    if path is not None:
        return path
    if "." in name:
        parent, parent_is_package = _locate(name.rpartition(".")[0])
        if parent is not None and not parent_is_package:
            return parent
    return None


def _defines(path, symbol):
    """这个符号是不是模块自己定义的（`def`／`class`／赋值／再导出都算）。"""
    text = _read(path)
    for pattern in (r"^\s*(?:def|class)\s+%s\b", r"^\s*%s\s*[:=]", r"^\s*from\s+\S+\s+import\s+[^\n#]*\b%s\b"):
        if re.search(pattern % (re.escape(symbol),), text, re.M):
            return True
    return False


def _imports(tree, package):
    """语法树里 import 了什么。返回 `(模块名, 它属于哪个 `from` 源)`，后者用来判符号导入。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                prefix = (base + "." + node.module) if node.module else base
            else:
                prefix = node.module or ""
            if prefix:
                found.append((prefix, None))
                found += [(prefix + "." + alias.name, prefix) for alias in node.names]
    return found


def _imported_names(path):
    """一个文件里真正被 import 的模块名（含 `from X import Y` 展开出的 `X.Y`）。

    走 tokenizer，不走近似正则：注释、docstring、字符串里写到的名字一律不算——本文件自己就要在
    说明里举 `from tkinter import colorchooser` 这类例子，靠切词才不会被自己绊倒。
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            stream = io.StringIO(handle.read())
        tokens = [(token.type, token.string) for token in tokenize.generate_tokens(stream.readline)]
    except (OSError, tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return set()
    names = set()
    index = 0
    while index < len(tokens):
        kind, word = tokens[index]
        if kind == tokenize.NAME and word == "from":
            source, index = _dotted(tokens, index + 1)
            if source:
                names.add(source)
            if index < len(tokens) and tokens[index][1] == "import":
                index += 1
                while index < len(tokens):
                    kind, word = tokens[index]
                    if kind == tokenize.NAME:
                        symbol, index = _dotted(tokens, index)
                        if symbol:
                            names.add(source + "." + symbol if source else symbol)
                    elif kind == tokenize.OP and word == ",":
                        index += 1
                    elif kind == tokenize.OP and word == "(":
                        index += 1
                    elif kind == tokenize.OP and word == ")":
                        continue
                    else:
                        break
            continue
        if kind == tokenize.NAME and word == "import":
            index += 1
            while index < len(tokens):
                kind, word = tokens[index]
                if kind == tokenize.NAME:
                    module, index = _dotted(tokens, index)
                    if module:
                        names.add(module)
                elif kind == tokenize.OP and word == ",":
                    index += 1
                else:
                    break
            continue
        index += 1
    return names


def _dotted(tokens, index):
    """从 index 起吃一个点分名，返回 `(名字, 新的下标)`。"""
    parts = []
    while index < len(tokens):
        kind, word = tokens[index]
        if kind == tokenize.NAME:
            parts.append(word)
            index += 1
            continue
        if kind == tokenize.OP and word == "." and parts:
            index += 1
            continue
        break
    while index < len(tokens) and tokens[index][1] in ("as",):
        index += 2 if index + 1 < len(tokens) else 1
    return ".".join(parts), index

def _package_of(path):
    """文件在 `程序\\` 里的包名（用于展开相对 import）；根目录文件返回空串。"""
    if not os.path.abspath(path).startswith(HERE + os.sep):
        return ""
    parts = os.path.relpath(path, HERE).split(os.sep)[:-1]
    return ".".join(part for part in parts if part.isidentifier())


def walk_closure():
    """从启动脚本走一遍 import 闭包。

    返回 `(读过的文件集合, 解析不到的 (文件, 模块名) 列表)`。只往下跟 `程序\\` 里的模块——
    Lib 里的标准库不递归，否则一条 import 就能把半个标准库拖进来。
    """
    queue = [ENTRY] + [os.path.join(HERE, name) for name in HOST_SCRIPTS]
    read = set()
    missing = []
    while queue:
        path = queue.pop()
        if path in read:
            continue
        read.add(path)
        tree = _parse(path)
        if tree is None:
            continue
        for name, owner in _imports(tree, _package_of(path)):
            if name.split(".")[0] in BUILTIN:
                continue
            target = _resolve(name)
            if target is None:
                if owner is not None:
                    holder = _resolve(owner)
                    if holder is not None and _defines(holder, name.rpartition(".")[2]):
                        continue
                missing.append((os.path.relpath(path, ROOT), name))
                continue
            if os.path.isfile(target) and os.path.abspath(target).startswith(HERE + os.sep):
                queue.append(target)
    return read, missing


class ClosureTests(unittest.TestCase):
    """启动路径上不许出现「盘上没有」的 import。"""

    @classmethod
    def setUpClass(cls):
        cls.read, cls.missing = walk_closure()

    def test_the_walk_really_walked(self):
        # 新入口移除了两条历史兼容导入；仍要求足以覆盖核心模块，避免闭包走空。
        self.assertGreaterEqual(len(self.read), 45,
                                "闭包只读到 %d 个文件，八成是解析器坏了——别让这条用例假绿" % len(self.read))

    def test_every_imported_module_exists_on_disk(self):
        broken = sorted(set(item for item in self.missing if item[1].split(".")[0] not in HOST_ONLY))
        self.assertEqual(broken, [], "这些 import 在盘上找不到（模块被裁掉了？）：" + repr(broken))

    def test_only_the_blender_host_modules_are_allowed_to_be_absent(self):
        absent = sorted(set(name.split(".")[0] for _rel, name in self.missing))
        self.assertTrue(set(absent) <= HOST_ONLY,
                        "只允许 Blender 宿主模块缺席，实际还有：" + repr(sorted(set(absent) - HOST_ONLY)))
        self.assertIn("bpy", absent,
                      "`previs_progress.py`／`blender_previs_template.py` 里那句 `import bpy` 本来就该解析不到")


class ResolverTests(unittest.TestCase):
    """解析口径自己的用例：真红过才算闸，别让它退化成永远为真。"""

    def test_single_file_module_allows_attribute_like_import(self):
        self.assertIsNotNone(_resolve("os"))
        self.assertIsNotNone(_resolve("os.path"), "`import os.path` 是合法的属性导入，不能误报")

    def test_a_package_submodule_must_really_exist(self):
        with tempfile.TemporaryDirectory() as root:
            package = os.path.join(root, "closure_fixture_package")
            os.mkdir(package)
            with open(os.path.join(package, "__init__.py"), "w", encoding="utf-8") as handle:
                handle.write("attribute = 1\n")
            with open(os.path.join(package, "present.py"), "w", encoding="utf-8") as handle:
                handle.write("value = 1\n")
            with mock.patch(__name__ + ".HERE", root):
                self.assertIsNotNone(_resolve("closure_fixture_package"), "包本身存在")
                self.assertIsNotNone(_resolve("closure_fixture_package.present"))
                self.assertIsNone(_locate("closure_fixture_package.absent")[0])
                self.assertIsNone(_resolve("closure_fixture_package.absent"), "缺失子模块不能被父包救活")
                self.assertIsNone(_resolve("closure_fixture_package.attribute"), "包属性不能冒充 import 子模块")

    def test_requirements_whitelist_requires_real_runtime_files(self):
        with tempfile.TemporaryDirectory() as root:
            site = os.path.join(root, "site-packages")
            os.mkdir(site)
            for name in ("allowed_fixture", "unlisted_fixture"):
                with open(os.path.join(site, name + ".py"), "w", encoding="utf-8") as handle:
                    handle.write("value = 1\n")
            requirements = os.path.join(root, "requirements.txt")
            with open(requirements, "w", encoding="utf-8") as handle:
                handle.write("allowed-fixture==1.0\nmissing-fixture==1.0\nPillow==13.0.0\n# ignored\n")
            whitelist = _requirements_imports(requirements)
            self.assertEqual(whitelist, {"allowed_fixture", "missing_fixture", "PIL"})
            with mock.patch.multiple(__name__, THIRD_PARTY=whitelist, SITE_PACKAGES=site):
                self.assertIsNotNone(_locate("allowed_fixture")[0])
                self.assertIsNone(_locate("missing_fixture")[0], "登记白名单不等于依赖存在")
                self.assertIsNone(_locate("unlisted_fixture")[0], "不能放行整个 site-packages")

    def test_closure_does_not_use_user_site_or_ignore_importerror(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as user_site:
            entry = os.path.join(root, "closure_fixture_entry.py")
            name = "closure_user_site_only_fixture"
            with open(entry, "w", encoding="utf-8") as handle:
                handle.write("try:\n    import %s\nexcept ImportError:\n    pass\n" % name)
            with open(os.path.join(user_site, name + ".py"), "w", encoding="utf-8") as handle:
                handle.write("value = 1\n")
            with mock.patch.multiple(__name__, HERE=root, ENTRY=entry, HOST_SCRIPTS=(),
                                     THIRD_PARTY={name}), mock.patch.object(sys, "path", [user_site] + sys.path):
                self.assertIsNone(_resolve(name), "用户 site 不能兜底当前 runtime")
                walked, missing = walk_closure()
                self.assertIn(entry, walked)
                self.assertEqual(missing, [(os.path.relpath(entry, ROOT), name)],
                                 "捕获 ImportError 也不能放行缺失 import")

    def test_namespace_package_without_init_is_recognised(self):
        self.assertIsNotNone(_resolve("batch_frames_tool"), "`keyframe_comfy.py` 就是这么引它的")
        self.assertFalse(os.path.isfile(os.path.join(HERE, "batch_frames_tool", "__init__.py")),
                         "它本来就靠命名空间包成立")

class PruneTests(unittest.TestCase):
    """第 34 期第 11 条的裁剪状态不许被无声改动。"""

    def test_pruned_list_is_the_documented_58(self):
        self.assertEqual(len(PRUNED), 58)
        self.assertEqual(len(set(PRUNED)), 58, "清单里有重复项")

    def test_bundled_runtime_provides_required_standard_library(self):
        # R3199/R3211已批准完整3.14随包运行时与白名单依赖；旧58项仅保留历史清单，
        # 不能再要求升级后的标准库从磁盘消失。依赖闭包可解析仍由上面两道强断言守卫。
        required = ('tkinter', 'json', 'ssl', 'urllib.request', 'zipfile', 'sqlite3',
                    'multiprocessing.pool', 'tkinter.colorchooser')
        missing = [name for name in required if _locate(name)[0] is None]
        self.assertEqual(missing, [], '当前完整随包运行时缺少必需标准库：' + repr(missing))

    def test_restored_portable_modules_are_resolvable_on_disk(self):
        missing = [name for name in PRUNED if name not in PLATFORM_OR_PRIVATE and _locate(name)[0] is None]
        self.assertEqual(missing, [], "完整 runtime 缺少已恢复的标准库模块：" + repr(missing))

    def test_source_imports_of_restored_modules_are_resolvable(self):
        restored = tuple(PRUNED)
        hits = []
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if not name.endswith((".py", ".pyw")):
                    continue
                path = os.path.join(base, name)
                for module in sorted(_imported_names(path)):
                    if not any(module == name or module.startswith(name + ".") for name in restored):
                        continue
                    if _resolve(module) is not None:
                        continue
                    owner, _, symbol = module.rpartition(".")
                    holder = _resolve(owner) if owner else None
                    if holder is not None and _defines(holder, symbol):
                        continue
                    hits.append("%s → %s" % (os.path.relpath(path, ROOT), module))
        self.assertEqual(sorted(set(hits)), [], "源码引用的已恢复模块仍必须可解析：" + repr(sorted(set(hits))))

    def test_the_xml_prune_kept_etree_and_parsers(self):
        """第 34 期第 14 条裁的是 `xml.dom`／`xml.sax`；etree 与 parsers.expat 是**在用**的，不许跟着丢。"""
        self.assertIsNotNone(_locate("xml.etree.ElementTree")[0], "integrations.py 读 .docx 走它")
        self.assertIsNotNone(_locate("xml.parsers.expat")[0], "plistlib 与 etree 的兜底解析都靠它")

if __name__ == "__main__":
    unittest.main(verbosity=2)
