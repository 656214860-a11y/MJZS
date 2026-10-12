# -*- coding: utf-8 -*-
"""打不开项目（ERRNO 2）那一处的自检（第 45 期）。运行：python test_project_open.py

用户报的现象：点开项目弹「无法打开项目 · [Errno 2] No such file or directory:
…\\storyboard\\分镜拆分\\episode.json」——config 里的 episode_dir 指的是 分镜拆分 目录，
而真正那份 episode.json 早被规范化挪进了 定稿_… 子目录（新位置记在 文件路径映射.json 里）。
这里盯住三件事：改名挪走后还认得出、认「当前分镜」而不是一条死路、真找不到时说人能看懂的话。
"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import desktop
import engine


def episode(eid="EP001", title="看它，别看我", shots=("SH001", "SH002")):
    return {"episode_id": eid, "title": title,
            "shots": [{"id": sid, "title": "镜头", "duration": 5, "characters": ["CHAR_001"],
                       "location": "LOC_001", "frame": "frames/%s.png" % sid,
                       "video_prompt": "人物抬头看向镜头", "dialogue": []} for sid in shots]}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def project(td, cfg=None):
    """一个最小项目：只摆一份能过 validate 的镜头 JSON 与配置。"""
    proj = Path(td) / "p"
    (proj / "episode").mkdir(parents=True)
    write(proj / "config.json", cfg if cfg is not None else {"episode_dir": "episode"})
    return proj


class RenamedStoryboardTests(unittest.TestCase):
    """分镜被改名／挪进定稿目录后，配置里那条老路要按映射表认回来。"""

    def test_the_alias_map_brings_the_renamed_episode_back(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": str(Path(td) / "p" / "storyboard" / "分镜拆分")})
            real = write(proj / "storyboard" / "分镜拆分" / "定稿_EP001" / "episode.json", episode())
            write(proj / "storyboard" / "分镜拆分" / "文件路径映射.json",
                  {"storyboard/分镜拆分/episode.json": "storyboard/分镜拆分/定稿_EP001/episode.json"})
            studio = engine.Studio(proj)
            self.assertEqual(studio.episode_path, real.resolve())
            self.assertEqual(studio.episode_dir, real.resolve().parent)
            self.assertEqual([s["id"] for s in studio.episode["shots"]], ["SH001", "SH002"])

    def test_the_repaired_pointer_is_written_back_for_the_next_start(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": str(Path(td) / "p" / "storyboard" / "分镜拆分")})
            real = write(proj / "storyboard" / "分镜拆分" / "定稿_EP001" / "episode.json", episode())
            write(proj / "storyboard" / "分镜拆分" / "文件路径映射.json",
                  {"storyboard/分镜拆分/episode.json": "storyboard/分镜拆分/定稿_EP001/episode.json"})
            engine.Studio(proj)
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(cfg["episode_file"]), real.resolve())
            self.assertEqual(Path(cfg["episode_dir"]), real.resolve().parent)
            self.assertEqual(engine.Studio(proj).episode_path, real.resolve(), "第二趟直读配置，不再找")

    def test_a_correct_config_is_left_alone(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": "episode", "episode_file": "episode/episode.json"})
            write(proj / "episode" / "episode.json", episode())
            before = (proj / "config.json").read_text(encoding="utf-8")
            engine.Studio(proj)
            self.assertEqual((proj / "config.json").read_text(encoding="utf-8"), before)


class CurrentStoryboardTests(unittest.TestCase):
    """配置那条路是死路时，认「当前分镜」（ui_settings 的 frame_json）——它才是界面上正用的那份。"""

    def test_the_current_storyboard_beats_the_stale_directory(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": "storyboard/分镜拆分"})
            write(proj / "episode" / "episode.json", episode("EP009", "旧的那份"))
            current = write(proj / "storyboard" / "分镜拆分" / "定稿_EP005" / "episode.json",
                            episode("EP005", "正在做的"))
            write(proj / "ui_settings.json",
                  {"frame_json": "storyboard/分镜拆分/定稿_EP005/episode.json"})
            studio = engine.Studio(proj)
            self.assertEqual(studio.episode_path, current.resolve())
            self.assertEqual(studio.episode["episode_id"], "EP005")

    def test_the_newest_final_folder_is_the_last_resort(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": "storyboard/分镜拆分"})
            older = write(proj / "storyboard" / "分镜拆分" / "定稿_EP001" / "episode.json", episode())
            newer = write(proj / "storyboard" / "分镜拆分" / "定稿_EP002" / "episode.json",
                          episode("EP002", "后写的"))
            os.utime(older, (1_600_000_000, 1_600_000_000))
            os.utime(newer, (1_700_000_000, 1_700_000_000))
            self.assertEqual(engine.Studio(proj).episode_path, newer.resolve())

    def test_an_explicit_episode_file_wins_over_the_config(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": "episode", "episode_file": "episode/episode.json"})
            write(proj / "episode" / "episode.json", episode("EP001", "配置里的"))
            picked = write(proj / "storyboard" / "分镜拆分" / "EP003_分镜.json", episode("EP003", "点的那份"))
            studio = engine.Studio(proj, episode_file=picked)
            self.assertEqual(studio.episode_path, picked.resolve())
            self.assertEqual(studio.episode["episode_id"], "EP003")
            self.assertEqual(studio.episode_dir, picked.resolve().parent)


class UnopenableProjectTests(unittest.TestCase):
    """真找不到时说人能看懂的话：写清缺什么、下一步做什么，而不是抛 [Errno 2]。"""

    def test_a_project_without_any_episode_says_what_to_do(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {"episode_dir": "storyboard/分镜拆分"})
            with self.assertRaises(ValueError) as caught:
                engine.Studio(proj)
            message = str(caught.exception)
            self.assertIn("找不到镜头 JSON", message)
            self.assertIn("第03步", message)
            self.assertNotIn("Errno", message)

    def test_a_missing_folder_is_caught_before_anything_else(self):
        with tempfile.TemporaryDirectory() as td:
            gone = str(Path(td) / "早就删掉的项目")
            with self.assertRaises(ValueError) as caught:
                desktop.Desktop.load(SimpleNamespace(), gone)
            self.assertIn("项目目录不存在或已被移动", str(caught.exception))
            self.assertIn(gone, str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
