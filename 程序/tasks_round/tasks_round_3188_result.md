# R3188 结果：T10 包化——infra/（L1 基础设施层）第一批 8 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "eb4d5e2a", "credential_hits": 0, "evidence_sha256": "02f2a7dfb09b9842", "exit": 0, "failed": 0, "passed": 111, "round": 3188, "tests": "run_selftests.py -k client_profiles model_secrets qwen_setup token_saver comfy_service seedream_api cloud_assets tk_timers"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。`smoke_test.py --affected` 冒烟检查项 9/9 绿、定向 59 个测试文件经隐藏桌面执行（结果见验证记录）；`smoke_test.py --architecture` 架构门禁 **483/483 全绿（200.3s）**；覆盖率基线重测 **622 模块／74 覆盖**（97 条目标用例全过）；分支覆盖率下限门禁 9/9 绿。
3. **欠账少了吗**：是。T10 包化 **infra/ L1 第一批**：`infra/` 实体由 24 → 32 个。L1 顶层剩余实体（app_icon/broadcaster 等高扇出枢纽与长尾）继续分批；L4/L3 收官项同前轮盘点；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `infra/` 实体 | 8 个低扇出顶层 L1 模块 `git mv` 入 `infra/`：client_profiles、cloud_assets、comfy_service、model_secrets、qwen_setup、seedream_api、tk_timers、token_saver。 |
| 别名门面 ×8 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = infra.<名>` 别名门面；`import <扁平名> is import infra.<名>` 实体同一性保持。 |
| 消费方 import | 约 40 个生产文件改包路径导入（`import infra.X as X`／`from infra.X import` 惯例，含 domain/、orchestrator/、ui/、agent/、contract/ 跨层消费边与 infra/ 域内互引）；AST 复扫残留裸引用为 0。 |
| 真实缺陷修复 ×1 | `orchestrator/workflow_settings.py` 导入改写后局部名丢失：`import client_profiles` → `import infra.client_profiles as client_profiles`（保留旧局部符号，`profile_for_model`/`profile_for_mode` 调用点不动）；同文件 `qwen_setup`/`client_profiles` 其余两处 from-import 同步。该缺陷由 `--affected` 门禁中 workflow_settings 相关用例暴露（NameError），修复后复测。 |
| HTTP 边界台账 | `tests/architecture/test_http_boundary.py` 白名单 `'seedream_api.py'` → `'infra/seedream_api.py'`——实体迁移后按新包路径登记，`urlopen` 直连仍受白名单棘轮约束，未放宽。 |
| 棘轮台账 | `维护记录/架构统一基数.json` 裸 `json.loads` 债务条目文件字段随包路径迁移：`comfy_service.py`×2、`qwen_setup.py`、`seedream_api.py` → `infra/` 前缀（脚本批量改 6 处文件字段）；`test_unification_ratchet` 复测转绿。 |
| 基线与文档 | `覆盖率基线.json` 重测 **622 模块／74 覆盖**（614+8，97 条目标用例全过）；`runbook.md` §11 同步（622/74/548）；`architecture.md` infra 目录行「首批 23 个」→「共 32 个」；`PROJECT_MAP.md` 模型与安全／成本与运行保障两行模块路径改 `infra/` 前缀；`_layers.py` 扁平登记名天然兼容未改；`distribution_manifest.md` glob 已覆盖。 |

## 验证记录

- `smoke_test.py --affected client_profiles model_secrets qwen_setup token_saver comfy_service seedream_api cloud_assets tk_timers`：冒烟检查项 **9/9**；定向门禁选中 **59 个测试文件／159 工作单元**，经隐藏桌面执行——首轮与架构门禁并发抢 GUI 令牌致 900s 包装超时（底层日志 ALL TESTS PASSED），串行复跑 **627 秒 0 红／ALL TESTS PASSED**，冒烟合计 **10/10 通过**。
- `smoke_test.py --architecture`：**483/483 全绿（200.3s）**。首轮曾报 5 红（覆盖率基数 614→622、http 白名单旧扁平名、seedream 直连条目、json.loads 债务台账扁平名、状态页轮次头陈旧），台账随包路径全部对齐后复测清零。
- `tests.architecture.test_branch_coverage_floor`＋`test_coverage_baseline`：**9/9 绿**（L0/L1 顶层门面文件仍在，模块集合口径不变）。
- 覆盖率：`scripts/coverage_report.py` 重测写入 `维护记录/覆盖率基线.json`（97 条目标用例全通过，模块被覆盖 74/622）。
- 未跑：`--all --safe` 全量（结构治理批，按 §5 口径由合并轮凭据兜底）；`distribution_build --verify`。

## 过程损耗（如实）

- **workflow_settings 别名回归**：批量 import 重写把 `import client_profiles` 改成 `import infra.client_profiles`（无 `as`），模块内 3 处 `client_profiles.*` 调用点 NameError——`--affected` 首轮捕获。教训：`import X` → `import pkg.X` 必须补 `as X` 保局部名，或同步改调用点；本批已统一 `as` 口径并复扫。
- **架构门禁首轮 5 红全为台账口径**：包路径迁移后四类登记面（覆盖率模块计数、HTTP 白名单、json.loads 债务、状态页轮次头）需同步，均非源码缺陷；已全部对齐后 483/483。

## 下一步（T10 后续批次）

- infra/ L1 剩余顶层实体继续分批（长尾低扇出优先；broadcaster/app_icon 等枢纽随批推进）。
- L4/L3 收官项同前轮：`stage_execution_service`（扇出 50）单独一轮、`writing_api` 随拆分批、`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
