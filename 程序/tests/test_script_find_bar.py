"""REQ-S02-36（R2）：单框查找替换条——纯函数命中位置＋真 Tk 查找/替换链路。

``_search_positions`` 无 Tk 可测；``FindBar`` 挂在真 ``tk.Text`` 上验证
上一个/下一个循环、大小写选项、单个/全部替换、计数与 ``Esc`` 关闭。
"""
import sys
import time
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from script_find_bar import FindBar, _search_positions
from ui_widgets import TextArea


def _settle(widget, iterations=6):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.02)


def _sel(preview):
    """``tag_ranges`` 返回 textindex 对象；统一转成字符串再比较。"""
    return tuple(str(index) for index in preview.tag_ranges('sel'))


class SearchPositionsTests(unittest.TestCase):
    def test_positions_offsets_and_order(self):
        """REQ-S02-36：返回左闭右开字符偏移，按出现顺序、不重叠。"""
        self.assertEqual(_search_positions('ab cd ab', 'ab'), [(0, 2), (6, 8)])
        self.assertEqual(_search_positions('aaaa', 'aa'), [(0, 2), (2, 4)])
        self.assertEqual(_search_positions('nothing', 'x'), [])
        self.assertEqual(_search_positions('', 'a'), [])
        self.assertEqual(_search_positions('abc', ''), [])
        self.assertEqual(_search_positions('a\nb\na', 'a'), [(0, 1), (4, 5)])

    def test_case_option(self):
        """REQ-S02-36：默认区分大小写；``nocase=True`` 忽略大小写。"""
        text = 'Alpha ALPHA alpha'
        self.assertEqual(_search_positions(text, 'alpha'), [(12, 17)])
        self.assertEqual(_search_positions(text, 'alpha', nocase=True),
                         [(0, 5), (6, 11), (12, 17)])
        self.assertEqual(_search_positions(text, 'ALPHA'), [(6, 11)])
        self.assertEqual(_search_positions(text, 'ALPHA', nocase=True),
                         [(0, 5), (6, 11), (12, 17)])


