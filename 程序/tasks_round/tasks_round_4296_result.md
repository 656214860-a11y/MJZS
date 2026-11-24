# R4296 结果：提示文字统一第二批——5 个界面模块换统一文字组件，登记下调到实测
<!-- round-evidence: {"commit_base": "09ca569f", "credential_hits": 0, "evidence_sha256": "f6dcc22610a21b56", "exit": 0, "failed": 0, "passed": 4, "round": 4296, "tests": "run_selftests.py -k text_component_boundary"} -->

## 开头三问

- 本轮属于哪种类型：功能轮（任务卡 L4-U8b，任务书 `tasks_round/L4界面层优化任务书.md` §4.10；车道 `codex/l4-text-unify`，基线 `09ca569f`，工作树 `.agents/worktrees/l4-text-unify`）。
- 测试跑了吗、三个基线：先红后绿。定向命令 `run_selftests.py -k text_component_boundary ui_token` 改前 31 条中 3 红（全部在边界守卫文件，红的原因就是登记下调后产品未改，见「改前红」），改后同命令 31 条全绿、退出码 0。`smoke_test.py --architecture` 第一遍 701 条中 1 红（`pet_cloud.py::Cloud` 类行数棘轮，登记值过期，见「如实说明」），把该文件改动排成等量两行后第二遍 701 条全绿、退出码 0。`smoke_test.py --affected` 因 `test_skills` 环境性失败退出码 1（见「卡外发现」）。全量回归本轮没跑。
- 欠账少了吗：少了。本轮把 8 处自写字体、颜色的 Label 换成统一文字组件或去掉多余 font 参数，登记表相应下调：`desktop_shared_menus.py` 8→6、`stage_model_picker.py` 6→5、`pet_cloud.py` 4→3、`ui_usage_detail.py` 4→0（整行删除，文件进 `TEXT_PAGE_COMPONENTS`）；`desktop_account_page.py` 4 处全是 `FONTS['heading_2']` 标题，按卡面跳过、登记不动。没有新增欠账。

## 改前红

登记表调小、`TEXT_PAGE_COMPONENTS` 加好 `ui_usage_detail.py` 之后、产品代码未动时跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k text_component_boundary ui_token`，退出码 1，31 条用例中 `architecture.test_text_component_boundary` 3 条红：

```text
===== test_hand_styled_labels_only_decrease =====
AssertionError: Lists differ: ['desktop_shared_menus.py 有 8 处 > 登记 6', '[95 chars]记 0'] != []

First list contains 4 additional elements.
First extra element 0:
'desktop_shared_menus.py 有 8 处 > 登记 6'

+ []
- ['desktop_shared_menus.py 有 8 处 > 登记 6',
-  'pet_cloud.py 有 4 处 > 登记 3',
-  'stage_model_picker.py 有 6 处 > 登记 5',
-  'ui_usage_detail.py 有 4 处 > 登记 0'] : 提示文字请用 HintLabel/DescriptionBlock/ProgressLabel 或样式 Muted.TLabel，不要调大登记值：desktop_shared_menus.py 有 8 处 > 登记 6; pet_cloud.py 有 4 处 > 登记 3; stage_model_picker.py 有 6 处 > 登记 5; ui_usage_detail.py 有 4 处 > 登记 0
```

```text
===== test_migrated_pages_do_not_hand_style_raw_labels =====
AssertionError: Lists differ: ['ui_usage_detail.py:57 font', 'ui_usage_d[73 chars]ont'] != []

First list contains 4 additional elements.
First extra element 0:
'ui_usage_detail.py:57 font'

