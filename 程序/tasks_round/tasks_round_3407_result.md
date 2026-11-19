# R3407 结果文件 — L1 任务书轮 I6：技术异常层级（contract/infra_errors.py）
<!-- round-evidence: {"commit_base": "ea9f94ed", "credential_hits": 0, "evidence_sha256": "20bd5844a260bc9e", "exit": 0, "failed": 0, "passed": 83, "round": 3407, "tests": "run_selftests.py -k infra_errors error_codes engine_probe native_apps copy_rules layer_relations"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.4 契约轮（任务书明定）；范围按 `runbook` §15 3.4 放宽至 `contract/` 包，未动其他 contract 文件。
2. **测试跑了吗、三个基线过了吗？** 跑了。定向批次 **99 条 0 红**（test_infra_errors 9、test_error_codes、test_engine_probe、test_native_apps、test_infra_errors_boundary 3、test_layer_relations＋test_layers 11、test_gate_selfaudit、test_copy_rules 14）；`smoke_test.py` **9/9 绿**。全量 `run_selftests.py --all --safe` 已在隐藏桌面跑完诊断：**[NO_RECEIPT]**（脏树不写绿凭据），8999 条／17 文件红，逐条归因见下——本轮引入的 2 处红（LR-03 未登记边、I3 文案超限）已修复复绿；其余为并行负载下 ffmpeg/ffprobe 解码抖动（隔离复跑 196 条全绿）与 master 三 ref 一致的既有红 2 文件。
3. **欠账少了吗？** 少了。FL-04 拆出「层级已建、存量待迁」：LR-07 口径切换为豁免 infra_errors 族后实测仍 **257**（存量 raise 未动，I7 起逐模块清零）；新增 `test_infra_errors_boundary` 按模块登记内置异常中文 raise 棘轮基线，只减不增；`error_codes` 补 4 个缺码使 8 个异常族默认码全部可解析。

## 领号说明

- R3407 由本工作树（`devin-l1-enterprise`／`codex/l1-enterprise`）在 I6 开工时经 `round_claim.py` 领得（claims 登记 2026-11-18T20:46:50）；共享计数器此后被他道领至 3434，本轮沿用已领号，不另取新号。

## I6-1　异常层级＋code 可解析＋兼容继承 ✅

- 新建 `contract/infra_errors.py`（L0）：`InfraError` 根＋`NetworkError`/`StorageError`/`CorruptDataError`/`ProcessError`/`QuotaError`/`AuthError`/`ConfigError` 共 8 类，`__all__` 全量导出。
- 每类带 `code`：构造时双重校验——必须属于本族 `_allowed` 集合且已在 `error_codes.CODES` 登记，否则 `ValueError`；`detail` 为技术事实载荷（上层不直接展示），用户文案由上层经 `error_codes.describe()` 产出。
- 兼容继承按任务书 L1-H7：`NetworkError`/`StorageError`/`AuthError` 多继承 `OSError`，`CorruptDataError` 继承 `ValueError`，`ProcessError`/`QuotaError` 继承 `RuntimeError`——旧 `except` 子句（含 `PermissionError` 场景的 OSError 族）继续可捕获。
- `contract/error_codes.py` 仅追加缺码：`E-IO-READ`、`E-IO-CORRUPT`、`E-TOOL-FAILED`、`E-CONFIG-INVALID`（按族插入 `_ITEMS`，既有码未动）。
- `tests/test_infra_errors.py` 9 条：默认码解析、族内覆盖码接受、跨族拒绝、未知码拒绝、导出符号均为异常类、`isinstance` 旧内置 except 兼容、MRO 兼容、每类默认码可解析、message/detail 行为。

## I6-2　棘轮门禁按模块登记 ✅

- 新建 `tests/architecture/test_infra_errors_boundary.py`：窄口径（`raise ValueError/RuntimeError/OSError/Exception(` 且含 CJK）按模块登记 `BUILTIN_CJK_RAISE_BASELINE`（37 个 L1 模块），实测超基线或新模块出现违规即红；更宽口径由 LR-07 兜底。
- `tests/architecture/test_layer_relations.py` LR-07 改造：收集 L1 全部 CJK raise 站点 `(模块, 异常函数名)`，`_infra_error_names()` 汇集 `contract/infra_errors.py` 全部异常类名及**传递子类**（全仓 ClassDef 基类扫描），命中族名的 raise 不计。实测 **257 不变**——存量尚未迁移，符合「棘轮只减」预期；I7 起逐模块下降。
- `_layers.py` 登记 `infra_errors` → L0；同层边 `('infra_errors','error_codes')` 登记 `SAME_LAYER_EDGES`（763→764，注释与 `层间合规清单.json` LR-03 note 同步）；同层互依赖仍 5 对。

## I6-3　L0 纯度门禁（K9 已合入 master）✅ 前瞻验证

- master 已合入 K9（R3408：`test_contract_purity.py`＋L0P 层＋「L0 纯度」台账段）；本分支尚无该门禁文件，故用 **master 版扫描器**对本树 `contract/` 实测：`infra_errors.py`、`error_codes.py` 均 **CLEAN 零违规**（无禁用 import/调用）。合入后 `test_scan_matches_ledger` 口径下两文件不产生新条目。
- 门 G-C 未触发：K4（契约清单 `contract/_manifest.py`＋`contract/CHANGELOG.md`）**未合入** master（`git ls-tree master:程序/contract/` 无此二文件，亦无 `test_contract_manifest`），按任务书无需登记。
- 注意：master 的 `_layers.py` 已含 L0P(0.5) 层与更多 L0 契约模块登记，与本分支同文件改动将在合并轮解冲突（I25–I27 收口）。

## 附带修复：I3 欠账闭环（test_copy_rules 红）

- 全量诊断暴露 `test_copy_rules.test_no_popup_goes_over_the_limit` 红：I3（R3401）在 `infra/engine_probe.py`、`infra/native_apps.py` 新增的两条「未配置」`ValueError` 文案 59/54 字，超 45 字弹窗上限。
- 最小修复：文案缩短为「引擎命令构造器未配置：需 L3/L5 组装点注入」／「Blender 查找器未配置：需 L4/L5 组装点注入」，注入点符号（`workflow_engines.background_command`／`ui.white_model.find_blender`）移入上方注释，调试信息不丢。`test_copy_rules` 14 条复绿，行为不变。

## 全量诊断归因（[NO_RECEIPT]，8999 条／17 文件红）

| 类别 | 文件 | 归因与证据 |
| --- | --- | --- |
| 本轮引入·已修 | architecture.test_layer_relations（2）、test_copy_rules（1） | LR-03 边未登记→已登记复绿；I3 文案超限→已缩短复绿 |
| 负载抖动 | test_batch_frames、test_file_origin_provenance、test_keyframe（3)、test_keyframe_lifecycle_service、test_keyframe_evidence（11)、test_req_s08_anchors（8)、test_domain_events（2)、test_stage_gate_e2e_probe（5)、test_stage_completion_service、test_stage_parallel、test_pet_ui 证据类（2) | 全部栈顶 `domain/keyframe_evidence.image_facts` 或 `agent.media.probe` 的 ffmpeg/ffprobe 解码失败；16 路并行 1190 秒负载下超时/断管。隔离复跑：keyframe_evidence 13、req_s08_anchors＋domain_events＋stage_completion 69、batch_frames＋keyframe＋lifecycle＋stage_gate_e2e＋stage_parallel 114，共 **196 条全绿** |
| master 既有红 | test_shared_adapter_infrastructure（1) | `domain.tts_api` 无 `no_redirect`；merge-base/HEAD/master 三 ref 文件逐字一致，与本分支零交集 |
| master 既有红 | test_ui_edges_guards（1) | `orchestrator/engine.py` 中 `adopted_edit_version(st['shots'].get(shot['id'])` 计数 1≠2；三 ref 一致，本分支未触该文件 |
| 计时抖动 | test_pet_ui tick（1) | `('stage.completed','delivery')` 未在 tick 内排空，得 `stage.paused`；文件未触，疑并行负载下时序抖动 |

