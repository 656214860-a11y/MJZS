# R1832 结果：desktop_script_pages.content_box 改写成类（整理轮）

- 改动：`_ScriptStructurePage.content_box` 用 c2c 改写成 `_ContentBox`，原方法变成两行的薄壳；c2c 在多行签名上多留了一行续行，已手工删掉；宿主字段从 `self.page` 改名为 `self.owner`，避免出现 `self.page.page`。`OVERSIZE_CAPS` 删除该条。
- 差分测试先行：`tests/test_content_box_equivalence.py`，旧方法取 HEAD 原文内嵌，替换到同一张剧本结构页上；预置两份自然剧本并采用其一、钉死修改时间后，两轮逐个点两个内容框的“修改内容（随后输入文字）／恢复删除／保存修改”，对照每步控件树、状态栏全部写入与落盘正文。旧实现自比为绿。
- 变异检验：保存提示“已保存”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、test_script_structure_page_equivalence、test_checkbox_column、test_ui_reading_density 通过；test_stage_wiring 有 1 项红（`test_the_main_page_keeps_the_table_and_gains_the_entry`），换回 HEAD 原文同样红，非本轮引入；`run_selftests.py --architecture` 通过。
- 断言未动。
