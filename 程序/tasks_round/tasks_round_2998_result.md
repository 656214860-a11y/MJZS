# R2998 结果：「项目文件」入口迁至内容区右缘图标列，文件名列宽动态自适应
<!-- round-evidence: {"commit_base": "2fb0c240", "credential_hits": 0, "evidence_sha256": "40b1d06bf803c11e", "exit": 0, "failed": 0, "passed": 17, "round": 2998, "tests": "run_selftests.py -k files_panel writing_page"} -->

## 三问

1. **轮次类型**：功能轮（§3.1）——共享桌面外壳 UI 布局与 REQ-S01-90 契约变更，文档先行。
2. **测试跑了吗、三个基线过了吗**：跑了。`run_selftests.py -k files_panel` 8/8 绿；`-k compact_layout ui_edges_pages idea_chat` 8 文件 215 条 0 红；`smoke_test.py --affected desktop_files_panel desktop_layout` 门禁 13 文件全绿；默认冒烟 8/8（affected 合计 9/9）。首次 idea_chat 定向 16 红经核验为工作树未物化 gitlink 技能子仓的环境基线问题（R2966 同类），同步主工作区后复跑全绿，非本轮回归。
3. **欠账少了吗**：是——REQ-S01-90 旧契约（标题行右上角入口）随本轮实现闭环；列内下方留白是为后续图标功能预留的既定空间，无需登记欠账；无新增欠账。

## 本轮做了什么

1. **入口迁列（需求 1）**：`desktop_files_panel.ProjectFilesPanel.build()` 在内容区容器（`canvas.master`）内以 `pack(side='right', fill='y')` 建 `rail` 图标列——先于任何停靠面板 pack，恒为该容器最右竖条，与画布同高（即聊天区滚动条右侧的整列），图标钮 `project_files`（`RailIcon.TButton`＋Tooltip「项目文件」）pack 进列顶，列内下方留白给后续图标功能。按钮不再挂 `title_row`；列内常驻 0 尺寸 `rail_sizer` 占位子件，按钮隐藏（无项目／会员页／参考网站页）时列塌回约 1px。显隐仍走 `sync_entry()`，开合仍走 `toggle/open_panel/collapse`，面板外按下判定把 `rail` 整列纳入豁免。
2. **停靠关系不变**：`script_box`＋`sep` 打开时仍 `pack(side='right')`，因 pack 顺序落在图标列左侧——视觉为 `[内容][分隔线][文件面板][图标列]`，面板右缘贴图标列左缘，主内容区收窄语义与 R2962 一致。
3. **文件名列宽动态化（需求 2）**：`script_box` 内加 0 高 `script_width_sizer` 驱动面板请求宽；`_fit_script_width()` 在渐进填表收尾（`finish()`）与内容区 `<Configure>` 去抖（`_on_files_area_resize`→after_idle）后，按 `SCRIPT_FILE_FONT` 实测最长行显示文本（含 `[标签] ` 前缀）＋`SCRIPT_CELL_OVERHEAD` 量宽，钳制在 `SCRIPT_LIST_MIN_WIDTH`（184）与「内容区宽一半、`SCRIPT_PANEL_MAX_WIDTH`（480）」上限之间；Treeview 列保持 `stretch` 铺满，超长文件名仍可经行悬停卡片看全文。
4. **页头零回归**：`desktop_layout.align_header` 仍把 `files_button` 计入页头最小高测量（按钮已不在标题行内，但保留同高节奏，页头高度与改前一致），仅更新注释说明。
5. **测试契约同步（§2.4，有意变更）**：`test_entry_is_icon_only_rail_button` 父级断言由 `title_row` 改为 `rail`，并新增真实 Tk 几何断言（列贴内容区右缘、与画布同高、图标在列顶、下方留白）；`test_panel_hidden_by_default_and_toggles_docked_right` 面板右缘断言改为贴图标列左缘；新增 `test_icon_column_shared_across_work_pages`（script/storyboard/assets 三页共用同一根列）与 `test_file_list_width_fits_longest_filename`（写入长文件名后验证面板宽跟上、受上限约束）。

## 改动文件

- `程序/desktop_files_panel.py`：rail 图标列＋`rail_sizer`、`script_width_sizer`＋`_fit_script_width`/`_script_list_font`/`_on_files_area_resize`/`_fit_script_width_debounced`、`_pack_button`/`sync_entry`/`_outside_press` 适配、模块与类 docstring 更新。
- `程序/desktop_layout.py`：`align_header` 中 files_button 计入页头高的注释更新（逻辑未动）。
- `程序/docs/stages/S01_剧本准备.md`：REQ-S01-90／DES-S01-90 改写为图标列位置、列内留白与动态宽度契约。
- `程序/tests/test_files_panel.py`：契约断言同步＋两个新用例（列共享、动态宽度）。

## 验证记录

- `run_selftests.py -k files_panel`：8 条全绿（14.0 秒）。
- `run_selftests.py -k compact_layout ui_edges_pages idea_chat`：8 个测试文件 215 条 0 红（537.6 秒）。
- `smoke_test.py`：8/8；`smoke_test.py --affected desktop_files_panel desktop_layout`：门禁 13 个测试文件 ALL TESTS PASSED，冒烟合计 9/9（门禁 701 秒）。
- **环境注记**：首次 `-k compact_layout ui_edges_pages idea_chat` 中 `test_idea_chat` 5 个分片共 16 红，全部为 `workflow_settings.freeze_skills` 报 `SKILL 引用缺失`——本工作树 4 个 gitlink 技能子仓未物化（`reference/HoLLMwood`、`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/编剧技能集`；`剧本制作` 主工作区本就为空，属既有状态）。按 R2966 先例将主工作区 `D:\漫剧制作助手\程序` 对应目录整目录同步进工作树（含 `.git`，供 skill_package_pins 哈希核验）后复跑 215 条全绿；`git status` 确认子仓内容不进暂存区，本轮提交不含子仓文件。建议后续在工作树引导或文档中固化该同步步骤（R2966 已提同一建议）。
- `project_status.md`：功能分支不提交状态页（§2.6 仅 master 可提交），轮次头同步由合入 master 的合并轮完成。
- 凭据自查：改动为 UI 布局与测试，无密钥形态内容。
