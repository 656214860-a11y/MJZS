# R2921 结果：T10 包化——infra/（L1 基础设施）批次 23 模块迁移
<!-- round-evidence: {"commit_base": "74220116", "credential_hits": 0, "evidence_sha256": "06c6298757ddd20b", "exit": 0, "failed": 0, "passed": 202, "round": 2921, "tests": "run_selftests.py -k account_store aigc_lint app_icon broadcaster clipboard_lock config_snapshot engine_probe h3_reference hash_backend http_client lease_verifier line_endings log_maintenance model_diagnostics native_asset_codec request_ledger script_text_reader store_program_locator update_notice usage_history usage_snapshot workflow_process_registry workspace_maintenance"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**；定向 16 个测试文件 202 条用例全绿（证据 `evidence/R2921.json`）；未跑全量（合入 master 前由合并门禁按凭据口径执行）。
3. **欠账少了吗**：是。T10「约 358 个顶层文件包化」推进一批：`infra/`（L1）落地 23 个模块实体＋23 个别名门面；`contract/`（L0）此前批次已在 master。`domain/`、`orchestrator/`、`ui/` 三包与 `app.py`/`pet_cloud.py`/`writing_api.py` 大模块拆分仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `infra/` 实体 | 23 个模块 `git mv` 入 `infra/`：account_store、aigc_lint、app_icon、broadcaster、clipboard_lock、config_snapshot、engine_probe、h3_reference_adapter、hash_backend、http_client、lease_verifier、line_endings、log_maintenance、model_diagnostics、native_asset_codec、request_ledger、script_text_reader、store_program_locator、update_notice、usage_history、usage_snapshot、workflow_process_registry、workspace_maintenance。 |
| 别名门面 ×23 | 顶层同名 `.py` 改为**模块别名门面**：`sys.modules[__name__] = 实体`，`import <扁平名>` 返回包内实体本体——私有名（`_slots`/`_HOST_FAILURES`/`_parse_args`）、模块级状态与 `mock.patch('<扁平名>.…')` 补丁面完全穿透；4 个带 `__main__` 的门面（app_icon/engine_probe/log_maintenance/workspace_maintenance）附 `__main__` 转发，`python <名>.py --cleanup` 等直跑入口与退出码语义不变（app_icon 的 main 返回 Path 不套 SystemExit）。 |
| 消费方 import | 40 个生产文件改 `import infra.<名> as <名>`／`from infra.<名> import …`，局部名不变、逻辑零改动；`skill_tools.py` 保留扁平 `import line_endings`（`test_line_endings` 源串契约要求，别名门面下行为等价）。 |
| `__file__` 锚点修复 ×6 | 移入 `infra/` 后 `Path(__file__).parent` 会错指 `infra/`：account_store、app_icon、log_maintenance、workspace_maintenance 的 `PROGRAM`、aigc_lint 的 `_PACKAGE`、engine_probe 的 `ledger_path()` 统一改 `.parents[1]`（程序根）。 |
| 扫描器包感知 | `tests/architecture/_scan.py`：`is_package_facade` 识别名单再导出（contract 存量）与别名门面（含 `__main__` 转发块，块内禁 import 防漏依赖边）；`module_scan_files`/`registry_key`/`module_import_rows` 等棘轮口径不变（门面排除、实体以扁平登记名入图）。 |
| 台账与基线 | `架构统一基数.json` 三处 file 字段改包内路径（engine_probe×2、lease_verifier）；`test_http_boundary.py` 白名单 `http_client.py`→`infra/http_client.py`；`test_coverage_baseline.py` 改包感知生产口径；`覆盖率基线.json` 重测 **433 模块／67 覆盖**；`runbook.md`、`architecture.md`、`PROJECT_MAP.md`、`distribution_manifest.md` 同步。 |

## 验证记录

- `smoke_test.py`：8/8 通过。
- `smoke_test.py --architecture`：**470 条全绿**（当轮实测，含 unification/coverage/layers/circular/size 全部棘轮）。
- 定向：`run_selftests.py -k <23 个模块名>` → 16 文件 202 条；首轮 47 红全部定位修复（门面穿透性＋`__file__` 锚点＋`__main__` 直跑），复跑全绿；`test_line_endings` 单独复绿 16/16。
- `scripts/skill_package_pins.py --check`：3 个外部技能包 0 问题（本工作树按登记提交补齐 4 个 gitlink 检出：AIGC创作全流程、剧本锻造、编剧技能集、reference/HoLLMwood，均为固定提交）。
- `python workspace_maintenance.py --help`／`engine_probe.py --help`：门面 `__main__` 转发实测输出正常。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按 `full-safe-receipts.json` 凭据口径执行）。

## 过程损耗（如实）

- 初版名单式门面（`from infra.x import (名单)`）无法穿透私有名与模块补丁面，定向 47 红暴露；改别名门面后归零。contract/ 存量门面仍是名单式——其模块面无状态、测试无私有依赖，暂不动；后续批次统一时可一并切别名式。
- `test_skill_reference_injection` 在干净工作树报红：4 个 gitlink 技能包未检出（worktree 不自动初始化嵌套仓），按 `外部技能包哈希.json` 固定提交从主工作区本地克隆补齐，非产品回归。

## 下一步（T10 后续批次）

- `domain/`（L2 业务）、`orchestrator/`（L3）、`ui/`（L4）包与剩余顶层前缀族，逐批同法迁移；门面清除轮统一改写测试导入后删除全部门面。
- `app.py`、`pet_cloud.py`、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
