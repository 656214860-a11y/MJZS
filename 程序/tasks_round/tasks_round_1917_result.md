# R1917 功能轮结果：旧页面文字层级首步——视频工作台页头说明改用 DescriptionBlock

- 改动：`desktop_media_pages.py` 的 `header_note` 由手写 `ttk.Label(style='Muted.TLabel', font=TEXT_DESC['font'])` 改为 `ui_widgets.DescriptionBlock`。颜色同为 `text_secondary`、字体同为 `TEXT_DESC['font']`，视觉仅多出统一的垂直内边距；窗口缩放时的 `wraplength` 绑定保留。
- 未迁移（登记，非遗漏）：带成功／警告语义色的标签（`desktop_media_pages.py`、`asset_detail.py`、`desktop_project_pages.py` 的提示）会被 `DescriptionBlock`／`ProgressLabel` 强制覆盖前景色，迁移会改视觉，须先定语义色表达；`heading_1`／`heading_2` 标题类标签同理。
- 验证：经 gui_hidden 跑 `run_selftests.py -k text_component token_boundary video_navigation media_pages video_workbench previs`，全部通过。未跑全量、未跑架构全门禁、未实机查看界面。断言未动。
- 回滚：`git revert` 本轮提交。
