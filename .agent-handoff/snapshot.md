# 当前快照

## 2026-10-12：O27 完成，继续 O28

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O26 已完成，**O27 已完成（R1352）**，下一项 O28。
- O27（视频技术合格与创意验收分开）：`engine.py` 新增 `review_source`／`content_reviewed`／`review_label` 与 `review_by`，无人值守自动技术放行写 `review_by='auto'`＋`AUTO_REVIEW_NOTE`，真人验收写 `review_by='user'`，老记录按旧前缀 `无人值守自动验收` 回推；交付页新增「采用」列，视频制作页与交付页验收列改用 `review_label`；`approved_versions` 与自动粗剪/交接包取版口径不变（自动放行仍算已验收）。见 [R1352](../程序/tasks_round/tasks_round_1352_result.md)。
- 验证证据：定向 `-k integration ui_edges video` 318/318、架构 312/312、默认冒烟 8/8，0 红；1352 − 1351 = 1 < 5 且未命中 §5 升级条件，本轮不跑全量。上次绿全量 1351（tree c97c1336），下一五轮欠账点 1356。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1352；全量在干净 master 工作树 `run_selftests.py --all --safe`。主树提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O28（见 `tasks_round_1267_result.md` O28 条目：本地/云端任务统一可恢复状态与错误分类；`engine.py:239` 已存 local_request；M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1351，下一欠账点 1356）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
