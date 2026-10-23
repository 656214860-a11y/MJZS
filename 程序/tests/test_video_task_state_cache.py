# -*- coding: utf-8 -*-
"""generation_active 的跨工作集活跃集合缓存：签名没变复用，state/config 一变立即重算。"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(os.path.dirname(HERE))

import video_task_state as vts


def make(td):
    project = Path(td) / "p"
    episode = project / "episode" / "episode.json"
    episode.parent.mkdir(parents=True)
    episode.write_text(json.dumps({"shots": []}), encoding="utf-8")
    own = project / "data"
    own.mkdir()
    (own / "state.json").write_text(json.dumps({"shots": {}}), encoding="utf-8")
    return project, episode, SimpleNamespace(root=project, episode_path=episode, state=lambda: {"shots": {}})


def add_workspace(project, episode, name, shots, same_episode=True):
    root = project / "cloud_video" / name
    (root / "data").mkdir(parents=True)
    other = project / "other.json"
    (root / "config.json").write_text(json.dumps(
        {"episode_file": str(episode if same_episode else other)}), encoding="utf-8")
    (root / "data" / "state.json").write_text(json.dumps({"shots": shots}), encoding="utf-8")
    return root


class GenerationActiveCacheTests(unittest.TestCase):
    def setUp(self):
        vts._OTHER_ACTIVE.clear(); vts._LISTINGS.clear(); vts._RESOLVED.clear()

    def test_other_workspace_active_shot_locks_and_state_change_unlocks(self):
        with tempfile.TemporaryDirectory() as td:
            project, episode, studio = make(td)
            root = add_workspace(project, episode, "w1", {"SH001": [{"state": "running"}]})
            self.assertTrue(vts.generation_active(studio, "SH001"))
            self.assertFalse(vts.generation_active(studio, "SH002"))
            (root / "data" / "state.json").write_text(
                json.dumps({"shots": {"SH001": [{"state": "downloaded"}]}}), encoding="utf-8")
            self.assertFalse(vts.generation_active(studio, "SH001"))

    def test_new_workspace_appearing_is_noticed(self):
        with tempfile.TemporaryDirectory() as td:
            project, episode, studio = make(td)
            self.assertFalse(vts.generation_active(studio, "SH001"))
            add_workspace(project, episode, "w2", {"SH001": [{"state": "queued"}]})
            self.assertTrue(vts.generation_active(studio, "SH001"))

    def test_workspace_of_another_episode_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            project, episode, studio = make(td)
            add_workspace(project, episode, "w3", {"SH001": [{"state": "running"}]}, same_episode=False)
            self.assertFalse(vts.generation_active(studio, "SH001"))

    def test_unchanged_files_reuse_cached_set(self):
        with tempfile.TemporaryDirectory() as td:
            project, episode, studio = make(td)
            add_workspace(project, episode, "w4", {"SH009": [{"state": "running"}]})
            self.assertTrue(vts.generation_active(studio, "SH009"))
            from unittest.mock import patch
            with patch.object(vts, "read_cached", side_effect=AssertionError("签名没变不应重读")):
                self.assertTrue(vts.generation_active(studio, "SH009"))


if __name__ == "__main__":
    unittest.main()
