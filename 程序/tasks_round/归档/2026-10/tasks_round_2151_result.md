# R2151 结果：附档卡片选中时外框断线（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户报剧本准备页输入框里附档卡片选中时，主色外框断成几截。
- 测试和三个基线：在 worktree 分支 `claude/attach-focus` 上运行（经 gui_hidden）。
  - `run_selftests.py -k script_composer writing_page idea ui_composer ui_widgets button_consistency ui_theme`：327 条全过。
  - 默认冒烟：通过。
  - `--architecture`：411 项全过。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。
  - 真机未手动核对；隐藏桌面上用 PrintWindow 逐像素读过卡片四边。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
卡片内边距 `(8, 4)` 写在样式 `Tokens.Chip*.TFrame` 上，但 ttk.Frame 摆放子控件只看控件自身的 `padding` 选项，不看样式里的。图标、文件名都从卡片外沿 `x=0, y=0` 开始，白底把圆角边框盖断：文件名盖住上下边，图标盖住左边。

## 改动
- `desktop_idea_chat.py`：卡片 `ttk.Frame` 直接带 `padding=(SPACING['sm'], SPACING['xs'])`；× 的 `place` 从内边距里侧量起，加 `x=SPACING['sm'], y=-SPACING['xs']` 抵掉，× 仍贴卡片外沿右上角。
- `ui_composer_style.py`：删掉样式里不生效的 padding，留注释指向控件。

## 用户取舍
修好上、下、左三边。右上角 × 所在一小段仍被 × 盖住：要修就得把 × 往里收，会改动 `test_referenced_chip_is_highlighted_and_close_sits_top_right` 里「× 距卡片外角 ≤2 像素」的断言；用户选择保留 × 位置，断言未动。

## 测试
- 新增 `tests/test_script_composer.py::test_chip_content_keeps_off_the_border`：卡片里 pack 的子控件离上、下、左边至少一个内边距。修复前失败（`0 not greater than or equal to 8`），修复后通过。
- 已有测试断言未动。

## 用户需做
重启应用后生效。
