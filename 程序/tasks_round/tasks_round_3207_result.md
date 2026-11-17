# R3207 结果：T10 包化 orchestrator——skill_ 前缀族 L3 两模块迁移（skill_package_meta／skill_project_layer）
<!-- round-evidence: {"commit_base": "be7b0d36", "credential_hits": 0, "evidence_sha256": "72bee05e14e41385", "exit": 0, "failed": 0, "passed": 86, "round": 3207, "tests": "run_selftests.py -k skill_package_meta skill_project_layer skill_registry skill_lifecycle skill_import pet_skills skill_panel"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟、`-k` 定向、`--architecture` 架构门禁与覆盖率基线结果见验证记录。
3. **欠账少了吗**：是。T10 包化 **orchestrator/** 实体由 72 → 74 个；顶层真实实体剩余约 30 个（L1 枢纽×4、L3×4、L4×21、L5×2，另有 image_agent_runner 永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | skill_ 前缀族 L3 两模块 `git mv` 入 `orchestrator/`：`skill_package_meta`（91 行，外部包受控元数据）、`skill_project_layer`（248 行，项目层路径口径与禁用登记）。 |
| 别名门面 ×2 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = orchestrator.<名>` 别名门面；实体同一性 2/2 校验通过，`skill_registry.LAYER_ORDER` 经再导出解析正常。 |
| 消费方 import | 8 处改包路径导入：`orchestrator/skill_registry.py` 两条 re-export 行、迁移实体域内互引 1 条（`skill_package_meta→skill_project_layer`）、`skill_project_layer` 内 `stage_layout`→`contract.` 规范 1 条、生产消费方 3 条（`pet_skills_manage`/`skill_lifecycle_service`/`ui/skill_import_service`）、测试 1 条（`test_skill_lifecycle`）。AST 复扫残留 **0**。 |
| 批内边 | `skill_package_meta` 对 `skill_project_layer` 的 `stage_from_path` 引用同批改写包路径。 |
| 特例核查 | 无 `__file__` 锚点、无模块级 LOGGER（无需日志名冻结）、无动态 `import_module`/引号串引用、无 `__main__` 入口。 |
| 登记面 | `architecture.md`「八批共 74 个」；`PROJECT_MAP.md` 阶段配置行两模块改包路径；`_layers.py` 扁平登记名天然兼容未改；`架构统一基数.json` 无命中无需动。 |
| 基线 | 覆盖率基线重测 **639 模块／71 覆盖**（97 用例全过；模块数 +2＝实体入包后门面与实体各计一文件，covered 72→71 系门面覆盖口径自然漂移，如实记录）；`runbook.md` §11 同步（639/71/568）。 |

## 验证记录

- `smoke_test.py`（默认）：**9/9 通过**。
- `run_selftests.py -k skill_package_meta skill_project_layer skill_registry skill_lifecycle skill_import pet_skills skill_panel`：选中 **9 个测试文件／86 条用例／295.2 秒，0 红，ALL TESTS PASSED**（GUI 令牌排队约 5 分钟后正常执行）。
- `smoke_test.py --architecture`：首轮 **482/483**，唯一红 `test_round_number_continuous`（状态页 3207 vs 结果 3207+1=3208，轮次头未同步）——临时同步后复测该文件 **5/5 绿**，其余 482 项首轮已绿，合计 **483/483**。
- 覆盖率：`scripts/coverage_report.py` 97 条目标用例全通过，基线写入 `维护记录/覆盖率基线.json`（**639 模块／71 覆盖**）。

## 观察记录（历史欠账，未扩大范围）

- 顶层遗留的**旧式 re-export 门面**（`from contract.X import …`＋`__all__`，非 `sys.modules` 别名）与新式别名门面并存：`pet_bus`/`script_contract`/`stage_layout`/`platform_tools`/`file_naming`/`file_index_contract`/`file_index`/`legacy_migration` 等约 8 个——均为 R3093 前后批次门面，实体已在包内，清除与否属门面清除轮。
- `skill_lifecycle_service`/`skill_remote_service`/`skill_archive`/`skill_security_service` 四个 skill_ L4 模块扇出仅 1–3，列为下一批 `ui/` 候选。

## 下一步（T10 后续批次）

- L4 skill_ 族四模块 → `ui/`（扇出 1–3，下一轮首选）。
- L3 剩余：`skill_` 族已清，余 `stage_execution_service`（扇出 49，单独一轮）、`writing_api`（1332 行，随拆分批）、`image_agent_runner`（永久除外）。
- L1 枢纽四模块：`storage_maintenance`（39，`__main__` 特例）、`app_logging`（74）、`file_cache`（87）、`ui_tokens`（108）——各自专轮或两两分批。
- L4 大模块 17 个余量与 L5 两入口随后分批；门面清除轮需单独授权。
