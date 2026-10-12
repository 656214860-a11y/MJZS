# 当前快照

## 2026-10-12：O21 完成，继续 O22

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O20 已完成，**O21 已完成（R1345）**，下一项 O22。
- O21（资产检索与候选墙可追溯性和批量决策）：`asset_reference_search` 新增 `score_parts`（清晰度/提示词/构图/来源/许可五项分项，`score` 由分项派生、口径不变）、`explain`/`_state`/`STATE_NOTES`（缺地址/缺来源/缺许可/低分/不可商用/来源冲突/重复/可入库八态）、`suppressed`（低分与同图重复逐条解释）；`rank` 记同图来源 `alts` 与 `conflict`；`normalize`/`_credit` 增 `collected_at`。`reference_wall` 新增「许可依据/采集日期/状态/同图来源」四列，状态栏说明挡下的候选；剔除候选不影响已入库资产。见 [R1345](../程序/tasks_round/tasks_round_1345_result.md)。
- 验证证据：O21 定向 `-k reference` 118/118、锚定 `-k asset_detail asset_plan asset_reference workflow_context skill_tools` 全绿、架构 312/312、默认冒烟 8/8，0 红；1345 − 1341 = 4 < 5 且未命中 §5，本轮不跑全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1345；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O22（见 `tasks_round_1267_result.md` O22 条目；依赖 O18、O39）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1341；到 1346 起跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