class FindBarTests(unittest.TestCase):
    def _make(self, text, state='normal'):
        root = tk.Tk()
        root.geometry('500x300+40+40')
        root.deiconify()
        root.update()

        def _destroy():
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass
        self.addCleanup(_destroy)
        # 同一 master 只能用一个几何管理器：preview 与 FindBar 都走 grid。
        area = tk.Frame(root)
        area.pack(fill='both', expand=True)
        area.rowconfigure(1, weight=1)
        area.columnconfigure(0, weight=1)
        preview = TextArea(area, wrap='word', undo=True, font=('Microsoft YaHei UI', 10))
        preview.grid(row=1, column=0, sticky='nsew')
        preview.insert('1.0', text)
        preview.configure(state=state)
        notices = []
        bar = FindBar(area, preview, notify=notices.append)
        # 与生产一致：FindBar 由 grid 管理，show()/hide() 走 grid_remove/grid。
        bar.grid(row=0, column=0, sticky='ew')
        bar.grid_remove()
        _settle(root)
        return root, preview, bar, notices

    def _keyword(self, bar, text):
        bar.keyword.delete(0, 'end')
        bar.keyword.insert(0, text)

    def test_find_next_prev_wrap_and_count(self):
        """REQ-S02-36：下一个/上一个循环命中，计数与 sel 高亮正确。"""
        root, preview, bar, _n = self._make('alpha 中段 beta alpha 尾 alpha')
        self._keyword(bar, 'alpha')
        self.assertTrue(bar.find_next())
        self.assertEqual(_sel(preview), ('1.0', '1.5'))
        self.assertEqual(bar.count_var.get(), '第 1/3 个')
        bar.find_next()
        self.assertEqual(_sel(preview), ('1.14', '1.19'))
        bar.find_next()
        self.assertEqual(_sel(preview), ('1.22', '1.27'))
        bar.find_next()   # 回绕到第一个
        self.assertEqual(_sel(preview), ('1.0', '1.5'))
        bar.find_prev()   # 回绕到最后一个
        self.assertEqual(_sel(preview), ('1.22', '1.27'))
        self.assertEqual(bar.count_var.get(), '第 3/3 个')

    def test_case_sensitive_toggle(self):
        """REQ-S02-36：默认不敏感匹配全部大小写；勾选 Aa 后只匹配同大小写。"""
        root, preview, bar, _n = self._make('Alpha ALPHA alpha')
        self._keyword(bar, 'ALPHA')
        bar.find_next()
        self.assertEqual(_sel(preview), ('1.0', '1.5'))
        self.assertEqual(bar.count_var.get(), '第 1/3 个')
        bar.sensitive.set(True)
        bar.find_next()   # 敏感后只剩 ALPHA 一处
        self.assertEqual(_sel(preview), ('1.6', '1.11'))
        self.assertEqual(bar.count_var.get(), '第 1/1 个')
        self._keyword(bar, 'alpha')
        bar.find_next()
        self.assertEqual(_sel(preview), ('1.12', '1.17'))

    def test_no_match_reports_and_clears(self):
        """REQ-S02-36：无命中时提示并计数归零。"""
        root, preview, bar, notices = self._make('只有正文')
        self._keyword(bar, '不存在')
        self.assertFalse(bar.find_next())
        self.assertEqual(bar.count_var.get(), '未找到')
        self.assertTrue(notices and '不存在' in notices[-1])

    def test_replace_one_and_all_in_edit_state(self):
        """REQ-S02-36：编辑态下单个替换与替换全部真实改文本并计数。"""
        root, preview, bar, notices = self._make('甲乙 甲丙 甲丁', state='normal')
        self._keyword(bar, '甲')
        bar.replacement.delete(0, 'end')
        bar.replacement.insert(0, 'X')
        self.assertEqual(bar.replace_one(), 1)
        _settle(root)
        self.assertIn('X乙', preview.get('1.0', 'end'))
        self.assertEqual(bar.replace_all(), 2)
        _settle(root)
        text = preview.get('1.0', 'end-1c')
        self.assertEqual(text, 'X乙 X丙 X丁')
        self.assertTrue(any('2' in message for message in notices))

    def test_replace_blocked_when_readonly(self):
        """REQ-S02-36：只读态拒绝替换并提示先进入编辑。"""
        root, preview, bar, notices = self._make('甲乙甲', state='disabled')
        self._keyword(bar, '甲')
        bar.replacement.insert(0, 'X')
        self.assertEqual(bar.replace_one(), 0)
        self.assertEqual(bar.replace_all(), 0)
        self.assertEqual(preview.get('1.0', 'end-1c'), '甲乙甲')
        self.assertTrue(any('编辑' in message for message in notices))

    def test_00_esc_and_entry_return_close_or_find(self):
        """REQ-S02-36：Esc 关闭查找条；Enter 触发下一个。

        本文件按名字排序第一个创建 Tk 的用例：隐藏桌面里第二个及以后
        解释器无法合成按键事件，故带 ``event_generate`` 的用例排在最前。
        """
        root, preview, bar, _n = self._make('aa bb aa')
        self._keyword(bar, 'aa')
        bar.show()
        _settle(root)
        self.assertTrue(bar.visible)
        # 合成按键要落在焦点控件上；高负载下焦点与事件投递都会延迟，
        # 确认焦点后重发直到生效（hide 幂等，重复 Esc 无害）。
        for _ in range(12):
            bar.keyword.focus_set()
            _settle(root, 2)
            bar.keyword.event_generate('<Escape>', when='now')
            _settle(root, 2)
            if not bar.visible:
                break
        self.assertFalse(bar.visible)
        bar.show()
        for _ in range(12):
            bar.keyword.focus_set()
            _settle(root, 2)
            bar.keyword.event_generate('<Return>', when='now')
            _settle(root, 2)
            if _sel(preview):
                break
        self.assertEqual(_sel(preview), ('1.0', '1.2'))


if __name__ == '__main__':
    unittest.main()
