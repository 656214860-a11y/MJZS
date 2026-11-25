# tasks_round_4511_result — UX-SLATE-PALETTE-SYNC（全套高级灰配色适配与设置页去绿）
<!-- round-evidence: {"commit_base": "444b6a359", "credential_hits": 0, "evidence_sha256": "4ae99ca628b719c9", "exit": 0, "failed": 0, "passed": 258, "round": 4511, "tests": "run_selftests.py -k ui_token_contract ui_theme ui_modern_system pet_settings shared_input_ui ui_motion sidebar_project_title"} -->

## 三问

- **本轮属于 §3 哪种类型**：修复轮（§3.2，UI 高级灰设计令牌同步与设置页提示条去绿）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向验收 1：`run_selftests.py -k ui_token_contract ui_theme ui_modern_system pet_settings shared_input_ui ui_motion` → 共 255 条用例（原有 250 条 + 新增 5 条），0 文件有红，0 跳过，退出码 `0`。
  - 定向验收 2：`run_selftests.py -k pet_ui` → 共 643 条用例（原有 642 条 + 新增 1 条），0 文件有红，0 跳过，退出码 `0`。
  - 架构门禁：`smoke_test.py --architecture` → Ran 708 tests in 287.672s，OK，退出码 `0`（改后实测，非历史凭据）。
  - 默认冒烟基线 8/8：本轮未跑 `smoke_test.py` 默认档（卡面验收命令未含）；全量 `--all --safe` 未跑，欠账口径以 `full-safe-receipts.json` 为准，本轮不宣称消灭历史全量欠账。
- **欠账少了吗**：本轮完成 `UX-SLATE-PALETTE-SYNC` 单卡配色适配与 6 条自动化回归测试，不涉及主干既有全量欠账变更。

## 缺陷复现方式与改前红灯原文（基线 `444b6a359`）

在未改产品代码前，于允许修改的 4 个测试文件新增 6 条回归测试：
1. `tests/test_ui_token_contract.py`：校验日间/夜间两套调色板的主色、次按钮、选中态、完成行底为低饱和冷中性高级灰（淘汰旧亮蓝 `#0F6FC0`/`#DBEAFE`/`#E8F3FB`/`#1D9BF0` 与绿底 `#F0FDF4`），且满足按压/悬停/常态明度递减及 `design_tokens.md` 双主题全登记。
2. `tests/test_ui_theme.py`：校验设置页提示条 `PaleGreenHint.TLabel` 使用 `surface_hover` + `text_secondary`（保留样式名、非绿色、对比度 ≥4.5:1），并校验侧栏项目卡片 `ProjectNameList` 的 `current` 行标签使用 `selection_bg` 与 `selection_text`。
3. `tests/test_pet_ui.py`：校验三虎头像 `SANHU_FUR`/`SANHU_EAR`/`SANHU_STAR` 与三档猫爪 `LEVEL_COLORS` 属于低饱和冷墨高级灰、三档明度严格递减且 `CAPTION_INK == '#000000'`。
4. `tests/test_shared_input_ui.py`：校验发送键圆面底色 `COLORS['primary']` 与续写条 `Composer.Notice.TFrame` 跟随高级灰令牌，无残留亮蓝。

改前原样运行第一条验收命令，退出码 `1`。`test_ui_token_contract` 实际运行并报 16 条子测试红（其余 6 个 GUI 文件当次因跨树全量测试持有 GUI 令牌超过 60 秒被 `[GUI_DEFERRED]` 延后，未计通过）：

```text
共 8 条用例，61.0 秒；1 个文件有红
### test_ui_token_contract（16 条红）
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='primary', value='#0F6FC0') =====
AssertionError: '#0F6FC0' unexpectedly found in {'#DBEAFE', '#0A4F8C', '#0C5FA6', '#E8F3FB', '#1D9BF0', '#0F6FC0'} : 不得残留旧亮蓝：primary=#0F6FC0
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='primary_hover', value='#0C5FA6') =====
AssertionError: '#0C5FA6' unexpectedly found ... : 不得残留旧亮蓝：primary_hover=#0C5FA6
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='primary_pressed', value='#0A4F8C') =====
AssertionError: '#0A4F8C' unexpectedly found ... : 不得残留旧亮蓝：primary_pressed=#0A4F8C
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='primary_subtle', value='#E8F3FB') =====
AssertionError: '#E8F3FB' unexpectedly found ... : 不得残留旧亮蓝：primary_subtle=#E8F3FB
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='secondary_pressed', value='#93C5FD') =====
AssertionError: 106 not less than or equal to 45 : secondary_pressed=#93C5FD 通道差过大，不属低饱和高级灰
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='secondary_text', value='#1E40AF') =====
AssertionError: 145 not less than or equal to 45 : secondary_text=#1E40AF 通道差过大，不属低饱和高级灰
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='selection_bg', value='#E8F3FB') =====
AssertionError: '#E8F3FB' unexpectedly found ... : 不得残留旧亮蓝：selection_bg=#E8F3FB
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='selection_text', value='#0A4F8C') =====
AssertionError: '#0A4F8C' unexpectedly found ... : 不得残留旧亮蓝：selection_text=#0A4F8C
===== test_slate_palette_replaces_legacy_blue_and_green_tokens (theme='day', key='selection_border', value='#B7D3EC') =====
AssertionError: 53 not less than or equal to 45 : selection_border=#B7D3EC 通道差过大，不属低饱和高级灰
===== test_slate_palette_replaces_legacy_blue_and_green_tokens =====
AssertionError: '#F0FDF4' == '#F0FDF4'
```

