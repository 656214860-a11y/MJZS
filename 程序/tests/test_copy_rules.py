# -*- coding: utf-8 -*-
"""第 48 期第 2、3 条：弹窗文案要短，按钮名字要统一。这里只做静态检查，不开窗口。

用户原话：
  二、所有页面的弹窗提示文字要简化通俗易懂、一目了然，不要太多废话；
  三、所有按钮名称、目录名字和文件名要标准统一、精准概括。

把这两句落成四条能跑的规矩（数字都在下面的常量里，要改规矩就改这几行）：
  一、弹窗文案：messagebox 的对话框，加上会被 safe() 弹成对话框的 ValueError／RuntimeError，
      最多 POPUP_LINES 行、去掉占位符后的固定文字最多 POPUP_CHARS 个字，也不许留连空行。
  二、按钮文案：汉字和拉丁字母挨在一起时必须留一个半角空格（「保存 API 设置」），
      不许混进全角符号，首尾不留空格。
  三、按钮名字要概括：最多 BUTTON_CHARS 个字，别把一整句说明塞进按钮。
  四、一个动作只有一个名字，别的写法一律算错，见 ONE_NAME。

只扫自己写的界面代码：随包带的「运行环境」和「维护记录」（历史，不改）不参与。
"""
import ast
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = str(Path(HERE).parent)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

POPUP_LINES = 3
POPUP_CHARS = 45
BUTTON_CHARS = 16

MESSAGEBOX = {"showerror", "showinfo", "showwarning", "askyesno", "askokcancel",
              "askyesnocancel", "askquestion"}
ERRORS = {"ValueError", "RuntimeError"}
# 自定义主／次按钮同样是用户可见的按钮；迁移到组件层后仍必须受文案契约约束。
BUTTON_TYPES = {"Button", "Checkbutton", "Radiobutton", "PrimaryButton", "SecondaryButton"}
SKIP_DIRS = {"运行环境", "__pycache__", ".git", "维护记录"}

# 同一件事只认一个名字：左边是唯一正确写法，右边是历史遗留的另一种叫法。
ONE_NAME = [
    ("测试连接", ("检测连通性", "检测接口连通性")),
    ("保存设置", ("保存 API 设置",)),
    ("桌面打开 ComfyUI", ("桌面打开ComfyUI",)),
    ("Skill 调用设置", ("Skill调用设置",)),
    ("+ 新建项目", ("＋ 新建项目",)),
    ("参考图目录", ("参考图文件夹",)),
    ("打开参考图目录", ("打开参考图文件夹",)),
    ("打开项目目录", ("打开项目文件夹",)),
]

# 目录/文件一律叫「目录」；用户看得见的名字里不许再冒出「文件夹」。
ENTRY_WORD = ("目录", "文件夹")

HAN = r"[\u4e00-\u9fff]"
LATIN = r"[A-Za-z]"
GLUED = re.compile("(?:%s%s|%s%s)" % (HAN, LATIN, LATIN, HAN))
FULLWIDTH = "＋＝＜＞　"


def ignored_paths(root):
    """root 下被版本库忽略的路径：(文件集合, 目录前缀元组)。
    git 不在、root 不在工作树里或命令失败时返回空，等于不额外跳过任何路径。"""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files",
             "--others", "--ignored", "--exclude-standard", "--directory", "-z"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace")
    except OSError:
        return set(), ()
    if proc.returncode != 0 or not proc.stdout:
        return set(), ()
    files, dirs = set(), []
    for entry in proc.stdout.split("\0"):
        if entry.endswith("/"):
            dirs.append(entry)
        elif entry:
            files.add(entry)
    return files, tuple(dirs)


