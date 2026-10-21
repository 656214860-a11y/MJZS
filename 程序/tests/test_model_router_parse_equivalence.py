"""ModelRouter.chat 的响应解析抽成 _parse_response：与原内联实现逐形状对照。"""
import itertools
import unittest

import model_router
import token_saver


def _legacy(wire_api, data, target):
    text = ''
    # 诊断只记录协议元数据，绝不记录提示词、正文或推理正文。这样 DeepSeek 等
    # 推理模型返回空 content 时，界面/日志能区分「实际请求成功但没有正文」和
    # 「模型 ID、协议或网络失败」，而不会泄露用户创作内容。
    response_meta = {'requested_model': target, 'wire_api': wire_api,
                     'response_id': '', 'finish_reason': '', 'response_shape': [],
                     'message_fields': [], 'reasoning_fields': [], 'reasoning_lengths': {},
                     'content_length': 0}
    if isinstance(data, dict):
        response_meta['response_id'] = str(data.get('id') or data.get('request_id') or '')
        if wire_api == 'messages':
            response_meta['finish_reason'] = str(data.get('stop_reason') or '')
            text = token_saver.anthropic_text(data)
        elif wire_api == 'responses':
            response_meta['response_shape'] = sorted(str(key) for key in data.keys())
            response_meta['finish_reason'] = str(data.get('status') or '')
            outputs = data.get('output')
            if isinstance(outputs, list):
                parts = []
                for output in outputs:
                    if not isinstance(output, dict):
                        continue
                    content = output.get('content')
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        # 工具调用、推理项等不是给用户看的正文，绝不能转成字符串
                        # 混进剧本；只接受 Responses 的 output_text 项。
                        if isinstance(block, dict) and block.get('type') == 'output_text':
                            value = block.get('text')
                            if isinstance(value, str):
                                parts.append(value)
                text = ''.join(parts)
            if not text and isinstance(data.get('output_text'), str):
                text = data['output_text']
        else:
            choices = data.get('choices')
            response_meta['response_shape'] = sorted(str(key) for key in data.keys())
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                choice = choices[0]
                response_meta['finish_reason'] = str(choice.get('finish_reason') or '')
                message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
                response_meta['message_fields'] = sorted(str(key) for key in message.keys())
                response_meta['reasoning_fields'] = [key for key in ('reasoning_content', 'reasoning', 'analysis')
                                                     if message.get(key) not in (None, '', [], {})]
                response_meta['reasoning_lengths'] = {
                    key: len(str(message.get(key) or ''))
                    for key in response_meta['reasoning_fields']}
                content = message.get('content')
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = ''.join(str(block.get('text') or '') for block in content if isinstance(block, dict))
            if not text:
                text = str(data.get('output_text') or data.get('content') or '')
    response_meta['content_length'] = len(text)
    return text, response_meta


SHAPES = [
    None, [], 'x', {},
    {'id': 'a1', 'request_id': 'r', 'stop_reason': 'end', 'status': 'done', 'output_text': 'OT', 'content': 'C'},
    {'request_id': 'r2', 'content': [{'type': 'text', 'text': 'hi'}], 'stop_reason': 'max'},
    {'status': 'completed', 'output': [
        {'content': [{'type': 'output_text', 'text': 'A'}, {'type': 'reasoning', 'text': 'no'},
                     {'type': 'output_text', 'text': 3}, 'junk']},
        'skip', {'content': 'notlist'}, {'content': [{'type': 'output_text', 'text': 'B'}]}]},
    {'status': 'completed', 'output': [], 'output_text': 'fallback'},
    {'status': 'completed', 'output': 'bad', 'output_text': 5},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': 'hello', 'reasoning_content': 'think'}}]},
    {'choices': [{'finish_reason': 'length', 'message': {
        'content': [{'text': 'p1'}, {'text': None}, 'zz', {'text': 'p2'}], 'reasoning': 'abc', 'analysis': ''}}]},
    {'choices': [{'message': {'content': None}}], 'output_text': 'tail'},
    {'choices': [{'message': 'str'}], 'content': 'ctop'},
    {'choices': [], 'content': 7},
    {'choices': ['x'], 'output_text': ''},
    {'choices': [{'finish_reason': None, 'message': {'content': '', 'reasoning_content': [1], 'reasoning': {}}}]},
]


class ParseResponseEquivalence(unittest.TestCase):
    def test_all_wire_apis_and_shapes(self):
        n = 0
        for wire, data in itertools.product(('chat', 'responses', 'messages', 'other', ''), SHAPES):
            old = _legacy(wire, data, 'm1')
            new = model_router._parse_response(wire, data, 'm1')
            self.assertEqual(new, old, (wire, data))
            n += 1
        self.assertEqual(n, 5 * len(SHAPES))


if __name__ == '__main__':
    unittest.main()
