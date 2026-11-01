"""stage_config：没有项目时读阶段配置不得把 None 当缓存键，否则之后任何保存都会在失效缓存时崩。"""
import tempfile
import unittest
from pathlib import Path

import stage_config


class EmptyProjectCacheTests(unittest.TestCase):
    def test_reading_without_project_leaves_no_none_key_behind(self):
        stage_config.get(None, 'keyframe')
        stage_config.get('', 'keyframe')
        for cache in (stage_config._SYNCHRONIZE_CACHE, stage_config._GET_CACHE):
            self.assertNotIn(None, cache)

    def test_saving_after_reading_without_project_still_works(self):
        stage_config.get(None, 'keyframe')
        with tempfile.TemporaryDirectory() as folder:
            stage_config.put(Path(folder), 'keyframe', model='')
            self.assertTrue(stage_config.path(Path(folder)).exists())


if __name__ == '__main__':
    unittest.main()