def program_sources(root=PROGRAM):
    """root 下所有自己写的 .py／.pyw，{正斜杠相对路径: 源码}。
    测试文件不查自己，历史记录不翻旧账；被版本库忽略的运行时数据也不是源码。"""
    root = os.fspath(root)
    ignored_files, ignored_dirs = ignored_paths(root)
    sources = {}
    for folder, dirs, names in os.walk(root):
        rel_folder = os.path.relpath(folder, root).replace(os.sep, "/")
        prefix = "" if rel_folder == "." else rel_folder + "/"
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and not any((prefix + d + "/").startswith(p) for p in ignored_dirs))
        for name in names:
            if not name.endswith((".py", ".pyw")) or name.startswith("test_"):
                continue
            rel = prefix + name
            if rel in ignored_files or any(rel.startswith(p) for p in ignored_dirs):
                continue
            sources[rel] = (Path(folder) / name).read_text(encoding="utf-8")
    return sources


_SOURCES = None


def shared_sources():
    """这次运行只扫一遍仓库：所有测试类共用同一份 {路径: 源码}。"""
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = program_sources(root=PROGRAM)
    return _SOURCES


@functools.lru_cache(maxsize=None)
def _parse(body):
    """同一份源码只建一次语法树。"""
    return ast.parse(body)


def calls(tree):
    """这个文件里所有调用，带上算得出来的函数名。"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        yield node, name


def flatten(node):
    """把拼出来的文案还原成一整句：认常量、f-string 和 + 拼接，别的当占位符。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                pieces.append("{…}")
        return "".join(pieces)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = flatten(node.left), flatten(node.right)
        if left is not None and right is not None:
            return left + right
    return None


@functools.lru_cache(maxsize=None)
def popups(tree):
    """这个文件里所有会弹成对话框的文案：[(行号, 文案)]。"""
    found = []
    for node, name in calls(tree):
        if name in MESSAGEBOX:
            args = node.args[1:2]                       # 第 0 个是标题
        elif name in ERRORS and node.args:
            args = node.args[0:1]                       # safe() 会把它当对话框正文
        else:
            continue
        for arg in args:
            text = flatten(arg)
            if text and re.search(HAN, text):
                found.append((node.lineno, text))
    return found


@functools.lru_cache(maxsize=None)
def buttons(tree):
    """这个文件里所有按钮／勾选框／单选框的固定文案：[(行号, 文案)]。"""
    found = []
    for node, name in calls(tree):
        if name not in BUTTON_TYPES:
            continue
        for keyword in node.keywords:
            value = keyword.value
            if keyword.arg in ("text", "label") and isinstance(value, ast.Constant) \
                    and isinstance(value.value, str):
                found.append((node.lineno, value.value))
    return found


def fixed_chars(text):
    """文案里那几个固定字（占位符和空白不算）。"""
    return len([ch for ch in text.replace("{…}", "") if not ch.isspace()])


def line_count(text):
    return len([one for one in text.split("\n") if one.strip()])