+ []
- ['ui_usage_detail.py:57 font',
-  'ui_usage_detail.py:59 font',
-  'ui_usage_detail.py:66 font',
-  'ui_usage_detail.py:68 font'] : 页面文字须用 HintLabel/DescriptionBlock/ProgressLabel：ui_usage_detail.py:57 font; ui_usage_detail.py:59 font; ui_usage_detail.py:66 font; ui_usage_detail.py:68 font
```

```text
===== test_migrated_pages_import_their_text_components =====
AssertionError: False is not true : ui_usage_detail.py 应导入：HintLabel
```

红的方向是「实测大于登记」（守卫同时抓超登记与欠登记，`test_text_component_boundary.py:187`）。`ui_usage_detail.py` 的两条页面守卫红是因为它的 `TEXT_PAGE_COMPONENTS` 登记与产品改动同批落地、产品还没换，属预期先红。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `tests/architecture/test_text_component_boundary.py` | `TEXT_PAGE_COMPONENTS` 加 `"ui_usage_detail.py": ("HintLabel",)`（第 18 行）；`STYLED_LABEL_CAPS`：`desktop_shared_menus.py` 8→6、`stage_model_picker.py` 6→5、`pet_cloud.py` 4→3、`ui_usage_detail.py` 行删除；`desktop_account_page.py` 4 未动。两条守卫与其它登记一字未动。 |
| `ui/desktop_shared_menus.py` | 第 20 行加 `from ui_widgets import HintLabel`；`SkillPickPanel` 空态提示 `tk.Label`（自写 bg/fg/font/padx/pady）→ `HintLabel`（第 161 行）；`CandidatePopup` 溢出提示 `tk.Label` → `HintLabel`（第 300–301 行）。文字内容、pack 参数不变。 |
| `ui/stage_model_picker.py` | 第 26 行 import 加 `HintLabel`；`_reasoning_block` 的等级说明 `tk.Label` → `HintLabel`（第 329 行）。 |
| `ui/pet_cloud.py` | `Cloud.status` 的 `ttk.Label` 去掉 `font=FONTS['caption']`，保留 `style='Muted.TLabel'`，排成两行（第 391–392 行）。该文件现 1349 行（卡面写约 983，早已超），本轮对它净行数变化为 0。 |
| `ui/ui_usage_detail.py` | 第 17–18 行：`ui_tokens` import 去掉 `FONTS`（文件内已无引用），`ui_widgets` 加 `HintLabel`；4 处带 font 的 `ttk.Label`：两处行首标签（`label+'：'`、`'余额：'`）→ `HintLabel`（第 57、66 行），两处数值 → 不带 font 的 `ttk.Label`（第 59–60、68–69 行）。文字内容、grid 参数不变。 |
| `tasks_round/tasks_round_4296_result.md` | 本文件。 |

`ui/desktop_account_page.py` 未动：登记的 4 处（第 181、207、250、510 行）全部是 `font=FONTS['heading_2']` 的标题文字，卡面明确标题类本卡不动。

## 登记表的数字怎么来的

- 改前实测由守卫自身报出（上文红输出）：`desktop_shared_menus.py` 8、`stage_model_picker.py` 6、`pet_cloud.py` 4、`ui_usage_detail.py` 4、`desktop_account_page.py` 4（未动）。
- 改后实测由守卫转绿反推：`test_hand_styled_labels_only_decrease` 对「实测大于登记」和「登记大于实测」双向都红，绿即登记=实测。逐文件：shared_menus 6、stage_picker 5、pet_cloud 3、usage_detail 0（移入 `TEXT_PAGE_COMPONENTS` 后页面守卫另查 font/fg/foreground 与组件导入，均过）。
- 换组件的字体差异如实说明：`HintLabel` 用 `TEXT_HINT`（`FONTS['caption']`，YaHeiUI 10，`ui_tokens.py:102,320` 起），原自写为 `FONTS['hint']`（YaHeiUI 9）/`FONTS['pet_hint']`（YaHeiUI 8）；这是统一组件自带的 token 字号，属本卡目的。`ui_usage_detail.py` 两处数值 Label 去掉 `font=FONTS['body']` 后走 ttk 默认字体，`ui_theme.py:8` 把 `FONT` 定为 `FONTS['body']`、`ui_theme.py:36` 配到 `'.'`，渲染不变；`pet_cloud.py` 去掉 `font=FONTS['caption']`（YaHeiUI 10）与默认 body（YaHeiUI 10）同档。

## 与任务书不同的地方

- 截图未产出：卡面要求改前改后各截一张隐藏桌面图。已写 `.agent-tmp/l4u8b_shots.py`（车道根、不入库，目录带 `.gitignore`），覆盖四个面：usage_detail 对话框、stage picker 弹层、shared skill 空态与候选溢出弹层、pet cloud。两次 `gui_hidden` 调用均被权限层拒绝，未拿到 PNG，「位置、换行、可见性没有变化」未能目检——列入未覆盖项。
- 行号：任务书按 22:50 主干登记，本车道行号以实测为准（上表）。
- `smoke_test.py --affected` 的模块参数按本轮改动给了 `stage_model_picker desktop_shared_menus pet_cloud pet_ui ui_usage_detail usage`（runner 展开为 16 个测试文件，见下）。

## 如实说明

- `smoke_test.py --architecture` 第一遍红 1 条（`Ran 701 tests in 229.094s`，`FAILED (failures=1)`）：`test_complexity_ratchet.test_registries_track_real_values` 报 `pet_cloud.py::Cloud 实际 1092，登记 1108，请下调到 1107`。原因：第一版把两行的 `self.status = ttk.Label(...)` 合成一行，`Cloud` 类行数净减 1，超出登记的 15 行余量。处理：把它排回两行（与改前行数持平，净 0 行），类行数回到余量内；`test_complexity_ratchet.py` 的登记不在允许清单内、未动。第二遍 `Ran 701 tests in 224.967s`，`OK`，退出码 0。
- `smoke_test.py --affected` 退出码 1：门禁 `run_selftests.py --serial -k stage_model_picker desktop_shared_menus pet_cloud pet_ui ui_usage_detail usage test_model_picker_draft_keep test_pet_ui test_shared_input_ui test_skills test_stage_reasoning` 中 `test_skills.py` `RegistryTests` 两条 `assertEqual(count(), 73)` 实测 71（`test_skill_distribution_matches_the_split_script_flow`、`test_a_temp_program_does_not_blank_out_the_default_registry`）。本轮只动 `ui/` 文字组件与守卫登记，不触碰 skills 注册表；该计数来自 `skills/` 目录扫描，疑似本工作树 skills 清单与断言的 73 不同步，未核实根因——记为卡外发现，未顺手修。
- 未跑全量自测（`run_selftests.py --all --safe`）；未在真实桌面目检；未 push、未 merge、未改主工作区。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git status --porcelain`／`git log -1 --format=%h`／`git rev-parse --abbrev-ref HEAD`（开工核对） | 0 | 干净、`09ca569f`、`codex/l4-text-unify` |
| `PY -B run_selftests.py -k text_component_boundary ui_token`（登记调小后、产品未改） | 1 | 31 条中 3 红，见「改前红」 |
| `PY -B smoke_test.py --affected stage_model_picker desktop_shared_menus pet_cloud pet_ui ui_usage_detail usage` | 1 | 冒烟「通过：9 项，失败：1 项」；唯一失败是 `test_skills` 两条 `71 != 73`（环境性，见上） |
| `PY -B scripts\dev.py claim` | 0 | 领到轮次 4296 |
| `PY -B smoke_test.py --architecture`（第一遍） | 1 | `Ran 701 tests`，`FAILED (failures=1)`：pet_cloud 类行数棘轮 |
| `PY -B smoke_test.py --architecture`（第二遍，pet_cloud 排回两行后） | 0 | `Ran 701 tests in 224.967s`，`OK` |
| `PY -B run_selftests.py -k text_component_boundary ui_token`（最终内容） | 0 | 31 条全绿，0 个文件有红，实际跳过 0 条 |
| `PY -B scripts\gui_hidden.py … -- PY -B ..\.agent-tmp\l4u8b_shots.py <输出目录> <前缀>`（改前、改后各一次） | — | 均被权限层拒绝，未产出截图 |
| `git diff --numstat` | 0 | 见下 |

