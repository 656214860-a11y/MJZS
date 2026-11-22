# R4073 结果：阶段文件图标的文件角标压在阶段图形右下角之上并改为醒目的实心色（REQ-S01-93 修订）
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "9c46b3feaef52de4", "exit": 0, "failed": 0, "passed": 151, "round": 4073, "tests": "run_selftests.py -k ui_icons files_panel"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，用户报的使用问题。任务卡 W4-UX-B5I（队列项 UX-B5I），车道 codex/ux-dock-icons，基准 5c85dd13。现象：项目文件停靠面板右侧阶段图标列里，13 个阶段图标右下角的文件角标不明显。根因：角标是白色纸面加灰边，和图标列的底色几乎同色（对比度 1.06）；角标外框贴在 31×34 画布的右下角，只有 15% 的面积落在 24×24 的阶段图形范围内，看上去是挂在图形外面的一小块白。复现：先写 3 条读 PNG 像素的用例，对基准的 13 张图全部失败（见「命令与结果」）。
- （二）测试跑了吗、三个基线：定向 `tests.test_ui_icons.StageFileBadgeTests` 对基准图 3 条全失败、对新图 3 条全过；架构门禁 696 条全过；默认冒烟没有单独跑；全量自测没跑。带界面的 `run_selftests.py -k ui_icons files_panel` 由提交工具在提交时跑，结果以本文件的证据行为准。
- （三）欠账少了吗：少了一条（文件角标不明显）。没有新增欠账。同一条反馈里的「目录左侧空白太多」「鼠标拖动调宽度」分别在 UX-B34、UX-B5W，不在本轮。

## 改了哪些文件

- scripts/build_nav_icons.py：`STAGE_FILE_CANVAS` 由 31×34 改为 28×28，`STAGE_FILE_BADGE_POS` 由 (18,20) 改为 (16,16)，`STAGE_FILE_BADGE_SIZE` 由 12×13 改为 12×12，`STAGE_FILE_BADGE_FOLD` 由 4 改为 3；`_file_badge_layer` 改为 `primary` 实心纸面、`primary_subtle` 折角、两条 `background_card` 文字线，外圈 1 像素不透明的 `background_primary` 描边。18 行新增、14 行删除。
- assets/nav/ 下 13 张 `<阶段>_files.png`：由上面的脚本重新生成（二进制文件）。
- tests/test_ui_icons.py：新增 `StageFileBadgeTests` 3 条用例（角标外框至少四成面积落在阶段图形范围内；角标主色不透明且与图标列底色的对比度不低于 4.5；角标最外一圈全是不透明的图标列底色）和算对比度的 3 个小函数；导入行加 `Counter`、`STAGES`、`NAV_ICON_SIZE`。94 行新增、1 行删除。既有用例没有改动。
- docs/stages/S01_剧本准备.md：REQ-S01-93、DES-S01-93 两条末尾各加一句修订说明，没有动别的行。
- tasks_round/tasks_round_4073_result.md 是本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4073 |
| 把基准（5c85dd13）的 assets/nav 图标导出到临时目录，用临时脚本把 `ui_icons._NAV_DIR` 指到该目录后跑 `StageFileBadgeTests` | 3 条全失败：`test_badge_sits_on_top_of_stage_glyph`（「script: 角标只有 15% 压在阶段图形上，外框 (18, 20, 30, 33)」）、`test_badge_main_color_stands_out_from_rail_background`（「script: 角标主色 (255, 255, 255) 与背景对比度只有 1.06」）、`test_badge_has_one_pixel_light_ring`（「Lists differ: [(18, 20), (19, 20), …] != []」） |
| 同一组用例读车道里重新生成的图 | 3 条全过 |
| python.exe -B scripts\build_nav_icons.py（提交前再跑一遍） | 「共 37 个图标」，退出码 0；37 张 PNG 的 SHA-256 与重跑前全部相同，`git status` 仍是 16 个改动文件 |
| python.exe -B smoke_test.py --architecture | 「Ran 696 tests in 270.446s」「OK」，退出码 0 |
| git diff --numstat | 16 个文件：13 张 PNG（二进制），3 个文本文件共 114 行新增、17 行删除（不含本文件） |

## 如实说明

- （一）13 张图是脚本生成的，不是手工改的：提交前重跑 `scripts/build_nav_icons.py`，生成结果和车道里的图逐字节相同。脚本一并重写其余 24 张导航图标，内容没有变化。
- （二）改前改后的实测数（口径与用例相同，13 张图数值一致）：画布 31×34 → 28×28；角标外框 (18,20)–(30,33) → (16,16)–(28,28)；外框落在 24×24 阶段图形范围内的面积占比 15.4% → 44.4%；角标主色 (255,255,255) → (15,111,192)；主色与图标列底色的对比度 1.06 → 4.90。
- （三）对比度下限 4.5 和「至少四成面积压在阶段图形上」是本轮定的口径，写进了 REQ-S01-93 的修订句；用户的原话只说角标不明显、应该盖在阶段图标之上的右下角，没有给数。用例只核对 `ui_tokens.COLORS` 这一套颜色。
- （四）画布变小了（31×34 → 28×28）。用到这 13 张图的既有用例（含 `tests/test_files_panel_stages.py::StageFileIconTests`）在架构门禁里通过；图标在面板里的实际摆放效果没有在真实界面上看过。
- （五）本卡的经过：改动由需求受理／机动执行窗口写好后，派给编码助手（OpenCode）只做跑测试、跑门禁和提交；当时 3 条用例放在一个新建的测试文件里，被结构规则 STR006（不得新增测试文件）拦下。随后由本窗口接手：把 3 条用例并入既有的 `tests/test_ui_icons.py`，删掉那个新文件，撤回 `governance/structure.json` 上的改动，再跑架构门禁。最终差异里除本结果文件外没有新增文件，也没有 `governance/structure.json`。
- （六）本轮由需求受理／机动执行窗口直接写代码。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。
- （七）架构门禁是 17:34–17:38 跑的；车道里要提交的 16 个文件最后一次内容改动在这之前（17:27），之后只有「命令与结果」里那次重跑生成脚本，内容没变。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上看新图标的显示效果；未 push、未 merge。
- 「目录左侧空白太多」「鼠标拖动调宽度」不在本轮（UX-B34、UX-B5W）。
