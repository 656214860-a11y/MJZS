# R1971 按钮一致性：页面宽度／间距走令牌，弹窗底栏顺序统一（功能轮，第二步）

## 改动
- `ui_tokens.py`：新增 `BUTTON_WIDTH_STAGE`(=CHAR_WIDTH 3xl)、`BUTTON_WIDTH_EDIT`(7)、`BUTTON_WIDTH_DIALOG`(=xl)；`desktop_page_support.STAGE_ACTION_WIDTH`、`desktop_script_pages.SCRIPT_EDIT_BUTTON_WIDTH` 改引用令牌（名字保留，外部导入不变）。
- 弹窗底栏统一为「主操作最右，取消／关闭紧挨其左，间距 `BUTTON_GAP`(8px)」：asset_reference_import、seedream_settings、reference_wall、background_characters、skill_panel_presets、skill_panel_workflow、pet_models_ui；desktop.py 回收站确认弹窗两颗按钮同宽 `BUTTON_WIDTH_DIALOG`。
- native_assets、desktop_writing_page 的紧凑行间距改引用 `BUTTON_GAP_TIGHT`（数值不变）。
- 剧本准备输入区按钮去掉 `SCRIPT_ACTION_PADDING` 覆盖：样式层按下态内边距会盖过控件级 padding，原先按下时按钮高度 29px 会回弹；现与其它页同为标准高度（输入区行约高 8px，未目测）。
- 新测试：`tests/test_button_consistency.py` 加 `ButtonRuleContractTests`（宽度常量来源、七个弹窗取消／关闭靠右且用 BUTTON_GAP），已用它抓出 pet_models_ui:587 漏改。
- 删除误入库的重复结果文件 `tasks_round_1968_result.md`（内容已在 1970）。

## 验证
相关 1242 条仅余已知红：architecture 三项（worktree 缺文件／轮次）、test_idea_chat／test_script_contract（worktree 缺 skills 文件，SKILL 引用缺失）、skill_panel_dropdown_layout（270≥248，已在基线 9f6d42e3 复现，与本轮无关）。断言未动。未跑 --all --safe，未真实窗口目测。
