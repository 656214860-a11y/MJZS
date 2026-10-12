# 当前快照

## 2026-10-12：O19 完成，继续 O20

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O18 已完成，**O19 已完成（R1343）**，下一项 O20。
- O19（初稿/定稿采用增加差异与影响预览）：新增只读 `storyboard_catalog_service.adoption_impact`——以同集已采用分镜为基线（同路径优先，否则同 episode_id），逐镜用稳定 ID 对比 `added`/`removed`/`changed`（duration/dialogue/assets/frame/video_prompt/title）/`reordered`（只报告不换号），并列出将失效的首帧 PNG（`media_root/帧`）与已生成视频镜头（`data/state.json`、`cloud_video/*/data/state.json` 中 shots 非空）。经 L3 `stage_execution_service.storyboard_adoption_impact` 与 L4 `storyboard_files.adoption_impact` 接线，在 `check_adoptable` 之后、采用之前把 summary 追加到状态栏（不弹窗、不改状态）。见 [R1343](../程序/tasks_round/tasks_round_1343_result.md)。
- 验证证据：O19 定向 `-k adoption_impact storyboard file_cache row_targets workflow_context` 78/78、`test_ui_edges.BatchContinuationTests.test_adopt_skips_adopted_without_confirm` 1/1、架构 312/312、默认冒烟 8/8，0 红；1343 − 1341 = 2 < 5，本轮不跑全量。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1343；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O20（P2，M）——保留 Animatic 强校验并降低大媒体重复读取成本（`tasks_round_1267_result.md` O20 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1341；到 1346 起跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
