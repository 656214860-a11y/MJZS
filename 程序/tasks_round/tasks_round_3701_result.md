# R3701 结果报告
<!-- round-evidence: {"commit_base": "3badb0b5", "credential_hits": 0, "evidence_sha256": "557721eecd1c9afb", "exit": 0, "failed": 0, "passed": 51, "round": 3701, "tests": "run_selftests.py -k test_artifact_index keyframe_lifecycle error_codes secret_status"} -->

## 三问

- 类型：§3.3 结构治理轮（新增模块＋1 个试点接入，任务书轮 I17 产物索引）。
- 测试：见下「验证」节；默认冒烟 9/9；定向 `run_selftests -k artifact_index keyframe_lifecycle storage_maintenance recycle` 全绿；`--affected keyframe_lifecycle_service` 10 项全过；`--gate` 增量串行因合并积压队列超 smoke 900s 上限（超时非断言失败）；架构门禁 573 条仅 1 环境红（依赖白名单分裂，见下）；全量串行复验 16 红文件中 3 个真实欠账同轮闭环（错误码黄金表/诊断导出清单/合并残留目录），余为隐藏会话 ffmpeg 0xC0000142 环境性（R3439 同根因）。
- 欠账：少了——I17-1~4 全部落地，L1-H4 产物索引入库。

## 变更

- 新增 L1 `infra/artifact_index.py`（约 230 行）：`index_path(project)` 落 `程序/data/artifact_index/<项目根 sha256[16]>.sqlite`（WAL，不写用户项目目录）；`register(path, stage, kind, parents=())` 候选态登记、parents 血缘共享 logical_id；`versions(logical_id)` 全版本序；`set_state` 四态机（候选→采用/回收、采用→归档、归档→回收、回收→候选），非法迁移抛 `ConfigError`；「回收」落盘经 `storage_maintenance.recycle_paths()`，回收失败抛 `StorageError` 且不写状态；`duplicates()` 按内容 sha256 分组；`rebuild()` 经 `executors.submit('io', …)` 后台扫描重建（有序路径、确定性结果）。
- 试点：`domain/keyframe_lifecycle_service` 加 `_index_register`/`_index_recycled` 两个 best-effort 登记调用（删除首帧登记+置回收；替换首帧登记新产物），只捕获 `(OSError, sqlite3.Error, ConfigError)`——索引可重建不阻断生命周期（L1-H4 丢损重建语义），既有测试断言未动。
- 登记：`_layers.py` L1 收 `artifact_index`、SAME_LAYER_EDGES 收 `artifact_index→executors`、`artifact_index→storage_maintenance`（共 766 条）；`层间合规清单.json` LR-09/LR-10 58→60；architecture.md L1 行+判定列+本轮记要、PROJECT_MAP 运行保障行。
- 基线：分支覆盖率基线 101 模块/2973 点/1639 覆盖（artifact_index.py 14 点 71.4%，工具实测 tests.test_artifact_index）；分支覆盖率下限登记 71.4；行覆盖率基线 671 模块/89 覆盖（artifact_index 131 行 91.6%，coverage_report 实测）；runbook 口径同步。

## 验收对照

- I17-1：`test_rebuild_after_index_loss_matches` 删除索引文件后 rebuild 结果与删前逐项一致。
- I17-2：`test_legal_chain_and_restore`/`test_illegal_transitions_raise` 覆盖五合法迁移与非法迁移 `ConfigError`（含未知状态）。
- I17-3：`test_recycle_uses_storage_maintenance` mock 断言 `recycle_paths(project,(path,),…)` 被调；`test_recycle_failure_blocks_transition` 回收失败不写状态。
- I17-4：`test_index_file_not_in_project_dir` 断言索引在 `程序/data/artifact_index` 内、项目目录外；keyframe_lifecycle 既有测试不改断言全过。

## 验证

- `run_selftests -k artifact_index keyframe_lifecycle storage_maintenance recycle`：全绿。
- `smoke_test.py --affected keyframe_lifecycle_service`：10/10。
- `smoke_test.py`：9/9。
- `smoke_test.py --gate`：增量队列合并积压 900s 超时（非断言失败）；改直跑 `run_selftests --serial` 全量串行（1038 单元）。串行与被掐断 --gate 的隐藏桌面孤儿争用 GUI 令牌（SUSPECT_CONCURRENCY）；孤儿清退后红项文件复验归因：
  - 真实欠账（同轮闭环 3 项）：`test_error_codes` 黄金表缺 I6/I8 五码（E-TOOL-FAILED/E-TOOL-TIMEOUT/E-CONFIG-INVALID/E-IO-CORRUPT/E-IO-READ，R3412 主干版表落后分支码表）；`test_secret_status_diagnostics` 导出清单漏 I14 新增的 `logs/metrics_summary.json`；`test_copy_rules` 命中合并遗留 `.AIGC创作全流程.bak-merge`（已删）。
  - 环境性：test_keyframe_evidence×11、test_req_s08_anchors×8、test_stage_gate_e2e_probe×5、test_pet_ui×2、test_keyframe×3、test_batch_frames、test_file_origin_provenance、test_stage_completion_service、test_stage_parallel 各 1——隐藏会话 ffmpeg `0xC0000142`（R3439 已录根因）致 `keyframe_evidence.image_facts` 解码失败；上述红文件常规会话定向全绿（`PawTests` 常规会话属未映射窗口工件、隐藏会话通过）。
  - `test_dependency_whitelist`：工作树解释器缺 psutil/nvidia-ml-py、共享解释器反向报邻车道 pydantic 五包——环境分裂，非产物回归。
- `smoke_test.py --architecture`：573 条仅 1 红 `test_whitelist_completeness`——环境性：本工作树系统解释器缺 psutil/nvidia-ml-py（运行环境解释器在邻车道侧），同一测试在共享解释器下反向报邻车道未登记 pydantic 五包；与 R3696 合并轮记录的环境分裂同一根因，非本轮产物回归。

## 备注

- 依赖 I10 `executors.submit('io')` 与 I8/I15 已入库基础设施；同层边两条已登记。
- `domain/keyframe_lifecycle_service`（L2）→ `infra/artifact_index`（L1）为下行依赖，不需同层边登记。
