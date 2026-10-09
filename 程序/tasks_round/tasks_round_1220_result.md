# R1220：剧本准备口语确认与历史窗口收口

本任务初领 R1218；验证期间另一任务领取 R1219，中央提交钩子要求最新已领取编号。仅暂存本任务两文件到 stash，在干净隔离分支重新领取 R1220 后恢复；未覆盖他人编号或文件。

## 修改

- writing_api.py：精确确认词增加 可以、好的、没问题、OK、ok。保留原 strip/rstrip 与整句匹配；不增加歧义词。带条件的“可以，但是把主角改成女的”仍修订当前阶段。
- _recent_chat_history 显式 recent_limit=12；CHAT_HISTORY_CHAR_LIMIT=12000 不变。窗口参数按历史消息条目计数，不保证 12 组问答。
- idea_chat.py 默认值 6 未改；状态机、JSON 结构与哈希校验未改。
- test_writing_api.py 新增两种确认流转及 12 条消息窗口测试；早期摘录 fixture 8→16。AST 核验原 43 个方法的断言完全一致，既有 mock 未改。

## 验证（实际结果）

1. 修复前仅运行新增 3 个无界面测试：FAILED (failures=6)，5 个确认子例及 6 条窗口行为被检出，修改条件反例通过。
2. 修复后同 3 项：OK，0.529 秒。
3. 精确加载 test_writing_api、test_idea_chat、test_idea_inline_brief，复用 run_selftests 的导入路径与 GUI 互斥锁后运行 unittest：Ran 165 tests in 62.323s；OK，0 失败、0 跳过。原 -k 模糊筛选会额外命中架构测试，故在等待令牌且尚未执行时取消，改为上述精确列表。
4. smoke_test.py 默认：通过 8 项，失败 0 项。未启动架构门禁。
5. git diff --check 无错误。原有六项用户修改 SHA256/删除状态 6/6 一致。

定向日志：本机临时目录 r1218-directed.log；冒烟 r1218-smoke.log；修复前 r1218-red.log。日志包含故障注入 OSError('disk') 及一条 Tk invalid command name ..._focus_first_interactive 的 after 回调警告，测试汇总仍为 OK；未为此扩改 UI。

用户明确本轮不跑全量、不加架构门禁，已遵守。历史全量不是当前改动验收；未重启应用、未实发付费 API。

## 自审与交付

两项验收已覆盖；生产只改 writing_api.py 两行，测试仅指定文件，另有本报告与必要接力/状态元数据；无新增依赖，无状态结构变更；现有确认语义与预算均保留。范围内同类必加口语已全部覆盖。
提交：本报告随实现提交，哈希见 master 的 R1220 提交及状态页落地记录。

[TASK_COMPLETE]
