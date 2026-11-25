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
from unittest.mock import Mock, patch
from contract.service_contract import SystemError

from cloud_video import PROVIDERS, provider_label, saved_provider_key, session_folder, settings_window
from image_fixtures import png


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

    def test_custom_seedance_and_official_trailing_slashes(self):
        for label, (kind, base, _, _) in PROVIDERS.items():
            config = {'cloud_provider': kind, 'base_url': base + '/' if base else 'https://custom.example.test/v1'}
            with self.subTest(label=label):
                self.assertEqual(provider_label(config), label)


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
            result = publish_session_config(root / 'session' / 'config.json', {'model': 'm1'},
                                   root / 'ui_settings.json', {'cloud_video_workspace': 'cloud_video/session'}, gateway=_gateway())
            self.assertTrue(result.ok)
            self.assertEqual(json.loads((root / 'session' / 'config.json').read_text(encoding='utf-8'))['model'], 'm1')
            self.assertEqual(json.loads((root / 'ui_settings.json').read_text(encoding='utf-8'))['cloud_video_workspace'], 'cloud_video/session')

    def test_second_write_failure_restores_existing_or_absent_session_config(self):
        from agent.core import save
        from orchestrator import stage_gate_gateways as gateways
        for existing in (True, False):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as td:
                config, prefs = Path(td) / 'config.json', Path(td) / 'ui_settings.json'
                save(prefs, {'workspace': 'old'})
                if existing:
                    save(config, {'model': 'old'})
                def publish(path, data):
                    if path == prefs:
                        raise OSError('模拟写失败')
                    save(path, data)
                with patch.object(gateways, 'cloud_video_gateway', return_value={'publish_json': publish}):
                    with self.assertRaises(ValueError):
                        gateways.publish_cloud_video_session_config(config, {'model': 'new'}, prefs, {})
                self.assertEqual(json.loads(prefs.read_text(encoding='utf-8')), {'workspace': 'old'})
                self.assertEqual(config.exists(), existing)
                if existing:
                    self.assertEqual(json.loads(config.read_text(encoding='utf-8')), {'model': 'old'})

    def test_publishes_studio_config(self):
        from cloud_video_service import publish_studio_config
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'config.json'
            result = publish_studio_config(path, {'model': 'test-model', 'live_enabled': True}, gateway=_gateway())
            self.assertTrue(result.ok)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'model': 'test-model', 'live_enabled': True})


class CloudResultTests(unittest.TestCase):
    def test_configuration_errors_are_classified_at_each_publish(self):
        import cloud_video_service as service
        calls = [(service.publish_session_config, ('config.json', {}, 'prefs.json', {}), 2),
                 (service.publish_workspace_preference, ('prefs.json', {}), 1),
                 (service.publish_studio_config, ('config.json', {}), 1)]
        for function, args, count in calls:
            self.assertTrue(function(*args, gateway={'publish_json': Mock()}).ok)
            for index in range(count):
                publisher = Mock(side_effect=[None] * index + [OSError('private detail')])
                with self.subTest(function=function.__name__, index=index), self.assertLogs('cloud_video_service', level='ERROR'):
                    result = function(*args, gateway={'publish_json': publisher})
                self.assertIsInstance(result, SystemError)
                self.assertIsNone(result.data)
                self.assertNotIn('private detail', result.reason)
                self.assertEqual(index + 1, publisher.call_count)
            with self.assertRaises(TypeError):
                function(*args, gateway={'publish_json': Mock(side_effect=TypeError('bug'))})

    def test_session_directory_failure_does_not_deliver_path(self):
        from cloud_video_service import session_folder as service_folder
        from stage_execution_service import project_context
        args = (project_context('project'), 'wan', 'https://example.test', 'model', 'source.json')
        with patch('pathlib.Path.mkdir', side_effect=OSError('private detail')):
            with self.assertLogs('cloud_video_service', level='ERROR'):
                result = service_folder(*args)
            self.assertIsInstance(result, SystemError)
            self.assertIsNone(result.data)
            with self.assertLogs('cloud_video_service', level='ERROR'), self.assertRaises(ValueError):
                session_folder('project', *args[1:])
        with patch('pathlib.Path.mkdir', side_effect=TypeError('bug')), self.assertRaises(TypeError):
            service_folder(*args)

    def test_l3_configuration_wrappers_reject_failed_results(self):
        import stage_execution_service as stage
        for name, args in [('session_config', ('config', {}, 'prefs', {})),
                           ('workspace_preference', ('prefs', {})), ('studio_config', ('config', {}))]:
            with self.subTest(name=name), patch('cloud_video_service.publish_' + name, return_value=SystemError('保存失败')):
                with self.assertRaisesRegex(ValueError, '保存失败'):
                    getattr(stage, 'publish_cloud_video_' + name)(*args)


