# 当前快照

## 2026-10-12：O30 完成，继续 O31

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O29 已完成，**O30 已完成（R1355）**，下一项 O31。
- O30（字幕估算轴与实际音频轴建立校准流程）：`subtitle_timing.py`（L1）保留等分低成本估算（`timed_entries` 行为不变），新增 `calibrate_entries(episode, audio=None)` 在镜内按权重重排字幕轴（有真实音频秒数／对齐区间就按真实值并计 `audio`，否则按 `line_weight` 句长分摊并记「未校准」，超镜头整镜压缩记 `overflow`）、`validate_entries`（非有限／负数／反向／重叠／越界报错）、`rows_from_entries`，`srt_rows` 改用校准轴；`subtitle_export_service.py`（L2）导出改用校准轴、返回 `(target, report)` 并写 `字幕校准.json`（来源音频摘要＋校准状态），新增 `pending_calibration`／`export_calibration`；`desktop.py` 导出后提示已校准句数或未校准句数。见 [R1355](../程序/tasks_round/tasks_round_1355_result.md)。
- 验证证据：`tests/test_subtitle_calibration.py`（新）23 条；定向 `-k subtitle ui_edges skill handoff stage tts` 690/690、架构 312/312、默认冒烟 8/8，0 红；1355 − 1351 = 4 < 5 且未命中 §5，本轮不跑全量。上次绿全量 1351（tree c97c1336），**下一五轮欠账点 1356——O31 收口时必须跑一次干净 master `--all --safe`**。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`；本轮 1355；全量在干净 master 工作树 `run_selftests.py --all --safe`。`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（`tests/architecture/test_round_baselines.py` 会校验）。提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O31（见 `tasks_round_1267_result.md` O31 条目：声音角色映射和导入音轨绑定到具体集/用途；建议项；M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1351，下一欠账点 1356）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
