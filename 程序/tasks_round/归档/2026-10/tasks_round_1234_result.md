# R1234 剧本准备前三项分目录、覆盖更新与四列布局

- 类型：§3.1 功能轮（含 L0 契约常量 `_STAGE_FILE_TYPES` 增补「角色卡」），中央领取 1234。
- 范围：`script_contract.py`、`idea_chat.py`、`writing_api.py`、`script_workspace_service.py`、`desktop.py`、`workflow_tasks.py`、`skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 及对应定向测试。
- 测试：架构门禁 311/311；默认冒烟 8/8；定向（idea_chat / writing_api / workflow_writing_stages / script_workspace / script_structure / script_agent_delivery_* / skills 系列）全绿。未跑全量，最近正式全量 R1230，差 4 轮，无升级触发。

## 行为变更

1. **角色卡独立目录**：阶段③角色卡从「项目设定」目录拆出，落入「角色卡」目录；`_project_file_type` 将「人物设定／角色卡」识别为角色卡；剧本准备页文件框由 3 列扩为 4 列（设定／大纲／角色卡／剧本），`uniform` 等宽，末列修正 padx 使真均分，随窗口伸缩。
2. **前三项放弃历史版本**：`reply_document_path` 对「项目设定／项目大纲／角色卡」改为同路径覆盖最新一份（含跨 `创意_日期` 批次回到同一份），不再追加 `(N)` 副本；自然剧本仍保留版本与「不覆盖已确认稿」。`save_reply` 改为「正文一致才复用、变了才覆盖」。
3. **换行口径容忍**：`_preparation_state` 校验对末尾换行差异容忍（与既有 relink 同口径），下载不写换行、自动保存追加换行不再误报「文件已删除或修改」，用户可正常确认角色卡进入自然剧本。

## 验证与断言登记

契约有意变更，同步断言未弱化：`test_workflow_writing_stages` 角色卡分类断言改为「角色卡」并保留项目设定反向断言；`test_idea_chat` 目录集合加「角色卡」、覆盖语义重写（设定覆盖 + 自然剧本仍 `(N)`）并新增跨批覆盖用例；`test_writing_api` 两处覆盖路径断言改为同路径，新增末尾换行容忍用例；`test_ui_edges` 扩为 4 类目录/列。

既有 1 条红为历史既有、与本轮无关：`test_idea_chat.SendMessageTests.test_enter_after_model_change_displays_the_submitted_conversation` 抛 `KeyError: 'receipt'`（desktop.py dispatch 属 Agent 发送流程，本轮未触碰），未在本轮修复。

## 自审

通过：仅根因模块及对应测试；新写入仍走 `reply_path_parts`／`stage_path_service.write_dir`，未越层、未新增模块；无 Tk 生命周期或删除语义变化。换行容忍仅放宽末尾换行差异，真正改动/删除正文仍判失效。需重启加载。

提交：见本轮回执；状态页下一轮 1235。
