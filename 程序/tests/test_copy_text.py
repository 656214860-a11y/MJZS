# -*- coding: utf-8 -*-
"""统一复制入口：互斥、可见失败与状态栏脱敏。"""
import unittest
from unittest import mock

import prompt_window


class _Owner:
    def __init__(self):
        self.value = None
    def clipboard_clear(self):
        self.value = None
    def clipboard_append(self, value):
        self.value = value
    def update_idletasks(self):
        return None


class CopyTextTests(unittest.TestCase):
    def test_writes_text_through_the_shared_entry(self):
        owner = _Owner()
        self.assertEqual(prompt_window.copy_text(owner, '待复制正文'), '')
        self.assertEqual(owner.value, '待复制正文')

    def test_busy_clipboard_is_a_visible_retryable_failure(self):
        owner = _Owner()
        with mock.patch('prompt_window.hold_clipboard') as hold:
            hold.return_value.__enter__.return_value = False
            self.assertIn('占用', prompt_window.copy_text(owner, '正文'))
        self.assertIsNone(owner.value)

    def test_status_preview_masks_credentials_but_not_normal_copy_text(self):
        text = 'api_key=secret-value sk-abcdefghijk 正文'
        self.assertNotIn('secret-value', prompt_window.copy_preview(text))
        self.assertNotIn('sk-abcdefghijk', prompt_window.copy_preview(text))
        owner = _Owner()
        self.assertEqual(prompt_window.copy_text(owner, text), '')
        self.assertEqual(owner.value, text)
