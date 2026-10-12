# 当前快照

## 2026-10-12：R1335 阶段④自然剧本按集解析与分集增量账本（独立功能轮，非 O 清单）
- 分支 `codex/episode-incremental-context`（基线 R1330 提交 ef1488e）。`script_contract` 新增 `split_script_episodes`／分集账本（`write_dir(project,'script')/剧本分集增量账本.json`，记每集 sha256 与 based_on 其余集快照）；`writing_api.reply()` 调用前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 调用后更新账本；`workflow_tasks._episode_change_notice()` 给本地 Agent 只报集号；首次／无账本退化为全量注入。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 验证：定向新增 5＋1＋1 条全绿；`tests.test_writing_api`／`tests.test_script_contract` 红点与改动前基线同形（缺 gitlink 假红）；默认冒烟 8/8；架构棘轮 3/3。全量未跑（同缺口必假红）。
- 欠账：本分支非 master，未写 `程序/project_status.md` 轮次头；合并 master 后由收口轮同步。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。

## 2026-10-12：O10 完成，继续 O11

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O09 已完成（O09 R1322，收口全量 R1328 修复＋R1322 凭据），**O10 已完成（R1330）**，下一项 O11。
- O10（资产「确认并采用」存在部分成功窗口）：`confirm_gates` 新增相位 `PENDING`／`APPLIED`／`FAILED`，`record(..., state=)` 落相位、`pending()` 只把 applied 当已确认（旧记录无 state 按 applied，避免重复问）；`adopt_asset_plan_choice` 改成「先记 pending → 落盘 → 成功记 applied」，落盘失败记 failed、中断留 pending，两者都不算确认完成；`asset_detail._pick` 失败给「候选还留着，可再点一次」的恢复提示。见 [R1330](../程序/tasks_round/tasks_round_1330_result.md)。
- 验证证据：O10 定向 96/96（confirm_gates／asset_detail／stage_wiring／asset_plan）、架构棘轮 5/5、默认冒烟 8/8，0 红；台账 `架构统一基数.json` 第四项三处行号平移（1025/1056/1072→1039/1070/1086）；收口安全全量见 [R1330](../程序/tasks_round/tasks_round_1330_result.md)。O09 收口全量 [R1322](../程序/tasks_round/tasks_round_1322_result.md)（4522/4522、tree 42e782ea）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”（未跟踪 outputs/ 等），`content_tree()` 在脏树返回空，因此全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1330 在 `o07-fullsafe-master` 干净 worktree 领取（该 worktree 索引里残留过一份比 HEAD 旧的暂存文档，`git reset --hard HEAD` 清掉后领取），主树提交只能点名路径。
- 下一步：O11（P1，M）——人工确认应绑定被确认内容而不是只绑名称（`confirm_gates.py:222/239/262` 用 anchor/canon/批次名造 key，`310/324` 只存 choice/by）。验收“替换候选、改冲突优先级、外部改台账、跨集同 ID 都触发正确复核；无关字段变化不扰动全部项目”。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
