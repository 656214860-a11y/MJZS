"""剧本准备的 Claude 会话超过 12 小时未写入即视为过期，改开新会话。"""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

import workflow_engines


class ClaudeSessionStaleTests(unittest.TestCase):
    def _setup(self, td, age):
        root = Path(td)
        project, home = root / 'p', root / 'home'
        session = str(uuid.uuid4())
        (project / '工作流任务').mkdir(parents=True)
        (project / '工作流任务' / 'Claude对话.json').write_text(json.dumps({'writing': session}), encoding='utf-8')
        log = home / '.claude' / 'projects' / 'x' / (session + '.jsonl')
        log.parent.mkdir(parents=True)
        log.write_text('{}', encoding='utf-8')
        stamp = time.time() - age
        os.utime(log, (stamp, stamp))
        return project, home

    def test_threshold(self):
        limit = workflow_engines.CLAUDE_SESSION_STALE_SECONDS
        for age, expected in ((limit + 60, True), (limit - 60, False)):
            with tempfile.TemporaryDirectory() as td:
                project, home = self._setup(td, age)
                with patch('pathlib.Path.home', return_value=home):
                    self.assertIs(workflow_engines.claude_session_stale(project, 'writing'), expected)

    def test_missing_binding_or_log_is_not_stale(self):
        with tempfile.TemporaryDirectory() as td:
            project, home = self._setup(td, 10 ** 6)
            with patch('pathlib.Path.home', return_value=home):
                self.assertFalse(workflow_engines.claude_session_stale(project, 'storyboard'))
            with patch('pathlib.Path.home', return_value=Path(td) / 'empty'):
                self.assertFalse(workflow_engines.claude_session_stale(project, 'writing'))


if __name__ == '__main__':
    unittest.main()
