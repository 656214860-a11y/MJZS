# R1979 合并轮：把按钮一致性分支 codex/wip-R1974 合入 master

## 改动
- 把 `codex/wip-R1974`（R1970／R1973／R1977：按钮最小宽度与间距令牌、页面宽度走令牌、弹窗底栏顺序、阶段弹窗脱离 Compact.TButton、侧栏紧凑模式补完）合入 master（合并前 `ecc7d849`）。
- 唯一冲突在 `desktop_writing_page.py` 的 `ui_tokens` 导入行：采用 `BUTTON_GAP_TIGHT` 版本（不再用 `SCRIPT_ACTION_PADDING`），并保留 master 已有的 `desktop_file_card` 导入。
- `project_status.md` 未改动（分支只写 `tasks_round`）；按 AGENTS.md 合并后补记另起一轮。

## 凭据
- `git diff <合并前master> -- project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'`：输出为空。
- 暂存区 `git diff --cached --stat -- project_status.md`：无改动。

## 验证
- 合并后相关 200 条（button_consistency、ui_style_engine、ui_modern_system、button_boundary、token_boundary、desktop_compact_layout、manual_plan、module_size、script_file、script_structure、skill_panel_dropdown、account_background、combobox 等）仅 1 条红：`architecture.test_module_size_ratchet`，`ui_widgets.py` 1535 行 > 1500。合并前 master 上该文件为 1536 行，同一条红本来就在，本合并使其减 1 行；拆分留待后续轮次。断言未动。
- 未跑 --all --safe，未真实窗口目测。
