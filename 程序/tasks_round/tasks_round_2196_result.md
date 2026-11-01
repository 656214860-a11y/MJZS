# R2196 结果：剧本准备页精简（功能轮）

## 三问
- 轮次类型：功能轮（§3）。用户问「剧本准备页的功能是否重复、过复杂、能否简化」，逐项裁决后改。
- 测试和三个基线：在 worktree 分支 `claude/script-page-slim` 上运行（Tk 测试经 gui_hidden）。
  - 定向：`run_selftests.py -k idea_chat desktop_compact_layout traceab requirement` 167 条全过；此前一轮 950 条定向全过，两处红已修（见测试）。
  - 默认冒烟：8 项全过。
  - `--architecture`：411 项全过（修了两处契约，见测试）。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 需求（用户逐项裁决）
1. 两个发送按钮都留。
2. 「添加剧本」改成真的本地导入 txt／md／docx，按正文自动归入设定／大纲／角色卡／剧本，认不出的进项目剧本；页面不再导入镜头 JSON（分镜页「导入JSON分镜」照旧）。
3. 「查看质检报告」与「质检目录」合并为「质检报告」：有报告开报告，没有开质检目录。
4. 删「下载文件」；模型回复自动存档；「刷新」保留。
5. 自动存档不覆盖手改过的同类文件：模型新回复另存新版本，状态栏提示；没手改过的照旧覆盖。
6. 三虎同一份剧本反复改稿不重复问是否进分镜；得到新剧本文件时才问。
7. 「采风」仅在素材来源为「对标爆款」「热点速成」时显示，否则隐藏不占位。
8. 去掉勾选列和底栏「删除」；表格 Ctrl／Shift 多选，右键「删除」删所选；不跨列批量删。

## 改动
- `idea_chat.py`：`AutoSaved`、`auto_save_reply`、`import_local_document`。
- `desktop_script_pages.py`：`auto_save_script_reply`、`add_script_files`、`open_script_quality`；删 `download_script`／`confirm_script`／`update_script_download_button`。
- `desktop_writing_page.py`：表格 `headings`＋`extended`，`selected_scripts`、合并的 `delete_script`、`script_menu`、`build_script_quality_buttons`、`update_recon_button`；删勾选列。
- `responsive_ui.py`：`FlowBar.hidden_children`／`set_visible`。
- `desktop_idea_chat.py`、`pet_ui_stages.py`、`desktop_lifecycle.py`、`script_contract.py`、`stage_exec.py`、`script_workspace_service.py`：文案与调用点跟随。
- `docs/stages/S01_剧本准备.md`：REQ-S01-76、DES-S01-76，REQ-S01-46／DES-S01-43、模块分工、测试锚定。
- `维护记录/skip台账.json`：`test_ui_writing_recon` 的 skip 登记位改到 `open_page`（两条）。

## 测试
- 断言未弱化；以下均为契约有意变更或新增，逐项列出：
  - 新增 `tests/test_flowbar_visibility.py`（2 条）、`test_idea_chat.py::test_add_script_files_reads_docx_text`、`test_add_script_files_sorts_local_files_into_four_columns` 等 REQ-S01-76 用例。
  - 改写 `test_script_page_services`、`test_idea_chat`、`test_writing_page_services`、`test_writing_restart`、`test_ui_writing_recon`、`test_script_workspace_service`：下载／勾选路径改为自动存档／多选。
  - `test_pet_ui`：三虎只在每份新剧本存档后问一次。
  - `test_ui_edges`：表格只显示文件名一列（`show=headings`）。
  - `test_desktop_compact_layout`：采风隐藏不量宽度；提示框 anchor `'nw'` 与 master R2181 相同。
  - `tests/architecture/test_manual_creative_publication_boundary.py`：桌面层调用 `idea_chat.save_reply` 改为 `auto_save_reply`，并新增 `import_local_document` 须注入 `publish`；调用次数与 publish 断言都在。
  - skip 台账随 `open_page` 更名。

## 已知取舍
- 旧的未存档回复不回填。
- 「同一份剧本」：模型对话里的第一份剧本才问，后续改稿不问；清空对话后再来一份会重新问。改稿不重发阶段完成。
- 与任何回复都对不上的同类文件按「手改过」处理。
- 多选时右键菜单只有「删除」。
- 旧下载路径里给 `brief_editor` 的赋值已删。

## 用户需做
重启应用后生效。
