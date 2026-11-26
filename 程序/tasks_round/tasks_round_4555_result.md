# R4555 结果报告：UX-CLOSE-X 统一全应用全部关闭 `×` 按钮
<!-- round-evidence: {"commit_base": "d3a911aef", "credential_hits": 0, "evidence_sha256": "4a96fcc664a02b66", "exit": 0, "failed": 0, "passed": 6, "round": 4555, "tests": "run_selftests.py -k close_button_unify"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（UI 交互与视觉统一）。
- **测试跑了吗、三个基线过了吗**：已跑。独立只读验收复核者（`2a8e7c73`）复跑定向套件 294/294 + `CloudCloseTests` 12/12 全绿（执行者自测 385/385 + 完整 `test_pet_ui` 643/643 全绿）；默认冒烟 **9/9** 通过（含隐藏桌面探针，对应 8/8 登记基线）；架构门禁 **711/711** 全通过（改前后 0 红）；未跑 `--all --safe` 全量回归（功能分支不触发全量，合并前按规则评估）。
- **欠账少了吗**：少了。3 处原生 `tk.Label` 关闭按钮迁入统一组件，`test_text_component_boundary.py` 的 `STYLED_LABEL_CAPS` 只减不增下调 3 项（`pet_cloud.py` 3→2、`ui_status_bar.py` 3→2、`desktop_idea_bubbles.py` 2→1）；覆盖率模块覆盖数由 148→149。

## 改动摘要
1. 新增 `程序/ui/ui_close_button.py`，提供统一 `CloseButton`（派生自 `SecondaryButton`）及紧凑圆角样式 `Tokens.Close.TButton` / `Tokens.Close.Compact[.Active].TButton`，由 `程序/ui_widgets.py` 导出并随 `setup_styles()` 装配（`ui_widgets.py` 1123/1125 行）。
2. 在 `程序/ui_tokens.py` 新增 `CLOSE_BUTTON_*` 令牌（4px 圆角、14pt/12pt bold 放大 `×`、常态浅底柔和灰 `×`、悬停红底 `danger` + 白 `×` `on_accent`、按下 `danger_pressed`），纳入日/夜主题自动刷新；在 `程序/ui/ui_hover_fade.py` 跳过 `Tokens.Close.` 渐变防首帧闪白。
3. 统一全应用全部 5 处关闭 `×` 按钮：
   - S02 结构剧本编辑器（`程序/ui/desktop_script_pages.py`）：36×37px·10pt → **24×28px·14pt bold**
   - S03 初步分镜编辑器（`程序/ui/storyboard_table_ui.py`）：36×37px·10pt → **24×28px·14pt bold**
   - S01 模型目录条标签（`程序/ui/desktop_idea_bubbles.py`）：原 9pt 裸 Label → **22×24px·12pt bold**，保留 `.close_tag` 与 `<Button-1>` 单次触发
   - 底部状态栏消息历史浮窗（`程序/ui/ui_status_bar.py`）：原 10pt 裸 Label → `CloseButton`
   - 三虎云朵对话框（`程序/ui/pet_cloud.py`，1351/1353 行）：原红底 `tk.Label` → `CloseButton` 统一常态中性+悬停红底白 `×`
4. 同步契约测试（`test_close_button_unify.py` 先红 6→后绿 6、`test_storyboard_page_loading.py`、`test_pet_ui.py`、`test_ui_theme.py`）、分层登记（`_layers.py`）、结构测试归属（`structure.json`/`structure-baseline.json`）、覆盖率基线与 `design_tokens.md`。

## 独立验收结论
- 执行者：独立同模型子代理 `401433e8`（`codex/ux-close-x-unify`，基线 `d3a911aef`）
- 独立验收者：独立只读同模型子代理 `2a8e7c73` — **VERDICT: PASS**（零阻断，未触碰 `desktop_layout.py` 与主工作树）
- 提交状态：本分支已按 `dev.py commit` 生成 `R4555` 证据提交（待性能优化会话释放主目录后合并入 `master`）。
