# R2058 后台全量红的修复（修复轮）

轮次类型：修复轮。日期：2026-10-25。依据：`logs/auto_full_safe.log`（HEAD 92e9c0c，15 个文件红）。

## 真实缺陷（改了源码）
- `pet_cloud.py`：`Cloud.show` 里读 `self.pet` 在没有 `pet` 属性的实例上抛 AttributeError（popup_no_interrupt 5 条）。改为 `getattr(getattr(self, 'pet', None), 'login_locked', lambda: False)()`，仍并在原条件里，行数不增（文件已在 1357 行上限）。
- `desktop_media_pages.py`：整理剪映素材交接包按钮引用了已迁走的 `self.media_logic`，改走 `self.media_page_services.open_path`。
- `desktop_account_page.py`：18 周岁勾选文案与状态提示超出文案门禁（按钮名 ≤16 字、对用户称“您”），改为「已满 18 周岁并同意协议」与「…填入您自己的 Key」。

- `desktop.py:661`（R2056 引入）：打开的项目不在侧栏列表里时，`list.parent(root)` 抛 TclError（`test_idea_chat.test_queued_request_does_not_follow_project_switch` 在主目录合并态下复现）。加 `list.exists(root)` 判断。

## 测试夹具同步（断言未动）
- `test_subtitle_export_service`：命名空间里的 `media_logic` 改指 `media_page_controller`。
- `test_idea_chat_presentation`：被测方法改读 `media_page_services.find_editor_shortcut`，夹具用 SimpleNamespace 提供，断言原样。
- `test_pet_ui.DesktopPetSeamTests.setUp`：隔离会员闸门 `entitlement_service.GATE_ENFORCED`（真实闸门已有 test_account_* 覆盖），5 条接缝用例不再随本机登录态变红。
- `test_pet_ui.CloudTests.test_the_cloud_stands_left_of_the_pet_...`：钉死 `_work_right`（同组其余用例都已这样做）。原因是云朵会被屏幕右界夹住，隐藏桌面较窄时 1072≠1206；源码行为无误。
- `test_idea_chat._Harness.settle_script_page`：固定等 0.18 秒改为“至少 0.18 秒，且页面请求过模型键时等到键解析完（上限 10 秒）”。后台全量里“正在读取聊天记录…”那一批红来自机器忙时后台线程 + 50ms 轮询没赶上，是夹具时序，不是回调缺陷。
- `distribution_selfcheck`：5 个散落在 `程序/` 顶层的 `tasks_round_19xx_result.md`（1925/1929/1930/1932/1941）`git mv` 到 `tasks_round/`，落入清单里已声明的 `程序/tasks_round/**`。

## 验证
- 主目录（含 skills）无提交合并 `codex/wip-R2058` 后实跑 `idea_chat req_s01_anchors leak_teardown writing_status_line idea_inline_brief idea_local_brief idea_semantic_brief`：210 条，仅上面 desktop.py:661 一条红，已修。
- 实跑：`run_selftests -k test_pet_ui`（605 条，0 红）、`distribution_selfcheck`（3 条，0 红）、popup_no_interrupt、copy_rules、static_names、subtitle_export_service、idea_chat_presentation、account、login_gate、pet_cloud（上述合并 222 条中仅下一条红）。
- 修后在主目录无提交合并态（7d9855a4）复跑 `idea_chat req_s01_anchors leak_teardown writing_status_line idea_inline_brief idea_local_brief idea_semantic_brief sidebar_project_title project_rename desktop_compact_layout pet_cloud popup_no_interrupt`：272 条，0 红；验完 `git merge --abort`，master 未留改动。
- 本 worktree 内无法验证（skills 子仓库为空，已由上一条主目录实跑覆盖）：`test_idea_chat`、`req_s01_anchors`、`idea_inline_brief`、`idea_local_brief`、`idea_semantic_brief`、`writing_status_line`。原因：worktree 里 `skills/00全流程SKILL/AIGC创作全流程` 是无 .gitmodules 映射的 gitlink，内容为空，发送链路报“SKILL 引用缺失”。
- 未运行：`--all --safe`、真实界面目测。
- `test_writing_status_line` 在本 worktree 红属 skills 缺失，主目录合并态下绿。
