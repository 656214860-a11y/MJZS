# R1610 编码/实现阶段质量评估（只读诊断）

本轮属于 §3.5 只读诊断轮：未改任何 `.py`，未改用户数据，仅新增本结果文件与随后同步的轮次头。
测试：按 §5 只读诊断默认不跑测试；本轮未运行测试，也未重跑全量。基线引用 R1605/e59e513（5346 项）与 R1606–R1609 各轮门禁记录，均为历史凭据，不代表本树实测。
欠账：本轮不改源码，`project_status.md` 全量欠账计数不变。

基线：master a72aed4。日期：2026-10-16。

## A 结论

实现质量整体高于同规模个人项目：有自建 AST 架构门禁 109 个测试文件、5359 个用例、统一 `service_contract` 四字段返回、分层/路径/删除/JSON-IO/密钥边界收口、13 阶段发布事务。**不是**需要重建的项目。

本轮确认的缺口集中在**工程化环节**（静态检查、类型检查、覆盖率度量、函数复杂度、机器可判定的出口脚本），而不是业务流程实现。另有两处真实静态缺陷（无效转义序列），以及若干契约文档与依赖分账缺口。

## B 证据与范围

读取：`程序/AGENTS.md`、`project_status.md`、`architecture.md`、`PROJECT_MAP.md`、`说明/生成服务失败处理契约.md`、`维护记录/`（缺陷台账、覆盖率判据、TODO 快照、架构统一基数、测试分层基线、优化待办队列）；只读扫描 `程序/*.py`（AST 行数/复杂度、导入、编译告警）、`tests/`、根目录 CI 脚本。
未做：不改 `.py`、不跑测试、不实机、不联网。局限见 L。

## C 代码规范 / 静态检查 / 类型检查 / 复杂度

**已有**：`tests/architecture/` 109 个文件构成自建静态门禁（分层 `test_layers`、循环 `test_no_circular_import`、路径 `test_path_authority`、删除 `test_remove_authority`、JSON-IO `test_json_io_boundary`、密钥 `test_secret_sink_audit`、模块行数 `test_module_size_ratchet`、静默异常 `test_silent_exception_ratchet`、TODO 快照、统一基数棘轮）。生产裸 `except:` 为 0 处，`except Exception: pass` 收敛到 4 个登记文件且只许下降。

- **Q1（B）无格式化／lint／类型检查**：仓库无 `pyproject.toml`／`ruff.toml`／`.flake8`／`mypy.ini`／`.pre-commit-config.yaml`，CI 脚本只跑 smoke 与 unittest，无静态分析步骤。类型提示近乎未用：仅 4 个文件 `import typing`、9 个文件有返回注解。证据：`scripts/local_ci.py` 三个步骤全为运行测试。
- **Q2（B）函数级复杂度无门禁**：`test_module_size_ratchet` 只限文件行数，不限函数。AST 扫描：5040 个函数中 43 个 ≥100 行、14 个 ≥200 行，最长 `keyframe_comfy.py:253 show` 626 行，其次 `desktop_writing_page.py:30 writing` 577 行、`pet_models_ui.py:310 open_manager` 497 行。证据：本轮 AST 统计（只读）。
- **Q3（C）真实静态缺陷：无效转义序列 2 处**：`tests/test_dev_entry.py:23`（`"\d"`）、`skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239`（`"\["`）。当前为 SyntaxWarning，未来 Python 将报 SyntaxError。这类问题正是 lint 门禁应捕获的；随附解释器为 **3.15.0a2**（alpha），升级/判废时间线不确定。

## D 接口契约稳定性（UI↔服务、AI 服务、任务队列）

**已有**：`service_contract` 四字段（`ok/reason/recoverable/data`）＋ `UserError/SystemError/Cancelled` 分类，`test_service_return_contract` 与统一棘轮守护；AI 侧有 `说明/生成服务失败处理契约.md`（acceptance/reason_code/retryable 判定表）；任务队列有 `test_persistent_task_queue`、`test_claim_queue_gateway`、`RetryRegistry`。

