"""项目列表排序键：登记了 created_at 就不碰磁盘（R1777 审计第 26 项）。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from desktop_project_pages import project_sort_key


class ProjectSortKeyTests(unittest.TestCase):
    def test_registered_created_at_does_not_touch_the_disk(self):
        with mock.patch.object(Path, 'stat', side_effect=AssertionError('不该读磁盘')):
            self.assertEqual(project_sort_key({'path': 'Z:/nowhere', 'created_at': 7}), 7)

    def test_missing_created_at_falls_back_to_ctime_or_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertGreater(project_sort_key({'path': folder}), 0)
            self.assertEqual(project_sort_key({'path': str(Path(folder) / 'gone')}), 0)


if __name__ == '__main__':
    unittest.main()
