"""账号表单用的两种输入框：

- ``EmailInput``：左边填账号，右边是可下拉的邮箱后缀（@qq.com 等主流邮箱，也可自己改）。
  ``get()`` 返回拼好的完整邮箱；整串地址（含 ``@``）粘进账号框或 ``insert`` 时会自动拆开。
- ``PasswordInput``：密码框，右侧一个小图标按钮切换明文／遮挡。
两者对外保持 ``LineInput`` 的用法（get／insert／delete／set_error／clear_error／bind／cget）。
"""
from tkinter import ttk

from ui_tokens import SPACING
from ui_widgets import LineInput, SecondaryButton, SelectBox

PASSWORD_MASK = '•'
PASSWORD_SHOWN_ICON, PASSWORD_HIDDEN_ICON = '🙈', '👁'      # 明文显示中／遮挡中（按钮上画的是点一下会变成的另一种）

EMAIL_SUFFIXES = ('@qq.com', '@163.com', '@126.com', '@gmail.com', '@outlook.com',
                  '@foxmail.com', '@hotmail.com', '@sina.com', '@icloud.com', '@yeah.net')


class EmailInput(ttk.Frame):
    def __init__(self, master=None, *, placeholder='邮箱账号', suffixes=EMAIL_SUFFIXES, **kwargs):
        super().__init__(master, **kwargs)
        self.local = LineInput(self, placeholder=placeholder)
        self.local.pack(side='left', fill='x', expand=True)
        self.suffix = SelectBox(self, values=suffixes, state='normal')
        self.suffix.set(suffixes[0])
        self.suffix.pack(side='left', padx=(SPACING['xs'], SPACING['none']))

    @property
    def error_message(self):
        return self.local.error_message

    def get(self):
        local = self.local.get().strip()
        if not local or '@' in local:
            return local
        suffix = self.suffix.get().strip()
        return local + (suffix if suffix.startswith('@') or not suffix else '@' + suffix)

    def insert(self, index, string):
        string = str(string)
        if '@' in string:
            local, _, domain = string.rpartition('@')
            self.local.delete(0, 'end')
            self.local.insert(0, local)
            self.suffix.set('@' + domain)
            return None
        return self.local.insert(index, string)

    def delete(self, first, last=None):
        return self.local.delete(first, last)

    def set_error(self, message=''):
        self.local.set_error(message)

    def clear_error(self):
        self.local.clear_error()

    def focus_set(self):
        self.local.focus_set()


class PasswordInput(ttk.Frame):
    def __init__(self, master=None, *, placeholder='', mask=PASSWORD_MASK, **entry_options):
        super().__init__(master)
        self.mask = mask
        self.local = LineInput(self, placeholder=placeholder, mask=mask, **entry_options)
        self.local.pack(side='left', fill='x', expand=True)
        self.shown = False
        self.toggle_button = SecondaryButton(self, text=PASSWORD_HIDDEN_ICON, takefocus=False,
                                             command=self.toggle)
        self.toggle_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))

    def toggle(self):
        self.shown = not self.shown
        self.local.set_mask('' if self.shown else self.mask)
        self.toggle_button.configure(text=PASSWORD_SHOWN_ICON if self.shown else PASSWORD_HIDDEN_ICON)

    @property
    def error_message(self):
        return self.local.error_message

    def get(self):
        return self.local.get()

    def insert(self, index, string):
        return self.local.insert(index, string)

    def delete(self, first, last=None):
        return self.local.delete(first, last)

    def set_error(self, message=''):
        self.local.set_error(message)

    def clear_error(self):
        self.local.clear_error()

    def cget(self, key):
        return self.local.cget(key) if key == 'show' else super().cget(key)

    def bind(self, sequence=None, func=None, add=None):
        return self.local.bind(sequence, func, add)

    def focus_set(self):
        self.local.focus_set()
