# R1868 结果（功能轮）：剩余数字间距就近令牌化、图标配色接 COLORS、token 门禁收紧

## 改动
- 11 个文件共 44 处数字 `padx/pady` 改为 `SPACING` 取值（用户 2026-10-22 授权“就近取 token”）：
  取最近一档，两档等距（2／6／10／14）取较小档，0 → `SPACING['none']`；最大偏差 2px（18→16、5→4、7→8、3→4）。
  文件：agent/prompt_optimizer、asset_reference_import、background_characters、cell_hover、cloud_assets、
  native_assets、qwen_setup、seedream_settings、shared_video_controls、storyboard_selection、workflow_settings。
- `ui_icons.py` 4 处 hex 改 `COLORS`：#ffffff→background_card（同色）、#2b78c5→primary、#aab6c6→border_input_hover、#edf1f5→surface_hover（后三者有细微色差）。
- `tests/architecture/test_token_boundary.py`：HEX 基线只剩 previs_monitor 1 处（导出 HTML 的 CSS，非 Tk）；PADDING 基线清空（零容忍）。
- `tests/test_ui_icons.py`：默认箭头色期望值 '#ffffff' 同步为 `COLORS['background_card']`（契约有意变更，同色、断言强度未动）。

## 核查
- 双调色板问题已不存在：ui_theme.py 无 hex，全部取自 ui_tokens（此前路线图待办过期）。

## 验证（本轮实测）
- 定向 `run_selftests.py -k token_boundary ui_icons …` 39 条 0 红（隐藏桌面）。
- 默认冒烟通过。
- 架构门禁 384 条：2 红（test_agents_md 读 维护记录/基准历史.json、test_skill_reference_injection 读子模块文件），
  均为本 worktree 缺文件；撤下本轮改动后在 HEAD 复跑同样 2 红，判定为环境问题、非本轮引入。
- 全量未跑；最近绿全量仍为 R1850。未做实机视觉验收。