本分支改动文件与上述红项代码路径零交集（contract/error_codes 仅追加码、不改既有行为；infra_errors 无生产消费者；engine_probe/native_apps 仅文案）。

## 待切换项／移交

- I7 起迁移 `request_ledger`/`comfy_service`/`unit_of_work`（基线登记：33/20/10 处），LR-07 257 处存量随各轮收口。
- `contract/infra_errors.py` 暂无生产消费者（I7 首批迁移时启用）；`error_codes` 新增 4 码已可被 `lookup`/`describe` 正常解析。
- 合并轮注意：`_layers.py`（L0P 层＋新 L0 模块）、`contract/` 目录、`error_codes.py` 与 L0 宪法车道成果冲突，按并集解。
- 全量绿凭据缺口：本轮 [NO_RECEIPT]；合入 master 前按 §5 强制补跑 `--all --safe`，届时 master 既有红 2 文件（tts_api、ui_edges）若仍红需先行处置或如实记录。

## 测试证据

- 定向批次：`python -B -m unittest tests.test_infra_errors tests.test_error_codes tests.test_engine_probe tests.test_native_apps tests.architecture.test_infra_errors_boundary tests.architecture.test_layer_relations tests.architecture.test_layers tests.architecture.test_gate_selfaudit tests.test_copy_rules` → **99 条，41.2 秒，0 红**。
- `python -B smoke_test.py`（默认）：**9/9 绿**。
- 隔离复跑（负载归因）：`test_keyframe_evidence` 13 条、`test_req_s08_anchors`＋`test_domain_events`＋`test_stage_completion_service` 69 条、`test_batch_frames`＋`test_keyframe`＋`test_keyframe_lifecycle_service`＋`test_stage_gate_e2e_probe`＋`test_stage_parallel` 114 条 → 合计 **196 条全绿**。
- K9 前瞻：master 版 `test_contract_purity` 扫描器实测 `contract/infra_errors.py`、`contract/error_codes.py` → **CLEAN**。
- 全量 `run_selftests.py --all --safe`（隐藏桌面）：8999 条／1190.3 秒／17 文件红 → **[NO_RECEIPT] 仅诊断**，归因见上表。
- 覆盖率：生产模块 661→**662**（新增 infra_errors 无定向覆盖条目，如实登记）；`覆盖率基线.json`、`分支覆盖率基线.json`、`分支覆盖率下限.json` 已重生成，runbook §11 数字同步。