## 改动清单（文件:行号）

- `程序/ui_tokens.py:24-64`：将 `_DAY_COLORS` 的 16 个主色/次按钮/选中态/进度/完成行令牌切换为深石墨高级灰冷中性体系（`primary=#2E3842`、`primary_hover=#212931`、`primary_pressed=#161C22`、`primary_subtle=#E9EEF1`、`primary_text=#33414E`、`focus=#4B5A68`、`accent=#64748B`、`progress=#3D4B58`、`secondary_bg=#E8EDF0`、`secondary_hover=#DCE3E7`、`secondary_pressed=#CFD8DE`、`secondary_text=#1F2933`、`selection_bg=#E5EBEF`、`selection_text=#141B22`、`selection_border=#BDC8D0`、`row_done_bg=#EFF3F4`），保留语义状态色与全部既有键名。
- `程序/ui_tokens.py:458-501`：将 `PET_PALETTE`（40 项）切换为高级灰冷墨层次（`fur=#8A96A3`、`ear=#B8C2CC`、`muzzle=#F2F5F7`、`ink=#1E2730`、`star=#5C6B7A`，三档猫爪 `#8E9BA8`/`#64748B`/`#3B4856` 由浅到深互异，四档心情同步收进冷灰体系，`caption_ink` 保持 `#000000`）。
- `程序/ui_tokens.py:506-553`：将 `_NIGHT_COLORS` 的 16 个对应令牌同步切换为夜间高级灰冷中性体系（`primary=#475569`、`primary_hover=#3A4758`、`primary_pressed=#2E3948`、`primary_subtle=#242E3B`、`primary_text=#CBD5E1`、`focus/accent/progress=#94A3B8`、`secondary_*=#283240/#323E4F/#3C4A5E/#E2E8F0`、`selection_*=#2B3646/#E2E8F0/#4B5B70`、`row_done_bg=#222B38`）。
- `程序/design_tokens.md:21-53, 83-115, 188`：同步更新日间板、夜间板全部 16 项高级灰 hex 登记与主色说明，确保双主题全部颜色 100% 匹配代码。
- `程序/ui/ui_theme.py:53-55`：将 `PaleGreenHint.TLabel` 样式改为 `background=COLORS['surface_hover']`、`foreground=COLORS['text_secondary']`，保持 `padding=(SPACING['sm'], SPACING['xs'])` 与样式名 `PaleGreenHint.TLabel` 不变。
- `程序/ui/desktop_sidebar_project.py:309-310, 340-341`：项目卡片 `current` 行标签改为 `background=COLORS['selection_bg'], foreground=COLORS['selection_text']`。
- `程序/ui/ui_composer_style.py`（只读核验）：确认发送键圆环、实心圆底（`sync_send_art`）、续写条全部自动消费新高级灰 `COLORS` 令牌，无硬编码亮蓝，无需改动。
- `程序/tests/test_ui_token_contract.py:64-93`：新增 2 条双主题高级灰契约与 `design_tokens.md` 全登记测试。
- `程序/tests/test_ui_theme.py:148-183`：新增 2 条 `PaleGreenHint.TLabel` 去绿与侧栏项目卡片 `current` 高亮测试。
- `程序/tests/test_pet_ui.py:2396-2426`：新增 1 条三虎头像与三档猫爪高级灰冷墨递进契约测试。
- `程序/tests/test_shared_input_ui.py:1564-1580`：新增 1 条发送键实心圆面与续写条高级灰令牌测试。

## 产物改动统计（`git diff --numstat`，不含本结果文件与自动证据）

```text
33	33	程序/design_tokens.md
31	0	程序/tests/test_pet_ui.py
17	0	程序/tests/test_shared_input_ui.py
36	0	程序/tests/test_ui_theme.py
30	0	程序/tests/test_ui_token_contract.py
4	2	程序/ui/desktop_sidebar_project.py
3	3	程序/ui/ui_theme.py
77	76	程序/ui_tokens.py
```

## 改后验收命令与尾部输出

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_token_contract ui_theme ui_modern_system pet_settings shared_input_ui ui_motion`（退出码 `0`）

```text
共 255 条用例，68.7 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
最近 5 轮自检中位基线：24.0 秒

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_ui`（退出码 `0`）

```text
共 643 条用例，73.6 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
最近 5 轮自检中位基线：37.0 秒

ALL TESTS PASSED
```

3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 `0`）

```text
----------------------------------------------------------------------
Ran 708 tests in 287.672s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证事项

- 未运行 `smoke_test.py` 默认冒烟档与全量 `run_selftests.py --all --safe`（不在本卡验收范围）。
- 未在可见桌面人工目视核对窗口实绘截图（所有 Tk 回归均在隐藏桌面下经真实样式与几何断言验证）。
