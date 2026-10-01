import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from storyboard_source_service import ALL_SOURCES_LABEL, source_options


class StoryboardSourceServiceTests(unittest.TestCase):
    def _board(self, root, name, episode, shots=1):
        path = Path(root) / name
        path.write_text(json.dumps({'episode_id': episode, 'title': name, 'shots': [{}] * shots}), encoding='utf-8')
        return path

    def test_multiple_sources_offer_all_and_preserve_current_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            first = self._board(temp, 'a.json', 'EP001')
            second = self._board(temp, 'b.json', 'EP002', 2)
            labels, sources, index = source_options([second, first], 'current', second)
            self.assertEqual(labels[0], ALL_SOURCES_LABEL)
            self.assertIsNone(sources[0])
            self.assertEqual(sources[index], second.resolve())
            self.assertIn('2镜', labels[index])

    def test_adopted_scope_selects_all_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            first = self._board(temp, 'a.json', 'EP001')
            _labels, sources, index = source_options([first], 'adopted', first)
            self.assertEqual(sources[index], first.resolve())

    def test_each_source_is_read_once_when_building_options(self):
        with tempfile.TemporaryDirectory() as temp:
            first = self._board(temp, 'a.json', 'EP001')
            with patch('storyboard_source_service.read_json', wraps=__import__('storyboard_source_service').read_json) as reader:
                source_options([first], 'current', first)
            self.assertEqual(reader.call_count, 1)