`git diff --numstat` 原文（提交前、结果文件生成前）：

```text
4	4	"程序/tests/architecture/test_text_component_boundary.py"
4	8	"程序/ui/desktop_shared_menus.py"
2	2	"程序/ui/pet_cloud.py"
2	5	"程序/ui/stage_model_picker.py"
7	8	"程序/ui/ui_usage_detail.py"
```

（git 输出里 `程序` 显示为八进制转义 `\347\250\213\345\272\217`，此处已解码；合计 18 增 27 删，不含本结果文件。）

## 下一轮还剩哪些文件

`STYLED_LABEL_CAPS` 现存 24 行：`asset_detail.py` 11（在途车道 s05-usage 改完才能动）、`desktop_shared_menus.py` 6、`stage_model_picker.py` 5、`desktop_account_page.py` 4（标题类，需先立标题组件的卡）、`pet_cloud.py` 3、`desktop_media_pages.py` 3（FIX-S11 在途）、`desktop_page_nav.py` 3、`ui_status_bar.py` 3，以及 2 处档 9 个文件、1 处档 7 个文件（明细见 `test_text_component_boundary.py:26-52`）。

## 未覆盖项

- 隐藏桌面截图未产出（`gui_hidden` 两次被权限层拒绝），四个面的「位置、换行、可见性没有变化」未目检；`.agent-tmp/l4u8b_shots.py` 留在车道根可复跑。
- 未跑全量自测；未真实桌面目检。
- `test_skills` 71≠73 的根因未查明（卡外发现）。
- 未 push、未 merge；复核、验收、合入归验收窗口。

## 提交

本文件随 R4296 的提交一起入库（分支 `codex/l4-text-unify`）。写本文件时提交号还没有产生，提交号见 `git log`。
