# -*- coding: utf-8 -*-
"""云端视频会话与标签纯逻辑自检。"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cloud_video import PROVIDERS, provider_label, saved_provider_key, session_folder, settings_window


def _gateway():
    from agent.core import save
    return {"publish_json": save}


class ProviderLabelTests(unittest.TestCase):
    def test_wan(self):
        self.assertEqual(provider_label({"cloud_provider": "wan", "base_url": "https://dashscope.aliyuncs.com/api/v1"}), "阿里云百炼 · 万相")

    def test_seedance(self):
        self.assertEqual(provider_label({"cloud_provider": "volcengine", "base_url": "https://ark.cn-beijing.volces.com/api/v3"}), "火山引擎 · Seedance")

    def test_custom_wan(self):
        self.assertEqual(provider_label({"cloud_provider": "wan", "base_url": "https://custom.com/v1"}), "自定义 · 万相兼容")

    def test_empty(self):
        self.assertEqual(provider_label({}), "阿里云百炼 · 万相")


class SessionFolderTests(unittest.TestCase):
    def make(self, td):
        proj = Path(td) / "p"
        (proj / "cloud_video").mkdir(parents=True)
        source = proj / "episode.json"
        source.write_text("{}", encoding="utf-8")
        return proj, source

    def test_dedup_same_config(self):
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            f1 = session_folder(proj, "wan", "https://x.com/v1", "m1", source)
            f1.mkdir(parents=True, exist_ok=True)
            (f1 / "config.json").write_text(json.dumps({"cloud_provider": "wan", "base_url": "https://x.com/v1", "model": "m1", "episode_file": str(source)}), encoding="utf-8")
            self.assertEqual(f1, session_folder(proj, "wan", "https://x.com/v1", "m1", source))

    def test_different_model_new_folder(self):
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            f1 = session_folder(proj, "wan", "https://x.com/v1", "m1", source)
            f1.mkdir(parents=True, exist_ok=True)
            (f1 / "config.json").write_text(json.dumps({"cloud_provider": "wan", "base_url": "https://x.com/v1", "model": "m1", "episode_file": str(source)}), encoding="utf-8")
            self.assertNotEqual(f1, session_folder(proj, "wan", "https://x.com/v1", "m2", source))

    def test_corrupt_session_config_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            bad = proj / "cloud_video" / "bad"
            bad.mkdir(parents=True, exist_ok=True)
            (bad / "config.json").write_text("[]", encoding="utf-8")
            self.assertNotEqual(session_folder(proj, "wan", "https://x.com/v1", "m1", source), bad)


class SessionPublicationTests(unittest.TestCase):
    def test_publication_requires_l3_gateway(self):
        from cloud_video_service import publish_studio_config
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, "L3"):
                publish_studio_config(Path(td) / 'config.json', {'model': 'm1'})

    def test_publishes_config_and_workspace_preference(self):
        from cloud_video_service import publish_session_config
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            publish_session_config(root / 'session' / 'config.json', {'model': 'm1'},
                                   root / 'ui_settings.json', {'cloud_video_workspace': 'cloud_video/session'}, gateway=_gateway())
            self.assertEqual(json.loads((root / 'session' / 'config.json').read_text(encoding='utf-8'))['model'], 'm1')
            self.assertEqual(json.loads((root / 'ui_settings.json').read_text(encoding='utf-8'))['cloud_video_workspace'], 'cloud_video/session')

    def test_publishes_studio_config(self):
        from cloud_video_service import publish_studio_config
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'config.json'
            publish_studio_config(path, {'model': 'test-model', 'live_enabled': True}, gateway=_gateway())
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'model': 'test-model', 'live_enabled': True})


class ProviderKeyTests(unittest.TestCase):
    def test_new_session_reads_the_model_pool_before_legacy_env(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.named_key', return_value='sk-encrypted') as named:
            value=saved_provider_key(Path(td), 'wan', {'key_provider':'model_pool'})
        self.assertEqual(value, 'sk-encrypted')
        named.assert_called_once_with('DASHSCOPE_API_KEY')


class KeyEntryPrivacyTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk();self.root.withdraw()
        except tk.TclError:
            self.skipTest(PLATFORM_TKINTER)
        self.addCleanup(self.root.destroy)

    def test_saved_key_stays_hidden_until_explicit_short_reveal(self):
        # 1ms 在安全全量的 Tk 事件调度下可能在首个 update 前就已到期，
        # 使“已短暂显示”断言随机失去观察窗口；保留自动回藏契约，
        # 仅给首个断言一个稳定的事件循环窗口。
        with (tempfile.TemporaryDirectory() as td,
              patch('cloud_video.saved_provider_key', return_value='sk-kept'),
              patch('cloud_video.KEY_REVEAL_MS', 100)):
            project=Path(td);source=project/'episode.json';source.write_text('{}',encoding='utf-8')
            desktop=SimpleNamespace(win=self.root,root=project,video=None,current_frame_json=lambda:source,
                                    cloud_settings_window=None)
            settings_window(desktop);self.root.update()
            win=desktop.cloud_settings_window
            key=next(widget for widget in win.winfo_children()
                     if str(widget.winfo_class())=='TEntry' and str(widget.grid_info().get('row'))=='3')
            self.assertEqual(key.cget('show'),'•')
            self.assertEqual(key.get(),'')
            button=next(child for frame in win.winfo_children() if str(frame.winfo_class())=='TFrame'
                        for child in frame.winfo_children()
                        if '显示已保存密钥' in str(child.cget('text')))
            button.invoke();self.root.update()
            self.assertEqual(key.cget('show'),'')
            self.assertEqual(key.get(),'sk-kept')
            self.root.after(150,self.root.quit);self.root.mainloop()
            self.assertEqual(key.cget('show'),'•')
            self.assertEqual(key.get(),'')


if __name__ == "__main__":
    unittest.main(verbosity=2)
