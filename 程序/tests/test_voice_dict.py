# -*- coding: utf-8 -*-
"""语音词典（data/语音词典.json）：热词／同音替换表／AI 优化配置的读写与会话注入。"""
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import domain.offline_asr_client as offline_asr_client
import domain.speech_api as speech_api
from domain import speech_api as speech_api_flat
from agent.core import save


class FakeInnerSession:
    """最小会话替身：start 时回放预置事件。"""
    def __init__(self, events):
        self.events = queue.Queue()
        self._events = list(events)
        self.started = self.finished = self.cancelled = False
        self.sent = []

    def start(self):
        self.started = True
        for event in self._events:
            self.events.put(event)

    def send(self, pcm):
        self.sent.append(pcm)

    def finish(self):
        self.finished = True

    def cancel(self):
        self.cancelled = True


def drain(session):
    events = []
    while True:
        kind = session.events.get(timeout=5)
        events.append(kind)
        if kind[0] == 'closed':
            return events


class NormalizeTests(unittest.TestCase):
    def test_defaults_and_string_forms(self):
        merged = speech_api.normalize_dictionary({
            'hotword': '漫剧， 子进程；\n角色卡',
            'replace': {'子进成': '子进程', '  ': 'x', 'same': 'same'},
            'ai': {'enabled': 'on', 'template': 'polish', 'prompt': ' 口语转书面语 '}})
        self.assertEqual(merged['hotword'], ['漫剧', '子进程', '角色卡'])
        self.assertEqual(merged['replace'], {'子进成': '子进程'})
        self.assertEqual(merged['ai'], {'enabled': True, 'template': 'polish', 'prompt': '口语转书面语'})
        self.assertEqual(speech_api.normalize_dictionary(None),
                         {'hotword': [], 'replace': {}, 'ai': dict(speech_api.DICT_DEFAULTS['ai'])})

    def test_hotword_list_form_dedupes(self):
        merged = speech_api.normalize_dictionary({'hotword': ['漫剧', '漫剧', ' 子进程 ', '']})
        self.assertEqual(merged['hotword'], ['漫剧', '子进程'])

    def test_invalid_values_raise_chinese_errors(self):
        for bad in ({'hotword': {'a': 1}}, {'hotword': ['x' * 101]},
                    {'hotword': ['词%d' % i for i in range(201)]},
                    {'replace': ['not-a-dict']}, {'replace': {'k' * 101: 'v'}},
                    {'ai': {'template': 'warp'}}, {'ai': {'prompt': 'x' * 2001}}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                speech_api.normalize_dictionary(bad)

    def test_read_dictionary_tolerates_bad_sections(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / '语音词典.json'
            self.assertEqual(speech_api.read_dictionary(path)['hotword'], [])
            path.write_text(json.dumps({'hotword': '漫剧', 'replace': '坏', 'ai': '坏',
                                        'unknown': 1}), encoding='utf-8')
            merged = speech_api.read_dictionary(path)
        self.assertEqual(merged['hotword'], ['漫剧'], '坏节回默认而不拖垮好节')
        self.assertEqual(merged['replace'], {})
        self.assertFalse(merged['ai']['enabled'])
        self.assertNotIn('unknown', merged)

    def test_save_dictionary_writes_normalized_and_validates_first(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'data' / '语音词典.json'
            saved = speech_api.save_dictionary(
                {'hotword': '漫剧,子进程', 'replace': {'子进成': '子进程'},
                 'ai': {'enabled': True, 'template': 'fix', 'prompt': ''}},
                publish=save, path=target)
            self.assertEqual(saved['hotword'], ['漫剧', '子进程'])
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['replace'],
                             {'子进成': '子进程'})
            with self.assertRaises(ValueError):
                speech_api.save_dictionary({'ai': {'template': 'warp'}}, publish=save, path=target)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['hotword'],
                             ['漫剧', '子进程'], '校验失败不动文件')


class ApplyReplacementsTests(unittest.TestCase):
    def test_longest_key_first_and_empty_safe(self):
        table = {'进程': '线程', '子进程': '子进程', '好': '好'}
        self.assertEqual(speech_api.apply_replacements('他说子进程好', table), '他说子进程好')
        table = {'子进程': '子线程', '进程': '线程'}
        self.assertEqual(speech_api.apply_replacements('子进程在跑', table), '子线程在跑')
        self.assertEqual(speech_api.apply_replacements('', table), '')
        self.assertEqual(speech_api.apply_replacements('原文', {}), '原文')

    def test_reads_dictionary_when_table_omitted(self):
        with patch.object(speech_api, 'read_dictionary',
                          return_value={'replace': {'子进成': '子进程'}}):
            self.assertEqual(speech_api.apply_replacements('他说子进成'), '他说子进程')


class HotwordTextTests(unittest.TestCase):
    def test_space_joined_for_engine(self):
        self.assertEqual(speech_api.hotword_text({'hotword': ['漫剧', '子进程']}), '漫剧 子进程')
        self.assertEqual(speech_api.hotword_text({'hotword': []}), '')


class CreateSessionDictionaryTests(unittest.TestCase):
    """create_session：离线注入热词、两后端都过替换表包装。"""

    def _offline_settings(self):
        return {**dict(speech_api.DEFAULTS), 'backend': 'offline',
                'offline': {**dict(speech_api.DEFAULTS['offline']), 'hotword': '旧词'}}

    def test_offline_session_gets_merged_hotword_and_replace_wrapper(self):
        captured = {}

        def factory(settings, *, fallback=None):
            captured['settings'] = settings
            return FakeInnerSession([('final', 's1', '他说子进成好'), ('closed', '', '')])

        dictionary = {'hotword': ['漫剧', '子进程'], 'replace': {'子进成': '子进程'},
                      'ai': {'enabled': False, 'template': 'fix', 'prompt': ''}}
        with patch.object(speech_api, 'read_dictionary', return_value=dictionary), \
             patch.object(speech_api, 'api_key', return_value=''), \
             patch.object(offline_asr_client, 'OfflineAsrSession', side_effect=factory):
            session = speech_api.create_session(self._offline_settings())
        self.assertIsInstance(session, speech_api._DictionarySession)
        self.assertEqual(captured['settings']['offline']['hotword'], '旧词 漫剧 子进程')
        session.start()
        events = drain(session)
        self.assertEqual(events[0], ('final', 's1', '他说子进程好'), 'final 过替换表')
        self.assertEqual(events[-1][0], 'closed')

    def test_no_replace_returns_raw_session(self):
        dictionary = {'hotword': [], 'replace': {},
                      'ai': {'enabled': False, 'template': 'fix', 'prompt': ''}}
        inner = FakeInnerSession([('final', 's1', '原文'), ('closed', '', '')])
        with patch.object(speech_api, 'read_dictionary', return_value=dictionary), \
             patch.object(speech_api, 'api_key', return_value=''), \
             patch.object(offline_asr_client, 'OfflineAsrSession', return_value=inner):
            session = speech_api.create_session(self._offline_settings())
        self.assertIs(session, inner)
        session.start()
        self.assertEqual(drain(session)[0], ('final', 's1', '原文'))

    def test_cloud_session_ignores_hotword_but_applies_replace(self):
        captured = {}

        class FakeRealtime:
            def __init__(self, settings, *, connect=None):
                captured['settings'] = settings
                self.events = queue.Queue()

            def start(self):
                self.events.put(('final', 'c1', '他说子进成好'))
                self.events.put(('closed', '', ''))

            def send(self, pcm):
                pass

            def finish(self):
                pass

            def cancel(self):
                pass

        dictionary = {'hotword': ['漫剧'], 'replace': {'子进成': '子进程'},
                      'ai': {'enabled': False, 'template': 'fix', 'prompt': ''}}
        with patch.object(speech_api, 'read_dictionary', return_value=dictionary), \
             patch.object(speech_api, 'RealtimeSession', FakeRealtime):
            session = speech_api.create_session(
                {**dict(speech_api.DEFAULTS), 'backend': 'cloud'})
        self.assertIsInstance(session, speech_api._DictionarySession, '云端也过替换表')
        self.assertNotIn('hotword', captured['settings'].get('offline') or {})
        session.start()
        self.assertEqual(drain(session)[0], ('final', 'c1', '他说子进程好'))


class FacadeTests(unittest.TestCase):
    def test_flat_facade_is_domain_entity(self):
        self.assertIs(speech_api_flat, speech_api)


if __name__ == '__main__':
    unittest.main()
