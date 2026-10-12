# 当前快照

## 2026-10-12：O23 完成，继续 O24

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O22 已完成，**O23 已完成（R1347）**，下一项 O24。
- O23（连贯性问题从发现到解除的闭环）：`continuity_ledger` 新增结构化 `issues`（稳定编号 `CI-<kind>-<scope>`、涉及镜头/资产、证据、严重度）与 `03_continuity/output/continuity_issues.json` 登记表（`merge_issues`／`sync_issues`／`decide_issue`／`issue_gate`）：同一问题不重复新增、修好解除、解除后再现重开、证据变化重开且清空决定；人工忽略必须写理由并记下作用版本；`stage_parallel.ledger_ready` 改用 `issue_gate`（忽略后不再拦）；`stage_execution_service` 补 L3 门面；桌面连贯性页加「问题闭环」表与「忽略（写明理由）」按钮。见 [R1347](../程序/tasks_round/tasks_round_1347_result.md)。
- 验证证据：O23 定向 124/124＋160/160、架构 312/312、默认冒烟 8/8，0 红；1347 − 1346 = 1 < 5 且未命中 §5，本轮不跑全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1347；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O24（见 `tasks_round_1267_result.md` O24 条目；「尚未开始先不拦」的兼容策略与正式生产模式分开）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1346，下一欠账点 1351）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
