# R3320 结果：L2领域服务层优化任务书轮9（修复轮：两处硬违规）
<!-- round-evidence: {"commit_base": "1f752e0b", "credential_hits": 0, "evidence_sha256": "c57e0972fcce2dbe", "exit": 0, "failed": 0, "passed": 170, "round": 3320, "tests": "run_selftests.py -k tts http_client white_model blender request_recording http_boundary"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.2 修复轮。任务书轮 9「两处硬违规」：`tts_api.py` 绕过 `http_client` 直连（违反规则 42 出站请求唯一入口）、`white_model_service.py` 内置 `D:/`、`E:/` 盘符兜底（违反规则 12 路径唯一权威）。本轮只改根因所在模块与直接测试，不扩张范围。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 定向自检 `run_selftests.py -k tts http_client white_model blender request_recording http_boundary` | **11 个测试模块 / 170 条用例 / 3.8 秒 / 0 红文件 / ALL TESTS PASSED**（含 architecture.test_http_boundary 2 条、architecture.test_tts_publication_boundary 3 条、test_tts 14+ 条、test_http_client 全部新旧用例、test_request_recording 11 条、test_white_model_* 三件） |
| `smoke_test.py --affected tts_api white_model_service http_client tts white_model request_recording http_boundary` | **绿**：门禁定向 **27 个测试模块串行 580 秒 / 0 红文件 / ALL TESTS PASSED**；冒烟合计 **10/10 通过**（关键词在任务书点名两项基础上按 `_affected_test_plan` 实测补齐——仅 `tts_api white_model_service` 会漏掉 test_tts／test_request_recording／architecture.test_http_boundary，见「偏差与说明」2） |
| 任务书点名补充：`tests/architecture/test_atomic_write_boundary.py` | **6/6 OK**（单独补跑，任务书验收点名项） |
| 默认冒烟 `smoke_test.py` | **9/9 通过**，exit 0 |
| 架构门禁 `smoke_test.py --architecture` | **502 条 / 241.37s / FAILED（failures=2）**：失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3316 记录的**分支固有红集合逐名一致**（AGENTS.md HEAD 即 16028>16000 字节预算；`project_status.md` 状态页 3259 冻结、仅 master 可提交，本轮对两文件零改动）。本轮点名门禁 `test_http_boundary`（2 条）、`test_atomic_write_boundary`（6 条）、`test_branch_coverage_floor` 全部通过，无新增红 |
| 全量回归 `--all --safe` | **未运行**：本轮非 master 提交点累计触发条件；改动为传输收口＋常量目录探测，无写入边界、Tk 生命周期、删除语义与层级登记表变更 |

**3. 欠账少了吗？**
减少。任务书两处 P0 硬违规全部消除：`domain/tts_api.py` 对 `urlopen`／`build_opener`／`urllib.request` 的引用清零（架构白名单条目同步删除），`white_model_service.py` 的 `D:/`、`E:/` 盘符候选删除。**至此任务书轮 1–9 全部实现轮执行完毕**，剩余欠账仅：合入 master、按规则 35 产出 `tasks_round/任务完成/`《任务完成文件》、分支固有架构红 2 条（存量，待 master 合并轮处理）。

## 修复内容

### 1. `tts_api` 收口 `http_client`（规则 42）

任务书原文写「改为走 `http_client.request_json()`」，但 TTS 响应是**二进制音频**——`request_json()` 会对响应体做 UTF-8 解码并尝试 JSON 解析，非 UTF-8 字节流（mp3/wav 头含大量非法序列）会被 `errors='replace'` 损坏，无法满足「返回原始音频 bytes」契约。因此本轮在 `infra/http_client.py` 内抽出共用传输内核并新增二进制入口（详见「request_bytes 设计说明」），`tts_api` 经统一边界发出站请求——规则 42 的实质（超时必填、错误码、有界重试、响应上限、凭据脱敏、熔断）全部生效。

- `domain/tts_api.py:510` `synthesize()`：删除函数内 `from urllib.request import Request, build_opener` 与 `build_opener(no_redirect()).open(request, timeout=120)` 直连；改为函数内 `import infra.http_client as http_client`（保持「HTTP 栈按需加载」意图，与 volcengine/wan 等既有按需 import 先例一致）后调 `http_client.request_bytes('POST', <base>/audio/speech, headers={Authorization, Content-Type}, payload=body, timeout=120, max_bytes=TTS_AUDIO_MAX_BYTES)`（`:535`）。请求 URL、JSON body（`payload()` 产物不变）、Authorization、Content-Type、timeout=120 逐点等价；新增 `TTS_AUDIO_MAX_BYTES = 64 MiB`（`:20`）给有界读取一个明确上限——旧实现 `response.read()` 无上限。
- 顶层同步删除 `import infra.app_logging`（仅旧错误分支 `swallowed()` 使用）与 `from infra.api_endpoints import no_redirect`（重定向安全改由 `RequestsJsonOpener` 承担，见下）。`from urllib.parse import urlparse`、`from contract.error_codes import code_of`、`from contract.project_context import ProjectContext` 保留。
- `RequestLedger.metered_units` 计量包裹位置不变（`with meter:` 内发请求），任务书 §风险表要求的「L1 轮 1 落地后 4 处 `RequestLedger` 消费方核验」由 `tests/test_request_recording.py` 覆盖：预算拒绝时 `RequestsJsonOpener.open` 零调用、传输超时记 `money_state='unknown'`/`budget_cost='0.2'` 结算语义不变（11 条用例全绿）。

### 2. `white_model_service` 去盘符硬编码（规则 12）

`domain/white_model_service.py:440` `blender_candidates()`：删除 `choices.extend([Path('D:/Blender/blender.exe'), Path('E:/Blender/blender.exe')])`。候选顺序保持为 **配置（`BLENDER_ENV` 环境变量 → settings['blender']）→ `shutil.which('blender')`（PATH）→ `ProgramFiles`/`ProgramFiles(x86)` 下 `Blender Foundation/*/blender.exe` glob**，只读发现语义不变；`:449` 注释留痕规则 12。`ProgramFiles` 缺失时仍回退 `C:/Program Files` 默认值（环境变量缺省兜底，非盘符硬编码候选）。

## request_bytes 设计说明

`infra/http_client.py` 重构为三层：

| 层 | 位置 | 职责 |
| --- | --- | --- |
| `_request()` | `:78` | 共用出站内核：超时必填、`payload` JSON 序列化并强制 POST、`retries`/`retry_statuses`/`max_bytes`/`allow_retry_post`/`opener`/`sleep` 可选项、有界重试（POST 默认不重试，`allow_retry_post=True` 放行）、`_read_limited` 响应上限、`_classify` 错误码分类、`_safe_headers` 凭据脱敏、`_circuit_*` 熔断、HTTPError 读 64KB 错误体。成功返回 `success({'status', 'body': bytes, 'headers'})`；`caller` 形参仅用于未知关键字 `TypeError` 文案（`request_json()`/`request_bytes()` 各自署名）。 |
| `request_json()` | `:169` | 签名 `request_json(method, url, *, headers=None, payload=None, timeout, **opts)` **逐字不变**；先 `setdefault('Content-Type', 'application/json')`（含无 payload 的 GET，与旧行为一致）再调 `_request`，成功后把 `body` bytes 做 UTF-8/`errors='replace'` 解码＋`json.loads`（失败为 `None`），产出 `{'status','json','text','headers'}`——旧返回形状逐键保留。 |
| `request_bytes()` | `:194` | 新增；同签名同 `**opts`；仅当 `payload is not None` 时才 `setdefault` JSON Content-Type（GET 不谎称 JSON）；成功 `data` 为 `{'status','body': bytes,'headers'}`，**不做文本解码、不加 `text`/`json` 键**——二进制音频等响应的唯一合规通道。 |

行为保持核验：`request_json` 的重试/熔断/上限/脱敏路径原样下沉到 `_request`，既有 `tests/test_http_client.py` 全部用例未改断言即通过；新增 `RequestBytesTests`（`:140`）7 条＋`RequestsTransportTests` 2 条覆盖：字节原样返回且无 `text`/`json` 键、payload 强制 POST＋JSON 序列化＋Content-Type/Authorization 透传、POST 默认不重试、429→`E-NET-RATE-LIMIT` 且 `error_body` 保留、timeout/unreachable 分类、`max_bytes` 超限拒绝、熔断在两入口间共享、`timeout` 必填 TypeError。

## 重定向与凭据安全验证

- 旧实现：`build_opener(no_redirect()).open(...)`——`infra.api_endpoints.no_redirect` 自建 opener 不跟随重定向。
- 新实现：`http_client._default_opener()` 返回 `contract.platform_tools.RequestsJsonOpener`，其 `open()`（`platform_tools.py:584`）用 `session.get_adapter(url).send(...)` **绕过 `Session.send`/`resolve_redirects`**，注释明示「Session.send builds _next even with redirects disabled」——`HTTPAdapter.send` 本身不跟随 3xx，302/301 直接以 `status_code` 返回，`RequestsJsonOpener` 对非 2xx 抛 `urllib.error.HTTPError` → `_classify` 归 `E-NET-CLIENT` 且 `status` 保留 → `synthesize` 抛 `ValueError("TTS 请求失败（HTTP 302）：…")`，与旧 `no_redirect` 语义等价。
- 凭据：因重定向根本不被跟随，`Authorization: Bearer` 头不存在转发到第三方域的路径；`_safe_headers` 另对响应侧 `authorization`/`cookie` 等脱敏。
- 测试佐证：`test_tts.py` 的 `_synthesize_patches` 额外 patch `urllib.request.build_opener` 为 `AssertionError` 守卫——TTS 一旦自建 opener 立即红；`test_http_client.RequestsTransportTests` 走真 `ThreadingHTTPServer` 验证 `/audio` 返回含非法 UTF-8 字节的二进制体被 `request_bytes` 原样取回（`b'\x00\xff\xfe\x89PNG-audio-bytes'` 逐字节相等）。

## 错误分类对照（直连时代 → http_client 时代）

| 场景 | 旧行为 | 新行为 | 一致性 |
| --- | --- | --- | --- |
| HTTP 错误状态（4xx/5xx/3xx） | `HTTPError` → `ValueError(f"TTS 请求失败（HTTP {exc.code}）：{detail≤400}")` | `ServiceResult(!ok, data.status=code, data.error_body≤64KB)` → `ValueError(f"TTS 请求失败（HTTP {status}）：{detail[:400]}")` | ✅ 异常类型与文案逐字一致（新用例 `test_synthesize_http_error_keeps_legacy_wording` 断言 500＋body 全等） |
| 2xx 空 body | `ValueError("TTS 未返回音频")` | `result.ok` 且 `body` 为空 → 同文案 `ValueError` | ✅ 新用例 `test_synthesize_empty_audio_rejected` |
| 2xx 有 body | 返回 `raw` bytes | 返回 `data['body']` bytes | ✅ 新用例断言 `b"FAKEAUDIO"` |
| 超时 | `TimeoutError`（urllib 抛出原样） | `_request` 归 `E-NET-TIMEOUT` → `TimeoutError(detail)` | ✅ 同异常类型（消息文本为归类后摘要，非逐字契约） |
| 连不上/其他传输错 | `urllib.error.URLError` | `E-NET-UNREACHABLE` 等 → `urllib.error.URLError(detail)` | ✅ 同异常类型 |
| 响应超 `max_bytes` | 无上限，`read()` 全量返回 | `E-NET-CLIENT`＋`status`＋`error_body='响应体超过上限'` → `ValueError("TTS 请求失败（HTTP <status>）：响应体超过上限")` | ⚠️ 新增上界（64 MiB）：超大音频从「放行」变「拒绝」，属有界读取的预期收紧，文本 ≤4000 字场景不可达 |
| 熔断/重试 | 无（直连单次） | 继承 `http_client` 统一策略：POST 默认不重试（计费安全）、同 host 连续失败熔断 30s | ✅ 规则 42 语义，TTS 单次计费请求不被重放 |

## 测试更新明细

- `tests/test_http_client.py`：新增 `RequestBytesTests` 7 条＋`RequestsTransportTests` 内 `/audio` 端点与 2 条真服务器用例（`:140`、`:398`、`:406`）；既有 `RequestJsonTests` 断言零改动全绿。
- `tests/test_tts.py`：fake opener 迁到 `infra.http_client._default_opener` 视角（`_AudioOpener`/`_AudioResponse`/`_synthesize_patches`，`:26-72`）；新增 HTTP 错误文案、空音频、timeout/URLError 三条错误映射用例；`urllib.request.build_opener` 守卫防回归；既有请求体/voice override 断言保留并加 header/timeout 断言。
- `tests/test_request_recording.py`：两处 `patch('urllib.request.build_opener')` 改 `patch.object(platform_tools.RequestsJsonOpener, 'open')`——预算拒绝断言 `open` 零调用、超时断言 `open.call_count==1` 与台账 `money_state`/`budget_cost` 不变（`:159-186`）。
- `tests/test_white_model_workspace.py`：删 `test_legacy_drives_stay_in_the_candidate_list`，新增 `test_candidates_have_no_fixed_drive_letter_fallbacks`（`:137`）、`test_path_discovery_finds_blender_without_drive_letters`（`:149`）、`test_program_files_discovery_finds_blender_without_drive_letters`（`:158`）——后两条即任务书「Blender 不在 D/E 盘仍能被探测到」用例（PATH 与 Program Files 两条真实探测路径，临时目录造 exe）。
- `tests/architecture/test_http_boundary.py`：`ALLOWED` 移除 `'domain/tts_api.py'`（`:17` 起），直连白名单只减不增；`test_http_boundary` 2 条用例绿，扫描确认 `domain/` 下已无 urlopen/build_opener 调用点。

## 先红证据

按「先改测试、再改源码」顺序执行：测试改造完成后跑定向，旧实现下集中红 **8 条**——5 条 TTS 用例被 `build_opener` 守卫判红（TTS 仍自建 opener）、2 条 Blender 用例因 `D:/`、`E:/` 仍在候选列表而红、1 条 `architecture.test_http_boundary` 因 `domain/tts_api.py` 仍含直连调用而红；源码收口后同一批用例转绿（170 条定向用例 0 红）。

## 验收对照（任务书轮 9）

- [x] **`tests/architecture/test_http_boundary.py` 绿（`tts_api` 不再直连）** → 2/2 OK；`ALLOWED` 已删 `domain/tts_api.py`，`domain/tts_api.py` 内 `urlopen`/`build_opener`/`urllib.request` 引用为零。
- [x] **`tests/architecture/test_atomic_write_boundary.py` 绿** → 6/6 OK（单独补跑）。
- [x] **用例：Blender 不在 D/E 盘时仍能被探测到** → `test_path_discovery_finds_blender_without_drive_letters`、`test_program_files_discovery_finds_blender_without_drive_letters` 绿；候选断言显式 `assertNotIn D:/E:`。
- [x] **用例：`tts_api` 走 `http_client` 且错误码与改前一致** → 出站统一 `request_bytes`；错误分类对照表见上，HTTP 文案/空音频/TimeoutError/URLError 四类用例逐点等价断言。
- [x] **`smoke_test.py --affected` 绿** → 27 模块门禁串行 580s 0 红＋冒烟 10/10（关键词按实测补齐，见偏差 2）。

## 改动清单（10 个文件＋自动证据）

| 文件 | 改动 |
| --- | --- |
| `domain/tts_api.py` | `synthesize()` 直连→`http_client.request_bytes`；删 `build_opener`/`no_redirect`/`app_logging` 引用；新增 `TTS_AUDIO_MAX_BYTES`；错误映射对齐旧分类 |
| `infra/http_client.py` | 抽 `_request()` 共用内核；新增 `request_bytes()`；`request_json()` 签名与返回形状不变（JSON 解码上移到包装层） |
| `domain/white_model_service.py` | `blender_candidates()` 删 `D:/`、`E:/` 盘符兜底，注释留痕规则 12 |
| `tests/test_http_client.py` | `RequestBytesTests` 7 条＋真服务器 `/audio` 二进制 2 条 |
| `tests/test_tts.py` | mock 目标迁 `_default_opener`；`build_opener` 守卫；新增 3 条错误映射用例 |
| `tests/test_request_recording.py` | mock 目标迁 `RequestsJsonOpener.open`；预算/超时/台账断言不变 |
| `tests/test_white_model_workspace.py` | 删盘符用例，新增 3 条无盘符探测用例 |
| `tests/architecture/test_http_boundary.py` | `ALLOWED` 移除 `domain/tts_api.py` |
| `维护记录/分支覆盖率基线.json` | `scripts/branch_coverage_report.py` 重测刷新（见偏差 3） |
| `tasks_round/tasks_round_3320_result.md` | 本文件 |

另由 `dev.py commit` 自动生成 `tasks_round/evidence/R3320.json`（凭据扫描＋定向测试凭据）。

## 实测基线汇总

- 定向自检：`run_selftests.py -k tts http_client white_model blender request_recording http_boundary` → **11 模块 / 170 用例 / 3.8s / 0 红 / ALL TESTS PASSED**。
- 点名补充：`tests.architecture.test_atomic_write_boundary` → **6/6 OK**。
- 受影响门禁：`smoke_test.py --affected <7 关键词>` → 门禁串行 **27 模块 / 580s / 0 红**；冒烟 **10/10**。
- 默认冒烟：`python -B smoke_test.py` → **9/9**，exit 0。
- 架构门禁：`python -B smoke_test.py --architecture` → **502 条 / 241.37s / failures=2**，失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3316 分支固有红逐名一致；`test_http_boundary`/`test_atomic_write_boundary`/`test_branch_coverage_floor` 全绿。本轮对 AGENTS.md、project_status.md 零改动。
- 全量回归：`--all --safe` 未运行（理由见三问表）。

## 偏差与说明

1. **`request_bytes` 替代任务书字面的 `request_json()`**：任务书验收实质是「出站走 http_client 统一边界、错误分类一致」。`request_json()` 对响应体强制 UTF-8 解码＋JSON 解析，二进制音频会被破坏且丢失 `bytes` 契约；故新增 `request_bytes()` 与 `request_json()` 共用 `_request` 内核，`request_json` 签名/行为零变化。规则 42 的全部保障（超时必填、错误码、有界重试、响应上限、脱敏、熔断）对两入口同等生效。
2. **`--affected` 关键词按实测补齐**：任务书写 `--affected tts_api white_model_service`，但 `_affected_test_plan` 实测该组合只选中 19 个模块且**漏掉 test_tts、test_request_recording、architecture.test_http_boundary**（`tts_api` 不是任何测试文件名子串、测试经 `from domain import tts_api` 导入使顶层名为 `domain`）；本轮用 `tts_api white_model_service http_client tts white_model request_recording http_boundary` 并集实测选中 **27 个模块**，是任务书意图（覆盖全部受影响消费者）的严格超集。
3. **`分支覆盖率基线.json` 随本轮刷新**：`_request` 抽取使 `http_client.py` 决策点 17→19，`test_baseline_decision_points_match_current_entities` 强制基线与当前 AST 一致，故必须重跑 `scripts/branch_coverage_report.py`（82 个目标用例全过、`tests_ok=true`）。重测顺带吸收两处与本改动无关的覆盖读数漂移：`unit_of_work.py` covered 19→20（40.8%，下限 32.0）、`file_index.py` covered 72→71（79.8%，下限 78.0）——模块集合 87 个与 targets 82 个前后一致，均为棘轮下限之上。
4. **64 MiB 音频上界是新增行为**：旧 `response.read()` 无上限；新 `max_bytes=TTS_AUDIO_MAX_BYTES` 超限走 `E-NET-CLIENT`→`ValueError`。单句 ≤4000 字文本产出音频远低于 64 MiB，属防御性上界而非契约收紧。
5. **`synthesize` 内 `import urllib.error` 保留在失败分支**：仅为抛 `URLError` 所需，与「HTTP 栈按需加载」意图一致；模块内已无 `urllib.request`/`build_opener`/`urlopen` 引用。
6. **未动外来文件**：`tasks_round/L2领域服务层优化任务书.md`（外来勘误 M）、R3276 外来未跟踪四件（诊断报告/结果文件/两份任务书）、`project_status.md`（仅 master 可提交）一律不入暂存区。
7. **`--all --safe` 未跑**：非 master 提交点累计触发条件未达；改动为传输收口与目录探测常量，无写入边界/Tk 生命周期/删除语义/层级登记表变更。

## 遗留欠账

- 任务书轮 1–9 实现全部完成；**任务书尚未闭环**——剩合入 master 与规则 35《任务完成文件》（`tasks_round/任务完成/L2领域服务层优化·任务完成.md`），建议在合入轮或下一轮收尾时产出。
- 分支固有架构红 2 条（AGENTS.md 字节预算、状态页轮次冻结）——存量问题，与本轮无关，待 master 合并轮处理。
- 全量 `--all --safe` 未跑；若验收要求对最终树补跑可另行执行。

## 提交

- 分支 `codex/wip-r3282`（领号 R3320，工作树 `dsh-864fd932-4054`；领号记录见 `<git common-dir>/round-claims.json`，2026-11-18T11:09:21+08:00 认领）。
- 主提交：`1f752e0b`（11 个文件：3 个生产文件——domain/tts_api.py、domain/white_model_service.py、infra/http_client.py；5 个测试/架构文件——tests/test_http_client.py、tests/test_tts.py、tests/test_request_recording.py、tests/test_white_model_workspace.py、tests/architecture/test_http_boundary.py；维护记录/分支覆盖率基线.json；本结果文件；自动生成的 tasks_round/evidence/R3320.json）。
- 结果文件补记提交：本提交（`R3320: 补记结果文件commit哈希1f752e0b`；docs-only 补记同样带 `--tests` 重跑定向测试刷新证据）。
- 轮次证据以 `tasks_round/evidence/R3320.json` 为准（`run_selftests.py -k tts http_client white_model blender request_recording http_boundary` exit 0 / **170 通过 / 0 失败**，凭据扫描 0 命中）。
