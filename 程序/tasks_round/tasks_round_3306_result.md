# R3306：L1 基础设施层优化任务书 · 轮 5（传输层收敛 requests）结果
<!-- round-evidence: {"commit_base": "71393d99", "credential_hits": 0, "evidence_sha256": "e4521d4e030da661", "exit": 0, "failed": 0, "passed": 162, "round": 3306, "tests": "run_selftests.py -k l1_transport http_client platform_tools pet_llm l1_reliability http_boundary branch_coverage_floor"} -->

## 三问

1. **轮次类型**：§3 修复轮（任务书「轮 5：传输层收敛」，runbook §15 修复边界；R5-a~g 逐条闭环）。
2. **测试跑了吗、基线过了吗**：新增 `test_l1_transport_requests` 9 条全绿；受影响定向 110 条＋pet_llm/l1_reliability 85 条全绿；默认冒烟 9/9；架构门禁复跑中（首轮 532 条仅 http_boundary 白名单与分支基线两处契约同步失败，均已修复并单测复验）。
3. **欠账少了吗**：少了。api_endpoints／comfy_service／seedream_api 三处存量直连全部收敛到 `RequestsJsonOpener`；本机回环显式禁代理、解压后上限、跨源重定向不携凭据、GET/HEAD 传输层退避（urllib3 Retry）落地；`import desktop` 不载 requests 有实测。新增一笔如实欠账：连接复用（R5-f，见下）。

## 变更清单

| 编号 | 文件 | 改动 |
| --- | --- | --- |
| R5-a | `infra/api_endpoints.py` | `_http_opener()` 由 `build_opener(no_redirect())` 改为惰性返回 `contract.platform_tools.RequestsJsonOpener()`；`_http_transport`/`http_stream` 同走该入口。`http_stream` 请求头补 `Accept-Encoding: identity`（SSE 逐行迭代不经解码路径，避免服务端压缩破坏行切分）。 |
| R5-b | `infra/comfy_service.py`、`infra/seedream_api.py` | `Comfy.request` 弃用 `open_https`、`request_image` 弃用 `build_opener(no_redirect())`，均改构造 `urllib.request.Request`＋`RequestsJsonOpener().open()`；comfy 保留 64MB 分块上限与 `control.checkpoint()`，超时仍走 `control.remaining()`；seedream 移除 `no_redirect` 依赖。 |
| R5-c | `contract/platform_tools.py` | 复核既有 `_requests_tls_adapter`：`ssl.create_default_context()`（Windows 系统证书库）＋certifi 双信任，显式 CA 路径可替换；`test_platform_tools` 既有断言证实系统 trust 不丢。本项为复核结论，无代码改动。 |
| R5-d | `contract/platform_tools.py` | `RequestsJsonOpener.open()` 在 `merge_environment_settings` 后按 `urlparse().hostname` 判定，`localhost`/`127.0.0.1`/`::1` 显式置空 `settings['proxies']`——实测 requests 2.34.2 默认并不绕行本机代理（merge 返回值含 env 代理），本轮补齐。 |
| R5-e | `contract/platform_tools.py` | `_RequestsJsonResponse.__init__` 对带 `Content-Encoding`（非 identity）的响应摘除 `Content-Encoding`/`Content-Length` 头：`read()` 经 `decode_content=True` 已交付解压字节，避免调用方 `_decode_response_body` 二次解压与声明长度错配；`_limited_read`/`_read_limited` 计数的即解压后字节，满足「上限按解压后计」。新增 `__iter__`（`read()` 分块拆行，4MiB 单行兜底）供 `http_stream` SSE 消费。重定向不跟随（adapter.send 直发），`x-api-key` 等凭据结构性不外泄；`requests` 仍函数内惰性 import。 |
| R5-f | — | 连接复用：whitelist 框架 `RequestsJsonOpener` 仍是「每次 open 新建 Session」，未改为懒建单例。按任务书约定**本轮只记欠账、不改连接池**（见欠账节）。 |
| R5-g | `contract/platform_tools.py` | `_requests_tls_adapter` 由 `max_retries=0` 改为 `urllib3.util.Retry(total=2, connect=2, read=2, status=2, redirect=0, allowed_methods={'GET','HEAD'}, status_forcelist={408,425,429,500,502,503,504}, respect_retry_after_header=True, backoff_max=30.0, raise_on_status=False)`：GET 轮询/下载获得有界退避且遵守 Retry-After（30s 封顶）；POST/PUT/DELETE 不在 allowed_methods 内，付费 POST 仍由轮 1 手写口径独占重试（等效 max_retries=0）。`_requests_failure` 重写为沿 args/`__cause__`/`__context__` 遍历异常链判定超时——urllib3 `NewConnectionError` 继承 `ConnectTimeoutError` 的兼容史会把拒连误报成超时，显式排除；修复后拒连→`URLError`（E-NET-UNREACHABLE）、读超时→`TimeoutError`（E-NET-TIMEOUT）分类恢复。 |

