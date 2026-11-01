# R1157：剧本准备气泡右键清屏（收尾见 R1159）

## §7 三问

1. 修复轮：补齐上方气泡区右键清屏入口，不改变磁盘记录删除语义。
2. 默认冒烟 8/8；受影响回归 100 条中 1 条失败；气泡测试 16/16、菜单与复制边界 4/4。未跑完整架构或全量安全回归；最近历史全量凭据为 R1155，本轮未触发五轮或升级条件，不冒用历史通过。
3. 本次清屏已实现，历史提示词断言阻断整组回归；未减少无关欠账，尚未完成提交同步。

## 实现

- 复用已有气泡右键 ContextMenu，消息、示例和空白处均提供“清屏”。
- 清空显示、气泡索引和标签，取消排队的历史渲染并更新显示代次，避免旧批次重新填入。
- 保留持久化聊天、输入草稿和附件；刷新恢复历史。未重启或实发模型。

## 实测与待办

- 新增两项测试先红：缺少 clear_bubble_view；实现后气泡组首次因新测试把附件 tuple 转成 list 产生快照比较错误，修正测试快照类型后受影响运行中气泡组 16/16。
- `smoke_test.py --affected idea_chat`：默认 8/8；受影响共 100 条，1 个文件有红。日志 `%TEMP%/r1157-affected.log`。
- 唯一失败为 `SendMessageTests.test_sending_starts_the_selected_workflow_without_creating_a_script_file`，test_idea_chat.py:593 仍断言“禁止擅自直接返回剧本、大纲或分镜方案”。HEAD 已存在此断言，而 R1156 workflow_tasks.py 已改为设定→大纲→角色卡→自然剧本逐阶段确认。本轮未修改该测试或提示生成逻辑。
- `unittest tests.architecture.test_context_menu_boundary tests.architecture.test_copy_entry_boundary`：4 条、3.471 秒、OK；日志 `%TEMP%/r1157-boundary.log`。
- `git diff --check` 通过。未弱化或跳过既有断言。
- 已询问用户是否授权把遗留断言改为检查当前四阶段确认契约。待回复后最小复测，再完成报告、主状态页、提交及主目录同步。未满足完成条件。
- 主目录 42 个既有修改路径的原字节快照保存在 `%TEMP%/r1157-main-before.json`；不得覆盖这些用户修改。

## 提交

尚未提交；代码保留在 codex/claude-npm-detection 工作树。无匹配队列 ID，未冒领其他任务。

## 后续闭环

用户确认更新遗留断言；定向复测 1/1，最终受影响 100/100、冒烟 9/9。并行 R1158 已合入，中央重新领取 R1159 收尾，详见 tasks_round_1159_result.md。
