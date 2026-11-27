# R4630 结果：C20 日/夜主题实时切换补漏（已展开下拉框、透明色键浮窗与 success_text 映射）
<!-- round-evidence: {"commit_base": "4c24a49ac", "credential_hits": 0, "evidence_sha256": "08822f7d049880a2", "exit": 0, "failed": 0, "passed": 65, "round": 4630, "tests": "run_selftests.py -k theme style_engine"} -->

1. **轮次类型**：UI 主题热切换修复轮（卡 C20，分支 `codex/opt-c20-theme-live`，工作树 `.wt/opt_c20`）。
   - 核实 R4523 已实现绝大多数存量控件与图标的实时换色，但在真 Tk 复核中发现 3 处已建成界面热切换缺口并就地修复于 `ui/ui_theme.py`：
     - `color_map()`：先跳过未变化的色键（`before.lower() == after.lower()`），避免日→夜时 `success`（`#15803D -> #15803D`）遮蔽 `success_text`（`#15803D -> #4ADE80`），修复状态栏成功提示等前景在深色底上保持暗绿的问题。
     - `_recolor_combobox_popdown()` + `recolor_tree()`：对已展开过的 `ttk.Combobox`，按旧→新调色板语义同步其 Tcl 子控件 `.popdown.f.l`（`Listbox`）的 `-background`/`-foreground`/`-selectbackground`/`-selectforeground`（它不在 Python `winfo_children()` 中）。
     - `_recolor_transparentcolor()` + `recolor_tree()`：对带 `-transparentcolor` 属性的顶层窗（如已打开的三虎云朵 `PetCloud`），随 `bg` 同步更新透明色键，避免切主题后底板变为不透明矩形。
   - 在 `tests/test_ui_theme.py`（`ThemeRefreshTests`）追加 3 条先红后绿回归用例，未动任何既有测试断言。
2. **测试与三基线**：
   - `run_selftests.py -k theme style_engine`：3 个测试文件 / 65 条用例全过，0 跳过（exit 0，6.8s）。
   - `smoke_test.py`：9/9 通过（exit 0）。
   - 架构门禁（`test_module_size_ratchet`、`test_complexity_ratchet`、`test_static_hygiene`、`test_constant_condition_ratchet`、`test_scrollbar_theme_boundary`、`test_box_boundary`）：26/26 通过（exit 0）。
   - 覆盖率／模块规模／结构三基线未放宽、未弱化；`ui/ui_theme.py` 680 行，仍在 800 行默认上限内；未触碰 `ui_tokens.py`（C19）与 `_layers.py`（C10）。
3. **欠账变化**：
   - 清零已建成页面在日/夜实时切换中的 3 处残留盲区（已展开下拉框 Listbox、`-transparentcolor` 浮窗、`success_text` 颜色碰撞）。
   - 无新增欠账。
