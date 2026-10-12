# 当前快照

## 2026-10-12：O25 完成，继续 O26

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O24 已完成，**O25 已完成（R1350）**，下一项 O26。
- O25（首帧批量任务统一目标集、重试与替换解释）：`keyframe_batch` 新增 `batch_plan`（三意图 `missing`／`retry`／`replace`＋六态＋跳过原因＋实际模型与参考图）：`missing` 只取从没提交过的缺帧镜头、已提交跳过不重付费、`deleted` 任何模式不复活、空文件／未配置／越界一律跳过并给原因；`keyframe_comfy` 弹窗新增「批次意图」下拉与目标集预览，Agent／Seedream／本地三条路径与 `auto_batch` 都按统一目标集并记录计划。见 [R1350](../程序/tasks_round/tasks_round_1350_result.md)。
- 验证证据：O25 定向 93/93、`keyframe previs stage_execution` 全绿、`todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 27/27、`test_skip_hygiene` 3/3、架构 312/312、默认冒烟 8/8，0 红；1350 − 1346 = 4 < 5 且未命中 §5，本轮不跑全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1350；下次收口全量在干净 master 工作树 `run_selftests.py --all --safe`。主树提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O26（见 `tasks_round_1267_result.md` O26 条目：白模及外部工具工作区可配置且可写；`white_model_service.py:77`／`:88`；S/M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1346，下一欠账点 1351）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
