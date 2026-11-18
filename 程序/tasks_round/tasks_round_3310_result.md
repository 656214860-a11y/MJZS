# R3310 结果：L2领域服务层优化任务书轮6（修复轮：事务原语接入 7 处）
<!-- round-evidence: {"commit_base": "d6af4c75", "credential_hits": 0, "evidence_sha256": "d3fc485d4fd33e83", "exit": 0, "failed": 0, "passed": 13, "round": 3310, "tests": "run_selftests.py -k uow_write_paths"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.2 修复轮。任务书轮 6 预设「事务原语接入 7 处」——按任务书原文定性记录：**本轮修的是 P0「回滚不完整」这个缺陷，不是结构治理；该轮判据以「缺陷闭环」为准，不以「模块数」为准**（任务书轮 6 节明文要求结果文件记录此定性）。前置轮 5（R3297）已交付 `infra/unit_of_work` 唯一跨文件回滚原语，本轮把 7 个 L2 写路径的自造备份/恢复底座全部收敛到该原语。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 先红（改前实测） | **12 失败 + 1 错误 / 13 用例**：`tests/test_uow_write_paths.py` 对改前代码实测，跨文件第二写失败或取消时第一写不恢复、多处「原本不存在」路径不删除、取消不触发回滚（输出摘录见「先红证据」） |
| 转绿（改后） | **绿**：`run_selftests.py -k uow_write_paths` → 13 条用例 / 2.7s / 0 红文件 / ALL TESTS PASSED（本轮收尾复跑确认） |
| 定向自检 | **绿**：`run_selftests.py -k <本轮触及模块关键词>` → 89 条用例 / 0 红文件 |
| `smoke_test.py --affected` | **绿**：按本轮全部改动模块展开 → 68 个测试文件 / 510s / 0 红文件，覆盖 7 个事务模块及其全部消费者 |
| 默认冒烟 `smoke_test.py` | **9/9 通过**，exit 0 |
| 架构门禁 `smoke_test.py --architecture` | **502 条，FAILED（failures=2）**：`test_entry_files_stay_within_budget`（AGENTS.md 16028>16000，HEAD 即超支）、`test_round_number_continuous`（`project_status.md` 状态页 3259 冻结、仅 master 可提交）——与 R3275–R3297 记录的**分支固有红集合逐名一致**；本轮曾引入的分支决策点红（`global_library_service.py` 13≠17）已通过补 2 条用例＋工具重测刷新基线修复并复跑确认；`test_atomic_write_boundary`、`test_white_model_service_json_boundary` 等相关门禁全绿 |
| 全量回归 `--all --safe` | **绿**：1,990 条用例 / 1259.5s / 0 红文件（1 条既有登记 skip 位）；全量之后仅新增测试用例与基线 JSON（生产代码零改动），增量由分支覆盖率目标套件 1,459 条全绿覆盖，如实记录 |
| 分支覆盖率 | 工具重测刷新：87 模块 / 决策点 1288/2420；`global_library_service.py` 7/17(41.2%)→**11/17(64.7%)**，越过 53.0 下限；目标用例全通过 |

**3. 欠账少了吗？**
减少。任务书点名的「7 处各写一遍暂存→替换→失败恢复、4 处回滚不完整、取消与进程中断不回滚」已全部收敛：跨文件业务事务唯一走 `infra.unit_of_work.begin/commit/rollback`（磁盘 journal 抗崩、`except BaseException` 覆盖取消与 `KeyboardInterrupt`、回滚失败抛 `RollbackFailedError` 不吞原异常）；单文件原子发布仍走 `agent.core.replace`；`orchestrator/stage_asset_gateways.py` 与 `stage_execution_service.py` 的 `Path.replace` lambda 网关已收敛为 `agent.core.replace`，`_REPLACE_REGISTERED` **只缩不涨**（净减 2 项）。剩余欠账如实记录：轮 7 `business_log`、轮 8 `ServiceResult` 收口、轮 9 两处硬违规属后续轮次；分支固有 2 条架构红待 master 合并轮处理。

---

## 设计决策

| 决策点 | 结论与理由 |
| --- | --- |
| **回滚底座收敛** | 3 套自造备份底座 → 1 套 `infra.unit_of_work`：① 手工「旧字节快照＋失败写回/删除」（asset_batch×2、asset_detail、local_video_settings、video_prompt_publication、projects、idea_chat 补回滚）全部删除改登记 UOW；② `white_model_service.migrate` 的目录级 `shutil.move` 回滚保留——UOW 只登记普通文件，目录迁移回滚仍须反向 move，且 move-back 失败经 `app_logging.swallowed` 记录不吞原异常；③ `global_library_service` 复制出的**用户可见新文件**有意不进 UOW——保留 identity 校验回收（`storage_maintenance.recycle_paths` 语义），UOW 只管源清单/项目索引/来源索引三个 JSON。 |
| **登记完整性** | 每个多文件事务把**全部**参与路径一次性 `begin`：含「原本不存在」路径（rollback 时删除而非写回），路径经 `resolve()`＋`normcase` 去重；`except BaseException` 捕获取消/`KeyboardInterrupt`/`SystemExit`，rollback 自身失败只记 `app_logging.swallowed` 不顶掉原异常。 |
| **网关收敛** | `stage_asset_gateways.py`、`stage_execution_service.py` 原 `lambda source, target: Path(source).replace(target)` 改为暴露 `agent.core.replace`——后者含发布/缓存失效与 Windows 锁重试，裸 `Path.replace` 绕过两者；`_REPLACE_REGISTERED` 相应删 2 项（只缩不涨达标）。`white_model_service.py` 保留登记值 2：`test_white_model_service_json_boundary` 禁止该模块 import `agent.core`，其两处 `temporary.replace(target)` 属 L2 边界内既有形态，已在登记表注释说明。 |
| **idea_chat 事务边界** | `receive_brief` 在 `_append_raw_brief` **之前** `begin(raw_path, complete_path)`，整个字段抽取/锁校验/文档生成/`publish_json(complete_path)` 包进 try，末尾 `commit`；raw 追加失败、complete 发布失败或取消均回滚 raw 追加。inline_text 路径本就不写 raw（调用方稍后覆盖保存），登记为快照无害。 |

## 先红证据（改前实测）

新测试文件 `tests/test_uow_write_paths.py`（404 行 / 13 用例）先于生产改动落盘，对改前代码实测：

```
FAILED (failures=12, errors=1)   # 13 条用例
```

典型红项：取消注入后资产登记表/目标图未恢复（`test_import_asset_image_cancel_restores_image_and_registry`）、rename_asset 回滚后新建 registry 残留（`test_rename_asset_cancel_restores_plan_and_registry`）、`receive_brief` raw 追加后第二写失败不回滚（`test_receive_brief_cancel_restores_raw_append`）、`projects._write_transaction` 多文件取消不恢复（`test_write_transaction_cancel_restores_all_files`）等。改后同文件 13/13 绿。

## 验收对照（任务书轮 6）

- [x] **5 处「回滚不完整」各有复现用例，改前红、改后绿** → 13 用例覆盖全部 7 个改动点（含 2 处原本「无回滚」的 projects/idea_chat）：asset_batch import/rename、asset_detail bind、local_video_settings save、white_model sync/import/migrate、video_prompt stage_import 回滚失败保原异常、global_library copy_to_project/copy_to_library、idea_chat receive_brief、projects write_transaction。改前 12F+1E、改后 13/13 绿。
- [x] **`test_atomic_write_boundary.py` 绿（`_REPLACE_REGISTERED` 只许缩不许涨）** → 净减 2 项（删 `stage_execution_service.py`、`stage_asset_gateways.py` 两个 lambda 登记）；`white_model_service.py` 保持 2 并加注释说明受 json 边界测试约束；门禁实测绿。
- [x] **3 套备份底座收敛为 1 套** → 见「设计决策」表：文件级事务全部 `infra.unit_of_work`；目录级 move 与用户可见复制目标按语义保留并注明理由；单文件原子发布仍 `agent.core.replace`（非备份底座，是既有唯一原语）。
- [x] **`smoke_test.py --affected` 覆盖全部 7 个模块及其消费者** → 68 个测试文件全绿。
- [x] **触发全量（碰写入边界白名单）** → `run_selftests.py --all --safe` 1,990 条 / 0 红文件（1 条既有登记 skip）。

## 改动清单（14 个文件）

| 文件 | 改动 |
| --- | --- |
| `domain/asset_batch_service.py` | `import_asset_image` 登记资产登记表＋目标图入 UOW，删手工字节快照/恢复；`rename_asset` 登记 plan＋registry（新建 registry 回滚时删除） |
| `domain/asset_detail_service.py` | `_publish` 登记目标图＋asset 索引，删 `old_index`/`old_dest` 本地恢复，`except BaseException` 回滚 |
| `domain/local_video_settings_service.py` | 登记工作流副本＋`config.json`，删重复旧字节恢复，保留注入 copy/publish 网关与临时清理 |
| `domain/white_model_service.py` | `sync_project_copy`/`import_previs_media` 登记目标＋索引/记录入 UOW 改用局部 `from agent.core import replace`；`migrate_legacy_directories` 登记 manifest＋config.json，目录回滚保留反向 `shutil.move` 并记日志 |
| `domain/video_prompt_publication.py` | `stage_import` 登记草稿目标＋历史备份路径，删 `restore_bytes` 手工回滚，回滚失败不顶掉原异常、历史目录尽力清理 |
| `domain/global_library_service.py` | `copy_to_project` 登记源清单＋项目索引＋来源索引；`copy_to_library` 登记全局索引；复制目标留 UOW 外保留 identity 回收；回滚/回收失败只记日志 |
| `domain/projects.py` | `_write_transaction` 全部目标路径入 UOW，删逐字节手工回滚，`except BaseException` |
| `domain/idea_chat.py` | `receive_brief` raw/complete 双路径同事务：`begin` 提前至 `_append_raw_brief` 之前，整个抽取/发布包 try，`except BaseException` 回滚 |
| `orchestrator/stage_asset_gateways.py` | `Path.replace` lambda → `agent.core.replace` |
| `stage_execution_service.py` | 同上网关收敛 |
| `tests/test_uow_write_paths.py` | 新增 404 行 13 条回滚回归用例（先红后绿） |
| `tests/test_global_library_service.py` | +34 行：补 `copy_to_project`/`copy_to_library` 取消回滚用例，驱动分支覆盖率 13→17 决策点真实重测 |
| `tests/architecture/test_atomic_write_boundary.py` | `_REPLACE_REGISTERED` 删 2 项＋white_model 注释（只缩不涨） |
| `维护记录/分支覆盖率基线.json` | `branch_coverage_report.py` 工具重测刷新：87 模块 / 1288/2420；`global_library_service.py` 41.2%→64.7%（越 53 下限） |
| `tasks_round/tasks_round_3310_result.md` | 本文件 |

## 实测基线汇总

- 定向自检：`run_selftests.py -k uow_write_paths` → 13 条 / 2.7s / ALL TESTS PASSED（收尾复跑）；`-k <触及模块>` → 89 条 / 0 红。
- 受影响门禁：`smoke_test.py --affected` → 68 文件 / 510s / 0 红。
- 默认冒烟：`python -B smoke_test.py` → 9/9，exit 0。
- 架构门禁：`python -B smoke_test.py --architecture` → 502 条 / 215s / failures=2，失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3297 分支固有红逐名一致；两失败输入文件本轮零改动（`git diff HEAD -- AGENTS.md project_status.md` 为空）。本轮曾引入的决策点红已修复：补 `test_global_library_service` 2 条用例＋重测刷新基线（13→17 决策点、41.2%→64.7%）。
- 全量回归：`run_selftests.py --all --safe` → 1,990 条 / 1259.5s / 0 红文件（1 条既有登记 skip：需捆绑技能包的真机验证位）。全量后增量仅测试用例＋基线 JSON，生产代码零改动；增量由分支覆盖率目标套件 1,459 条（OK，skipped=2）全绿覆盖。
- 分支覆盖率：`branch_coverage_report.py` → 87 模块 / 1288/2420 决策点 / 目标用例全通过；`global_library_service.py` 64.7% ≥ 53.0 下限。

## 偏差与说明

1. **`_REPLACE_REGISTERED` 变动方向**：净减 2（`stage_execution_service`、`stage_asset_gateways`），符合「只许缩不许涨」；`white_model_service` 保持 2 未动并注明受 `test_white_model_service_json_boundary` 约束（禁 import `agent.core`）。
2. **`white_model_service` 用局部 import**：`from agent.core import replace` 写在函数内而非顶层——顶层导入会触发 `test_record_publication_is_injected_not_imported`（L2 正式 JSON 发布须经注入网关）；局部导入只为原子替换原语所需，与既有先例一致。
3. **目录级回滚保留 `shutil.move`**：`migrate_legacy_directories` 迁移的是目录，UOW 只登记普通文件；反向 move 失败经 `app_logging.swallowed('white_model_service.migrate.move_back')` 记录、不吞原异常（有专用用例 `test_migrate_move_back_failure_is_logged_not_silent`）。
4. **`global_library_service` 复制目标在 UOW 外**：复制出的用户可见文件若中途失败须按 identity 校验回收（防误删用户后加内容），而非 UOW 快照写回；索引类 JSON 全部入 UOW。
5. **`分支覆盖率下限.json` 未上调**：`global_library_service.py` 实测 64.7%、下限仍 53.0——下限表「只许人工上调」，棘轮收紧留待专项，本轮只刷新基线不动下限。
6. **全量后增量如实记录**：`--all --safe` 跑在最终生产代码树上；其后仅新增 `test_global_library_service` 用例与基线 JSON（无 `.py` 生产改动），增量经 1,459 条目标套件全绿验证。若验收要求对含测试增量的最终树再跑一次全量，可补跑。
7. **未动**：`tasks_round/L2领域服务层优化任务书.md`（外来勘误改动）、R3276 外来未跟踪四件（诊断报告/结果文件/任务书×2）、`project_status.md`（仅 master 可提交）一律不入暂存区。

## 遗留欠账

- 任务书轮 7（`infra/business_log.py`＋8 模块接入）、轮 8（4 处 `ServiceResult` 收口）、轮 9（`tts_api` 走 `http_client`、`white_model` 去盘符硬编码）——后续轮次。
- 分支固有架构红 2 条（AGENTS.md 字节预算、状态页轮次冻结）——存量问题，与本轮无关，待 master 合并轮处理。
- `infra/idempotency.py`、`domain/domain_events.py` 行覆盖 CORE_FLOORS 仍 0.0——各自轮次实现后刷新。
- 全部轮次收尾后输出 `tasks_round/任务完成/L2领域服务层优化·任务完成.md`（任务书 §7.2），本轮非末轮不产出。

## 提交

- 分支 `codex/wip-r3282`（领号 R3310，工作树 `dsh-864fd932-4054`；领号记录见 `<git common-dir>/round-claims.json`）。
- 主提交：`d6af4c75`（16 文件：10 个生产/网关文件、tests/test_uow_write_paths.py、tests/test_global_library_service.py、tests/architecture/test_atomic_write_boundary.py、维护记录/分支覆盖率基线.json、本结果文件、tasks_round/evidence/R3310.json）。
- 结果文件补记提交：本提交（`R3310: 补记结果文件commit哈希d6af4c75`；docs-only 补记同样带 `--tests uow_write_paths` 重跑定向测试刷新证据）。
- 轮次证据以 `tasks_round/evidence/R3310.json` 中 `run_selftests.py -k uow_write_paths` exit 0 / 13 通过 / 0 失败为准。
