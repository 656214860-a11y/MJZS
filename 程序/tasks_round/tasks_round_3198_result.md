# R3198 结果：T10 包化——infra/（L1 基础设施层）第二批 7 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "014aa52f", "credential_hits": 0, "evidence_sha256": "a07b86da29181606", "exit": 0, "failed": 0, "passed": 32, "round": 3198, "tests": "run_selftests.py -k integrations comfy_runtime native_apps stage_model_value model_metering asset_prompt_rules diagnostic_capture golden_outputs writing_api_stage_config"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 9/9 绿；`smoke_test.py --affected` 定向与 `smoke_test.py --architecture` 架构门禁结果见验证记录；覆盖率基线重测见验证记录。
3. **欠账少了吗**：是。T10 包化 **infra/ L1 第二批**：`infra/` 实体由 32 → 39 个。L1 顶层剩余 12 个真实实体（model_pool/model_router/pet_llm/file_cache/app_logging/storage_maintenance/ui_tokens/ui_plugin_registry/api_endpoints/project_settings/pet_state/continuity_ledger 等中高扇出；file_index 顶层已是再导出门面）继续分批；L4/L3 收官项同前轮盘点；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `infra/` 实体 | 7 个低扇出（入度 5–9）顶层 L1 模块 `git mv` 入 `infra/`：integrations、comfy_runtime、native_apps、stage_model_value、model_metering、asset_prompt_rules、diagnostic_capture。 |
| 别名门面 ×7 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = infra.<名>` 别名门面；`import <扁平名> is import infra.<名>` 实体同一性 7/7 校验通过。 |
| 消费方 import | 34 个生产文件改包路径导入（`import infra.X as X`／`from infra.X import` 惯例，含 domain/、orchestrator/、ui/、agent/、contract/ 跨层消费边与顶层互引）；AST 复扫残留 **0 处**（含 infra/ 域内 `model_diagnostics`→`diagnostic_capture` 一条补网）。测试文件维持扁平导入经门面解析，不改。 |
| `__file__` 锚点 ×3 | `infra/comfy_runtime.py` `desktop_settings.json` 侧载、`infra/asset_prompt_rules.py` `asset_manifest.schema.json`、`infra/diagnostic_capture.py` `PROGRAM` 根——均改 `.parents[1]` 锚回程序根（数据文件留顶层，语义不变）。 |
| 批内边 ×3 | `infra/native_apps.py` 三处懒加载 `comfy_runtime`/`integrations` 改 `infra.` 前缀。 |
| 棘轮台账 | `架构统一基数.json`：① `comfy_runtime.py`→`infra/comfy_runtime.py`（第四项路径随包迁移）；② **Python 3.14 ast.dump 漂移全量重对齐**——第四项 63 个 json.loads 锚点摘要按当前解释器实测重算，3 个多调用作用域按行序重建（债务集合不变，disposition/reason 全保留）；`层级` 节 `native_apps` 豁免条目为 stem 口径，迁移后仍命中，未动。 |
| 测试契约同步 ×2 | `test_golden_outputs.py` `_PROGRAM_DIR` 锚改测试自身 `parents[1]`（原取被迁模块 `__file__.parent`，入包后指向 `infra/`）；`test_writing_api_stage_config_boundary.py` 源码断言改包路径写法。断言强度与黄金文件均不变，按 §2.4 记录。 |
| 基线与文档 | `architecture.md` infra 目录行「共 32 个」→「共 39 个」；`PROJECT_MAP.md` 七模块均无独立条目（被「模型与安全」「成本与运行保障」等行覆盖），无需改；`_layers.py` 扁平登记名天然兼容未改；`distribution_manifest.md` glob 已覆盖；`smoke_test.py` 无本批模块源路径检查。 |

## 验证记录

- `smoke_test.py`（默认）：**9/9 通过**。
- `smoke_test.py --affected integrations comfy_runtime native_apps stage_model_value model_metering asset_prompt_rules diagnostic_capture`：冒烟检查项 **9/9**；定向门禁选中 **44 个测试文件**，经隐藏桌面执行——首轮 1 红 `test_golden_outputs.test_asset_stage_rules`（黄金归一锚 `_PROGRAM_DIR` 取 `asset_prompt_rules.__file__.parent`，模块入 infra/ 后父目录变 `infra/`，改锚测试自身 `parents[1]` 程序根，断言与黄金文件不动）；修复后复跑 **144 秒 0 红／ALL TESTS PASSED**，冒烟合计 **10/10 通过**。
- `smoke_test.py --architecture`：首轮 **5 红**，逐项处理后二轮 **483/483 全绿（171.5s）**：
  1. `test_baseline_modules_exist…`＋`test_coverage_tool_runs…`——覆盖率基线未含 7 个新 infra/ 实体，重测刷新 **629 模块／74 覆盖**（97 条目标用例全过）；
  2. `test_round_number_continuous`——状态页轮次头按惯例临时同步 3199（仅 master 提交，本分支不入提交）；
  3. `test_bare_json_load_debt…`——**环境漂移修复**：`运行环境/Python` 于当日 17:50 被替换为 Python 3.14.7，`ast.dump` 输出格式变化使第四项台账全部 63 个 json.loads 锚点摘要漂移（干净 master 检出同测同样红，非本批引入）；按「同值异摘要」口径重对齐——57 个单点条目改摘要、3 个多调用作用域（video_prompt_results.parse_result×3、seedream_api.request_image×2、validate_repo.validate_repository×4）按行序重建条目并保留原 disposition/reason，债务集合不变；
  4. `test_writing_api_reads_stage_model…`——源码字符串断言 `'import stage_model_value'` 不含包前缀，按 §2.4 契约同步改包路径写法（断言强度不变）。
- 覆盖率：`scripts/coverage_report.py` 重测写入 `维护记录/覆盖率基线.json`（97 条目标用例全通过，模块被覆盖 74/629）；`runbook.md` §11 同步（629/74/555）。
- 过程插曲（如实）：首轮批量重写脚本误用 `read_text`/`write_text` 默认换行转换，把约 600 个无关文件（contract/、scripts/、维护记录/ 等）的 CRLF 归一成 LF——`git reset --hard` 全量回滚后按 `newline=''` 双向保留行尾重做，本批实际改动收敛为 41 个文件（7 改名＋7 门面＋34 消费方＋3 锚点/边修复＋台账/基线/文档），diff 已逐文件核验无行尾噪声。

## 观察记录（历史欠账，未扩大范围）

- `tests/architecture/test_migrated_ui_boundaries.py` 的 `test_adapter_imports_are_limited_to_registered_entrypoints` 读 `ROOT/(module+'.py')` 顶层路径：`storyboard_files`/`asset_batch` 早已迁 ui/，读到的是门面，`desktop` 的 `contract.platform_tools` 导入又被 `split('.')[0]` 归为 `'contract'` 跳过——该检查当前**实际为空转**（早于本批存在，非本批引入）。如实记录，是否修复由后续轮次决定。

## 下一步（T10 后续批次）

- infra/ L1 剩余 12 个真实顶层实体继续分批（中扇出优先：model_router 13、continuity_ledger 18、api_endpoints 20、pet_state/project_settings/ui_plugin_registry 22；高扇出枢纽 pet_llm 28、model_pool 46、storage_maintenance 48、app_logging 74、ui_tokens 113、file_cache 116 随批推进或专轮）。
- L4/L3 收官项同前轮：`stage_execution_service`（扇出 50）单独一轮、`writing_api` 随拆分批、`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
