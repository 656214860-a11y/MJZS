# R4057 结果：清理界面模块里没用到的提示框引入
<!-- round-evidence: {"commit_base": "8ec3f4f2", "credential_hits": 0, "evidence_sha256": "7be6e1ca7bb6b9a8", "exit": 0, "failed": 0, "passed": 6, "round": 4057, "tests": "run_selftests.py -k notification_boundary"} -->

## 开头三问

- 本轮属于哪种类型：清理轮（任务卡 B-L4-U12，车道 `codex/l4-unused-imports`，基线 `8ec3f4f2`）。只删未使用的 `messagebox` 引入，不改任何行为。8 个界面模块的改动与新增守卫由上一位执行者完成；本轮只核对、跑门禁、领号、写结果文件、提交，未改其内容一个字。
- 测试跑了吗、三个基线：定向守卫 `tests.architecture.test_notification_boundary` 6 条全过；架构门禁 696 条全过、失败集合为空；默认冒烟 8 项全过（上一位执行者实测）。`--affected` 一步见下，有 16 条环境红，与本卡无关，按卡未重跑。
- 欠账少了吗：少了一条欠账——8 个界面模块不再引入用不到的 `messagebox`，并新增语法树守卫防止回潮。没有新增欠账，未改基线文件。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ui/asset_batch.py` | `from tkinter import ttk,messagebox` → `from tkinter import ttk` |
| `ui/cloud_video.py` | `from tkinter import ttk,messagebox` → `from tkinter import ttk` |
| `ui/keyframe_comfy.py` | `from tkinter import ttk, messagebox` → `from tkinter import ttk` |
| `ui/local_previs.py` | `from tkinter import ttk, messagebox` → `from tkinter import ttk` |
| `ui/native_assets.py` | `from tkinter import ttk, messagebox` → `from tkinter import ttk`（`_AssetControls.build` 内局部引入） |
| `ui/skill_panel.py` | `from tkinter import messagebox, ttk` → `from tkinter import ttk` |
| `ui/tts_settings.py` | `from tkinter import ttk, messagebox` → `from tkinter import ttk` |
| `ui/white_model.py` | `from tkinter import messagebox, ttk` → `from tkinter import ttk` |
| `tests/architecture/test_notification_boundary.py` | `NotificationBoundaryTests` 新增守卫 `test_ui_modules_do_not_import_messagebox`，按语法树判断；允许名单 `UI_MESSAGEBOX_IMPORT_ALLOWED = {'asset_detail.py', 'reference_wall.py', 'storyboard_files.py'}` |
| `tasks_round/tasks_round_4057_result.md` | 本文件 |

保留的 3 个模块仍引入 `messagebox`，因为测试直接用到它们：`asset_detail` 被 `tests/test_asset_detail.py` 用到、`storyboard_files` 被 `tests/test_final_viewer.py` 用到、`reference_wall` 被 `tests/test_reference_wall.py` 用到。

如实说明：上述实现与测试由**上一位执行者**完成，本轮只核对与提交。

## 命令与退出码

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git status --porcelain` | 0 | 正好 9 个已修改文件，与卡面一致 |
| `git diff --stat` | 0 | 8 个 ui 文件各 +1/−1；守卫文件 +26 |
| `python.exe -B -m unittest tests.architecture.test_notification_boundary -v` | 0 | 6 条全过 |
| `python.exe -B smoke_test.py --architecture` | 0 | 696 条通过，失败集合为空，未改任何基线文件 |
| `python.exe -B scripts\dev.py claim` | 0 | 领到轮次 4057 |

## 改动前后

- 改前跑新守卫失败，失败信息列出的正是这 8 个模块（`asset_batch.py`、`cloud_video.py`、`keyframe_comfy.py`、`local_previs.py`、`native_assets.py`、`skill_panel.py`、`tts_settings.py`、`white_model.py`），原有 5 条通过。
- 改后守卫 6 条全过；默认冒烟 8 项全过；架构门禁 696 条全过。

## `--affected` 如实记录

`smoke_test.py --affected asset_batch cloud_video keyframe_comfy skill_panel white_model` 选中 58 个测试文件、1661 条用例，4 个文件共 16 条红：

- 14 条报「未找到 FFmpeg 解码器」（`test_keyframe_evidence` 11 条、`test_pet_ui` 2 条、`test_stage_parallel` 1 条）：本机 `运行环境/ffmpeg/bin` 不存在，PATH 里也没有 ffmpeg。
- 2 条是 `tests/test_skills.py` 的 `71 != 73`：工作树里没有主工作区那些未跟踪的技能数据。

总控已逐条核对，并在不含本卡改动的 master 上复现了同样的红，判定这 16 条全部是环境缺口，**没有本卡引入的新红**，与本卡改动无关。因此这一步按卡未重跑，也没有安装 FFmpeg 或复制主工作区数据去消红。

## 未覆盖项

- 未跑全量自测（`run_selftests.py --all --safe`）。
- 未 push、未 merge、未 rebase；提交哈希见提交后 `git log -1`。
