import tempfile
import unittest
from pathlib import Path

from project_naming import dated_path


class ProjectNamingTests(unittest.TestCase):
    def test_user_visible_names_use_day_and_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)
            first=dated_path(parent,'剧本',at=0)
            first.mkdir()
            second=dated_path(parent,'剧本',at=0)
            self.assertEqual(first.name,'剧本_19700101')
            self.assertEqual(second.name,'剧本_19700101_2')
            self.assertNotIn('000000',first.name)


if __name__ == '__main__':
    unittest.main()
