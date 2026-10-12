# 当前快照

## 2026-10-12：O28 完成，继续 O29

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O27 已完成，**O28 已完成（R1353）**，下一项 O29。
- O28（本地/云端任务统一可恢复状态与错误分类）：`video_progress` 新增只读 `task_status`／`status_label`／`status_next`／`status_detail`／`error_kind`，把提交中/结果不确定/排队/生成中/下载中/下载失败/技术不合格/待审核/已采用统一成一套名并各给「下一步」（查询/补配置/显式重做），错误归鉴权/限额/模型协议/内容拒绝/网络/本机磁盘/未分类（本机磁盘先判，其余复用 `pet_agent.classify`）；`engine.poll` 记 `download_error`（取回失败保留 succeeded，再查询续取不重生成）；视频页状态行与交付页逐镜行显示统一状态与下一步。见 [R1353](../程序/tasks_round/tasks_round_1353_result.md)。
- 验证证据：定向 `-k video_task_status integration video ui_edges` 332/332、架构 312/312、默认冒烟 8/8，0 红；1353 − 1351 = 2 < 5 且未命中 §5 升级条件，本轮不跑全量。上次绿全量 1351（tree c97c1336），下一五轮欠账点 1356。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`；本轮 1353；全量在干净 master 工作树 `run_selftests.py --all --safe`。`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（`tests/architecture/test_round_baselines.py` 会校验）。提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O29（见 `tasks_round_1267_result.md` O29 条目：预算由多个计数器汇总为请求级可对账记录；`engine.py` 按视频秒数预留、`skill_budget.py` 与 `pet_agent.Budget` 计数不同；M/L）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1351，下一欠账点 1356）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
