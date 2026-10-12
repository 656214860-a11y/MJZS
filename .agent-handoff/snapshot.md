# 当前快照

## 2026-10-12：O22 完成，继续 O23

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O21 已完成，**O22 已完成（R1346）**，下一项 O23。
- O22（资产正典、变体与镜头引用提供变更影响视图）：`asset_plan` 新增只读 `asset_impact`／`deletion_references`（正典 `canonical_board`／`character_anchor`、`state_variants`、被哪些采用镜头哪些字段引用、需复核首帧、受影响已生成视频、`orphan`／`protected` 与删前引用清单）；`asset_context.referencing_shots` 与 `references` 同口径；`stage_execution_service` 补 L3 门面；资产详情页顶部提示被引用/可回收（`asset_impact_note`）。改变体不覆盖正典、删除受引用资产先给引用列表、孤立资产可回收（依赖 O18；O39 回收侧未完成）。见 [R1346](../程序/tasks_round/tasks_round_1346_result.md)。
- 验证证据：O22 定向 `-k asset_impact asset_context asset_plan asset_detail asset_reference` 64/64、`test_todo_comment_snapshot`＋`test_unification_ratchet` 5/5、架构 312/312、默认冒烟 8/8，0 红；1346 − 1341 = 5 ≥ 5，收口补一次干净 master 全量（`--all --safe`）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1346；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O23（见 `tasks_round_1267_result.md` O23 条目；依赖 O11、O18）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1341；本轮 1346 收口补跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
