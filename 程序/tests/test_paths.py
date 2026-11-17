# -*- coding: utf-8 -*-
"""云端工作集路径语义回归：项目根目录的判定只留一处实现。"""
import unittest
from pathlib import Path

from contract.storyboard_paths import is_cloud_workspace, project_root


class CloudWorkspacePathTests(unittest.TestCase):
    def test_plain_project_directory_is_its_own_root(self):
        project = Path("D:/工作/漫剧项目")
        self.assertFalse(is_cloud_workspace(project))
        self.assertEqual(project_root(project), project)

    def test_cloud_workspace_points_back_at_the_project(self):
        workspace = Path("D:/工作/漫剧项目/cloud_video/万相_EP001")
        self.assertTrue(is_cloud_workspace(workspace))
        self.assertEqual(project_root(workspace), Path("D:/工作/漫剧项目"))

    def test_local_backend_workspace_is_not_a_cloud_workspace(self):
        workspace = Path("D:/工作/漫剧项目/工作流任务/白模自动制作/20260920")
        self.assertFalse(is_cloud_workspace(workspace))
        self.assertEqual(project_root(workspace), workspace)

    def test_project_root_is_idempotent(self):
        workspace = Path("D:/工作/漫剧项目/cloud_video/Seedance_EP002")
        root = project_root(workspace)
        self.assertEqual(project_root(root), root)

    def test_engine_uses_the_shared_helper_for_cloud_shot_folders(self):
        import engine
        source = Path(engine.__file__).read_text(encoding="utf-8")
        self.assertNotIn("parent.name=='cloud_video'", source)
        self.assertIn("is_cloud_workspace(", source)
