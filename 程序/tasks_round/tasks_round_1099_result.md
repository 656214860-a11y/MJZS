# R1099 内联简报功能轮（进行中，待完整验收）

- 类型：功能轮。
- 范围：用户列明的七个生产模块、对应 tests；必要收尾文档已获用户授权。
- 当前状态：实施完成，完整验收进行中，功能尚未合入 master。

## 已实施

发送框预填默认示例，八项必填采用 script_contract 标签常量及 idea_chat 单一门禁；标记不进入发送或保存内容。移除创作信息弹窗及首字清空绑定，当前模板经原发布网关覆盖写项目 brief_creation.md。锁别名来自 workflow_settings，统筹区只读展示制作锁及偏离徽标。默认示例和真实用户项目未修改。

工作树：C:/Users/LAIBIAO/AppData/Local/Temp/assistant-slim-apply，分支 codex/inline-brief，基于 f5c2b3a。主树既有用户预设不动。

## 本轮实跑证据

- run_selftests.py -k idea_inline idea_chat_attachment_refresh：9/9，通过。
- smoke_test.py：8/8，通过。
- run_selftests.py --layer architecture：增量 38/38，通过；不是全架构凭据。
- run_selftests.py -k idea brief workflow：235/235，通过。初次失败暴露页面构建期间高度计算早于 display_lines 定义，已改为空闲回调。
- smoke_test.py --affected idea_chat workflow：9/9，通过。
- run_selftests.py --layer architecture --all：308 项中两项失败，原因是新报告对应下一轮号需同步、删除旧表单造成注释快照行号变化；已同步元数据，待复验。未修改门禁判据。
- 直接 unittest 启动新文件因 skip_reasons 路径失败；改用项目自检入口后通过。
- 新面板测试初次误用了类名 SkillPanel，改为现有 Panel 后通过。
- 日志位于当前用户 TEMP/R1099-{focused,inline,architecture,smoke}.log，不纳入仓库。

## 删除功能对应测试、断言未动的范围

“断言未动”仅指未触及的保留功能断言，不代表以下移除功能的断言仍存在。

- test_idea_chat_attachment_refresh.py：原八个表单刷新用例随功能移除，替换为上传不覆盖内联草稿检查。
- test_idea_chat.py：移除 test_brief_form_attachment_fill_can_be_deleted_and_saved；按任务书改写 test_brief_form_save_does_not_send_or_replace_chat_draft 为内联编辑不自动发送或落盘；不可读附件用例保留原提示语断言，改从 notify 捕获。
- test_dialog_boundary.py：移除仅针对旧表单的 FormDialog 检查，保留全仓裸窗检查，新增旧入口不存在断言。
- test_input_boundary.py：移除仅针对旧表单双 TextArea 的用例，其他控件边界断言不改。

## 授权冲突与下一步

用户已明确允许仅按新契约迁移冲突断言。test_idea_chat.py：发送 fixture 补齐八项；初始空框改为完整示例；空框行为先显式清空再保留原断言；缺项改为仅提示、不写聊天或原稿；附件相对路径与正文隔离断言保持。test_stage_command_contract.py：仅替换已废除的“填写创作信息”错误文案。新 test_idea_inline_brief.py 覆盖八项逐项缺失/示例占位、跨行值、别名、发送/另存、默认文件不变、只读锁及不再清空示例。

下一步：完整架构及 Tk 生命周期要求的完整安全回归；凭据扫描、收尾提交、合入并同步主树状态。当前不得标 TASK_COMPLETE。

## 未运行项

本次完整安全回归、完整架构最终复验、真实应用视觉验收尚未完成。没有引用历史通过冒充本轮通过。主树用户预设 SHA256 与开工前一致；默认示例未修改。仅同步必要状态、结果及注释/测试分层元数据。
