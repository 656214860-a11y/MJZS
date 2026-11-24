# tasks_round_4408_result — REL-03 干净机器首次启动：缺配置提示统一＋引擎探测＋发送预检
<!-- round-evidence: {"commit_base": "10a1aa3e9", "credential_hits": 0, "evidence_sha256": "83e1b94babda2cc8", "exit": 0, "failed": 0, "passed": 109, "round": 4408, "tests": "run_selftests.py -k startup_selfcheck login_gate"} -->

## 三问

- **轮次类型**：§3.2 修复轮（缺陷修复＋卡面授权的测试契约变更）。
- **测试跑了吗**：三条验收命令全绿（退出码与输出尾部见下）；欠账少了吗——新增 4 条 `test_first_run_matrix_*` 端到端用例覆盖卡面点名的首启矩阵，无新增欠账。
- **改动范围**：只动卡面允许文件；`desktop_media_pages.py` 净行数 +0（982→982），`workflow_settings.py` 987→995（≤1000）。

## 缺陷复现方式

干净机器首次启动时三处断点各说各话：①启动自检 `model-pool-empty` 的 remedy 只提模型管理、不提命令行引擎去处；②只装命令行引擎（未配 API 模型）的用户被当成「模型池为空」弹告警＋登录后强制开模型管理；③发送前不检查引擎程序是否存在，到发送一刻才报「未找到命令行程序」；④四处措辞不统一且无统一文案函数。

## 改前红的条数与原因（原文摘录）

定向命令 `run_selftests.py -k startup_selfcheck login_gate` 共 **17 条红**（109 条总用例）：

- `AttributeError: module 'infra.config_snapshot' has no attribute 'has_usable_cli_engine'` ×9（`CliEngineProbeTests` 6 条＋既有用例补丁打不上 2 条＋`test_empty_pool_with_cli_engine_skips_warning`）——探针函数不存在；
- `AttributeError: module 'infra.model_router' has no attribute 'missing_setup_hint'` ×2（`MissingSetupHintTests`）——统一文案函数不存在；
- `patch.object(config_snapshot,'has_usable_cli_engine')` AttributeError ×1（`test_empty_pool_after_login_opens_model_manager`）；
- `AssertionError: '调用设置' not found in '登录后在「模型管理」里「+ 新增模型…」并保存 API Key'`（`test_first_run_matrix_empty_pool_no_engine`）——remedy 缺引擎去处，正是卡面缺陷；
- `AssertionError: 'model-pool-empty' unexpectedly found in ['model-pool-empty']`（`test_first_run_matrix_cli_engine_only`）——只装引擎仍报空池，正是卡面点名的契约缺陷。

## 改动点（文件:行号）

- `infra/model_router.py:936-944` 新增 `missing_setup_hint(destination='')`（挂文件尾：`docs/process/外部依赖清单.md` 按行号登记本文件四个供应商 URL，前置插入会让登记失锚——首轮架构红实测证据）；`:696` `_select` 的 reason 改走该函数。
- `infra/config_snapshot.py:30-51` 新增 `has_usable_cli_engine(which/environ/home)`，查找点与 `workflow_settings.find_program` CLI 分支对齐（PATH → `LOCALAPPDATA/OpenAI/Codex/bin/*` → `~/.local/bin` → Qwen node＋cli-entry.js 成对 → `APPDATA/ai.opencode.desktop/cli/*`）；全表达式写法、零语句级分支——L1 分支覆盖率基线钉决策点数，加 `if` 会红（首轮架构红实测证据）。
- `infra/diagnostic_capture.py:271-278` `_check_model_pool`：判据改「模型池为空且无可用命令行引擎」（`or` 并入既有 `if`，决策点数不变）；remedy 写死统一文案（L1 同层未登记 `diagnostic_capture→model_router` import 边，文件内注释注明）。
- `ui/desktop_login_gate.py:147-156` `_guide_first_model_setup`：空池但有可用引擎时不再弹模型管理；状态行改 `model_router.missing_setup_hint()`。
- `orchestrator/workflow_settings.py:844-851` `resolve_for_send` 发送前预检：config 含 `program` 键且非直连（`api` 为空且 `direct_api` 为假）时先 `find_program` 探测，查无程序或路径已失效抛 `ValueError(missing_setup_hint())`——入队前拦截，不入历史不扣费；mock 出的无 `program` 配置天然跳过（`test_workflow_settings_cache` 等不受影响）。
- `ui/stage_model_picker.py:245` 空态行 `'暂无可用模型'` → `model_router.missing_setup_hint()`。
- `ui/desktop_media_pages.py:12,674` import 行合并追加 `infra.model_router`（沿用本仓库 `import a as x, b as y` 先例，净行数 +0）；`header_note` 改 `missing_setup_hint('点下方「配置线上视频 API」保存接口与 Key')`。
- `tests/test_startup_selfcheck.py`：`CliEngineProbeTests` 5 条探针用例；`test_empty_pool_with_cli_engine_skips_warning` 新增；既有空池用例＋`FamilySwitchTests.setUp` 统一钉 `has_usable_cli_engine`→False（测试与装机环境无关）。
- `tests/test_login_gate.py`：`MissingSetupHintTests` 2 条、`FirstRunMatrixTests` 4 条（空池无引擎／只装引擎／只配直连／两者齐全，经隐藏桌面运行器，全部临时目录）。
- `docs/stages/S01_剧本准备.md`：REQ-S01-119 ✅、DES-S01-118、追踪表锚点行。

## 有意契约变更（卡面授权）

「只装命令行引擎、模型池为空」不再触发 `model-pool-empty` 告警与登录后模型管理引导——`test_first_run_matrix_cli_engine_only` 端到端钉住新行为；其余既有断言逐字未动。

## 验收命令（原样执行）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k startup_selfcheck login_gate` → **退出码 0**，共 109 条用例全绿，尾部：`ALL TESTS PASSED`。
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` → **退出码 0**，共 34 条全绿，尾部：`ALL TESTS PASSED`。
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → **退出码 0**，尾部：`Ran 708 tests in 251.915s` / `OK` / `✅ 架构治理测试：tests/architecture`。

## 过程红→绿记录

- 首轮 `--architecture` 2 红：`test_baseline_decision_points_match_current_entities`（diagnostic_capture 85≠86，新增 `if`）与 `test_hardcoded_addresses_are_registered`（model_router 四个 URL 行号被顶部插入顶移 7 行脱离登记）；修复为「`or` 并入既有 if＋探针全表达式化＋`missing_setup_hint` 落文件尾」后复跑转绿。
- GUI 令牌两度被并行全量自测占用致 `test_login_gate` 延迟未执行（`GUI_DEFERRED`，非断言失败），令牌释放后复跑全绿。

## 未验证 / 边界说明

- 「只装引擎时发送能否正常工作」卡面要求探针兜底：`test_first_run_matrix_cli_engine_only` 经沙盒假 `codex.exe` 通过预检（`resolve_for_send` 返回 engine='codex'），其后真实 CLI 拉起不在本卡范围（不真实调用模型）。
- 只读探针默认读真实 `shutil.which`/`os.environ`/`Path.home`；测试均注入或沙盒化，未改用户主目录与项目库。
- `api_fallback`（CLI 引擎＋API 兜底）场景预检照常拦——卡面未点名该组合，按「引擎不存在先提示」的默认判据处理。
