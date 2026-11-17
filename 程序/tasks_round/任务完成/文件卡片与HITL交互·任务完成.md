# 文件卡片与 HITL 交互·任务完成文件

> 与《文件卡片与HITL交互任务书.md》一一对应（规则 35，逐条覆盖）。
> 相关轮次：R3101（任务书入库）、R3102、R3114、R3118、R3123、R3128、R3132、R3135、R3138；R3146（合并轮，已在隔离工作树合入当前 master 并全绿，待快进）。

## 逐条任务完成证据

### 轮 1 → R3102

- 新增 `tests/test_message_parts.py`：Part/Message 序列化往返、schema_version、旧扁平→parts 迁移（thinking 保留为 REASONING、正文不丢）。 → 完成：R3102（tasks_round/tasks_round_3102_result.md）。
- 旧 `对话.json` 打开后迁移成功且原内容不丢；`test_idea_chat*` 相关回归全绿（契约变更断言同步改写）。 → 完成：R3102（tasks_round/tasks_round_3102_result.md）。
- `python -B smoke_test.py` 8/8；动到 L0 契约则 `--architecture` 全绿。 → 完成：R3102（tasks_round/tasks_round_3102_result.md）。

### 轮 2 → R3114

- 新增 `tests/test_chat_status.py`：状态迁移、取消令牌语义（停止后后台真停）、继续/重新生成、消息队列。 → 完成：R3114（tasks_round/tasks_round_3114_result.md）。
- 逐字渲染经 `after()` 合并（非每 token 一次 `update`）；`-k idea_chat_controller writing_api` 回归全绿。 → 完成：R3114（tasks_round/tasks_round_3114_result.md）。
- 手动验证：停止后无残留半截 part；继续生成能续上；重新生成重发同消息。 → 转欠账（需真机人工验证；R3114 结果文件已注明）。

### 轮 3 → R3118

- 新增 `tests/test_part_renderers.py`（真 Tk 隐藏桌面：各 part 渲染/折叠/展开）+ `tests/test_message_toolbar.py`（复制/删除/编辑/引用/重新生成）。 → 完成：R3118（tasks_round/tasks_round_3118_result.md）。
- 01 气泡区显示 reasoning 折叠卡、tool 卡、artifact 卡；02–13 产物以卡片出现。 → 完成：R3118（tasks_round/tasks_round_3118_result.md）。
- 删除撤回可恢复；`smoke_test.py` 8/8。 → 完成：R3118（tasks_round/tasks_round_3118_result.md）。

### 轮 4 → R3123

- 新增 `tests/test_hitl.py`（无 Tk：信封序列化、决策枚举、风险分级、超时）+ `tests/test_hitl_ui.py`（真 Tk：选择卡渲染/选择回填、审批门三按钮）。 → 完成：R3123（tasks_round/tasks_round_3123_result.md）。
- `confirm_gates` 现有调用点全部走信封，无散落弹窗（架构门禁新增「禁止直接 messagebox 审批」检测）。 → 完成：R3123（tasks_round/tasks_round_3123_result.md）。
- 选择卡选中的值正确注入下游（生成用所选候选）。 → 完成：R3123（tasks_round/tasks_round_3123_result.md）。

### 轮 5 → R3128

- 新增 `tests/test_media_render.py`（真 Tk：缩略图/Lightbox/多候选切换/收藏）+ `tests/test_code_highlight.py` + `tests/test_diff_view.py`。 → 完成：R3128（tasks_round/tasks_round_3128_result.md）。
- 收藏入库走 `asset_batch`/`storage_maintenance` 语义；diff 接受后落盘、拒绝后还原。 → 完成：R3128（tasks_round/tasks_round_3128_result.md）。

### 轮 6 → R3132

- 新增 `tests/test_checkpoint_tree.py`（无 Tk：append-only、parent 链、fork 不覆盖、剪枝、存引用）+ `tests/test_branch_tree_ui.py`（真 Tk：节点树渲染/切换对比/重新提问）。 → 完成：R3132（tasks_round/tasks_round_3132_result.md）。
- fork 后原对话不丢、可切回；长会话增量索引（不全量重算）。 → 完成：R3132（tasks_round/tasks_round_3132_result.md）。

### 轮 7 → R3135

- 新增 `tests/test_citation.py` + `tests/test_asset_hovercard.py`（真 Tk：tag hover 弹出/关闭、cite 点击定位）。 → 完成：R3135（tasks_round/tasks_round_3135_result.md）。
- 引用点定位到原文档片段；悬浮卡显示资产正典图/属性。 → 完成：R3135（tasks_round/tasks_round_3135_result.md）。

### 轮 8 → R3138

- 新增 `tests/test_video_audio_card.py`（真 Tk：封面/播放按钮/导出 SRT 入口）+ `tests/test_param_panel.py` + `tests/test_multimodal_upload.py`（拖拽/粘贴生成 file part）+ `tests/test_background_task.py`（转后台/通知/断点续跑）。 → 完成：R3138（tasks_round/tasks_round_3138_result.md）。
- 视频/音频不内嵌播放（零依赖），外部打开正确；参数写回生效；后台任务完成后通知。 → 完成：R3138（tasks_round/tasks_round_3138_result.md）。

## 未完成/待办

- 合入 master：`merge-31xx`（`480464e3`，R3146）已解决全部冲突并通过架构门禁 483/483、冒烟 9/9；main 工作树仍被其他车道的 MERGE_HEAD 占用，待其结束后 `git merge --ff-only merge-31xx`。

## 诚实边界声明

机器校验器只核验条目覆盖与证据/处置标记，不核验证据内容真假；以上证据真实性与人工目测结论由用户抽检（规则 35 决策 13）。
