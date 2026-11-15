# R2898 功能轮结果：任务书轮 4/5——13 阶段接入共享输入框＋取消按模型隔离
<!-- round-evidence: {"commit_base": "96ed7445", "credential_hits": 0, "evidence_sha256": "b8a34aa5bf4c10d8", "exit": 0, "failed": 0, "passed": 984, "round": 2898, "tests": "run_selftests.py -k test_shared_input test_skill_command test_idea_chat test_idea_download_import test_idea_inline_brief test_pet_ui test_ui_edges_pages test_ui_batch5 test_video_ui test_leak_teardown test_script_composer test_compact_layout"} -->

- 轮次类型：功能轮（§3.1，用户任务书《共享输入框与skill体系重构任务书》轮 4）。
- 任务书：`程序/tasks_round/共享输入框与skill体系重构任务书.md`。
- 分支：`codex/wip-R2898`（R2898 已由本工作树领号，见 `.git/round-claims.json`）。

## 改动

- `desktop_shared_send.py`（新，L4）：共享输入框的发送分流唯一入口。
  - `stage_for_index`/`current_stage`：页序号 → `pet_bus.STAGES`（`pet_state.PAGE_OF` 同序），非阶段页返回空。
  - `send()`：`/阶段` → `show_stage` 切页后把剩余正文在新阶段上下文重新 `parse_command`（`/阶段 /skill` 连发不再把 `/skill` 当正文）；`/skill`／`/子引擎` → `_resolve_skill` 解析到目标阶段与技能文件，跨阶段先切页再派发；自由文本 → `_send_free`。
  - `_send_free`：script 走 `send_message` 既有链（简报/制作锁/直连 API 全保留），用 `draft_text` 判受理——简报门禁早退保留原文；其余 6 个有流程阶段（storyboard/assets/keyframe/previs/video/audio）走 `open_flow_agent`（复用 `_FlowAgentLaunch`→`resolve_for_send`→成果发布链）；无流程阶段（script_structure/animatic/continuity/final/edit/delivery）与空阶段回状态栏提示，不新开对话。
  - 会员闸门复用 `account.stage_gate`；上游完成门禁仍由 `desktop_shared_input.upstream_send_error` 在发送前统一执行，本模块不复制判定。
  - `host_options`/`make_shared_input`：宿主回调集（发送分流、附件仅 script 页、模型弹窗复用 `StageModelPicker`＋`BaseDialog`）。
- `desktop.py`：`_init_body_and_status` 建唯一 `shared_input` 实例，`pack(before=status_label)` 位于画布与状态栏之间。
- `desktop_page_nav.py`：`_sync_shared_input` 随 `page_index` 对阶段页 `set_stage` 换上下文（不重建实例）、对非阶段页 `pack_forget`；视频页状态栏隐藏时不用 `before` 锚点；锁定/免费/首页路由在 `show` 里再隐藏一次。
- `desktop_writing_page.py`：composer 不再新建 TextArea——`idea_input`/`input_box` 直接指向共享 Text（同一实例）；composer 卡片只留附件行与发送/终止按钮；页面级绑定（输入提示、fit_composer、Esc 中断、Enter 发送）按 `page_index==script` 守卫，避免共享输入框在其他阶段触发剧本页逻辑；`input_hint` 改挂 `shared_input` 本体（`place(in_=…)` 要求 in_ 是标签祖先的后代，否则 TclError 静默吞掉、提示永不显示——R2898 实测修复）。
  - 共享 Text 常驻后的生命周期收口（`test_leak_teardown` 236→237 控件回归驱动）：`Desktop._composer_dispatch` 统一转派页面级绑定（Button-1/FocusIn/FocusOut/Return/KP_Enter/<<Modified>>/Destroy），绑定按 `_composer_bound_box` 控件身份只挂一次；`input_hint` 标签跨页复用同一实例；`VoiceInput` 按输入框实例复用（录音会话不因换页孤立）；`fit_composer` 不再改共享 Text 的 `height`（行数归 `SharedStageInput` 的 `TEXT_ROWS['sm']` 统一管理，剧本页写再多行也只在框内滚动）；composer 尾段抽为模块级 `_composer_input_tail`，`_WritingPage` 回到 589 行（复杂度棘轮上限 600）。