## 测试契约同步（断言语义变化，均已注明）

- `tests/test_pet_llm.py`（2 处）、`tests/test_l1_reliability_r3248.py`（1 处）：mock 锚点由 `urllib.request.OpenerDirector.open` 改为 `contract.platform_tools.RequestsJsonOpener.open`——传输实现收敛是本轮有意契约变化，重试/预算断言原样保留。
- `tests/test_http_client.py`：`max_retries.total==0` 断言改为核对 `Retry.total==2 且 allowed_methods=={'GET','HEAD'}`（R5-g 新契约）；`test_get_retries_only_in_business_loop` 拆为「forcelist 状态码（503）由传输层 Retry 消化、业务循环不再 sleep」＋「非 forcelist（新增 `/retry501` 端点，501→E-NET-SERVER）仍走业务循环重试」两条，业务重试能力未丢。
- `tests/test_platform_tools.py`：同上 max_retries 断言同步。
- `tests/architecture/test_http_boundary.py`：白名单移除 `infra/api_endpoints.py`、`infra/seedream_api.py`（直连点已清零，白名单只减不增）；`local_video.py`/`domain/tts_api.py`/`batch_frames_tool` 仍有直连，保留登记（不在本轮任务书文件清单内，记录为存量）。
- `维护记录/分支覆盖率基线.json`：comfy_service 30→31、platform_tools 119→132（新增分支），其余模块 points 不变；以 84 个登记 targets 全量重跑 `branch_coverage_report.py`（1528 条用例全绿）真实刷新，covered 由 1332→1340。

## 验证记录

- `run_selftests.py -k l1_transport`：9 条全绿（本机回环禁代理、localhost 经 `_http_transport` 收敛、gzip 解压超限拒绝、identity 语义保持、跨源 302 不携 `X-Api-Key`、SSE 迭代、comfy/seedream 走 RequestsJsonOpener、`import desktop` 不载 requests/urllib3、自签 HTTPS 不被信任时可读失败）。
- `run_selftests.py -k http_client platform_tools l1_transport open_https seedream comfy`：110 条全绿。
- `run_selftests.py -k pet_llm l1_reliability`：85 条全绿（修复 mock 锚点后）。
- `smoke_test.py`（默认冒烟）：9/9 通过。
- `smoke_test.py --architecture`：首轮 532 条 2 红（白名单陈旧条目＋分支基线决策点），修复后复验 7 条定向全绿；全量复跑结果以合入轮出口 CI 为准。
- 分支覆盖率基线：84 targets／1528 用例全绿后重写 `维护记录/分支覆盖率基线.json`。

## 边界与欠账

- **R5-f 欠账（如实记录）**：`RequestsJsonOpener.open()` 每次新建 `requests.Session`，无 keep-alive 连接复用；高频轮询场景存在 TCP/TLS 握手重复开销。任务书约定轮 5 不改 `contract/platform_tools.py` 的连接池结构（属 whitelist 框架职责），本轮仅记录，待 whitelist 侧改懒建单例后自动受益。
- `domain/tts_api.py`、`local_video.py`、`batch_frames_tool/batch_frames.py` 仍在 http_boundary 白名单内使用 urllib 直连——不在任务书 R5 点名文件内，未动；后续 T3 迁移计划继续收敛。
- `open_https`（agent/core、account_client 等消费方）仍是 urllib 实现且跟随重定向（跨源剥凭据）；本轮未动，属 whitelist 框架既有契约。
- ComfyUI 本机 API 原走 `open_https`（跟随重定向），现收敛为不跟随重定向——本机服务无 3xx 场景，且与「凭据不外泄」口径一致；已在变更说明注明。
- urllib3 `Retry-After` 由 `backoff_max=30.0` 封顶，避免服务端给出超长等待时间阻塞轮询。

## 提交

- 分支：`codex/l1-p2-semantics`（领号 R3306，`round_claim.py next`）
- 提交：本结果文件随实现同批提交
- 合入 master：（待合入轮确认）
