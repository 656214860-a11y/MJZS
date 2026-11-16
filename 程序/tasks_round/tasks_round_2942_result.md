# R2942 功能轮：输入框对齐 DSH——补全浮层上移、图标悬停提示卡、流畅度收口；模型选择器内嵌共享输入框；剧本准备页「项目文件」单一列表＋折叠
<!-- round-evidence: {"commit_base": "db5f56ff", "credential_hits": 0, "evidence_sha256": "809cee1a4344cc74", "exit": 0, "failed": 0, "passed": 443, "round": 2942, "tests": "run_selftests.py -k test_idea_chat test_ui_edges_pages test_desktop_compact_layout test_writing_page_services test_shared_input_ui test_shared_input_stages test_video_ui test_skills"} -->

## 三问

1. **本轮类型**：功能轮（§3.1）。用户要求以 DeepSeek Harness 输入框为标准优化共享输入框（补全弹层位置、图标悬停提示卡、流畅度），并把 R2942 既有未提交工作（页面级「阶段配置」按钮＋模型下拉框删除、模型选择收进共享输入框）一并收口提交；UI 契约有意变更，测试定位与预期同步（§2.4），断言不弱化。
2. **测试与三个基线**：
   - 默认冒烟基线：**8/8** ✅（`python smoke_test.py`）
   - 架构门禁：**470/470** ✅（`python smoke_test.py --architecture`，154.9s；复杂度棘轮已含本轮登记）
   - 定向回归：`test_shared_input_stages`（23 例）＋ `test_idea_chat test_script_composer test_ui_edges_pages test_desktop_compact_layout test_idea_send_gate test_ui_writing_recon test_skills test_page_navigation_controller test_page_cache test_final_viewer test_stage_flow test_model_pool` → **共 523 条用例，0 红** ✅
   - 全量：未跑（改源码轮累计未达全量阈值，欠账口径见 runbook §4）。
3. **欠账**：无新增。`project_status.md` 轮次头随 master 合并轮更新（仅 master 可提交，worktree 只改不提交）。

## 用户要求（三点，逐条落实）

1. 输入 `/` 时技能补全弹层浮在**输入框正上方**（不再挤到右侧）——DSH 行为。
2. 鼠标悬停输入框图标有**提示卡片**。
3. 输入框**流畅度**收口。

## 产品改动

- `desktop_shared_input.py`：
  - 新增 `CompletionPopup` 类（135 行）：`/` 补全候选卡片锚定在输入盒正上方（place 浮层，同宽左对齐、下缘悬在盒顶，顶出屏幕才贴顶回退）；默认高亮第一项；上下键移动、Tab／点击／Enter 采纳；悬停跟随高亮（程序化选中带 `selecting` 标记，不误触 `<<ListboxSelect>>`）；失焦自动收掉；窗口重排经 `<Configure>` 跟随锚定。
  - 五个图标（✦ 技能／＋ 附件／🎤 语音／发送／模型下拉框）全部挂 `Tooltip` 悬停提示卡。
  - 流畅度：`skill_items()`／`engine_names()` 按实例缓存（切阶段、导入 skill 后失效）；补全弹层不再 `pack` 进输入条（消除每次按键的全条重排）。
  - 两处 `except Exception: pass` 改 `app_logging.swallowed()`（静默异常棘轮）。
  - 类行数棘轮：`CompletionPopup` 拆出后 `SharedStageInput` 543 行（上限 600 内）。
- `stage_model_picker.py`／`skill_panel.py`／`desktop.py`／各阶段页（app、资产、媒体、分镜、白模、故事板等 11 个页面模块）：页面级「阶段配置」按钮＋其模型下拉框删除，`stage_button`／`stage_button_for`／`attach_stage_pickers` 工厂删除；模型选择唯一入口=共享输入框右下角 `StageModelPicker` 下拉框按钮（Menubutton＋弹出菜单，推理档位子菜单），SKILL 走 ✦ 图标；`skill_panel.show` 面板保留（手动制作预检「修改配置」等入口仍用）。
- `desktop_shared_send.py`：`_model_picker` 模态弹窗入口删除（已被内嵌下拉框取代）。
- `tests/architecture/test_complexity_ratchet.py`：`('desktop.py','Desktop')` 登记 836 → 819（实测下调）。

## 测试契约变更（§2.4）

- `tests/test_shared_input_stages.py` 新增 6 例：补全弹层浮在输入盒上方（place 浮层、左对齐、同宽）、上下键/Tab 采纳、悬停高亮不自动采纳、失焦收掉、五图标 Tooltip、技能/引擎清单缓存与失效；原 `_completion` 内联断言改为 `box.completion.*` 新接口。
- `tests/test_ui_edges_pages.py`（R2942 部分）：阶段页「阶段配置」按钮断言改「不存在」；`test_every_page_opens_its_own_panel` 改为「页面不再有阶段配置按钮，共享输入框持唯一模型下拉框」。

## 同轮追加需求：剧本准备页「项目文件」单一列表＋折叠

用户要求：文件栏只保留一条「项目文件」栏，垂直展示当前页面生成的全部文件；位置在左侧阶段列表与右侧功能区之间；点图标可隐藏/打开；折叠时右侧功能区放大。

- `desktop_writing_page.py`：四张分类 DataTable（项目设定／项目大纲／角色卡／项目剧本）合并为**一条单列列表**（表头「文件名」，行仍为「[状态] 文件名」，类别存 `script_row_category` 供打开/删除/提示卡）；`script_box` 头部新增「项目文件」标签＋折叠按钮（`ICON_CHEVRON_LEFT/RIGHT`，`Tooltip` 说明）；`toggle_script_files` / `_apply_script_files_collapsed` 控制 `pack_forget`（列表＋标题隐藏、图标旋转），折叠状态存 `Desktop.script_files_collapsed` 跨页保持；`fill_script_list`／`all_script_items`／`current_script_tree`／`keep_one_selection` 改单树；`keep_script_headers_visible` 重 pack 修正为 `side='left', fill='y'`。
- `ui_tokens.py`：新增 `ICON_CHEVRON_LEFT`／`ICON_CHEVRON_RIGHT`。
- 折叠时 `talk`（`fill=both, expand=True`）自动吃掉整条文件栏宽度，右侧功能区放大，无需额外布局代码。

测试契约同步（§2.4，断言未弱化）：`test_idea_chat` 空列表断言改「栏头=项目文件、表头=文件名」并新增 `test_project_files_bar_collapses_and_expands`（默认展开→折叠后列表不可见且图标转右、聊天仍可用→再点恢复）；`test_ui_edges_pages` 四表断言改单表（四类文件同列表、每行只显示文件名、`script.md` 不出现）；`test_desktop_compact_layout` 行提示改单 `TreeRowCard`；`test_writing_page_services` 多选删除用例改 `page.script_tree`。

验证：冒烟 **8/8** ✅；架构门禁 **470/470** ✅；定向回归 15 个测试文件 → **534 条用例，0 红** ✅。

## 回归证据

- `python smoke_test.py` → 8/8 ✅
- 定向回归 13 个测试文件 → 523 条用例，0 红 ✅
- `test_shared_input_stages` 单文件 → 23 条用例，0 红 ✅
- 追加需求复验：冒烟 8/8 ✅；架构 470/470 ✅；定向回归 15 个文件 534 条用例 0 红 ✅
- 架构门禁首跑 5 红 2 错（类行数 673>600、Desktop 登记未随删除下调、轮次头滞后、两处静默异常、测试文件 BOM），全部修复后复跑绿。
