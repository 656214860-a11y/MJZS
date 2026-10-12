# 当前快照

## 2026-10-12：O14 完成，继续 O15

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O13 已完成，**O14 已完成（R1338）**，下一项 O15。
- O14（历史／上下文／输出文件采用不同维度，界面要解释清楚）：`writing_api.chat_session_overview`／`chat_session_summary`（只读）给出会话模型与调用方式、请求身份、上下文来源、已确认阶段文件数与自然剧本采用状态；桌面剧本页新增只读说明标签 `idea_session_label`，按当前显示模型刷新，切模型后随之更新。见 [R1338](../程序/tasks_round/tasks_round_1338_result.md)。
- 验证证据：O14 定向 `-k idea_chat` 131/131、关联 `-k ui_edges idea_inline_brief writing` 全绿、架构相关全绿、`-k desktop_startup_perf` 14/14、默认冒烟 8/8，0 红；`desktop.py` 增 Tk 标签，TODO 注释快照 desktop.py 行号 2749→2753。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；`1335`／`1337` 已被其他车道领走，本轮 1338。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O15（P2，M/L）——请求冻结与「已加载」清单扩展到所有生成链路（`tasks_round_1267_result.md` O15 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1336；next 到 1341 再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
