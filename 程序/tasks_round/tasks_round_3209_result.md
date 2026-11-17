# R3209 结果：T10 包化 ui/——skill_ 前缀族 L4 四模块迁移（skill_lifecycle_service／skill_remote_service／skill_archive／skill_security_service）
<!-- round-evidence: {"commit_base": "8319bac1", "credential_hits": 0, "evidence_sha256": "098bfe93fee3a483", "exit": 0, "failed": 0, "passed": 236, "round": 3209, "tests": "run_selftests.py -k skill_archive skill_remote skill_lifecycle skill_security skill_import pet_skills skill_panel skill_update"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟、`-k` 定向、`--architecture` 架构门禁与覆盖率基线结果见验证记录。
3. **欠账少了吗**：是。T10 包化 **ui/** 实体迁移累计七批共 129 个；顶层真实实体剩余约 26 个（L1 枢纽×4、L3×3、L4×17、L5×2，另有 image_agent_runner 永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | skill_ 前缀族 L4 四模块 `git mv` 入 `ui/`：`skill_lifecycle_service`（349 行，定位/改名/启停用/删除入口）、`skill_remote_service`（314 行，远程链接导入）、`skill_archive`（221 行，ZIP 安全解包导入）、`skill_security_service`（64 行，可执行内容警示）。 |
| 别名门面 ×4 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面；实体同一性 4/4 校验通过，`skill_import_service.untrusted_source_notice` 经 re-export 解析一致。 |
| 消费方 import | 生产 4 文件 9 处（`pet_skills_manage` 顶层×1＋行内×2、`ui/skill_import_service` re-export×1、`ui/skill_panel_import` 行内×6）＋测试 3 文件 7 处（`test_skill_lifecycle`/`test_skill_archive_import`/`test_skill_remote_import`/`test_skill_security`/`test_skill_update_check`，含 1 处 `mock.patch` 字符串目标同步包路径）＋实体域内规范 7 处（`skill_import_service`/`skill_registry`/`stage_layout` 已迁移依赖改包路径、批内边 `skill_remote_service→skill_archive`）。AST 复扫残留 **0**。 |
| 批内边 | `skill_remote_service` 对 `skill_archive` 的引用同批改写 `ui.` 前缀。 |
| 特例核查 | 无 `__file__` 锚点、无模块级 LOGGER、无动态 `import_module`/`__import__`、无 `__main__` 入口；`ui_plugin_registry` 无注册项（非懒加载插件）；`test_atomic_write_boundary` 的 `_TEMPORARY_BOUNDARIES` 按 `path.stem` 扁平名匹配，包路径迁移天然兼容未改。 |
| 登记面 | `architecture.md`「七批共 129 个」；`PROJECT_MAP.md` 阶段配置行四模块改包路径；`_layers.py` L4 扁平登记名天然兼容未改；`架构统一基数.json` 无命中无需动。 |
| 基线 | 覆盖率基线重测 **643 模块／71 覆盖**（97 用例全过；模块数 +4＝四门面与实体各计一文件，covered 持平 71）；`runbook.md` §11 同步（643/71/572）。 |

## 验证记录

- `smoke_test.py`（默认）：**9/9 通过**。
- `run_selftests.py -k skill_archive skill_remote skill_lifecycle skill_security skill_import pet_skills skill_panel skill_update`：选中 **11 个测试文件／236 条用例／53.0 秒，0 红，ALL TESTS PASSED**。
- `smoke_test.py --architecture`：首轮 **482/483**，唯一红 `test_round_number_continuous`（状态页 3208 vs 结果 3209+1=3210，轮次头未同步）——临时同步后复测该文件 **5/5 绿**，其余 482 项首轮已绿，合计 **483/483**。
- 覆盖率：`scripts/coverage_report.py` 97 条目标用例全通过，基线写入 `维护记录/覆盖率基线.json`（**643 模块／71 覆盖**）。

## 观察记录（历史欠账，未扩大范围）

- skill_ 前缀族至此**全部迁完**：L3 两枚（R3207）＋L4 四枚（本轮），顶层仅剩门面。
- `pet_skills_manage.py`（650 行，L4）仍是 skill 管理 UI 消费中枢，随 L4 大模块批推进。
- 测试文件中指向已迁移模块的**遗留扁平 import**（如 `test_skill_archive_import.py` 的 `import skill_panel`、`test_skill_lifecycle.py` 的 `import skill_import_service`）经门面解析正常，属门面清除轮统一改写范围，本轮不越界。

## 下一步（T10 后续批次）

- L4 余 17 个大模块：`app.py`(1486)、`pet_ui_stages`(1186)、`ui_widgets`(1125)、`pet_agent`(1093)、`desktop_shared_input`(968)、`desktop`(964)、`cell_hover`(962)、`pet_ui`(908)、`responsive_ui`(759)、`pet_ui_support`(667)、`pet_skills_manage`(650)、`asset_reference_images`(582)、`production_lock_fields`(421)、`local_video`(403)、`desktop_shared_send`(292)、`environment_check`(210)、`account_inputs`(105)——多数高扇出，逐批或逐模块推进。
- L1 枢纽四模块：`storage_maintenance`（39，`__main__` 特例）、`app_logging`（74）、`file_cache`（87）、`ui_tokens`（108）。
- L3 余 `stage_execution_service`（扇出 49，单独一轮）、`writing_api`（1332 行，随拆分批）、`image_agent_runner`（永久除外）；L5 `app_shortcut`/`desktop_launcher` 收尾。
- 门面清除轮需单独授权。
