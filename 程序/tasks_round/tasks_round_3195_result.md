# R3195 结果（UI 统一组件标准任务书 U3：图标取用门禁）
<!-- round-evidence: {"commit_base": "dfcb3cde", "credential_hits": 0, "evidence_sha256": "de4752e590d52a67", "exit": 0, "failed": 0, "passed": 29, "round": 3195, "tests": "run_selftests.py -k icon_source ui_icons architecture.test_agents_md"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（U3）。在既有图标入口之上新增静态门禁，只为 MDL2 字体写尺寸注释，不迁移或增加图标常量。
2. **测试跑了吗、三个基线过了吗？** `smoke_test.py` 9/9；`run_selftests.py -k icon_source ui_icons shared_input_ui script_composer idea_chat` 219/219，0 红、0 跳过；新门禁和架构清单核对 7/7。完整架构门禁 491 项，只有 `test_round_number_continuous` 1 红（本分支状态页 3176、已提交最新结果 R3178，状态页只能在 master 提交并由合并轮复验），其余 490 项绿。安全全量未跑，未冒称绿凭据。
3. **欠账少了吗？** 无新增违规或存量豁免。MDL2 存量按文件/常量 AST Load 次数冻结，仅允许减少；emoji 图标存量精确冻结在两文件 15 个图标字面量（阶段栏 13＋全部 1、视频封面空态 1），待零依赖任务书 M3 迁移阶段栏，不在本轮跨任务改动。

## 实现与坏样本

- `tests/architecture/test_icon_source_boundary.py` 只扫描生产 `.py`，识别直接或别名导入的 `ui_tokens.ICON_*`、`import ui_tokens as ...` 属性读取；排除与 MDL2 无关的应用快捷方式 `ICON_NAME`。输入图标行/面板及命名样式位于 `desktop_shared_input.py`、`desktop_shared_menus.py`、`ui/ui_composer_style.py`、`ui/workflow_settings_dialog.py`，这些允许文件的既有引用也只许减少、不许增加；其它文件（`ui/desktop_files_panel.py`、`ui/desktop_idea_bubbles.py`、`ui/desktop_script_pages.py`、`ui_widgets.py`、`white_model.py`）按实际存量数冻结，每处只许减少。新文件基线为零。
- 图标路径新代码只能经 `IconLoader.nav_icon`：执行代码中的 `assets/nav/...` 字面路径和 `Path('assets') / 'nav' / ...` 均报错；共享加载器及生成脚本是唯二所有者。现有 `test_ui_icons_boundary.py` 继续守护页面不得直接构造 `PhotoImage`。
- emoji 口径限图标命名赋值及控件 `text=` 的开头图标字面量，普通文案如 `处理成功 ✅`／`完成 ✅` 不误报。`ui/desktop_files_panel_filters.py` 的 `STAGE_RAIL_ICONS` 13 项＋`STAGE_RAIL_ALL` 1 项，`ui/ui_media_player.py` 的视频封面空态 1 项为冻结基线；来自 AST 当轮实测，不按作者估计凑数。好／坏样本覆盖新文件 `from ui_tokens import ICON_FOLDER as folder; icon=folder`、模块别名属性、直接 PNG 路径、emoji 图标、普通文案，门禁 6/6。
- `ui_tokens.py` 为已有 MDL2 字体 11pt／7pt 和侧栏 24px PNG 边界补注释；不新增、删减常量。`architecture.md` 登记新增门禁。

## 后续与提交

本轮提交 hash 以 Git 日志为准；`project_status.md` 连续性由 master 合并轮同步后复验。U1 草稿尚在另一工作树，U4–U7 尚未执行；整份任务书不标完成，不推送。
