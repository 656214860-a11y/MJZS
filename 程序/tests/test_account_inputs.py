"""R2054：邮箱框 = 左边填账号 + 右边可下拉的后缀（@qq.com 等）；密码框右侧有显示／隐藏明文的图标按钮。"""
import unittest

import tk_test_support
from account_inputs import EMAIL_SUFFIXES, PASSWORD_MASK, EmailInput, PasswordInput


class EmailInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def make(self):
        box = EmailInput(self.win)
        self.addCleanup(box.destroy)
        return box

    def test_account_part_plus_default_suffix_makes_the_address(self):
        box = self.make()
        self.assertEqual(box.get(), '', '没填账号：整框算空，不会只剩一个后缀')
        box.local.insert(0, ' 10001 ')
        self.assertEqual(box.get(), '10001' + EMAIL_SUFFIXES[0])
        box.suffix.set('@163.com')
        self.assertEqual(box.get(), '10001@163.com')

    def test_suffix_list_offers_mainstream_mailboxes_and_stays_editable(self):
        box = self.make()
        values = tuple(box.suffix.cget('values'))
        for suffix in ('@qq.com', '@163.com', '@gmail.com', '@outlook.com'):
            self.assertIn(suffix, values)
        box.suffix.set('corp.example.com')
        box.local.insert(0, 'me')
        self.assertEqual(box.get(), 'me@corp.example.com', '自己敲的后缀漏了 @ 也补上')

    def test_full_address_is_split_on_insert_and_kept_when_pasted(self):
        box = self.make()
        box.insert(0, 'a@b.cn')
        self.assertEqual((box.local.get(), box.suffix.get(), box.get()), ('a', '@b.cn', 'a@b.cn'))
        box.delete(0, 'end')
        box.local.insert(0, 'x@y.org')       # 整串地址直接粘进账号框：原样使用，不再拼后缀
        self.assertEqual(box.get(), 'x@y.org')

    def test_error_marking_goes_to_the_account_part(self):
        box = self.make()
        self.assertFalse(box.error_message)
        box.set_error('邮箱格式不正确')
        self.assertEqual(box.error_message, '邮箱格式不正确')
        box.clear_error()
        self.assertFalse(box.error_message)


class PasswordInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def test_icon_button_toggles_plain_text_and_back(self):
        box = PasswordInput(self.win, placeholder='密码')
        self.addCleanup(box.destroy)
        self.assertEqual(str(box.cget('show')), '', '占位文字不被遮挡')
        box.insert(0, 'abc12345')
        self.assertEqual(str(box.cget('show')), PASSWORD_MASK, '默认遮挡')
        icon_hidden = box.toggle_button.cget('text')
        box.toggle_button.invoke()
        self.assertEqual(str(box.cget('show')), '', '点一下显示明文')
        self.assertNotEqual(box.toggle_button.cget('text'), icon_hidden, '图标随状态换')
        self.assertEqual(box.get(), 'abc12345', '切换不改内容')
        box.toggle_button.invoke()
        self.assertEqual(str(box.cget('show')), PASSWORD_MASK)
        self.assertEqual(box.toggle_button.cget('text'), icon_hidden)

    def test_errors_and_bindings_go_to_the_entry(self):
        box = PasswordInput(self.win, placeholder='密码')
        self.addCleanup(box.destroy)
        hits = []
        box.bind('<Return>', lambda event: hits.append(1))
        box.local.event_generate('<Return>')
        box.set_error('请填写密码')
        self.assertEqual(box.error_message, '请填写密码')
        box.clear_error()
        self.assertFalse(box.error_message)

    def test_password_toggle_uses_clean_text_and_email_suffix_is_compact(self):
        """UX-LOGIN-CLEAN：密码显隐钮为无框文字按钮且不含 emoji；邮箱后缀框紧凑定宽 CHAR_WIDTH['xl']。"""
        from ui_tokens import CHAR_WIDTH
        box = PasswordInput(self.win, placeholder='密码')
        self.addCleanup(box.destroy)
        self.assertEqual(str(box.toggle_button.cget('style')), 'Tokens.Text.TButton')
        for _ in range(2):
            text = str(box.toggle_button.cget('text'))
            self.assertTrue(text)
            self.assertTrue(all(ord(ch) < 0x1F000 for ch in text), f'密码切换钮不应含 emoji：{text!r}')
            box.toggle_button.invoke()
        email = EmailInput(self.win)
        self.addCleanup(email.destroy)
        self.assertEqual(int(str(email.suffix.cget('width'))), CHAR_WIDTH['xl'])


if __name__ == '__main__':
    unittest.main()
