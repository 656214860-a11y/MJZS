# R4059 结果：初步分镜页与资产管理页按钮换行对齐
<!-- round-evidence: {"commit_base": "caf814a9", "credential_hits": 0, "evidence_sha256": "01a8c62bc1c10993", "exit": 0, "failed": 0, "passed": 5, "round": 4059, "tests": "run_selftests.py -k board_assets_buttons"} -->

## 开头三问

- 本轮属于哪种类型：修复轮（任务卡 B-L4-U7b，车道 `codex/l4-buttons-board-assets`，基线 `caf814a9`）。
- 测试跑了吗、三个基线：先红后绿；改前 `tests.test_board_assets_buttons` 3 条失败，改后 5 条全绿；`smoke_test.py` 9/9，`--architecture` 695 条全绿；`--affected` 有 2 条已知环境红（见下）。
- 欠账少了吗：没有新增欠账；`structure.json` 只补本卡测试的归属登记，基线只重写溯源字段，`violations` 未变。

## 改前红与实测数字

- T2（R2）红：「资产」行第二行第一颗「识别背景人物」x=112，本行第一颗 x=169，换行后回到行首标签下面。
- T4（R4）红：两档窗口底部 5 颗按钮宽度为 `手动制作资产` 154、`强制关闭 ComfyUI` 137、`制作记录` 114、`桌面打开 ComfyUI` 137、`浏览器打开 ComfyUI` 150。
- T1（R1）改前即绿：03 页已在用 `FlowBar`，换行后各行第一颗按钮 x 相同、行间不重叠；因此不改 `ui/storyboard_files.py`，T1 留作回归用例。
- T3、T5 改前即绿。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ui/desktop_asset_pages.py` | `asset_page()`：三个行首标签（资产／参考图／资产图片）移出 `FlowBar`，放进独立行框、`FlowBar` 排在标签右边；底部制作行 5 颗按钮统一 `width=STAGE_ACTION_WIDTH`（最长文字实测需要 150px，该宽度实测 154px）。按钮对象、文字、命令、`asset_gated_buttons` 与 `controls` 登记均未改。 |
| `tests/test_board_assets_buttons.py` | 新增 T1–T5 五组用例，量 `winfo_rootx/rooty/width/height/reqwidth`。 |
| `governance/structure.json` | `test_ownership` 新增 `程序/tests/test_board_assets_buttons.py`，`targets` 为 `程序/ui/desktop_asset_pages.py`。 |
| `governance/structure-baseline.json` | `--write-baseline` 只更新 `source_commit` 与两个 sha，`violations` 未动。 |
| `tasks_round/tasks_round_4059_result.md` | 本文件。 |

## 与任务书不同的地方

- 任务书说改 `desktop.py` 的 03 页构建函数；实际 03 页由 `ui/storyboard_files.py` 的 `_StoryboardFilesPage` 搭出，`desktop.py` 只有转调。本卡未改 `desktop.py`，也未改 `ui/storyboard_files.py`（T1 改前已绿）。

## 命令与退出码

| 命令 | 退出码 | 结果 |
|---|---|---|
| `gui_hidden.py … -m unittest tests.test_board_assets_buttons -v`（改前） | 1 | 5 条中 3 红（T2×1、T4×2），T1／T3／T5 绿 |
| 同一条命令（改后） | 0 | 5 条全绿，日志末尾 `OK` |
| `python.exe -B smoke_test.py` | 0 | 9/9 通过 |
| `python.exe -B smoke_test.py --affected storyboard_files desktop_asset_pages` | 1 | 选中 28 个测试文件、1043 条用例；2 条红，均为 `test_pet_ui.FrameBatchSeamTests` 的 `test_auto_keyframe_with_no_gap_finishes_as_completed`／`test_it_says_nothing_when_there_is_no_gap`，报错「未找到 FFmpeg 解码器」（第一类已知环境缺口）；另有 1 条登记跳过。按卡面判定该步通过。 |
| `python.exe -B smoke_test.py --architecture` | 0 | 695 条全绿，失败集合为空 |
| `python.exe -B scripts\dev.py claim` | 0 | 领到轮次 4059 |

## 未覆盖项

- 未跑全量自测（`run_selftests.py --all --safe`）。
- 未 push、未 merge、未改主工作区。
