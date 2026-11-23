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

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import desktop
import engine
import local_video
import projects as projects_mod
from contract import project_stages
from desktop_project_pages import ProjectPageServices
from stage_execution_service import project_registry_gateway


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

    def test_a_folder_without_config_is_called_an_empty_shell(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'p'
            p.mkdir()
            (p / 'ui_settings.json').write_text('{}', encoding='utf-8')
            for opener in (engine.Studio, local_video.open_studio):
                with self.subTest(opener=opener), self.assertRaises(ValueError) as caught:
                    opener(p)
                message = str(caught.exception)
                self.assertIn('没有项目配置文件 config.json', message)
                self.assertIn('重新查找项目', message)
                self.assertIn(str(p), message)
                self.assertNotIn('Errno', message)
                self.assertNotIn('无法读取', message)

    def test_a_corrupt_config_is_still_called_unreadable(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'p'
            p.mkdir()
            (p / 'config.json').write_text('{"episode_dir":', encoding='utf-8')
            for opener in (engine.Studio, local_video.open_studio):
                with self.subTest(opener=opener), self.assertRaises(ValueError) as caught:
                    opener(p)
                message = str(caught.exception)
                self.assertIn('config.json 无法读取', message)
                self.assertNotIn('没有项目配置文件', message)

    def test_a_config_that_is_not_an_object_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'p'
            p.mkdir()
            (p / 'config.json').write_text('[]', encoding='utf-8')
            for opener in (engine.Studio, local_video.open_studio):
                with self.subTest(opener=opener), self.assertRaises(ValueError) as caught:
                    opener(p)
                self.assertIn('顶层必须为对象', str(caught.exception))

    def test_opening_a_missing_folder_uses_the_standard_sentence(self):
        with tempfile.TemporaryDirectory() as td:
            gone = Path(td) / '早就删掉的项目'
            for call in (lambda: engine.read_project_config(gone),
                         lambda: local_video.open_studio(gone)):
                with self.subTest(call=call), self.assertRaises(ValueError) as caught:
                    call()
                message = str(caught.exception)
                self.assertIn('项目目录不存在或已被移动', message)
                self.assertNotIn('Errno', message)
            self.assertFalse(gone.exists())


def make_service(folder, name="故事_20261001"):
    """与改名找回用例同款的登记服务：程序目录与项目库全在临时目录。"""
    app = Path(folder) / "程序"; base = Path(folder) / "库" / "项目"; base.mkdir(parents=True)
    write(app / "config.json", {"downloads_root": str(Path(folder) / "库")})
    write(app / "projects.json", {"active": str(base / name), "projects": [
        {"name": "故事", "path": str(base / name), "created_at": 1, "status": "making"}]})
    from projects import Projects
    return Projects(app, gateway=project_registry_gateway()), base


def dir_listing(root):
    """目录内相对路径清单：失效登记的目录在任一动作前后必须一字不变。"""
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def fake_desktop(service):
    """沿用假桌面写法：真服务 + MagicMock 宿主，不建真实窗口。"""
    app = MagicMock()
    app.projects = service
    app._project_result_data = lambda r: desktop.Desktop._project_result_data(app, r)
    app._sync_project_picker = lambda **kw: desktop.Desktop._sync_project_picker(app, **kw)
    app._sync_project_group_styles = lambda: desktop.Desktop._sync_project_group_styles(app)
    app.mark_current_project = lambda: desktop.Desktop.mark_current_project(app)
    app.fill_projects = lambda tree: desktop.Desktop.fill_projects(app, tree)
    app.project_row_text = lambda p: desktop.Desktop.project_row_text(app, p)
    app.reload = lambda: desktop.Desktop.reload(app)
    app.reload()
    return app


def chooser_desktop(service, win):
    """项目选择窗用例的假桌面：真实 Tk + 真服务，确认框换成可断言的替身。"""
    app = MagicMock()
    app.win = win; app.root = None; app.projects = service
    app.project_page_services = ProjectPageServices(
        open_path=lambda *a, **k: desktop.open_path(*a, **k),
        context_menu=lambda *a, **k: desktop.ContextMenu(*a, **k),
        confirm=MagicMock(return_value=False))
    app._cleanup_project_path = None; app._startup_project_choice = False
    app.daily_project_choice = lambda: None
    app.safe = lambda fn: fn()
    app._project_result_data = lambda r: desktop.Desktop._project_result_data(app, r)
    app.fill_projects = lambda tree: desktop.Desktop.fill_projects(app, tree)
    return app


def popup_parts(win):
    """选择窗建好后取（弹窗, 列表, 动作按钮表）。"""
    popup = next(w for w in win.winfo_children() if isinstance(w, tk.Toplevel))
    tree = next(w for w in descendants(popup) if isinstance(w, ttk.Treeview))
    buttons = {str(w.cget('text')): w for w in descendants(popup) if isinstance(w, ttk.Button)}
    return popup, tree, buttons


def notice_text(popup):
    """选择窗顶部提示标签的当前文字（textvariable 内容）。"""
    for widget in descendants(popup):
        if isinstance(widget, ttk.Label) and str(widget.cget('textvariable')):
            return popup.tk.call('set', str(widget.cget('textvariable')))
    return ''


class EmptyShellOpenTests(unittest.TestCase):
    """登记还在、目录也在但没有 config.json（空壳）时，打开与列表的找回行为。"""

    def shell_and_candidate(self, service, base):
        """空壳登记 + 库里一个指回它的高匹配候选目录。"""
        old = service.info["active"]; shell = Path(old); shell.mkdir()
        (shell / "ui_settings.json").write_text("{}", encoding="utf-8")
        new = base / "新故事_20261001"; story = project_stages.storyboard(new) / "分镜拆分"
        story.mkdir(parents=True)
        write(new / "config.json",
              {"episode_dir": str(Path(old) / "03初步分镜" / "分镜拆分"),
               "episode_file": str(Path(old) / "03初步分镜" / "分镜拆分" / "episode.json")})
        return old, shell, new

    def test_desktop_load_claims_shell_and_refreshes_picker_before_page(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old, shell, new = self.shell_and_candidate(service, base)
            before = dir_listing(shell)
            app = fake_desktop(service)
            self.assertIn(old, [p["path"] for p in app._picker_items])
            with patch.object(desktop, "open_studio", return_value=None):
                desktop.Desktop.load(app, old)
            self.assertEqual(app.root, new)
            self.assertEqual(service.info["active"], str(new))
            app._sync_desktop_project_paths.assert_called_once_with(old, str(new))
            self.assertEqual([p["path"] for p in app._picker_items], [str(new)])
            self.assertIn("空目录没有动", app.status.set.call_args.args[0])
            self.assertEqual(dir_listing(shell), before, "认领不得往失效登记的目录里写东西")
            self.assertTrue(shell.is_dir(), "认领成功后原目录原样留在磁盘上")

    def test_desktop_load_on_shell_without_match_reports_shell_sentence(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old = service.info["active"]; shell = Path(old); shell.mkdir()
            (shell / "ui_settings.json").write_text("{}", encoding="utf-8")
            app = fake_desktop(service)
            with patch.object(desktop, "open_studio", return_value=None), \
                    self.assertRaises(ValueError) as caught:
                desktop.Desktop.load(app, old)
            message = str(caught.exception)
            self.assertIn("没有项目配置文件", message)
            self.assertIn("留下的空壳", message)
            self.assertIn("重新查找项目", message)
            self.assertNotIn("config.json：", message)
            self.assertTrue(projects_mod.needs_cleanup_after_open_error(caught.exception))
            engine_sentence = ('项目文件夹里没有项目配置文件 config.json：' + old
                               + '。这个文件夹可能是项目被移动或改名后留下的空壳；'
                               + '请在项目选择窗口选中这个项目后点「重新查找项目」，或把原来的项目文件夹放回原位后再打开。')
            self.assertFalse(projects_mod.needs_cleanup_after_open_error(ValueError(engine_sentence)),
                             'engine 的空壳报错不能走清理登记路径')
            self.assertEqual(dir_listing(shell), ["ui_settings.json"],
                             '打开失败不得往失效登记的目录里写东西')

    def test_project_row_text_marks_openable_missing_and_shell(self):
        with tempfile.TemporaryDirectory() as td:
            ok = Path(td) / "好项目"; ok.mkdir(); (ok / "config.json").write_text("{}", encoding="utf-8")
            gone = Path(td) / "已移走"
            shell = Path(td) / "空壳"; shell.mkdir(); (shell / "ui_settings.json").write_text("{}", encoding="utf-8")
            desk = MagicMock(); desk.root = None
            rows = {p["name"]: desktop.Desktop.project_row_text(desk, p) for p in
                    ({"name": "好", "path": str(ok)}, {"name": "移", "path": str(gone)},
                     {"name": "壳", "path": str(shell)})}
            self.assertNotIn("（", rows["好"])
            self.assertIn("目录已失效", rows["移"])
            self.assertIn("没有项目配置", rows["壳"])
            self.assertNotIn("目录已失效", rows["壳"])

    def test_delete_selected_project_on_shell_warns_and_cancel_preserves(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old = service.info["active"]; shell = Path(old); shell.mkdir()
            (shell / "ui_settings.json").write_text("{}", encoding="utf-8")
            free = base / "落单_20261002"; (free / "01剧本准备").mkdir(parents=True)
            before = dir_listing(shell)
            win = tk.Tk(); win.withdraw()
            try:
                app = chooser_desktop(service, win)
                desktop.Desktop._choose_project_impl(app)
                popup, tree, buttons = popup_parts(win)
                try:
                    tree.selection_set(old)
                    with patch.object(service, "delete", MagicMock()) as mocked_delete:
                        buttons["删除选中项目"].invoke()
                    message = app.project_page_services.confirm.call_args.args[2]
                    self.assertIn("建议先取消", message)
                    self.assertIn("没有项目配置文件", message)
                    self.assertIn("落单_20261002", message)
                    self.assertNotIn("文件夹", message, "删除警告统一叫「目录」")
                    mocked_delete.assert_not_called()
                    self.assertIn(old, [x["path"] for x in service.info["projects"]])
                    self.assertEqual(dir_listing(shell), before)
                finally:
                    if popup.winfo_exists():
                        popup.destroy()
            finally:
                win.destroy()

    def test_open_project_or_cleanup_on_shell_status_uses_shell_wording(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old = service.info["active"]; shell = Path(old); shell.mkdir()
            app = MagicMock()
            app.projects = service
            app.status = MagicMock()
            app.choose_project = MagicMock()
            app.load = MagicMock(side_effect=ValueError(projects_mod.empty_shell_open_error(old)))
            self.assertFalse(desktop.Desktop.open_project_or_cleanup(app, old))
            text = app.status.set.call_args.args[0]
            self.assertNotIn("剧本已删除", text)
            self.assertNotIn("删除选中项目", text)
            self.assertIn("重新查找项目", text)
            app.choose_project.assert_called_once_with()

    def test_chooser_enter_on_shell_shows_shell_notice(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old = service.info["active"]; shell = Path(old); shell.mkdir()
            win = tk.Tk(); win.withdraw()
            try:
                app = chooser_desktop(service, win)
                app.load = MagicMock(side_effect=ValueError(projects_mod.empty_shell_open_error(old)))
                desktop.Desktop._choose_project_impl(app)
                popup, tree, buttons = popup_parts(win)
                try:
                    tree.selection_set(old)
                    buttons["进入项目 →"].invoke()
                    text = notice_text(popup)
                    self.assertIn("没有项目配置文件", text)
                    self.assertIn("重新查找项目", text)
                    self.assertNotIn("项目目录不存在", text)
                    self.assertNotIn("剧本已删除", text)
                finally:
                    if popup.winfo_exists():
                        popup.destroy()
            finally:
                win.destroy()

    def test_refind_on_openable_registration_says_still_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            service, base = make_service(td)
            old = service.info["active"]; shell = Path(old); shell.mkdir()
            (shell / "config.json").write_text("{}", encoding="utf-8")
            win = tk.Tk(); win.withdraw()
            try:
                app = chooser_desktop(service, win)
                desktop.Desktop._choose_project_impl(app)
                popup, tree, buttons = popup_parts(win)
                try:
                    tree.selection_set(old)
                    buttons["重新查找项目"].invoke()
                    self.assertIn("还在原位", notice_text(popup))
                finally:
                    if popup.winfo_exists():
                        popup.destroy()
            finally:
                win.destroy()

    def test_shell_sentences_call_a_directory_a_directory(self):
        """空壳相关的提示统一叫「目录」，不混用「文件夹」（文案规则：目录就叫目录）。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            shell = base / "shell"; shell.mkdir()
            taken = base / "taken"; taken.mkdir()
            info = {"projects": [{"path": str(shell)}, {"path": str(taken)}]}
            sentences = {
                "打开提示": projects_mod.EMPTY_SHELL_OPEN_NOTICE,
                "打开报错": projects_mod.empty_shell_open_error(shell),
                "认领成功": projects_mod.claimed_registration_notice(shell),
                "手动认领已登记的目录": projects_mod.manual_claim_error(info, base, shell, taken),
            }
        for name, text in sentences.items():
            with self.subTest(name):
                self.assertNotIn("文件夹", text)
                self.assertIn("目录", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