- **Q4（B）持久化产物无 schema／版本字段与迁移守卫**：`assets.json`、`continuity_ledger.json`、`animatic_manifest.json`、批次台账、任务队列、`skill_config.json` 等正式 JSON 未见统一 `schema_version` 或校验/迁移入口；`file_cache`／`script_contract`／`asset_contract`／`stage_layout` 无 schema 常量。格式演进依赖“旧数据可读”的隐含约定，无显式版本闸。
- **Q5（B）AI“未受理”判定依赖适配器自觉**：契约文档明确“只有适配器能证明未受理才可传 `accepted=false`”，但未见逐适配器一致性测试固定其上报形状。适配器至少含 `qwen_adapter`、`volcengine`、`comfy_service`、`cloud_video`、`cloud_assets`、`native_assets`。若某适配器把 5xx 误报为已受理或反之，直接影响是否重提付费请求。
- 说明（澄清前提）：本产品是**单进程 Tkinter 桌面应用**，不存在传统“前后端”接口；此处“契约”映射为 UI 层↔L2/L3 服务返回形状与持久化产物格式，二者均有门禁。

## E 单元测试（时间线 / 状态机 / 计费 / 权限）

**已有**：5359 个测试函数、311 个测试文件。时间线 `test_animatic_timeline`；状态机 `test_lifecycle`、`test_keyframe_lifecycle_service`、`test_video_lifecycle_service`、`test_cancellation_status`、`test_pet_state`；计费 `test_request_ledger`、`test_usage_overview`、`test_writing_api_output_budget`、`test_idea_attachment_budgets`；队列/期限 `test_persistent_task_queue`、`test_execution_deadline`。

- **Q6（B）计费/金额算术缺不变量测试**：未见针对“分项求和=总额、不出现负额、币种隔离、四舍五入边界”的 property/表驱动用例；现有为场景型断言。
- **Q7（B）无行/分支覆盖率度量**：仓库无 coverage 工具与阈值；`测试分层基线.json` 只记 architecture/unit 计数与耗时，不记覆盖率。“覆盖核心路径”目前只能凭“对应用例存在”推断，个别逻辑被改动而用例未覆盖时不可见。
- **Q8（B）状态机缺全转移表测试**：生命周期测试为场景式，未以表枚举“允许/禁止转移 + 每个状态至少被覆盖一次”。
- 说明（澄清前提）：本应用无多用户“权限/角色”模型——单用户桌面工具，最接近“权限”的是阶段**制作锁/门禁**（`master_skill.gate`、`stage_handler_registry`）与并发**许可**（`stage_parallel` 许可，已有 `test_stage_parallel`）。把它当“权限系统”评估会有错误前提。

## F Code Review / 可维护性

- **Q9（B）大模块与日志面混用**：`module_size_ratchet` 上限仍保留 5 个大文件——`desktop.py` 2259、`pet_cloud.py` 2137、`skill_panel.py` 1886、`stage_execution_service.py` 1677、`script_contract.py` 1598 行。生产根目录 `print(` 606 处，与既有 `app_logging` 并存，运行期诊断口径不统一。
- 单人项目、**无 git 远端**、无 PR/第二评审；以 §4.2 自审清单与自动化门禁替代人工 CR。优点是门禁强；残余风险是单人盲区与“门禁没覆盖的语义错误无人复核”。

## G 文档

**已有且较强**：`architecture.md`、`PROJECT_MAP.md`、`AGENTS.md`、`README.md`、`配置说明.md`、`ui_components.md`、`design_tokens.md`、`distribution_manifest.md`；`说明/` 含产品需求与验收矩阵、失败处理契约、每分钟成本、金额预算、交付资料、维护约定、实际使用待验收清单。

- **Q11（C）文档缺口**：(a) 无单一“数据模型／字段字典”逐产物清单；(b) 任务状态与尝试链（R1604/O11 的 `run_id/attempt_id/provider_task_id/耗时/原因码`）无面向读者的状态说明；(c) 部署说明散在 README／使用说明／distribution_manifest，无单一 runbook；(d) 内部服务契约以 docstring 为准，无集中 API 参考。

## H 出口标准 / CI / 安全

