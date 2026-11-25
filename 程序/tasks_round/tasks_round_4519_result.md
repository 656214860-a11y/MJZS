# tasks_round_4519_result — FIX-NIGHT-THEME-PET-SYNC（夜间主题切换同步 ui.pet_ui/pet_ui_view 与 GearButton 底色）
<!-- round-evidence: {"commit_base": "589d81065", "credential_hits": 0, "evidence_sha256": "5c19ae89143ed610", "exit": 0, "failed": 0, "passed": 110, "round": 4519, "tests": "run_selftests.py -k ui_theme pet_settings ui_token_contract"} -->

## 三问

- **本轮属于 §3 哪种类型**：修复轮（§3.2，夜间主题切换时 `ui.pet_ui`/`ui.pet_ui_view` 再导出常量与 `GearButton` 默认底色同步修复）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向验收：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_theme pet_settings ui_token_contract` → 共 110 条用例（原有 108 条 + 新增 2 条），0 个文件有红，0 跳过，退出码 `0`。
  - 架构门禁：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → Ran 708 tests in 430.514s，OK，退出码 `0`（改后实测，非历史凭据）。
  - 默认冒烟基线 8/8 与全量 `--all --safe`：本轮未运行（不在本卡验收范围）；全量回归欠账以 `full-safe-receipts.json` 为准，本轮不宣称消灭历史全量欠账。
- **欠账少了吗**：本轮完成 `FIX-NIGHT-THEME-PET-SYNC` 两处真实缺陷修复并补齐 2 条先红后绿自动化回归测试；不涉及主干既有全量欠账变更。

## 缺陷复现方式与改前红灯原文（基线 `589d81065`）

在未改产品代码前，于 `程序/tests/test_ui_theme.py` 的 `ThemeRefreshTests` 新增 2 条回归用例：
1. `test_night_theme_syncs_pet_ui_reexported_tokens`：导入 `ui.pet_ui`、`ui.pet_ui_view`、`ui.pet_ui_support`，执行 `ui_tokens.set_theme('night')` 后断言三处 `GEAR_COLOR`、`GEAR_HOVER`、`CANVAS_BG` 均同步到当前夜间 `COLORS`，切回原主题后均同步恢复。
2. `test_night_theme_gear_button_uses_live_canvas_bg_and_gear_color`：切换夜间主题后创建 `GearButton(self.win)`，断言画布默认底色等于 `COLORS['background_primary']`、手绘兜底路径下 `gear-body` 填色等于 `ui.pet_ui.GEAR_COLOR[0]`、`gear-hole` 填色等于 `COLORS['background_primary']`、显式 `bg='#123456'` 保持不变，且切回原主题后新建 `GearButton` 同步恢复。

改前原样运行第一条验收命令，退出码 `1`，共 110 条用例，1 个文件（`test_ui_theme`）报 2 条红：

```text
共 110 条用例，21.9 秒；1 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

### test_ui_theme（2 条红）

===== test_night_theme_gear_button_uses_live_canvas_bg_and_gear_color (test_ui_theme.ThemeRefreshTests.test_night_theme_gear_button_uses_live_canvas_bg_and_gear_color) =====
AssertionError: '#f7f9f9' != '#10151c'
- #f7f9f9
+ #10151c

===== test_night_theme_syncs_pet_ui_reexported_tokens (test_ui_theme.ThemeRefreshTests.test_night_theme_syncs_pet_ui_reexported_tokens) =====
AssertionError: Tuples differ: ('#2E3842', '#161C22') != ('#475569', '#2E3948')

First differing element 0:
'#2E3842'
'#475569'

- ('#2E3842', '#161C22')
+ ('#475569', '#2E3948')
```

## 改动清单（文件:行号）

- `程序/ui_tokens.py:595-598`：在 `_CONSUMER_BINDS` 中补充 `'ui.pet_ui'`（`CANVAS_BG`、`GEAR_COLOR`、`GEAR_HOVER`）与 `'ui.pet_ui_view'`（`CANVAS_BG`），使切主题时已导入的再导出模块与视图模块同步更新。
- `程序/ui/pet_ui_support.py:318-320`：将 `GearButton.__init__` 默认参数 `bg=CANVAS_BG` 改为 `bg=None`，并在函数体内执行 `bg = CANVAS_BG if bg is None else bg`，保留显式 `bg` 传参行为，未传时读取切主题后的实时 `CANVAS_BG`。
- `程序/tests/test_ui_theme.py:580-644`：新增 `ThemeRefreshTests.test_night_theme_syncs_pet_ui_reexported_tokens` 与 `ThemeRefreshTests.test_night_theme_gear_button_uses_live_canvas_bg_and_gear_color` 两条回归测试。

## 产物改动统计（`git diff --numstat`，不含本结果文件与自动证据）

```text
65	0	程序/tests/test_ui_theme.py
2	1	程序/ui/pet_ui_support.py
4	0	程序/ui_tokens.py
```

## 改后验收命令与尾部输出

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_theme pet_settings ui_token_contract`（退出码 `0`）

```text
共 110 条用例，20.8 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
最近 5 轮自检中位基线：27.6 秒

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 `0`）

```text
----------------------------------------------------------------------
Ran 708 tests in 430.514s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证事项

- 未运行 `smoke_test.py` 默认冒烟档与全量 `run_selftests.py --all --safe`（不在本卡验收范围）。
- 未在可见桌面人工目视核对窗口实绘截图（所有 Tk 回归均在隐藏桌面下经真实控件与画布图元属性断言验证）。