class PopupCopyTests(unittest.TestCase):
    """第 48 期第 2 条：弹窗说人话，别啰嗦。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = shared_sources()

    def test_the_scan_still_catches_the_popups(self):
        """先保底：翻出来的弹窗文案得有几百条，不然是扫描器坏了、不是大家都写对了。"""
        total = sum(len(popups(_parse(body))) for body in self.sources.values())
        self.assertGreater(total, 400, "弹窗文案只数到 %d 条，扫描多半失效了" % total)

    def test_no_popup_goes_over_the_limit(self):
        over = []
        for rel, body in sorted(self.sources.items()):
            for line, text in popups(_parse(body)):
                if line_count(text) > POPUP_LINES or fixed_chars(text) > POPUP_CHARS:
                    over.append("%s:%d（%d 行 %d 字）%s"
                                % (rel, line, line_count(text), fixed_chars(text), text.replace("\n", "\\n")))
        self.assertEqual(over, [], "这些弹窗太长，压到 %d 行／%d 字以内：\n%s"
                         % (POPUP_LINES, POPUP_CHARS, "\n".join(over)))

    def test_no_popup_keeps_a_blank_gap_or_full_width_space(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in popups(_parse(body)):
                if "\n\n\n" in text or "\u3000" in text:
                    bad.append("%s:%d %s" % (rel, line, text.replace("\n", "\\n")))
        self.assertEqual(bad, [], "弹窗里别留连空行和全角空格：\n" + "\n".join(bad))


class ButtonNameTests(unittest.TestCase):
    """第 48 期第 3 条：按钮名字写法统一、一眼看懂。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = shared_sources()

    def test_the_scan_still_catches_the_buttons(self):
        total = sum(len(buttons(_parse(body))) for body in self.sources.values())
        self.assertGreater(total, 100, "按钮文案只数到 %d 条，扫描多半失效了" % total)

    def test_chinese_and_latin_keep_one_space_apart(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in buttons(_parse(body)):
                if GLUED.search(text):
                    bad.append("%s:%d %s" % (rel, line, text))
        self.assertEqual(bad, [], "汉字挨着字母了，中间补一个空格（照「保存 API 设置」写）：\n" + "\n".join(bad))

    def test_no_full_width_symbols_in_names(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in buttons(_parse(body)):
                hit = [ch for ch in FULLWIDTH if ch in text]
                if hit:
                    bad.append("%s:%d %s（%s）" % (rel, line, text, "、".join(hit)))
        self.assertEqual(bad, [], "按钮名里别混全角符号：\n" + "\n".join(bad))

    def test_names_have_no_stray_spaces(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in buttons(_parse(body)):
                if text != text.strip() or "  " in text:
                    bad.append("%s:%d %r" % (rel, line, text))
        self.assertEqual(bad, [], "按钮名首尾和中间都不要多余空格：\n" + "\n".join(bad))

    def test_names_stay_short_enough_to_read(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in buttons(_parse(body)):
                if fixed_chars(text) > BUTTON_CHARS:
                    bad.append("%s:%d（%d 字）%s" % (rel, line, fixed_chars(text), text))
        self.assertEqual(bad, [], "按钮名超过 %d 个字，把说明挪到旁边的提示文字里：\n%s"
                         % (BUTTON_CHARS, "\n".join(bad)))


class OneActionOneNameTests(unittest.TestCase):
    """第 48 期第 3 条：同一个动作在所有页面只留一个名字。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = shared_sources()

    def test_every_action_keeps_only_its_one_name(self):
        whole = "\n".join(self.sources.values())
        for canonical, legacy in ONE_NAME:
            self.assertIn(canonical, whole, "「%s」这个名字一处都没用上，是不是又被改回去了" % canonical)
            for old in legacy:
                self.assertNotIn(old, whole, "「%s」已经统一叫「%s」，别再冒出旧写法" % (old, canonical))

    def test_directories_are_called_directories(self):
        """目录就叫目录：按钮名和弹窗里不再冒出「文件夹」这种另一种叫法。"""
        bad = []
        for rel, body in sorted(self.sources.items()):
            tree = _parse(body)
            for line, text in buttons(tree) + popups(tree):
                if ENTRY_WORD[1] in text:
                    bad.append("%s:%d %s" % (rel, line, text.replace("\n", "\\n")))
        self.assertEqual(bad, [], "统一用「%s」，「%s」别再出现：\n%s"
                         % (ENTRY_WORD[0], ENTRY_WORD[1], "\n".join(bad)))


# 第 68 期任务 2：三虎的每一句都是对用户说的，所以用第二人称「您」。
# 下面这些是第三人称的典型写法（用户原话：不该说「停下等人确认」，要说「等您确认」）；
# 只在字符串常量里查——注释和 docstring 是对开发者说的，不算。
NO_SECOND_PERSON = ("等人确认", "等人处理", "等人点", "等人做", "转人工",
                    "人工确认", "人工验收", "人工制作", "人工处理",
                    "不打扰用户", "用户已在", "用户从控制台", "用户指定")


@functools.lru_cache(maxsize=None)
def literals(tree):
    """这个文件里所有会被用户看到的字符串常量（docstring 除外）：[(行号, 文字)]。"""
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            docstrings.add(id(body[0].value))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and re.search(HAN, node.value):
            found.append((node.lineno, node.value))
    return found


class PetVoiceTests(unittest.TestCase):
    """第 68 期任务 2：三虎所有对话都是对用户说的，用第二人称「您」。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = shared_sources()

    def test_the_scan_still_catches_the_wording(self):
        total = sum(len(literals(_parse(body))) for body in self.sources.values())
        self.assertGreater(total, 2000, "字符串常量只数到 %d 条，扫描多半失效了" % total)

    def test_nothing_talks_about_the_user_in_third_person(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            for line, text in literals(_parse(body)):
                for phrase in NO_SECOND_PERSON:
                    if phrase in text:
                        bad.append("%s:%d（%s）%s"
                                   % (rel, line, phrase, text.replace("\n", "\\n")[:80]))
        self.assertEqual(bad, [], "三虎是对用户说话，改成第二人称「等您…」：\n" + "\n".join(bad))


# 第 68 期任务 10：界面文案一律第二人称「您」。下面这三个文件是「写给模型／Agent 的提示词」，
# 里面的「你」指的是模型自己，不是用户，所以只在它们身上放行；以后再加这类提示词，把文件补进来。
PROMPT_FILES = ("infra/pet_llm.py", "infra/continuity_ledger.py", "orchestrator/workflow_tasks.py",
                "domain/voice_ai.py")




class SecondPersonTests(unittest.TestCase):
    """第 68 期任务 10：对用户说话用「您」，别用「你」。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = shared_sources()

    def test_the_prompt_files_still_say_you(self):
        total = sum(1 for rel, body in self.sources.items() if rel in PROMPT_FILES
                    for _line, text in literals(_parse(body)) if "你" in text)
        self.assertGreater(total, 0, "提示词文件里一条「你」都数不到，扫描多半失效了")

    def test_interface_copy_speaks_to_you_with_the_polite_pronoun(self):
        bad = []
        for rel, body in sorted(self.sources.items()):
            if rel in PROMPT_FILES:
                continue
            for line, text in literals(_parse(body)):
                if "你" in text:
                    bad.append("%s:%d %s" % (rel, line, text.splitlines()[0][:80]))
        self.assertEqual(bad, [], "对用户说话用「您」，只有 %s 里的「你」是指模型：\n%s"
                         % ("、".join(PROMPT_FILES), "\n".join(bad)))


class ScanScopeTests(unittest.TestCase):
    """扫描范围：被版本库忽略的运行时数据不查；git 不在或不认这个目录时退化为全扫。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="文案规则_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _write(self, rel, text="x = 1\n"):
        path = Path(self.tmp) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _git(self, *args, cwd=None):
        subprocess.run(["git", *args], cwd=cwd or self.tmp, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _init_repo(self):
        self._git("init")
        self._write(".gitignore", "运行数据/\n")
        self._write("运行数据/回收/旧脚本.py")
        self._write("界面.py")
        self._write("新写未入库.py")

    def test_1_ignored_paths_are_skipped(self):
        self._init_repo()
        sources = program_sources(self.tmp)
        self.assertEqual(set(sources), {"界面.py", "新写未入库.py"},
                         ".gitignore 忽略的运行时数据不该进扫描：" + repr(sorted(sources)))

    def test_2_embedded_repo_is_still_scanned(self):
        self._init_repo()
        nested = Path(self.tmp) / "内嵌仓库"
        nested.mkdir()
        self._git("init", cwd=str(nested))
        self._write("内嵌仓库/工具.py")
        sources = program_sources(self.tmp)
        self.assertIn("内嵌仓库/工具.py", sources,
                      "内嵌仓库没进版本库也没被忽略，必须继续扫")

    def test_3_non_repo_directory_returns_everything(self):
        folder = tempfile.mkdtemp(prefix="文案规则_非仓库_")
        self.addCleanup(shutil.rmtree, folder, True)
        Path(folder, "界面.py").write_text("x = 1\n", encoding="utf-8")
        Path(folder, "子目录").mkdir()
        Path(folder, "子目录", "工具.py").write_text("x = 1\n", encoding="utf-8")
        sources = program_sources(folder)
        self.assertEqual(set(sources), {"界面.py", "子目录/工具.py"})

    def test_4_missing_git_returns_everything(self):
        folder = tempfile.mkdtemp(prefix="文案规则_无git_")
        self.addCleanup(shutil.rmtree, folder, True)
        Path(folder, "界面.py").write_text("x = 1\n", encoding="utf-8")
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("git")):
            sources = program_sources(folder)
        self.assertEqual(set(sources), {"界面.py"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
