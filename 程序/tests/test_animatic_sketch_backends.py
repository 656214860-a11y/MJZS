"""REQ-S04-78/79：可插拔草图生成器——comfy_local 默认分流、付费后端显式开启门禁、导入替换图校验。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from domain import animatic_sketch_backends as backends
from infra.comfy_service import ComfyGenerationFailed, ComfySubmissionUncertain


SHOT = {'id': 'SH001', 'prompt': '角色站在门边', 'seconds': 3}


class _FakeComfy:
    """最小 Comfy 假客户端：只记录调用，不发任何网络请求。"""

    def __init__(self, *, files=(), graph=None, collect_error=None, submit_error=None):
        self.files = list(files)
        self.graph = graph if graph is not None else {}
        self.collect_error = collect_error
        self.submit_error = submit_error
        self.submits = []
        self.collect_calls = 0
        self.graph_calls = []

    def reference_config(self):
        return {'model': 'fake.safetensors'}

    def reference_graph(self, prompt, references, cfg):
        self.graph_calls.append((prompt, list(references), cfg))
        return self.graph

    def submit_graph(self, workspace, kind, prompt, graph):
        self.submits.append((workspace, kind, prompt, graph))
        if self.submit_error is not None:
            raise self.submit_error
        return 'record-1'

    def collect(self, workspace, record):
        self.collect_calls += 1
        if self.collect_error is not None:
            raise self.collect_error
        return list(self.files)


class RegistrationTests(unittest.TestCase):
    def test_register_rejects_bad_name_and_non_callable(self):
        for bad in ('', '   ', 123, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    backends.register(bad, lambda *a: None)
        with self.assertRaises(TypeError):
            backends.register('unit_test_nc1', 'not-a-callable')
        with self.assertRaises(TypeError):
            backends.register('unit_test_nc2', 42)

    def test_duplicate_registration_rejected_and_unregister_cleans_up(self):
        factory = lambda *a: Path('x.png')
        backends.register('unit_test_backend', factory)
        try:
            with self.assertRaisesRegex(ValueError, '已登记'):
                backends.register('unit_test_backend', factory)
        finally:
            backends.unregister('unit_test_backend')
        self.assertNotIn('unit_test_backend', {row['name'] for row in backends.list_backends()})
        backends.unregister('unit_test_backend')

    def test_list_backends_returns_sorted_readonly_metadata(self):
        backends.register('unit_test_zeta', lambda *a: None, paid=True, label='乙')
        backends.register('unit_test_alpha', lambda *a: None, label='甲')
        try:
            rows = backends.list_backends()
            self.assertEqual([row['name'] for row in rows], sorted(row['name'] for row in rows))
            meta = {row['name']: row for row in rows}
            self.assertEqual(meta['unit_test_zeta'],
                             {'name': 'unit_test_zeta', 'paid': True, 'label': '乙'})
            self.assertNotIn('factory', meta['unit_test_zeta'])
            meta['unit_test_alpha']['paid'] = True
            self.assertFalse(backends.BACKENDS['unit_test_alpha']['paid'])
        finally:
            backends.unregister('unit_test_zeta')
            backends.unregister('unit_test_alpha')


class CreateDispatchTests(unittest.TestCase):
    def _spy_factory(self, name):
        calls = []
        original = backends.BACKENDS[name]['factory']
        backends.BACKENDS[name]['factory'] = lambda *args: calls.append(args) or Path('out.png')
        return calls, original

    def test_missing_settings_dispatch_to_comfy_local(self):
        """缺省与空设置都落到默认 comfy_local 后端，render 契约四参可调用。"""
        calls, original = self._spy_factory('comfy_local')
        try:
            for settings in (None, {}, {'animatic_sketch_backend': ''}):
                render = backends.create(settings)
                self.assertTrue(callable(render))
                self.assertEqual(render('ws', SHOT, [], {'seed': 9}), Path('out.png'))
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0][3], {'seed': 9})
        finally:
            backends.BACKENDS['comfy_local']['factory'] = original

    def test_explicit_backend_name_is_dispatched(self):
        backends.register('unit_test_alt', lambda *a: Path('alt.png'), label='备用')
        try:
            render = backends.create({'animatic_sketch_backend': 'unit_test_alt'})
            self.assertEqual(render('ws', SHOT, [], {}), Path('alt.png'))
        finally:
            backends.unregister('unit_test_alt')

    def test_unknown_backend_name_rejected_with_chinese_error(self):
        with self.assertRaisesRegex(ValueError, '未知的草图生成后端：nonexistent'):
            backends.create({'animatic_sketch_backend': 'nonexistent'})

    def test_paid_backend_requires_explicit_opt_in(self):
        """付费后端默认关闭：缺失／False／字符串 'true'／整数 1 都拒绝且 factory 零调用。"""
        calls = []

        def factory(*args):
            calls.append(args)
            return Path('paid.png')

        backends.register('unit_test_paid', factory, paid=True, label='付费演示')
        try:
            for extra in ({}, {'animatic_allow_paid_sketch': False},
                          {'animatic_allow_paid_sketch': 'true'},
                          {'animatic_allow_paid_sketch': 1}):
                settings = dict(extra, animatic_sketch_backend='unit_test_paid')
                with self.subTest(extra=extra):
                    with self.assertRaisesRegex(ValueError, '付费草图后端默认关闭，需在设置中显式开启'):
                        backends.create(settings)
            self.assertEqual(calls, [])
            render = backends.create({'animatic_sketch_backend': 'unit_test_paid',
                                      'animatic_allow_paid_sketch': True})
            self.assertEqual(render('ws', SHOT, [], {'seed': 2}), Path('paid.png'))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][3], {'seed': 2})
        finally:
            backends.unregister('unit_test_paid')


class ComfyLocalRenderTests(unittest.TestCase):
    def test_empty_reference_list_still_builds_graph_and_fixes_seed(self):
        """REQ-S04-72：无参考图也照常构图提交；草图前缀与固定 seed 语义保留。"""
        fake = _FakeComfy(files=['sketch.png'],
                          graph={'8': {'class_type': 'RandomNoise',
                                       'inputs': {'noise_seed': 12345, 'other': 'keep'}}})
        result = backends.comfy_local_render('ws', SHOT, [], {'seed': 77, 'timeout': 1},
                                             client=fake)
        self.assertEqual(result, Path('sketch.png'))
        prompt, references, _cfg = fake.graph_calls[0]
        self.assertTrue(prompt.startswith('只生成分镜预演草图，不是正式资产或首帧。'))
        self.assertTrue(prompt.endswith(SHOT['prompt']))
        self.assertEqual(references, [])
        self.assertEqual(fake.submits[0][1], 'scenes')
        self.assertEqual(fake.submits[0][2], SHOT['prompt'])
        self.assertEqual(fake.submits[0][3]['8']['inputs']['noise_seed'], 77)
        self.assertEqual(fake.submits[0][3]['8']['inputs']['other'], 'keep')

    def test_default_seed_is_one_when_settings_omit_it(self):
        fake = _FakeComfy(files=['a.png'], graph={'1': {'inputs': {'seed': 999}}})
        backends.comfy_local_render('ws', SHOT, ['ref.png'], {}, client=fake)
        self.assertEqual(fake.submits[0][3]['1']['inputs']['seed'], 1)

    def test_timeout_never_resubmits(self):
        """collect 一直取不到图：超时只报人工核查且不自动重投，submit_graph 恰好一次。"""
        fake = _FakeComfy(files=[])
        with patch('time.sleep'):
            with self.assertRaisesRegex(ValueError, '不自动重复提交'):
                backends.comfy_local_render('ws', SHOT, [], {'timeout': 0.02}, client=fake)
        self.assertEqual(len(fake.submits), 1)
        self.assertGreaterEqual(fake.collect_calls, 1)

    def test_generation_failure_propagates_for_caller_retry(self):
        """ComfyGenerationFailed 原样上抛供调用方重试，不包装成其他异常。"""
        error = ComfyGenerationFailed('generation failed')
        fake = _FakeComfy(collect_error=error)
        with self.assertRaises(ComfyGenerationFailed) as raised:
            backends.comfy_local_render('ws', SHOT, [], {}, client=fake)
        self.assertIs(raised.exception, error)
        self.assertEqual(len(fake.submits), 1)

    def test_uncertain_submission_propagates_without_retry(self):
        error = ComfySubmissionUncertain('unknown submission')
        fake = _FakeComfy(submit_error=error)
        with self.assertRaises(ComfySubmissionUncertain) as raised:
            backends.comfy_local_render('ws', SHOT, [], {}, client=fake)
        self.assertIs(raised.exception, error)
        self.assertEqual(len(fake.submits), 1)
        self.assertEqual(fake.collect_calls, 0)

    def test_settings_injected_client_is_used_and_explicit_client_wins(self):
        """settings['comfy_client'] 注入与 client 参数等价；显式 client 优先。"""
        injected = _FakeComfy(files=['via-settings.png'])
        explicit = _FakeComfy(files=['explicit.png'])
        result = backends.comfy_local_render('ws', SHOT, [], {'comfy_client': injected})
        self.assertEqual(result, Path('via-settings.png'))
        result = backends.comfy_local_render('ws', SHOT, [], {'comfy_client': injected},
                                             client=explicit)
        self.assertEqual(result, Path('explicit.png'))
        self.assertEqual(len(injected.submits), 1)
        self.assertEqual(len(explicit.submits), 1)

    def test_missing_client_injection_raises_chinese_error(self):
        """未注入 ComfyUI 客户端：中文报错且不发起任何提交。"""
        with self.assertRaisesRegex(ValueError, 'ComfyUI 客户端'):
            backends.comfy_local_render('ws', SHOT, [], {})


class ImportedSketchValidationTests(unittest.TestCase):
    def test_accepts_png_jpg_and_webp_returning_suffix_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('a.png', 'b.webp', 'c.jpg', 'd.jpeg'):
                raw = b'image-bytes-' + name.encode('ascii')
                path = Path(folder) / name
                path.write_bytes(raw)
                with self.subTest(name=name):
                    suffix, data = backends.validate_imported_sketch(path)
                    self.assertEqual(suffix, path.suffix.lower())
                    self.assertEqual(data, raw)

    def test_uppercase_suffix_is_normalized_to_lowercase(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'UP.PNG'
            path.write_bytes(b'x')
            suffix, data = backends.validate_imported_sketch(path)
            self.assertEqual(suffix, '.png')
            self.assertEqual(data, b'x')

    def test_exactly_twenty_megabytes_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'exact.png'
            path.write_bytes(b'1' * backends.MAX_IMAGE_BYTES)
            self.assertEqual(backends.validate_imported_sketch(path)[0], '.png')

    def test_rejects_missing_empty_oversize_and_bad_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'bad.gif').write_bytes(b'GIF89a')
            (root / 'evil.exe').write_bytes(b'MZ')
            (root / 'empty.png').write_bytes(b'')
            (root / 'over.png').write_bytes(b'0' * (backends.MAX_IMAGE_BYTES + 1))
            for name in ('missing.png', 'bad.gif', 'evil.exe', 'empty.png', 'over.png'):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        backends.validate_imported_sketch(root / name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
