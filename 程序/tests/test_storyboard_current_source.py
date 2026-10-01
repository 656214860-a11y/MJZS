# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

from storyboard_selection import current_source


class StoryboardCurrentSourceTests(unittest.TestCase):
    def test_saved_current_source_is_resolved_without_a_desktop_instance(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / '03初步分镜' / '分镜拆分' / 'EP001_分镜.json'
            source.parent.mkdir(parents=True)
            source.write_text('{}', encoding='utf-8')
            (project / 'ui_settings.json').write_text(
                json.dumps({'frame_json': source.relative_to(project).as_posix()}), encoding='utf-8')

            self.assertEqual(source.resolve(), current_source(project))

    def test_legacy_source_is_remembered_through_the_callers_callback(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / 'episode' / 'episode.json'
            source.parent.mkdir(parents=True)
            source.write_text('{}', encoding='utf-8')
            remembered = []

            actual = current_source(
                project,
                legacy_sources=((project, source),),
                remember=remembered.append,
            )

            self.assertEqual(source.resolve(), actual)
            self.assertEqual([source.resolve()], remembered)

    def test_missing_saved_source_keeps_the_actionable_error(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / 'ui_settings.json').write_text(json.dumps({'frame_json': 'missing.json'}), encoding='utf-8')

            with self.assertRaisesRegex(ValueError, '上次的镜头 JSON 找不到'):
                current_source(project)