- **Q10（B）CI 为本地脚本、无可判定统一出口**：无 `.github/`、无远端；出口标准靠人工 `本地CI.cmd`（`scripts/local_ci.py`：默认冒烟＋安全全量）。全量约 615 秒／5346 项，反馈慢；`FULL_STEPS` 跳过增量门禁。无覆盖率阈值、无 lint/type 步骤，“CI 通过”非机器强制。
- **Q12（C）依赖与运行时边界未分账**：`skills/**` 与 `agent/optimizer_mcp_bridge.py` 引用 `PIL`／`openai`／`matplotlib`／`bpy`／`mathutils`／`mcp` 等第三方；主运行时核心为纯标准库（优点）。这些辅助依赖未与运行时分账，随附解释器为 **3.15.0a2**（alpha）。
- 安全面：生产无 `shell=True`、无 `pickle.load`、无裸 `except`；密钥走 DPAPI＋`test_secret_sink_audit`＋`密钥流审计`。**无 SAST/依赖漏洞扫描**，但攻击面小（本地、零运行时第三方依赖），不构成“已证明无高危漏洞”，只能说风险面有限。

## J 整改路线（待确认，不自动执行）

按“先低风险高收益、后可维护性”排序，均为独立轮，互不为前置：

1. **第一批（低成本、立即可验）**
   - Q3 修 2 处无效转义序列（纯修复轮）。
   - Q1 引入**零运行时依赖的静态门禁**：用标准库 `ast`/`tokenize` 新增 `tests/architecture/test_static_hygiene.py`（无效转义序列、未用导入、可疑裸 `print` 计数、`typing` 缺失登记），先冻结基线只许下降；如需 ruff/mypy，须明确仅开发期、不进分发包（待用户裁决是否允许开发期第三方工具）。
   - Q10 增加一条 `scripts/exit_gate.py`（或复用 `local_ci.py`）：串起 静态门禁＋架构门禁＋默认冒烟，非 0 即失败，作为机器可判定的“CI 通过”出口。
2. **第二批（契约与测试加强）**
   - Q2 新增函数行数棘轮（登记 ≥150 行的函数，只许下降），并拆解 `keyframe_comfy.show` 等最长函数。
   - Q4 为正式 JSON 产物加 `schema_version` ＋ 校验/迁移入口，并加“每个写入器都写版本”的边界测试。
   - Q5 每适配器加失败分类一致性测试（假传输固定 429/5xx/超时/鉴权形状 → 断言 `failure_policy` 输出）。
   - Q6/Q8 补金额不变量与生命周期转移表测试。
3. **第三批（度量与文档）**
   - Q7 引入覆盖率度量（若允许开发期工具则 coverage；否则以模块级“被测试引用”静态台账近似），先记基线不设硬阈值，再对核心模块（计费、状态机、发布、队列）设阈值。
   - Q9 继续拆 5 个大文件；统一运行期诊断到 `app_logging`（保留 CLI 必要 print）。
   - Q11 补数据模型字段字典、任务状态说明、部署 runbook。
   - Q12 登记辅助依赖清单与解释器版本策略（alpha → 稳定版迁移计划）。

## K 测试迁移/补充计划

不迁移、不删除现有测试。确认后：Q1/Q3 加静态门禁用例（可检出无效转义序列与未用导入）；Q4 加 schema 版本边界用例；Q5 加逐适配器失败分类用例（假传输，不联网）；Q6 加金额不变量表驱动用例；Q8 加生命周期转移表；Q2 加函数行数棘轮。先跑受影响用例，正式修改按 §5 走对应门禁；本轮只读诊断不跑测试。

## L 风险与限制

本轮为源码只读扫描与既有文档复核，未运行任何测试、未做故障注入、未实机、未联网、未核真实账单。函数复杂度与 print 计数为启发式静态统计，不含运行期权重；“无覆盖率度量”是能力缺失判断，不代表核心路径一定未覆盖。第三方依赖扫描基于 AST 顶层导入，可能漏掉运行期动态导入（已知 `ui_plugin_registry`／`stage_handler_registry` 为受控动态导入）。不得把建议当已实施，也不得把未检索到等同全仓不存在。

## M 完成状态

只读诊断完成（六维度＋清单）。未改产品代码、测试、配置、用户数据与既有结果文件；仅新增本报告并同步轮次头。下一步由用户确认 J 中各条目后再立执行轮。