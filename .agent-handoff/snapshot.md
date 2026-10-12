# 当前快照

## 2026-10-12：O09 完成，继续 O10

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O08 已完成（O07 R1312 实现＋R1314 收口全量；O08 R1318），**O09 已完成（R1322，收口全量 R1328 修复＋R1322 凭据）**，下一项 O10。
- O09（白模就绪没绑来源版本与真实可播放性）：`white_model_service` 新增 `shot_digest`／`source_digest`／`evidence_state`／`record_evidence` 登记采用分镜的镜头调度摘要与预演文件字节数／mtime／媒体事实；`previs_routing.ready` 按证据失效（旧成果只判过期、不删）；`previs_automation.verify` 校验通过即登记；`local_previs` 状态列与线上导入共用同一判据。见 [R1322](../程序/tasks_round/tasks_round_1322_result.md)。
- 验证证据：O09 定向 138/138、关联 172/172（stage_* 57 ＋ ui_edges 115）、默认冒烟 8/8、架构 312/312、收口安全全量 4522/4522（0 红，tree 42e782ea）——第 1 次全量唯一红是 SG-05 探针夹具（同符新语义），定向补登记后第 2 次全量 0 红；详见 [R1322](../程序/tasks_round/tasks_round_1322_result.md)；O07 收口全量 [R1312](../程序/tasks_round/tasks_round_1312_result.md)（4516/4516、tree 12ad4759）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”（未跟踪 outputs/ 等），`content_tree()` 在脏树返回空，因此全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1322、修复轮 1328 均在 `o07-fullsafe-master` 干净 worktree 领取，主树提交只能点名路径。
- 下一步：O10（P1，M）——资产“确认并采用”存在部分成功窗口（`stage_execution_service.py:667` 先写确认再应用选择），验收“第二次写入失败／进程中断／重复点击都能恢复到明确状态”，依赖 O11。默认只跑 `-k <本轮模块>` ＋ 默认冒烟。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