class ProviderKeyTests(unittest.TestCase):
    def test_new_session_reads_the_model_pool_before_legacy_env(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.named_key', return_value='sk-encrypted') as named:
            value=saved_provider_key(Path(td), 'wan', {'key_provider':'model_pool'})
        self.assertEqual(value, 'sk-encrypted')
        named.assert_called_once_with('DASHSCOPE_API_KEY')

    def test_legacy_session_key_fallback_is_read_only_and_host_bound(self):
        from secret_store_support import isolate_secret_store
        isolate_secret_store(self)
        for label, (kind, base, _, key_name) in PROVIDERS.items():
            if not base:
                continue
            for remembered in (False, True):
                with self.subTest(provider=label, remembered=remembered), tempfile.TemporaryDirectory() as td:
                    project = Path(td) / 'project'
                    session = project / 'cloud_video' / 'saved'
                    session.mkdir(parents=True)
                    env = session / '.env'
                    env.write_text('# isolated fixture only\n' + key_name + '=FAKE_TEST_VALUE\n', encoding='utf-8')
                    config = {'cloud_provider': kind, 'base_url': base + '/', 'project_dir': str(session)}
                    config_path = session / 'config.json'
                    config_path.write_text(json.dumps(config), encoding='utf-8')
                    before = {path: path.read_bytes() for path in (config_path, env)}
                    # Keep the compatibility fallback inside the fixture, never real private/.
                    with (patch('model_pool.named_key', return_value='') as named,
                          patch('cloud_video.__file__', str(Path(td) / 'app' / 'cloud_video.py'))):
                        self.assertEqual(saved_provider_key(project, kind, config if remembered else None, base),
                                         'FAKE_TEST_VALUE')
                        self.assertEqual(saved_provider_key(project, kind, config, 'https://other.example.test/v1'), '')
                    self.assertEqual(named.call_args_list, [((key_name,),), ((key_name,),)])
                    self.assertEqual({path: path.read_bytes() for path in before}, before)


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
            body=next(widget for widget in win.winfo_children()
                      if widget.grid_slaves(row=3,column=1))
            key=body.grid_slaves(row=3,column=1)[0]
            self.assertEqual(key.cget('show'),'•')
            self.assertEqual(key.get(),'')
            button=next(child for frame in body.winfo_children() if str(frame.winfo_class())=='TFrame'
                        for child in frame.winfo_children()
                        if '显示已保存密钥' in str(child.cget('text')))
            button.invoke();self.root.update()
            self.assertEqual(key.cget('show'),'')
            self.assertEqual(key.get(),'sk-kept')
            self.root.after(150,self.root.quit);self.root.mainloop()
            self.assertEqual(key.cget('show'),'•')
            self.assertEqual(key.get(),'')


class StaleSettingsWindowTests(unittest.TestCase):
    """设置窗打开后项目切换或宿主正忙：删除模型、保存设置都只报错，不写任何文件。"""

    def setUp(self):
        try:
            self.root=tk.Tk();self.root.withdraw()
        except tk.TclError:
            self.skipTest(PLATFORM_TKINTER)
        self.addCleanup(self.root.destroy)

    def press_all(self, desktop, change):
        def walk(widget):
            yield widget
            for child in widget.winfo_children():
                yield from walk(child)
        settings_window(desktop);self.root.update()
        win=desktop.cloud_settings_window
        self.addCleanup(lambda:win.winfo_exists() and win.destroy())
        buttons={str(w.cget('text')):w for w in walk(win) if w.winfo_class() in ('TButton','Button')}
        change(desktop)
        errors=[]
        with patch('cloud_video.notify',lambda _win,text,**kw:errors.append((text,kw['level']))):
            buttons['删除模型'].invoke();buttons['保存设置'].invoke()
        return errors

    def test_switched_project_and_busy_host_refuse_both_actions(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td);source=project/'episode.json';source.write_text('{}',encoding='utf-8')

            def desktop():
                return SimpleNamespace(win=self.root,root=project,video=None,current_frame_json=lambda:source,
                                       cloud_settings_window=None,worker=False,status=None)
            switched=self.press_all(desktop(),lambda d:setattr(d,'root',project/'other'))
            self.assertEqual(switched,[('项目已切换，请重新打开 API 设置','error'),
                                       ('当前项目已切换，请关闭设置后在对应项目重新打开','error')])
            busy=self.press_all(desktop(),lambda d:setattr(d,'worker',True))
            self.assertEqual(busy,[('请等待当前请求结束后删除模型','error'),
                                   ('当前任务尚未结束，请稍后保存','error')])
            self.assertEqual(sorted(p.name for p in project.iterdir()),['episode.json'])


class MotionReferencePayloadTests(unittest.TestCase):
    """AST-MOTION-REF：角色动态参考视频进 Seedance 的 content 槽位（不真实联网）。

    先红后绿依据：改前 ``VolcengineAdapter.payload`` 不读 ``motion_references``，
    支持分支断言 ``role=reference_video`` 条目为 0 条而失败。
    """

    def _library(self, td, rows):
        base = Path(td) / 'assetlib'
        image = base / 'assets/characters/CHAR_001.png'
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(png())
        plan_file = base / 'assets/资产清单/assets.json'
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(json.dumps(
            {'CHAR_001': {'name': '角色', 'motion_references': rows}},
            ensure_ascii=False), encoding='utf-8')
        return base, image

    def _adapter(self, model='doubao-seedance-2-0-251215'):
        from agent.volcengine import VolcengineAdapter
        return VolcengineAdapter({'cloud_provider': 'volcengine', 'model': model,
                                  'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                                  'resolution': '720p'})

    def _payload(self, td, rows, *, ref_id='CHAR_001', ref_image=None,
                 model='doubao-seedance-2-0-251215'):
        base, image = self._library(td, rows)
        frame = Path(td) / 'frame.png'
        frame.write_bytes(png())
        shot = {'video_prompt': '画面', 'duration': 4, '_reference_mode': 'seedance',
                '_asset_references': [{'id': ref_id, 'path': str(ref_image or image)}]}
        return base, self._adapter(model).payload(shot, frame)

    @staticmethod
    def _videos(payload):
        return [c for c in payload['content'] if c.get('role') == 'reference_video']

    def test_seedance_payload_carries_motion_reference(self):
        rel = 'assets/参考视频/角色/CHAR_001/turn.mp4'
        raw = b'\x00\x00\x00\x18ftypmp42fake'
        with tempfile.TemporaryDirectory() as td:
            base, image = self._library(td, [{'path': rel, 'name': 'turn.mp4',
                                              'duration': 3.2, 'sha256': 'f' * 64}])
            clip = base / rel
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(raw)
            frame = Path(td) / 'frame.png'
            frame.write_bytes(png())
            shot = {'video_prompt': '画面', 'duration': 4, '_reference_mode': 'seedance',
                    '_asset_references': [{'id': 'CHAR_001', 'path': str(image)}]}
            payload = self._adapter().payload(shot, frame)
            videos = self._videos(payload)
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0]['type'], 'video_url')
            self.assertTrue(videos[0]['video_url']['url'].startswith('data:video/mp4;base64,'))
            import base64 as _b64
            self.assertEqual(_b64.b64decode(videos[0]['video_url']['url'].split(',', 1)[1]),
                             raw)

    def test_motion_reference_skipped_when_model_lacks_support(self):
        """Seedance 1.5 不在 SUPPORT 表（只认 2.0／2.5）→ 跳过不带入，详情页写明仅存档。"""
        rel = 'assets/参考视频/角色/CHAR_001/turn.mp4'
        with tempfile.TemporaryDirectory() as td:
            base, image = self._library(td, [{'path': rel, 'name': 'turn.mp4'}])
            clip = base / rel
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(b'\x00\x00\x00\x18ftypmp42fake')
            frame = Path(td) / 'frame.png'
            frame.write_bytes(png())
            payload = self._adapter('doubao-seedance-1-5-pro-251215').payload(
                {'video_prompt': '画面', 'duration': 4, '_reference_mode': 'seedance',
                 '_asset_references': [{'id': 'CHAR_001', 'path': str(image)}]}, frame)
            self.assertEqual(self._videos(payload), [])

    def test_motion_reference_skipped_for_non_char_asset(self):
        """动态参考提交接线只认角色（CHAR_）；LOC/PROP 即便登记也不进请求。"""
        rel = 'assets/参考视频/角色/CHAR_001/turn.mp4'
        with tempfile.TemporaryDirectory() as td:
            base, image = self._library(td, [{'path': rel, 'name': 'turn.mp4'}])
            clip = base / rel
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(b'\x00\x00\x00\x18ftypmp42fake')
            loc = base / 'assets/scenes/LOC_001.png'
            loc.parent.mkdir(parents=True, exist_ok=True)
            loc.write_bytes(png(color='blue'))
            _base, payload = self._payload(td, [{'path': rel, 'name': 'turn.mp4'}],
                                           ref_id='LOC_001', ref_image=loc)
            self.assertEqual(self._videos(payload), [])

    def test_motion_reference_skips_escape_missing_and_bad_rows(self):
        rel = 'assets/参考视频/角色/CHAR_001/ok.mp4'
        rows = [{'path': '../escape.mp4'},
                {'path': 'assets/参考视频/角色/CHAR_001/gone.mp4'},
                'not-a-dict',
                {'path': rel}]
        with tempfile.TemporaryDirectory() as td:
            base, image = self._library(td, rows)
            clip = base / rel
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(b'\x00\x00\x00\x18ftypmp42fake')
            frame = Path(td) / 'frame.png'
            frame.write_bytes(png())
            shot = {'video_prompt': '画面', 'duration': 4, '_reference_mode': 'seedance',
                    '_asset_references': [{'id': 'CHAR_001', 'path': str(image)}]}
            payload = self._adapter().payload(shot, frame)
            videos = self._videos(payload)
            self.assertEqual(len(videos), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
