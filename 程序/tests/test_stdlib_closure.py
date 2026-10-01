# -*- coding: utf-8 -*-
"""标准库裁剪的静态守卫：启动 import 闭包必须都能在盘上解析，已裁模块不许回来。

第 34 期第 11 条从 `运行环境\\Python\\Lib` 剪掉 56 个「三重过滤都判定没人用」的标准库模块（第 14 条又补裁 `xml.dom`／`xml.sax` 两个）。
当场跑得绿，但当时的自检只抓得住**模块级**的 import（`run_selftests.py` 会把程序目录下每个 .py
都 import 一遍）；写在**函数体里**的 import 要等用户点到那条分支才会炸。所以补两道静态闸：

1. 从 `启动漫剧制作助手.pyw` 出发，把 import 闭包（含函数体里写的，也含被引模块自己的 import）逐层
   解析到盘上的文件；解析不到就是红。唯一放行的是「只在外宿主里存在」的模块——白模预演的脚本是在
   Blender 里跑的，`bpy` 本机 Python 当然没有。
2. 已裁的 58 个模块：源码里不许再 import，盘上也不许悄悄出现（要恢复得走归档，见报告 §18.4／§21）。

解析口径（两道闸都按这个走，宁可严一点）：

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
import tokenize
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
# 闭包从程序目录解析；运行时在同级的「运行环境」，不在程序目录内。
HERE = ROOT
PYTHON = os.path.join(os.path.dirname(ROOT), "运行环境", "Python")
LIB = os.path.join(PYTHON, "Lib")
DLLS = os.path.join(PYTHON, "DLLs")
ENTRY = os.path.join(ROOT, "app.py")

# 只在外宿主里存在的模块：本机 Python 解析不到是**正常**的，不算裁剪事故。
HOST_ONLY = {"bpy", "bpy_extras", "bmesh", "mathutils"}

# 在 Blender 宿主里跑的脚本：它们不在启动 import 闭包里（第 47 期白模页撤掉「制作进度」那一栏
# 以后，previs_progress.py 不再被哪个页面 import 了——它跟着白模批量任务复制进批次目录，交给
# Blender 里的 agent 用），但还是这个程序发货的一部分，一并走闭包。它们 import 的 bpy（还有
# mathutils）本来就解析不到：HOST_ONLY 这份放行名单就是为它们留的，别让它退化成空名单。
HOST_SCRIPTS = ("previs_progress.py", "blender_previs_template.py")

# 第 34 期第 11 条裁掉的 56 个模块，加上第 14 条补裁的 2 个（xml.dom／xml.sax），共 58 个，
# 写死在这里当回归闸：谁再去 import 它们，
# 这条用例先红，而不是等到用户那台机器上炸 ImportError。
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
    for root in (HERE, LIB):
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
        self.assertIsNotNone(_resolve("tkinter"), "包本身还在")
        self.assertIsNone(_locate("tkinter.colorchooser")[0], "被裁掉的子模块不许被父包救活")
        self.assertIsNone(_resolve("multiprocessing.pool"), "同上")

    def test_namespace_package_without_init_is_recognised(self):
        self.assertIsNotNone(_resolve("batch_frames_tool"), "`keyframe_comfy.py` 就是这么引它的")
        self.assertFalse(os.path.isfile(os.path.join(HERE, "batch_frames_tool", "__init__.py")),
                         "它本来就靠命名空间包成立")

class PruneTests(unittest.TestCase):
    """第 34 期第 11 条的裁剪状态不许被无声改动。"""

    def test_pruned_list_is_the_documented_58(self):
        self.assertEqual(len(PRUNED), 58)
        self.assertEqual(len(set(PRUNED)), 58, "清单里有重复项")

    def test_pruned_modules_are_still_absent_from_disk(self):
        back = [name for name in PRUNED if _locate(name)[0] is not None]
        self.assertEqual(back, [], "这些模块又回到盘上了：从 `模块裁剪备份_20260921_0310.zip`（第 11 条的 56 个）"
                                   "或 `xml_dom_sax裁剪备份_20260921_0328.zip`（第 14 条的 2 个）恢复"
                                   "（或升级运行环境）之后，请同步改这张清单与报告 §18.3／§21")

    def test_no_source_file_imports_a_pruned_module(self):
        heads = {}
        for module in PRUNED:
            head, _dot, tail = module.partition(".")
            if tail:
                heads.setdefault(head, set()).add(tail)
        pruned = set(PRUNED)
        hits = []
        for base, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if not name.endswith((".py", ".pyw")):
                    continue
                path = os.path.join(base, name)
                for module in sorted(_imported_names(path)):
                    if module in pruned:
                        hits.append("%s → %s" % (os.path.relpath(path, ROOT), module))
                        continue
                    head, _dot, tail = module.partition(".")
                    # 第 34 期第 14 条：`xml.dom.minidom` 这种「钻进被裁包更深处」的引用也要认出来，
                    # 所以只比尾巴的第一段（`dom`／`sax`），不比整条尾巴。
                    if tail and tail.split(".")[0] in heads.get(head, ()):
                        hits.append("%s → %s" % (os.path.relpath(path, ROOT), module))
        self.assertEqual(sorted(set(hits)), [], "有别的地方又引用了已裁模块：" + repr(sorted(set(hits))))

    def test_the_xml_prune_kept_etree_and_parsers(self):
        """第 34 期第 14 条裁的是 `xml.dom`／`xml.sax`；etree 与 parsers.expat 是**在用**的，不许跟着丢。"""
        self.assertIsNotNone(_locate("xml.etree.ElementTree")[0], "integrations.py 读 .docx 走它")
        self.assertIsNotNone(_locate("xml.parsers.expat")[0], "plistlib 与 etree 的兜底解析都靠它")

if __name__ == "__main__":
    unittest.main(verbosity=2)
