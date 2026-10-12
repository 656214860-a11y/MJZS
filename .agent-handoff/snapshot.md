# 当前快照

## 2026-10-12：O18 完成，继续 O19

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O17 已完成，**O18 已完成（R1342）**，下一项 O19。
- O18（来源账本从「仍在」升级为「仍是这个版本」）：`artifact_lineage` 新增 `check`/`source_status`（current/stale/missing/unknown + 逐来源明细）、多来源 `record(sources=…)`、只读 `affected` 影响清单与显式 `adopt`；`source_available` 语义保留但改为基于 `check()` 派生——内容变只标过期、不隐藏、不改写用户成品，仅 `missing` 才隐藏；剧本/分镜目录对过期项显示「原稿已变更／来源已变更」。见 [R1342](../程序/tasks_round/tasks_round_1342_result.md)。
- 验证证据：O18 定向 `-k artifact_lineage file_cache storyboard script_structure script_contract` 136/136、架构门禁 312/312、默认冒烟 8/8，0 红；1342 − 1341 = 1 < 5，本轮不跑全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1342；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O19（P2，M）——初稿和定稿采用增加差异与影响预览（`tasks_round_1267_result.md` O19 条目；依赖 O18）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1341；到 1346 起跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