- `desktop_idea_menus.py`：`@` 引用菜单只在剧本准备页弹出（共享输入框跨页常驻，引用是剧本专属）。
- `desktop_idea_chat.py`：`idea_chat_model` 注释更新（模型标识降级为行内署名与视图筛选）。
- `idea_transcript.py`：取消按模型隔离——
  - `model_history_path` 对所有模型统一返回 `01剧本准备/创意对话/对话.json`；`deleted_history_path` 同目录 `已删除消息.json`（恢复记录仍按行内 model/model_id 过滤）。
  - `_merge_legacy_model_files`：首次读取把旧 `模型会话/<稳定ID--摘要>/创意对话/`、`<提供方>/<模型>/创意对话/`（`writing/*/*/创意对话/对话.json` 全覆盖）按 `at` 归并、整行指纹去重写入统一文件；**只迁移不删旧文件**。
  - `_all_rows` 简化为「合并＋读统一文件」；原按模型分文件的迁移/导入块成为死代码（`model_history_path` 已与 `history_path` 同值，`source==target` 恒成立）整段移除。
  - `save_rows` 的 `model_id` 补写收紧：统一文件里 `model` 为空的行归属不明，不再按「本文件属于该模型」补写。
  - `remove_all` 两处统一文件语义修正（自审发现，均有回归）：
    - 旧代码把 `deleted_history_path`（现为统一 `已删除消息.json`）与 `model_history_path`（现为统一 `对话.json`）无条件列入回收清单——本模型在统一文件里没有行时 `remove_all` 仍会把混放所有模型的统一文件整删且不重写 `remaining`，他人对话与回收站记录全丢。现改为：统一对话文件仅在 `selected`（本模型确有行）非空时回收、回收后按 `remaining` 重写他人行；回收站文件按记录级 `model`/`model_id` 摘除本模型条目，仅当全部记录都属本模型时才整体回收。
    - 匹配口径与 `_row_indexes` 对齐（`model_id` 优先、显示名／调用名并认），`_drop_rows` 与 `extra` 计数同用 `_mine`。
    - `remove_all` 返回值修正：旧目录残留下多是已迁移副本，只有统一文件里没有的残留才计为额外删除（`len(rows)+extra`），同一条消息不再数两遍。
- `desktop_shared_input.py`：Enter 发送（Shift+Enter 换行）、补全选中优先、KP_Enter；`close_completion` 只在确实关闭时 `'break'`，放行剧本页 Esc 中断绑定。
- `tests/test_shared_input_stages.py`（新，17 例）：页序号→阶段映射、流程映射⊆pet_bus.STAGES、script/Storyboard/无流程阶段/`/阶段`连发/`/skill`/未知技能/会员闸门/派发失败保留草稿、`set_stage` 不重建、Enter 路由、单线程 transcript（统一路径、双模型同行、旧目录只迁一次且旧文件保留）。
- `tests/test_idea_chat.py`（契约改写）：`test_clear_screen_is_scoped_and_preserves_new_identical_messages` 改用 `append` 构造双模型共存行（`save_rows` 是整文件原子写，不再按模型分文件）；`test_uploaded_attachments_are_horizontal_ordered_and_openable` 断言改为「附件卡片在共享输入栏上方的 Composer 工具行」（REQ-S01-71 横向序与左右关系断言不变）；`test_delete_all_only_on_model_tab_and_clears_legacy_copies` 期望值 2 不变（由 `remove_all` 计数修正支撑）。
- `tests/test_idea_chat_remove_restore.py`：新增 `test_remove_all_without_rows_preserves_other_models_chat_and_trash`（R2898 回归：无行模型 remove_all 返回 0 且不动统一文件与回收站；有行模型清空只摘本模型记录、他人对话与删除记录保留）。
- `tests/test_pet_ui.py`（契约改写，§2.4）：`pet_start('script')` 用例补 `put_production_locks`（R2862 制作锁门禁先于「无轮询」判定）；`test_saving_claude_code_refreshes_the_open_stage_vendor_dropdown` 改写为 `StageModelPicker` 版本——R2862 后阶段面板不再内嵌模型下拉，「存池即刷打开中的模型选择器」契约平移，provider 下拉断言随之移除；`test_tk_gc_guard_skips_worker_threads` 去抖——`_PENDING_TK_GC` 是进程级队列，改按对象身份断言本批三对象被拦下（原「恰好 3 个」在 8 路并行重载下会被先前用例的积压干扰，984 例合跑复现 27≠3）。
- `tests/test_ui_batch5_stage_panel_and_script_page.py`（契约改写）：删除预设动作栏用例（R2862 已撤该栏）；三档窗口按钮不裁字断言保留；滚动兜底改为「内容超高才出滚动条、放得下则收起」——精简面板在最小窗高 430 内已放得下。
- `tests/test_ui_edges_pages.py`（契约改写）：输入区提示文本收集范围补 `d.shared_input`（提示标签挂共享栏、不在 `d.content` 内）；输入框高度断言 2 行→`TEXT_ROWS['sm']` 固定行数＋`idea_input is shared_input.input` 同一实例；「+ 在输入区下方」几何改为「附件卡片整体位于共享输入条上方」；`idea_input` 不再断言位于对话区容器内；两个 fit 用例改为「共享输入框行数固定、内容只影响框内滚动」。
- `tests/test_idea_chat.py`（契约改写追加）：三处空输入框高度断言 2→`TEXT_ROWS['sm']`（共享输入条固定行数）。
- `skill_panel.py`：`attach_stage_pickers` 改从 `stage_model_picker` 导入（R2881 面板精简后该 API 迁到新模块，`test_video_ui` 31 例由此恢复全绿）。
- `tests/architecture/_layers.py`：`desktop_shared_send`→L4。
- `architecture.md` SKILL 节、`PROJECT_MAP.md` 阶段配置行与 R1247 数据边界、`维护记录/覆盖率基线.json`＋`runbook.md` §11：登记 R2898 设计与模块基数 409。

