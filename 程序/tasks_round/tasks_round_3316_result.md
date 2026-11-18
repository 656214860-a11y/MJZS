# R3316 结果：L2领域服务层优化任务书轮8（结构治理轮：结果契约收口）
<!-- round-evidence: {"commit_base": "e008d757", "credential_hits": 0, "evidence_sha256": "9ca8678a094d154e", "exit": 0, "failed": 0, "passed": 196, "round": 3316, "tests": "run_selftests.py -k voice_ai handoff_bundle handoff_service shared_input_voice dialog_voice_input media_page recon white_model"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.3 结构治理轮。任务书轮 8「4 处自造 `{'ok': ...}` 收口为 `ServiceResult`」——类型行注明「4 个模块，分两轮**或申请按缺陷定性**」。本轮按缺陷定性执行：逐点核查后确认 **4 个点名位置中仅 2 个是真正的 L2 服务返回契约缺陷**（`voice_ai.optimize_text`、`handoff_service.verify_manifest`，连同同一边界的编排层薄包装 `stage_handoff_gateways.verify_handoff_bundle` 内两处同型 dict），另 2 个点名位置经定性为**非缺陷**（`recon_service._attempt` 是 L1 `model_pool.tools_*` 传输响应的内部规整形状；`white_model_service.py:262` 是项目索引数据字典＋`'ok'` 状态标签比较的扫描误报）。真缺陷全部收口为 `contract.service_contract.ServiceResult`，误报与 L1 内部形状不硬改、不越界。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 定向自检 `-k recon voice_ai handoff white_model` | **13 个测试文件 / 163 条用例 / 9.8 秒 / 0 红文件 / ALL TESTS PASSED**（覆盖 recon_service 四分片、white_model_ref/workspace/identity、handoff_bundle、handoff_service、voice_ai_optimize、ui_writing_recon、project_rename_reconcile） |
| 定向自检 `-k voice_input shared_input media_pages voice` | **9 个测试文件 / 94 条用例 / 8.7 秒 / 0 红文件 / ALL TESTS PASSED**（覆盖 desktop_voice_input 消费者：test_shared_input_voice 9 条、test_dialog_voice_input 3 条、test_voice_mcp 10 条、test_voice_dict 12 条、test_voice_ai_optimize 9 条等） |
| `smoke_test.py --affected`（voice_ai handoff_service handoff_bundle stage_handoff_gateways desktop_voice_input desktop_media_pages shared_input_voice media_page dialog_voice_input recon white_model） | **绿**：门禁定向 29 个测试文件串行 37 秒 / 0 红文件；冒烟合计 **10/10 通过** |
| 默认冒烟 `smoke_test.py` | **9/9 通过**，exit 0 |
| 架构门禁 `smoke_test.py --architecture` | **502 条 / 219.93s / FAILED（failures=2）**：失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3312 记录的**分支固有红集合逐名一致**（AGENTS.md HEAD 即 16028>16000 字节预算；`project_status.md` 状态页 3259 冻结、仅 master 可提交，本轮对两文件零改动）。本任务书点名的 `test_service_return_contract.py` **9/9 全绿**，含棘轮 `test_only_approved_l2_adopters_import_service_contract` |
| 全量回归 `--all --safe` | **未运行**：本轮非 master 提交点累计触发条件；改动为返回形状收口＋直接消费者同步适配，不触写入边界白名单、Tk 生命周期、删除语义与层级登记表 |

**3. 欠账少了吗？**
减少。任务书点名的「4 处自造 `{'ok': ...}`」中 2 处真缺陷已收口为 `ServiceResult`，`voice_ai` 由豁免转为正式采用方；`架构统一基数.json` adopters 29→**30**、exempt 48→**47**。剩余欠账如实记录：任务书预期的 29→33 不成立（`recon_service`/`handoff_service` 在本轮前已是 adopters，`white_model`/`recon` 两处点名经定性非缺陷），其余 47 个存量欠账模块仍按基数路线图「每轮最多迁移 3 个」另走；轮 9 `tts_api`/`white_model` 两处硬违规、分支固有架构红 2 条待后续轮次。

## 四处点名位置定性与处置

| 位置 | 现值（任务书） | 定性 | 处置 |
| --- | --- | --- | --- |
| `voice_ai.py:63-87` | 自造结果 dict | **真缺陷**：`optimize_text` 是 L2 服务入口，返回 `{'ok','text','reason'}` 平铺 dict | 已收口 `ServiceResult`（见下） |
| `handoff_service.py:136,173` | 自造结果 dict | **真缺陷**：`verify_manifest` 是 L2 校验服务，返回 `{'ok': not problems, 'problems','missing','count','label'}` 混合形状 | 已收口 `ServiceResult`（见下） |
| `recon_service.py:398` | 自造结果 dict | **非缺陷**：`_attempt` 内 `{'ok': False, 'status': 0, 'kind': 'bug', ...}` 是 `model_pool.tools_search/tools_fetch`（L1 传输协议）响应的内部规整；L2 边界 `run()` 与幂等路径 `_cached_success()`（R3282）早已返回 `ServiceResult`/`success(...)`，本轮核验未破坏 | 不改（改了会跨进 L1 传输契约，越出本轮边界） |
| `white_model_service.py:262` | 自造结果 dict | **扫描误报**：`read_project_index` 返回 `{'schema': 1, 'shots': {...}}` 项目索引**数据**字典，本无 `ok` 键；同文件 `'ok'` 字面量是 `evidence_state(...) != 'ok'` 状态标签比较，非结果 dict | 不改 |

另：同一契约边界上的 `orchestrator/stage_handoff_gateways.py::verify_handoff_bundle`（L3 编排对 `verify_manifest` 的薄包装）内有两处同型 `{'ok': False, 'problems': [...], ...}` dict（缺清单、清单损坏），属同一缺陷面的直接延伸，一并收口为 `UserError`，未引入兼容层。

## 改动明细（旧形状 → 新 ServiceResult）

### `domain/voice_ai.py::optimize_text`

| 分支 | 旧 | 新 |
| --- | --- | --- |
| 空输入 | `{'ok': False, 'text': '', 'reason': '没有可优化的文本'}` | `UserError('没有可优化的文本', data={'text': ''})` |
| 模板/提示词不合法 | `{'ok': False, 'text': source, 'reason': problem}` | `UserError(problem, data={'text': source})` |
| chat 调用异常 | `{'ok': False, ..., 'reason': 'AI 优化调用失败（…）'}` | `SystemError(同 reason, data={'text': source})` |
| 返回非 dict / `ok` 假 / 为空 / 过长 | `{'ok': False, ..., 'reason': …}` | `SystemError(同 reason, data={'text': source})` |
| 成功 | `{'ok': True, 'text': cleaned, 'reason': ''}` | `success({'text': cleaned})` |

错误分类按语义：空输入与模板配置是用户可修正的前置条件 → `UserError`；模型调用异常、返回格式/为空/过长属运行环境 → `SystemError`。失败 `data` 一律保留 `{'text': 原文}`，与旧 dict 的 `text` 字段语义一致，UI 回退路径不丢听写原文。模块 docstring 已写明契约。

### `domain/handoff_service.py::verify_manifest`

| 分支 | 旧 | 新 |
| --- | --- | --- |
| manifest 非 dict | `{'ok': False, 'problems': ['交接包清单格式不正确'], 'missing': [], 'count': 0, 'label': ''}` | `UserError('交接包清单格式不正确', data={同报告})` |
| 有 problems | `{'ok': False(=not problems), 'problems', 'missing', 'count', 'label'}` | `UserError('；'.join(problems), data=report)` |
| 无 problems | `{'ok': True, 'problems': [], 'missing', 'count', 'label'}` | `success(report)`，`report={'problems','missing','count','label'}` |

失败分类全用 `UserError`：交接包缺文件/被改/清单损坏是**输入包本身的缺陷**，用户换一份有效包即可修正，非运行环境故障；`reason` 取 problems 拼接，报告四字段原样进 `data`。`missing`（清单声明缺镜，素材包允许）不进 problems、不影响成败——与旧 `ok = not problems` 语义逐点等价。`is_failure` 行为与旧 `ok=False` 一一对应（无 `Cancelled` 路径）。

### `orchestrator/stage_handoff_gateways.py::verify_handoff_bundle`

- 缺 `交接包清单.json` → `UserError(problem, data={'problems':[problem],'missing':[],'count':0,'label':''})`（旧同型 dict）；
- 清单读不出/坏 → 同上 `UserError`；
- 其余透传 `verify_manifest` 的 `ServiceResult`，docstring 注明与 domain 同一契约。

### 消费者适配（无兼容层，直接改访问方式）

- `ui/desktop_voice_input.py::_start_ai_optimize`：worker 内 `optimize_text` 抛异常的兜底从 `{'ok': False, 'text': text, 'reason': …}` dict 改为 `SystemError(str(exc)[:160], data={'text': text})`；轮询改 `result.ok` / `result.reason` / `(result.data or {}).get('text','')`；`tasks.finish(ticket, succeeded=result.ok, error=result.reason or '')`。用户可见文案不变。
- `ui/desktop_media_pages.py::verify_handoff` 的 `done(report)`：改名 `done(result)`，`report.get('label')`→`(result.data or {}).get('label')`，`report.get('ok')`→`result.ok`，失败分支 problems 取自 `data`、兜底 `result.reason`；三条 status 文案逐字保留。
- `stage_execution_service.verify_handoff_bundle` 为 re-export 透传，无需改。
- 测试侧注入的 `chat` 替身（`tests/test_shared_input_voice.py` 等）返回 `{'ok','text'}` dict 是 **L3 `WritingRequestAdapter.chat` 适配器协议**，不是 `optimize_text` 返回，保持不动。

### 测试更新

- `tests/test_voice_ai_optimize.py`：全部 `result['ok']/['text']/['reason']` 断言改 `.ok`/`.data['text']`/`.reason`（期望值不变）；新增 `test_result_uses_service_contract_types` 断言 `ServiceResult` 类型、`UserError`/`SystemError` 分类与 `is_failure`。
- `tests/test_handoff_bundle.py`：`verify_manifest`/`verify_handoff_bundle` 断言改 `.ok`/`.data[...]`（期望值不变，含「声明缺镜不算失败」「越界条目失败」等语义用例）；新增 `test_verify_results_use_service_contract_types`。
- `tests/architecture/test_service_return_contract.py`：硬编码 adopters 集合加入 `voice_ai`（棘轮唯一合法更新方式）。

## 先红证据

按「先改测试断言为 ServiceResult 访问器、再改源码」顺序执行：测试先行改造后跑定向，`voice_ai.optimize_text` 与 `verify_manifest`/`verify_handoff_bundle` 仍返回 dict，集中表现为 `AttributeError: 'dict' object has no attribute 'ok'` 及两条契约类型断言红（`assertIsInstance(..., ServiceResult)` 失败）；源码收口后同一批用例转绿（26 条聚焦用例 OK、架构契约 9 条 OK）。

## 验收对照（任务书轮 8）

- [x] **4 处均改用 `contract.service_contract` 的 `success`/`UserError`/`SystemError`** → 按任务书自带的「申请按缺陷定性」口径：2 处真缺陷（voice_ai、handoff，含同边界编排包装 2 处同型 dict）已全部收口；2 处点名经定性为非 L2 服务返回缺陷（recon L1 传输内部形状、white_model 数据字典/状态标签误报），如实记录不硬改——硬改会破坏 L1 协议或业务数据契约，反而违反「只改这 4 个服务」边界。
- [x] **`tests/architecture/test_service_return_contract.py` 绿** → 9/9，含 adopters 棘轮与 ledger 一致性断言。
- [x] **更新 `维护记录/架构统一基数.json` 的 `adopters` 并同步棘轮** → adopters 29→**30**（仅 `voice_ai` 新增；任务书预估 33 因 recon/handoff 本已是 adopters、white_model/recon 非缺陷而不适用）、exempt 48→**47**、`exempt_count` 同步；架构测试硬编码集合与 ledger 双向一致。
- [x] **`smoke_test.py --architecture` 绿** → 502 条中失败集合与分支固有红 2 条逐名一致、无新增红；点名门禁 `test_service_return_contract` 全绿。（「绿」按本分支既有口径＝无新增失败，分支固有红已在 R3275–R3312 连续记录。）

## 改动清单（10 个文件）

| 文件 | 改动 |
| --- | --- |
| `domain/voice_ai.py` | `optimize_text` 8 个返回点 dict→`UserError`/`SystemError`/`success`；import `contract.service_contract`；docstring 写明契约 |
| `domain/handoff_service.py` | `verify_manifest` 3 个返回点 dict→`UserError`/`success`；import `ServiceResult` 相关符号；docstring 写明契约与 data 报告字段 |
| `orchestrator/stage_handoff_gateways.py` | `verify_handoff_bundle` 缺清单/坏清单两处 dict→`UserError(data=报告)`；透传 `ServiceResult`；docstring 注明契约 |
| `ui/desktop_voice_input.py` | worker 异常兜底 dict→`SystemError`；轮询与 `tasks.finish` 改 `.ok`/`.reason`/`.data` 访问 |
| `ui/desktop_media_pages.py` | `verify_handoff` 的 `done()` 消费 `ServiceResult`（`.ok`/`.reason`/`.data.get`），文案不变 |
| `tests/test_voice_ai_optimize.py` | 断言改 ServiceResult 访问器；新增契约类型用例 1 条 |
| `tests/test_handoff_bundle.py` | 断言改 ServiceResult 访问器；新增契约类型用例 1 条 |
| `tests/architecture/test_service_return_contract.py` | 硬编码 adopters 集合 +`voice_ai`（棘轮同步） |
| `维护记录/架构统一基数.json` | `voice_ai`：exempt_items→adopters；`exempt_count` 48→47 |
| `tasks_round/tasks_round_3316_result.md` | 本文件 |

另由 `dev.py commit` 自动生成 `tasks_round/evidence/R3316.json`（凭据扫描＋定向测试凭据）。

## 实测基线汇总

- 定向自检一：`run_selftests.py -k recon voice_ai handoff white_model` → **13 文件 / 163 用例 / 9.8s / 0 红 / ALL TESTS PASSED**。
- 定向自检二：`run_selftests.py -k voice_input shared_input media_pages voice` → **9 文件 / 94 用例 / 8.7s / 0 红 / ALL TESTS PASSED**。
- 受影响门禁：`smoke_test.py --affected <11 关键词>` → 门禁串行 **29 文件 / 37s / 0 红**；冒烟 **10/10**。
- 默认冒烟：`python -B smoke_test.py` → **9/9**，exit 0。
- 架构门禁：`python -B smoke_test.py --architecture` → **502 条 / 219.93s / failures=2**，失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3312 分支固有红逐名一致；`test_service_return_contract` 9/9 全绿。本轮对 AGENTS.md、project_status.md 零改动。
- 全量回归：`--all --safe` 未运行（理由见三问表）。

## 偏差与说明

1. **4 处点名只收口 2 处**：任务书类型行允许「分两轮或申请按缺陷定性」。`recon_service.py:398` 的 dict 是 `model_pool.tools_*` L1 传输响应规整（`run()`/`_cached_success()` 边界早已是 `ServiceResult`，本轮核验 `_cached_success` 仍返回 `success(...)` 未破坏）；`white_model_service.py:262` 返回 `{'schema':1,'shots':{...}}` 项目索引数据、`'ok'` 仅为 `evidence_state` 状态标签——均非服务返回契约缺陷，强改属越界。编排层 `verify_handoff_bundle` 两处同型 dict 属同一缺陷面直接消费者边界，一并收口。
2. **adopters 30 ≠ 任务书预估 33**：`recon_service`、`handoff_service` 在本轮前已是 adopters（历史迁移轮完成）；`voice_ai` 为唯一新增；`white_model_service`、`recon_service` 两处点名非缺陷不产生新 adopters。exempt 48→47 与 adopters 29→30 为实际扫描读数，棘轮（架构测试＋ledger）已按实际值同步。
3. **`verify_manifest` 失败分类全用 `UserError`**：包内文件缺失/改动、清单损坏都是「换一份有效交接包即可修正」的用户可修输入问题；无运行环境类失败分支，故无 `SystemError`。`missing` 声明缺镜不算失败的原语义保留。
4. **`voice_ai` 失败 data 保留 `{'text': 原文}`**：与旧 dict 的 `text` 字段等价，UI 在 `result.ok=False` 时经 `_say(result.reason)` 提示、原文仍在输入框，不丢听写内容。
5. **注入 `chat` 的 dict 协议不动**：`WritingRequestAdapter.chat` 返回 `{'ok','text',...}` 是 L3 写作网关适配器协议（`optimize_text` docstring 明示），与 L2 服务返回契约是两层不同形状；`test_shared_input_voice` 等替身 dict 保持原样，94 条相关用例全绿佐证。
6. **未动外来文件**：`tasks_round/L2领域服务层优化任务书.md`（外来勘误改动）、R3276 外来未跟踪三件（诊断报告/结果文件/任务书）、`project_status.md`（仅 master 可提交）一律不入暂存区。
7. **`--all --safe` 未跑**：非 master 提交点累计触发条件未达；改动为返回形状收口与直接消费者适配。

## 遗留欠账

- 任务书轮 9（`tts_api` 走 `http_client.request_json`、`white_model` 去 `D:/E:` 盘符硬编码）——后续轮次，本任务书尚未闭环。
- `架构统一基数.json` 其余 47 个 exempt 存量模块按「每轮最多迁移 3 个 service」路线图另走。
- 分支固有架构红 2 条（AGENTS.md 字节预算、状态页轮次冻结）——存量问题，与本轮无关，待 master 合并轮处理。
- 全量 `--all --safe` 未跑；若验收要求对最终树补跑可另行执行。
- 全部轮次收尾后输出 `tasks_round/任务完成/L2领域服务层优化·任务完成.md`（任务书 §7.2），本轮非末轮（轮 9 未完成）不产出。

## 提交

- 分支 `codex/wip-r3282`（领号 R3316，工作树 `dsh-864fd932-4054`；领号记录见 `<git common-dir>/round-claims.json`）。
- 主提交：`e008d757`（11 个文件：5 个生产文件——domain/voice_ai.py、domain/handoff_service.py、orchestrator/stage_handoff_gateways.py、ui/desktop_voice_input.py、ui/desktop_media_pages.py；3 个测试/架构文件——tests/test_voice_ai_optimize.py、tests/test_handoff_bundle.py、tests/architecture/test_service_return_contract.py；维护记录/架构统一基数.json；本结果文件；自动生成的 tasks_round/evidence/R3316.json）。
- 结果文件补记提交：本提交（`R3316: 补记结果文件commit哈希e008d757`；docs-only 补记同样带 `--tests` 重跑定向测试刷新证据）。
- 轮次证据以 `tasks_round/evidence/R3316.json` 为准（`run_selftests.py -k voice_ai handoff_bundle handoff_service shared_input_voice dialog_voice_input media_page recon white_model` exit 0 / **196 通过 / 0 失败**，凭据扫描 0 命中）。
