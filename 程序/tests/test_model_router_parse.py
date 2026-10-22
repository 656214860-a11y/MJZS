"""model_router._parse_response 的正文提取：各协议外壳下取到的正文与兜底顺序。"""
import unittest

import model_router


def text(wire, data):
    return model_router._parse_response(wire, data, 'm1')[0]


class ParseResponseTests(unittest.TestCase):
    def test_responses_falls_back_to_output_text_only_when_output_is_empty(self):
        self.assertEqual(text('responses', {'output': [], 'output_text': '兜底'}), '兜底')
        self.assertEqual(text('responses', {'output': 'bad', 'output_text': 5}), '')

    def test_completions_joins_list_content_blocks_and_skips_non_dicts(self):
        data = {'choices': [{'message': {'content': [{'text': 'p1'}, {'text': None}, 'zz', {'text': 'p2'}]}}]}
        self.assertEqual(text('chat', data), 'p1p2')

    def test_completions_string_content_wins_and_empty_content_falls_back(self):
        self.assertEqual(text('chat', {'choices': [{'message': {'content': 'hello'}}]}), 'hello')
        self.assertEqual(text('chat', {'choices': [{'message': {'content': None}}], 'output_text': 'tail'}), 'tail')

    def test_messages_reads_chat_completions_shell_with_list_content(self):
        data = {'choices': [{'message': {'content': [{'type': 'text', 'text': ' a'}, {'type': 'reasoning', 'text': 'no'},
                                                     {'type': 'output_text', 'text': 'b '}, 'junk']}}]}
        self.assertEqual(text('messages', data), 'ab', '只取 text／output_text 块，去首尾空白')


if __name__ == '__main__':
    unittest.main()