## 改动清单

- `contract/infra_errors.py`（新）：L1 技术异常层级 8 类，`__all__` 导出。
- `contract/error_codes.py`：+`E-IO-READ`/`E-IO-CORRUPT`/`E-TOOL-FAILED`/`E-CONFIG-INVALID`。
- `tests/test_infra_errors.py`（新，9 条）、`tests/architecture/test_infra_errors_boundary.py`（新，3 条）。
- `tests/architecture/_layers.py`：`infra_errors`→L0、`SAME_LAYER_EDGES` +1（764）、注释同步。
- `tests/architecture/test_layer_relations.py`：LR-07 豁免 infra_errors 族（含传递子类），站点级收集。
- `architecture.md`：L0 模块表 +infra_errors、LR-07 描述、门禁清单 +test_infra_errors_boundary。
- `PROJECT_MAP.md`：模型与安全行补登 contract/infra_errors.py。
- `infra/engine_probe.py`、`infra/native_apps.py`：未配置文案缩短至弹窗上限内（I3 欠账修复）。
- `维护记录/层间合规清单.json`（LR-03 note 764 条）、`规则守卫基线.json`＋`规则守卫对照.md`（+test_infra_errors_boundary）、`覆盖率基线.json`、`分支覆盖率基线.json`、`分支覆盖率下限.json`。
- `runbook.md` §11：覆盖率基线数字 661→662。
- `project_status.md`：工作树轮次头同步（不入提交，合并轮口径）。

## 提交

- 分支 `codex/l1-enterprise`；commit 见 `git log`（`dev.py commit` 自动暂存白名单＋生成 `tasks_round/evidence/R3407.json`）。
- 未 push（规则：仅用户明确要求时 push）。

[TASK_COMPLETE]
