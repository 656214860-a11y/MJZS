# R2927 结果：T10 包化——domain/（L2 业务服务）批次 22 模块迁移
<!-- round-evidence: {"commit_base": "c93c164e", "credential_hits": 0, "evidence_sha256": "b1cdc3e13a41a655", "exit": 0, "failed": 0, "passed": 153, "round": 2927, "tests": "run_selftests.py -k animatic_service audio_import_service confirm_gates delivery_import_service edit_service final_service handoff_service idea_attachments idea_brief_form idea_document_paths idea_script_heuristic idea_transcript legacy_adoption_service recycle_recovery_service speech_api stage_workspace_service storyboard_adoption_service subtitle_export_service subtitle_timing tts_api video_lifecycle_service asset_reference_prompts"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**（随附解释器口径）；定向 22 个模块关键词 235 条用例全绿；覆盖率基线重测 **456 模块／69 覆盖**。
3. **欠账少了吗**：是。T10 包化推进第二批：`domain/`（L2）落地 22 个模块实体＋22 个别名门面；`infra/`（L1）首批已在 master（R2924）。`orchestrator/`（L3）、`ui/`（L4）与剩余顶层前缀族、`app.py`/`pet_cloud.py`/`writing_api.py` 大模块拆分仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `domain/` 实体 | 22 个 L2 模块 `git mv` 入 `domain/`：animatic_service、audio_import_service、confirm_gates、delivery_import_service、edit_service、final_service、handoff_service、idea_attachments、idea_brief_form、idea_document_paths、idea_script_heuristic、idea_transcript、legacy_adoption_service、recycle_recovery_service、speech_api、stage_workspace_service、storyboard_adoption_service、subtitle_export_service、subtitle_timing、tts_api、video_lifecycle_service、asset_reference_prompts。入选口径：`_layers.py` 登记 L2 且扇出最低的 22 个（native_assets 经核实为 L4，留给 ui/ 批次）。 |
| 别名门面 ×22 | 顶层同名 `.py` 为 `sys.modules[__name__] = domain.<名>` 别名门面（同 R2921 infra 批口径）：私有名、模块级状态与 `mock.patch('<扁平名>.…')` 补丁面穿透；本批无 `__main__` 直跑入口，无需转发块。 |
| 消费方 import | 34 个生产文件改 `import domain.<名> as <名>`／`from domain.<名> import …`（含 `writing_api.py` 一处逗号多导入手工补改）；包内互导 5 处（animatic→edit_service/tts_api、audio_import→tts_api、idea_brief_form/idea_transcript→idea_document_paths、subtitle_export→subtitle_timing）同步改包路径。 |
| `__file__` 锚点修复 ×3 | idea_document_paths、idea_transcript、speech_api 的 `Path(__file__).resolve().parent` 改 `.parents[1]`（程序根）。 |
| 日志名保持扁平 ×10 | 10 个模块 `logging.getLogger(__name__)` 会变 `domain.<名>`，改显式扁平名 `getLogger('<名>')`——`assertLogs('<扁平名>')` 契约与日志过滤口径不变。 |
| 扫描器/门禁适配 | 15 个架构测试的实体源码读取路径改 `domain/<名>.py`；`smoke_test.py` keyword 锚点改 `domain/idea_transcript.py`；`test_http_boundary.py` 白名单 `tts_api.py`→`domain/tts_api.py`；`test_coverage_baseline.py` CORE_FLOORS `video_lifecycle_service.py`→`domain/video_lifecycle_service.py`。 |
| 棘轮台账 | `test_unification_ratchet.py`：`_l2_source_files`/`_point_exists` 改经 `module_scan_files` 归一实体（第三项 basename 口径不变）；`架构统一基数.json` 第四项 6 个 file 字段改 `domain/<名>.py`（relpath 口径）；`test_service_return_contract.py` 采用方扫描改实体路径；`test_writing_api_stage_config_boundary.py` 两处 import 串锚点改 `domain.idea_script_heuristic`。 |
| 基线与文档 | `覆盖率基线.json` 重测 **456 模块／69 覆盖**（+22 实体＋`domain/__init__.py`）；`runbook.md` §11 数字同步；`architecture.md` 目录树加 `domain/`；`PROJECT_MAP.md` 3 处、`distribution_manifest.md` glob 同步。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `smoke_test.py --architecture`（随附解释器）：**470 条全绿**（当轮实测）。
- 定向：`run_selftests.py -k <22 个模块名>` → 235 条用例 0 红（首轮暴露 `getLogger(__name__)` 日志名漂移，修复后复绿）。
- `scripts/skill_package_pins.py --check`：3 个外部技能包 0 问题（本工作树按登记提交补齐 4 个 gitlink 检出，同 R2921 处置）。
- 导入冒烟：`domain.*` 实体、扁平门面、`stage_execution_service`/`writing_api`/`desktop` 重消费者全部可导入，无循环。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按 `full-safe-receipts.json` 凭据口径执行）。

## 过程损耗（如实）

- 首轮架构门禁在系统 Python 3.14 下跑出 8 红：其中 6 个为真实迁移适配项（棘轮路径口径、台账 relpath、import 串锚点、runbook 数字），2 个为工作树环境项（未跟踪 `维护记录/基准历史.json`、4 个 gitlink 技能包未检出）；另有 `ast.dump` 哈希在 3.14 下整体漂移造成的系统性误报——改用随附解释器复跑后归零，教训：**本仓门禁一律用 `运行环境\Python\python.exe`**。
- `import X, Y` 逗号多导导入不被正则覆盖，`writing_api.py` 一处手工补改；已全库复扫确认无残留。

## 下一步（T10 后续批次）

- `orchestrator/`（L3）、`ui/`（L4）包与剩余顶层前缀族，逐批同法迁移；本轮已验证的适配点（实体路径解析、relpath/basename 双口径台账、日志名冻结、gitlink 补齐、随附解释器口径）直接复用。
- `app.py`、`pet_cloud.py`、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 门面清除轮：全部批次完成后统一改写测试导入、删除全部门面。
