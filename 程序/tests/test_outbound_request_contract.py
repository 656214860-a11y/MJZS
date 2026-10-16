# -*- coding: utf-8 -*-
"""出站请求契约：同一逻辑请求在各适配器上的请求形状（T5）＋出站素材白名单（T11）。

T5 口径：四个内置文本适配器对**同一逻辑请求**必须给出各自协议的正确形状；三个 OpenAI 兼容
适配器的请求体必须逐字段一致，差异只允许出现在地址与认证头——换模型时字段静默丢失是最贵的错。

T11 口径：出站素材只允许是本次声明的素材（首帧／已登记参考图），且必须是有界图片
（PNG / JPEG 签名 + ≤20MB）；项目里的其它文件一个字节都不许出现在请求体里。

不联网（传输层是记录器）、不调模型、不用 Tk。
"""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

import model_router as m


MESSAGES = ({'role': 'user', 'content': '写一句台词'},)
SYSTEM = '你是编剧。'
BODY = {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': 'ok'}}]}}

# (名字, 适配器类, 默认模型, 协议)
ADAPTERS = (
    ('deepseek', m.DeepSeekAdapter, 'deepseek-v4-pro', 'chat'),
    ('gpt', m.GPTAdapter, 'gpt-4o', 'chat'),
    ('qwen', m.QwenAdapter, 'qwen-max', 'chat'),
    ('anthropic', m.AnthropicAdapter, 'claude-opus-5', 'messages'),
)


def _recorder(seen):
    def transport(url, payload, headers, timeout):
        seen.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return dict(BODY)
    return transport


class RequestShapeTests(unittest.TestCase):
    """同一逻辑请求 → 每个适配器自己的正确请求形状。"""

    def send(self, factory, model, *, options=None, system=SYSTEM):
        seen = {}
        adapter = factory(key='test', transport=_recorder(seen))
        adapter.chat(list(MESSAGES), options=options, model=model, system=system)
        return adapter, seen

    def test_every_adapter_sends_its_own_auth_header(self):
        for name, factory, model, api in ADAPTERS:
            with self.subTest(adapter=name):
                _, seen = self.send(factory, model)
                headers = {str(key).lower(): value for key, value in seen['headers'].items()}
                self.assertEqual(headers.get('content-type'), 'application/json')
                if api == 'messages':
                    self.assertEqual(headers.get('x-api-key'), 'test')
                    self.assertIn('anthropic-version', headers)
                    self.assertNotIn('authorization', headers)
                else:
                    self.assertEqual(headers.get('authorization'), 'Bearer test')

    def test_system_prefix_lands_in_the_protocol_specific_slot(self):
        for name, factory, model, api in ADAPTERS:
            with self.subTest(adapter=name):
                payload = self.send(factory, model)[1]['payload']
                self.assertEqual(payload['model'], model)
                self.assertIn('max_tokens', payload)
                if api == 'messages':
                    self.assertEqual(payload['system'], SYSTEM)
                    self.assertEqual(payload['messages'], list(MESSAGES))
                    self.assertIn('cache_control', payload)
                else:
                    self.assertEqual(payload['messages'][0], {'role': 'system', 'content': SYSTEM})
                    self.assertEqual(payload['messages'][1:], list(MESSAGES))

    def test_no_system_prefix_when_system_is_empty(self):
        for name, factory, model, api in ADAPTERS:
            with self.subTest(adapter=name):
                payload = self.send(factory, model, system='')[1]['payload']
                if api == 'messages':
                    self.assertEqual(payload['system'], '')
                else:
                    self.assertEqual(payload['messages'], list(MESSAGES))

    def test_token_limit_and_temperature_only_when_asked(self):
        for name, factory, model, _api in ADAPTERS:
            with self.subTest(adapter=name, case='默认'):
                payload = self.send(factory, model)[1]['payload']
                self.assertEqual(payload['max_tokens'], 1024)
                self.assertNotIn('temperature', payload)
            with self.subTest(adapter=name, case='显式'):
                payload = self.send(factory, model,
                                    options={'max_tokens': 256, 'temperature': 0.3})[1]['payload']
                self.assertEqual(payload['max_tokens'], 256)
                self.assertEqual(payload['temperature'], 0.3)

    def test_openai_compatible_adapters_agree_on_the_same_body(self):
        bodies = [self.send(factory, model)[1]['payload']
                  for name, factory, model, api in ADAPTERS if api == 'chat']
        # 同一逻辑请求：结构必须逐字段一致，只允许 model 值本身不同。
        shapes = [dict((key, value) for key, value in body.items() if key != 'model') for body in bodies]
        self.assertEqual(shapes[0], shapes[1])
        self.assertEqual(shapes[1], shapes[2])
        self.assertEqual([body['model'] for body in bodies],
                         [model for name, factory, model, api in ADAPTERS if api == 'chat'])

    def test_endpoint_follows_the_declared_base_url_and_protocol(self):
        for name, factory, model, api in ADAPTERS:
            with self.subTest(adapter=name):
                adapter, seen = self.send(factory, model)
                self.assertTrue(seen['url'].startswith(adapter.base_url), seen['url'])
                tail = '/messages' if api == 'messages' else '/chat/completions'
                self.assertTrue(seen['url'].endswith(tail), seen['url'])

    def test_sent_request_is_exactly_what_was_built(self):
        """发送的请求体／请求头必须就是 payload()／headers() 的产物：中间不许再改写。"""
        for name, factory, model, _api in ADAPTERS:
            with self.subTest(adapter=name):
                adapter, seen = self.send(factory, model)
                self.assertEqual(seen['payload'],
                                 adapter.payload(model, list(MESSAGES), None, SYSTEM))
                self.assertEqual(seen['headers'], adapter.headers())


PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')


class OutboundMaterialTests(unittest.TestCase):
    """出站素材白名单：只送本次声明的素材，只接受有界图片。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'p'
        self.frame = self.root / 'frames' / 'SH001.png'
        self.frame.parent.mkdir(parents=True)
        self.frame.write_bytes(PNG)
        self.decoy = self.root / '.env'
        self.decoy.write_text('DASHSCOPE_API_KEY=sk-secret-decoy', encoding='utf-8')

    def adapter(self):
        from agent.wan import WanAdapter
        return WanAdapter({'model': 'wan-test', 'base_url': 'https://example.invalid'})

    def shot(self, **extra):
        return {'video_prompt': '镜头', 'duration': 5, 'generate_audio': True, **extra}

    def test_only_the_declared_frame_goes_out(self):
        payload = self.adapter().payload(self.shot(), self.frame)
        encoded = payload['input']['img_url'].split(',', 1)[1]
        self.assertEqual(base64.b64decode(encoded), PNG)
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('sk-secret-decoy', text)
        self.assertNotIn(self.decoy.read_text(encoding='utf-8'), text)

    def test_payload_carries_no_extra_keys_and_writes_no_local_copy(self):
        payload = self.adapter().payload(self.shot(), self.frame)
        self.assertEqual(sorted(payload), ['input', 'model', 'parameters'])
        self.assertEqual(sorted(payload['input']), ['img_url', 'prompt'])
        self.assertEqual(sorted(payload['parameters']),
                         ['audio', 'duration', 'prompt_extend', 'resolution', 'watermark'])
        self.assertEqual(sorted(path.name for path in (self.root / 'frames').iterdir()),
                         ['SH001.png'])

    def test_non_image_and_oversize_files_are_rejected(self):
        note = self.root / 'note.txt'
        note.write_text('不是图片', encoding='utf-8')
        for path in (note, self.decoy):
            with self.subTest(path=path.name):
                with self.assertRaises(ValueError):
                    self.adapter().payload(self.shot(), path)
        big = self.root / 'big.png'
        big.write_bytes(PNG + b'\x00' * (20 * 1024 * 1024))
        with self.assertRaises(ValueError):
            self.adapter().payload(self.shot(), big)

    def test_reference_mode_sends_only_the_declared_references(self):
        reference = self.root / 'assets' / 'CHAR_001.png'
        reference.parent.mkdir(parents=True)
        reference.write_bytes(PNG)
        payload = self.adapter().payload(
            self.shot(_reference_mode='wan', _asset_references=[{'path': str(reference)}],
                      _white_model_reference=None),
            self.frame)
        media = payload['input']['media']
        self.assertEqual([row['type'] for row in media], ['first_frame', 'reference_image'])
        for row in media:
            self.assertTrue(row['url'].startswith('data:image/png;base64,'), row['url'])
        self.assertNotIn('sk-secret-decoy', json.dumps(payload, ensure_ascii=False))

    def test_asset_image_url_is_type_checked_and_bounded(self):
        from agent.shot_assets import image_url
        self.assertTrue(image_url(self.frame).startswith('data:image/png;base64,'))
        with self.assertRaises(ValueError):
            image_url(self.decoy)


if __name__ == '__main__':
    unittest.main()