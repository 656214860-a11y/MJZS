# -*- coding: utf-8 -*-
"""行尾门禁（第 7 轮）：程序目录里不许有 CR CR LF，写入一律走「写入即校验行尾」。

第 62 期那次「启动失败，详情已保存到 启动错误.log」：`pet_ui.py` 被写文件脚本写成了
「CR CR LF」，CPython 读到只剩一个空行的那一行，抛 `SyntaxError: expected ':'`，而自检的
Tk 保护会把 `\r\n` 归一，表面上是绿的——只有双击 `.pyw` 才炸。根子只有一条：**读的时候
把 `\r` 留下来了，写的时候文本模式又翻译一次**。

这一份盯两件事：

1. 现在的盘：程序目录整棵扫一遍，文本文件不许有落单的 CR／CR CR LF、不许不是 UTF-8；
   第 62 期那批受害文件（＋ 第 7 轮门禁第一次跑时真查出来的 3 个）再单独钉住各自的行尾。
2. 以后的写入：`line_endings.write_text` 的每个分支（新文件、已有文件、坏文件修好、
   拦下不写），以及程序自己的文本写入面确实走的是它。

运行：python test_line_endings.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = Path(HERE).parent
sys.path.insert(0, str(PROGRAM))
os.chdir(PROGRAM)

import line_endings

# 第 62 期那批（README 二十四节记的四个）＋ 第 7 轮门禁第一次跑时查出来的三个。后三个当时
# 是真坏的：两个测试文件整篇 CR CR LF、体积分析那份夹了 1 处 —— 门禁上线当天就地修好，
# 行尾值钉在这儿，谁再写坏谁红。
VICTIMS = (
    ('desktop.py', line_endings.CRLF),
    ('pet_ui.py', line_endings.CRLF),
    ('README.md', line_endings.CRLF),
    ('skill_panel.py', line_endings.CRLF),
    ('tests/test_model_pool.py', line_endings.CRLF),
    ('tests/test_seedream_direct.py', line_endings.CRLF),
    ('维护记录/体积分析_20260921.md', line_endings.CRLF),
)
# 接上「写入即校验行尾」的写入点；以后新加的文本写入面往这儿补一行。
WRITERS = ('run_selftests.py', 'skill_tools.py')


class ProgramTreeTests(unittest.TestCase):
    def test_the_program_tree_has_no_cr_cr_lf(self):
        """整棵程序目录扫一遍：文本文件不许有落单的 CR／CR CR LF、不许不是 UTF-8。"""
        found = line_endings.audit(PROGRAM)
        dirty = {rel: line_endings.problems(PROGRAM / rel) for rel, info in found.items()
                 if not info['clean']}
        self.assertEqual(dirty, {}, '这些文件的行尾坏了（CR CR LF 会让双击 .pyw 直接炸）：%r' % dirty)
        self.assertGreater(len(found), 300, '扫到的文件太少（%d 个），扫描口径断了' % len(found))

    def test_the_victims_keep_their_own_line_endings(self):
        """第 62 期那批 ＋ 本轮查出来的：各自的行尾钉住，谁换了都在这儿红。"""
        for rel, eol in VICTIMS:
            with self.subTest(file=rel):
                path = PROGRAM / rel
                self.assertTrue(path.is_file(), '%s 不在（门禁的名单该跟着改）' % rel)
                self.assertEqual(line_endings.inspect(path.read_bytes())['eol'], eol,
                                 '%s 的换行符被换了' % rel)
                self.assertEqual(line_endings.problems(path), [])

    def test_the_writers_go_through_the_helper(self):
        """程序自己的文本写入面必须走 line_endings.write_text（不许再各写一套）。"""
        for name in WRITERS:
            source = (PROGRAM / name).read_text(encoding='utf-8')
            with self.subTest(file=name):
                self.assertIn('import line_endings', source, '%s 没导入 line_endings' % name)
                self.assertIn('line_endings.write_text', source,
                              '%s 没接上「写入即校验行尾」' % name)


class ComposeTests(unittest.TestCase):
    def test_every_flavour_of_line_ending_is_folded_to_the_target_one(self):
        self.assertEqual(line_endings.compose('a\r\nb\nc\rd', line_endings.LF), 'a\nb\nc\nd')
        self.assertEqual(line_endings.compose('a\r\nb\nc\rd', line_endings.CRLF),
                         'a\r\nb\r\nc\r\nd')

    def test_a_body_that_already_carries_cr_cr_lf_cannot_stay_damaged(self):
        """坏文件读进来（正文里全是 CR CR LF）再铺出去，绝不能还是 CR CR LF。"""
        body = '第一行\r\r\n第二行\r\r\n'
        self.assertEqual(line_endings.compose(body, line_endings.CRLF), '第一行\r\n第二行\r\n')

    def test_a_line_ending_that_is_neither_lf_nor_crlf_is_refused(self):
        with self.assertRaises(ValueError):
            line_endings.compose('a\nb', '\r')


class InspectTests(unittest.TestCase):
    def test_the_counts_and_the_verdict(self):
        info = line_endings.inspect(b'one\r\ntwo\nthree\r\r\nfour')
        self.assertEqual(info['crlf'], 2)
        self.assertEqual(info['double_cr'], 1)
        self.assertEqual(info['lone_cr'], 1)
        self.assertEqual(info['lf'], 1)
        self.assertFalse(info['clean'])
        self.assertEqual(info['eol'], line_endings.CRLF)

    def test_clean_files_read_clean(self):
        for raw in (b'a\r\nb\r\n', b'a\nb\n', b'', b'single line'):
            with self.subTest(raw=raw):
                self.assertTrue(line_endings.inspect(raw)['clean'])

    def test_a_cr_only_file_is_not_clean_and_reads_as_lf(self):
        info = line_endings.inspect(b'a\rb\r')
        self.assertFalse(info['clean'])
        self.assertEqual(info['lone_cr'], 2)
        self.assertEqual(info['eol'], line_endings.LF)


class WriteTests(unittest.TestCase):
    def test_a_new_file_lands_as_crlf_without_any_cr_cr_lf(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / '新文件.py'
            self.assertEqual(line_endings.write_text(path, '第一行\n第二行\n'), line_endings.CRLF)
            self.assertEqual(path.read_bytes(), '第一行\r\n第二行\r\n'.encode('utf-8'))
            self.assertNotIn(b'\r\r\n', path.read_bytes())
            self.assertFalse((Path(td) / '新文件.py.tmp').exists(), '临时文件要收干净')

    def test_an_existing_file_keeps_its_own_line_endings(self):
        with tempfile.TemporaryDirectory() as td:
            lf = Path(td) / 'lf.py'; lf.write_bytes(b'a\nb\n')
            crlf = Path(td) / 'crlf.py'; crlf.write_bytes(b'a\r\nb\r\n')
            line_endings.write_text(lf, '一\n二\n')
            line_endings.write_text(crlf, '一\n二\n')
            self.assertEqual(lf.read_bytes(), '一\n二\n'.encode('utf-8'))
            self.assertEqual(crlf.read_bytes(), '一\r\n二\r\n'.encode('utf-8'))

    def test_a_body_mixing_both_flavours_comes_out_with_one_flavour_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'mixed.py'; path.write_bytes(b'a\r\nb\r\n')
            line_endings.write_text(path, '一\r\n二\n三\r四')
            self.assertEqual(path.read_bytes(), '一\r\n二\r\n三\r\n四'.encode('utf-8'))
            self.assertNotIn(b'\r\r', path.read_bytes())

    def test_a_damaged_file_is_repaired_by_read_then_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'broken.py'
            path.write_bytes('第一行\r\r\n第二行\r\r\n'.encode('utf-8'))
            self.assertTrue(line_endings.problems(path), '坏文件要看得出来')
            text, eol = line_endings.read_text(path)
            self.assertEqual(eol, line_endings.CRLF)
            self.assertEqual(text, '第一行\n第二行\n')
            line_endings.write_text(path, text, eol)
            self.assertEqual(line_endings.problems(path), [])
            self.assertEqual(path.read_bytes(), '第一行\r\n第二行\r\n'.encode('utf-8'))

    def test_a_bad_line_ending_argument_leaves_the_file_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'keep.py'
            path.write_bytes(b'keep\r\n')
            with self.assertRaises(ValueError):
                line_endings.write_text(path, '换掉\n', eol='\r')
            self.assertEqual(path.read_bytes(), b'keep\r\n')
            self.assertFalse((Path(td) / 'keep.py.tmp').exists())


class AuditTests(unittest.TestCase):
    def test_the_audit_only_picks_up_text_and_flags_damage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'ok.py').write_bytes(b'a\n')
            (root / 'bad.md').write_bytes(b'a\r\r\n')
            (root / '图.png').write_bytes(b'\x89PNG\r\r\n')
            (root / '__pycache__').mkdir()
            (root / '__pycache__' / 'x.py').write_bytes(b'a\r\r\n')
            found = line_endings.audit(root)
            self.assertEqual(sorted(found), ['bad.md', 'ok.py'])
            self.assertEqual([rel for rel, info in found.items() if not info['clean']], ['bad.md'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
