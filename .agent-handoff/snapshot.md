# 当前快照

## 2026-10-12：O32 完成，继续 O33

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O31 已完成，**O32 已完成（R1357）**，下一项 O33（剪辑/交付统一采用版本、覆盖率和清单发布，P2／事实·建议）。
- O32（剪辑输出规格不能固定替代项目规格）：`script_contract.py`（L0）新增 `resolve_output_spec`／`preview_spec`／`output_filter`（等比缩小＋居中留边，绝不裁切）／`loudness_filter`／`overlay_metrics`／`describe_output_spec`，`PRODUCTION_LOCK_DEFINITIONS` 增加 `resolution`／`fps`；`engine.py`（L3）`_encode` 改用 `stage_config.workflow_lock` 的规格（内嵌字幕字号／边距与音量随规格，`qc.json` 记 `output_spec`），新增 `output_spec`／`output_spec_text`；`edit_service.assemble_image_timeline(..., spec=)`／`animatic_service.build_bundle(..., spec=)`／`stage_execution_service.animatic_preview_spec` 让预演低清但画幅跟项目；后期页导出前显示实际规格。见 [R1357](../程序/tasks_round/tasks_round_1357_result.md)。
- 验证证据：`tests/test_output_spec.py`（新）15 条；定向 15/15＋关联 136/136、架构与端到端 66/66＋153/153＋120/120、默认冒烟全绿，0 红；真实 ffmpeg 端到端：9:16→1080x1920@30、16:9→1920x1080@30（源 640x360 等比留边未裁切）。1357 − 1356 = 1 < 5 且未命中 §5，本轮不跑全量。**上次绿全量：1356（tree 006d0295、4749/4749、425.3 秒、0 红），下一五轮欠账点 1361。**
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`；本轮 1357；全量在干净 master 工作树 `run_selftests.py --all --safe`。`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（`tests/architecture/test_round_baselines.py` 会校验）。提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O33（见 `tasks_round_1267_result.md` O33 条目：剪辑/交付统一采用版本、覆盖率和清单发布；`engine.py` 拼接选择已审核匹配版本、`desktop.py` 交付视图读最新版本、成片/QC/manifest 分步发布）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
