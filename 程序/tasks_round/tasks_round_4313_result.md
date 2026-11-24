# R4313 · AST-STALE-VIDEO：过期口径收窄与视频持久过期只读现算
<!-- round-evidence: {"commit_base": "7c2904ea6", "credential_hits": 0, "evidence_sha256": "34741d724d363105", "exit": 0, "failed": 0, "passed": 40, "round": 4313, "tests": "run_selftests.py -k keyframe_evidence video_staleness req_s08_anchors"} -->

## 开头三问

- （一）本轮类型：功能轮（AGENTS.md §3.1），车道 `codex/ast-stale-video`，基准 `master` `7c2904ea6`。
- （二）测试跑了吗、三个基线：已跑定向与架构关键门禁——`run_selftests.py -k coverage_baseline keyframe_evidence video_staleness req_s08_anchors` 45/45 通过（0 红）；`run_selftests.py -k layer_relations layers no_circular_import` 52/52 通过（0 红）；`scripts/coverage_report.py` 15 组定向目标全绿并刷新 `维护记录/覆盖率基线.json`（133/681）。默认冒烟与完整架构门禁由合入出口 CI 覆盖；全量回归未跑（以 `full-safe-receipts.json` 为准）。
- （三）欠账少了吗：未新增欠账。

## 改动文件

- `程序/domain/asset_plan.py`：配合过期口径收窄。
- `程序/domain/keyframe_evidence.py`：`_creative_payload` / `_metadata_digest` 收窄过期口径（只留影响画面生成的字段，旧口径 `narrow=False` 保留 `title` 等原有字段以兼容旧证据）。
- `程序/domain/video_staleness.py` & `程序/video_staleness.py`：新增视频持久过期只读现算模块与顶层兼容门面；自含只读 `_load_assets` 避免导入 `agent.shot_assets` 成环。
- `程序/domain/storyboard_catalog_service.py`：新增 `generated_video_versions()` 与 `stale_video_shots()` 只读现算入口。
- `程序/tests/test_video_staleness.py`、`程序/tests/test_keyframe_evidence.py`、`程序/tests/test_req_s08_anchors.py`：补充视频过期与首帧收窄口径测试；`test_req_s08_17` 构造由改集标题改为新增一镜以匹配新口径，断言未改。
- `程序/tests/architecture/_layers.py`：登记 `video_staleness`（L2）及两条有向同层边 `('storyboard_catalog_service', 'video_staleness')`、`('video_staleness', 'storyboard_lifecycle')`。
- `程序/维护记录/覆盖率基线.json` & `程序/runbook.md`：真实重测刷新生产模块数 679 → 681（133 有覆盖、548 未触达）。
- `程序/tasks_round/tasks_round_4313_result.md`：本文件。

## 验证记录

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `scripts/coverage_report.py <15 targets> --json 维护记录/覆盖率基线.json` | 0 | 模块被覆盖 133/681，目标用例全通过 |
| `run_selftests.py -k layer_relations layers no_circular_import` | 0 | 52 条全绿，0 红 |
| `run_selftests.py -k coverage_baseline keyframe_evidence video_staleness req_s08_anchors` | 0 | 45 条全绿，0 红 |
