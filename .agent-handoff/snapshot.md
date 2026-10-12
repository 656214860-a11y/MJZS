# 当前快照

## 2026-10-12：O15 完成，继续 O16

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O14 已完成，**O15 已完成（R1339）**，下一项 O16。
- O15（请求冻结与「已加载」清单扩展到所有生成链路）：核对各入口，直连 API（`capture_request`→`freeze_skills`）与桌面 Agent 投递（`open_flow_agent` 唯一入口，writing 分支 `validate_selected_skills`＋`freeze_skills`）都消费发送边界一次捕获的快照；手动任务书不发模型请求；媒体生成冻结由 O12 关闭。新增 `tests/test_request_freeze_entries.py` 3 条入口差异测试（含静态入口核对），未改生产逻辑。见 [R1339](../程序/tasks_round/tasks_round_1339_result.md)。
- 验证证据：O15 定向 `-k request_freeze_entries` 3/3、关联 `-k workflow_settings writing` 全绿、默认冒烟 8/8，0 红。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；`1335`／`1337` 已被其他车道领走，本轮 1339。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O16（P2，M）——四角色审核结果需要可定位的依据与修订范围（`tasks_round_1267_result.md` O16 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1336；next 到 1341 再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
