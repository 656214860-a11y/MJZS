# 当前快照

## 2026-10-12：O16 完成，继续 O17

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O15 已完成，**O16 已完成（R1340）**，下一项 O17。
- O16（四角色审核结果可定位的依据与修订范围）：`hollmwood_roles._run` 每次算 `review_basis`（brief／SKILL／节奏／审核 system 四组 sha256），逐条记 `review_records`（role／attempt／verdict／rule_compliant／creative_signoff／review_text，位置／违反规则／修订建议／通过条件都留在审核原文）；`review_audit.scope`＋每条 `creative_signoff` 明确「APPROVED 只等于规则合格，创意满意由用户确认」；返工 prompt 只针对退回意见里的明确问题且不重复注入节奏；`RoleExecutionError` 与 `writing_api` 成功/失败结果都带 `hollmwood_review_audit`；桌面完成文案改为「…已通过（规则合格；创意满意由您确认）」。见 [R1340](../程序/tasks_round/tasks_round_1340_result.md)。
- 验证证据：O16 定向 `-k hollmwood` 51/51、关联 `-k writing` 139/139、`-k idea_chat` 全绿、`-k stage_prompt_governance` 15/15、`-k copy_rules` 14/14、`-k todo_comment` 2/2、`-k unification_ratchet` 3/3、默认冒烟 8/8，0 红。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；`1335`／`1337` 已被其他车道领走，本轮 1340（上次绿全量 1336，1341 起需再跑全量）。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O17（P2，M）——剧本结构「形式合格」与「内容完备」分开，不让 Writer/Editor 名称暗示运行了模型（`tasks_round_1267_result.md` O17 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1336；next 到 1341 再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