## 三问

- 本轮属于 §3.1 功能轮（任务书 5 轮中的第 4 轮）。
- 测试跑了，三个基线实测：
  - 默认冒烟 `smoke_test.py`：8/8 通过。
  - `smoke_test.py --affected`（desktop_writing_page／desktop_shared_input／desktop_shared_send／idea_transcript／skill_panel／stage_handler_registry／desktop_page_nav／desktop_idea_chat 及全部消费者）：839 例 0 红，ALL TESTS PASSED。
  - `smoke_test.py --architecture`：470 例，1 红——`test_round_number_continuous`（project_status.md 停在 2872、最新结果 R2898→期望 2899；仅 master 可提交状态页，合并轮前预期红，见欠账）。`test_class_size_does_not_grow` 曾因 `_WritingPage` 涨到 628 行转红，抽出 `_composer_input_tail` 后回到 589 行转绿。
  - 定向补跑（重构后）：`run_selftests.py -k leak_teardown pet_ui ui_batch5 video_ui compact_layout inline_brief semantic_brief slowpage writing_page idea_send_gate` 749 例，1 红（`test_idea_inline_brief` 空输入框 Enter 契约——共享输入框空文本拒收，已按 §2.4 改写断言）复测 43 例全绿；`-k idea_chat` 169 例全绿；`-k shared_input idea_chat idea_download_import skill_command` 234 例中 idea_chat 两处高度断言按共享输入契约改写后全绿。
- 欠账：`project_status.md` 轮次同步仍是 master 侧欠账（本工作树 project_status 停在 2872，最新结果将为 2898；仅 master 可提交该文件，`test_round_number_continuous` 在合并轮前预期仍红，如实记录）。无流程阶段（剧本结构/分镜预演/连贯性清单/分镜定稿/后期剪辑/质检与交付）无既有 Agent 入口，免费文本回状态栏提示——任务书未要求为它们新建流程，`/阶段`切页与 `/skill` 提示可用。

## 验收对照

- [x] 13 页共用同一个底部输入框（`Desktop.shared_input` 唯一实例，`_sync_shared_input` 只 `set_stage`/`pack_forget`）。
- [x] 01 有气泡、02–13 无气泡（气泡仅 `desktop_writing_page`/`idea_log` 创建，其余页面无引用）。
- [x] 03 页（storyboard）发送经 `open_flow_agent('storyboard',…)` 走既有成果发布链（`stage_execution_service.publish_stage_*`），状态栏反馈沿用流程回执。
- [x] 切模型后对话历史同一线程：`model_history_path` 统一单文件，`_merge_legacy_model_files` 首次读取迁移且旧文件保留。
- [x] `test_shared_input_stages.py` 新增；`test_idea_chat*`/`test_idea_download_import` 契约断言已同步改写。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
