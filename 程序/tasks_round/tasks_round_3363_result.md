# R3363：master 全量自检 16 红定性修复（环境缺口＋传输 mock 失配＋三处真回归）结果
<!-- round-evidence: {"commit_base": "9e3d1924", "credential_hits": 0, "evidence_sha256": "29b3f5bf4762d537", "exit": 0, "failed": 0, "passed": 1062, "round": 3363, "tests": "run_selftests.py -k model_pool_redirects api_cache_usage model_gateway_robustness latent_defects_r2175 auto_full_safe secret_status_diagnostics core shared_adapter_infrastructure keyframe_evidence keyframe batch_frames file_origin_provenance req_s08 pet_ui stage_gate_e2e_probe stage_parallel"} -->

## 三问

1. **轮次类型**：§3.2 修复轮。起因：master `9e3d1924` 自动全量自检连续多轮 16–19 个测试文件红（`full-safe-receipts.json` 真实凭据），且红项集合逐轮漂移、日志带 `SUSPECT_CONCURRENCY`。本轮先把 16 红逐一定性，再按根因最小修复。
2. **测试跑了吗、基线过了吗**：定向复验全部转绿（见下）；默认冒烟 9/9；`--affected desktop seedream_api keyframe_evidence auto_full_safe` 118 文件批次与 `--architecture` 结果以提交前实测为准。ffmpeg 组 19 文件 825 条在工作树（含 `运行环境/ffmpeg`）全绿。
3. **欠账少了吗**：少了。`.wt/ci` 干净检出的运行环境缺口由 `auto_full_safe` 自动补齐（硬链接），不再依赖人工预置；四个测试文件的 mock 锚点与 requests 传输现实对齐；三处真回归修复。

## 红项定性（16 文件 → 三类根因）

| 类别 | 文件 | 根因 | 处置 |
| --- | --- | --- | --- |
| 环境缺口 | test_keyframe、test_keyframe_evidence、test_keyframe_lifecycle_service、test_file_origin_provenance、test_batch_frames、test_req_s08_anchors、test_pet_ui、test_stage_gate_e2e_probe、test_stage_parallel 等 ~10 个 | `.wt/ci` 是 git 干净检出，`运行环境/` 被 `.gitignore` 排除 → `tool_path('ffmpeg')` 返回 `None` → `run_process([None,…])` 抛 `TypeError: expected str, bytes or os.PathLike object, not NoneType` | `scripts/auto_full_safe.py` 新增 `_fill_bundled_tools()`：把主工作树 `运行环境/ffmpeg` 子树**硬链接**进检出（同盘零拷贝、被忽略目录 `git clean` 不动、目标已存在即跳过）；已手工预置 `.wt/ci/运行环境/ffmpeg`（9 文件硬链接，`git status` 仍干净，`tool_path` 双双解析成功） |
| 测试 mock 失配 | test_model_pool_redirects、test_api_cache_usage、test_model_gateway_robustness、test_latent_defects_r2175 | R3307 把出站传输收敛到 `RequestsJsonOpener`（requests/urllib3 栈）后，这四个文件仍 patch `urllib.request._opener`/`HTTPHandler.http_open`——mock 根本拦不到请求，全部打到 `DRAMA_SUPPRESS_NETWORK` 抑制或真实网络 | mock 锚点改为 `requests.adapters.HTTPAdapter.send`（`RequestsJsonOpener` 正是 `session.get_adapter().send()` 直发，不经 `Session.send`/redirect 解析），`requests.Response`＋`urllib3.HTTPResponse(body=BytesIO)` 回放状态码/头/体；断言同步 `PreparedRequest` API（`url`/`method`/`headers.get()`/`body`）；全部补 `patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK':'0','NO_PROXY':'*'})` 显式解除抑制。**断言语义零变化**：仍验证「重定向不跟随、凭据不外泄、SSE 生命周期、Retry-After、超时/断线/截断归 network」 |
| 真回归 ×3 | test_core（1 条）、test_shared_adapter_infrastructure（1 条）、test_secret_status_diagnostics（1 条） | 见下 | 见下 |

### 三处真回归明细

- **`desktop.py`**：R3342 临时清扫排程 `self.win.after(...)` 在 `Desktop.__new__` 测试替身（无 Tk 窗口）上 `AttributeError`。修：`win=getattr(self,'win',None)` 守卫，无窗口不排程（无消息循环可挂，语义本就不该排）。
- **`infra/seedream_api.py`**：R3306 收敛传输时移除了 `no_redirect` 的再导出，但 `tests/architecture/test_shared_adapter_infrastructure.py` 断言「重定向拒绝唯一实现在 api_endpoints、消费方经共享符号引用」。修：恢复 `from infra.api_endpoints import no_redirect  # noqa: F401`（唯一实在，消费方引用不变）。
- **`tests/test_secret_status_diagnostics.py`**：R3342 把 `diagnostics/latest.json` 加进导出白名单（`export_candidates()` 第三成员），`test_export_never_leaves_the_whitelist` 期望值未同步，且 `flush_artifact_states()` 在导出前可能落盘使 latest.json 非确定在场。修：测试内显式造 `latest.json` 使在场确定，期望名单同步为 `['logs/diagnostics/latest.json','logs/启动错误.log']`——白名单收窄断言原样保留（§2.4 契约同步，非弱化）。

### 顺手加固（同根因域）

- **`domain/keyframe_evidence.py`**：`decoder = tool_path('ffmpeg')` 为 `None` 时直接 `run_process([None,…])` 抛 `TypeError`；改为显式 `raise ValueError('首帧图片损坏或解码器不可用…')`，与本模块「友好 ValueError」契约一致（机器无 ffmpeg 时错误语义正确，仍不伪造证据）。

## 验证记录

- `run_selftests.py test_model_pool_redirects`：4/4 绿；`test_api_cache_usage`：15/15；`test_model_gateway_robustness`：16/16；`test_latent_defects_r2175`：14/14（含真实回环套接字超时/断线/截断用例，urllib3 Retry 生效）。
- `run_selftests.py test_auto_full_safe test_secret_status_diagnostics test_core test_shared_adapter_infrastructure`：185 条 0 红（1 条既有登记 skip）。
- ffmpeg 组 `test_keyframe* test_file_origin_provenance test_batch_frames test_req_s08_anchors test_pet_ui test_stage_gate_e2e_probe test_stage_parallel` 等 19 文件关键词批：**825 条 0 红**（工作树自带 `运行环境/ffmpeg`，证实红项纯环境性）。
- `smoke_test.py` 默认冒烟：9/9。
- `smoke_test.py --affected desktop seedream_api keyframe_evidence auto_full_safe`：118 文件批次（后台隐藏桌面），结果见提交证据。
- 新增 `tests/test_auto_full_safe.py::BundledToolTests` 3 条：ffmpeg 子树补齐且 Python 不进检出／源缺失容忍／已存在不覆盖。

## 与并发因素的关系

日志中的 `SUSPECT_CONCURRENCY`（红项时有其他 PID 持 GUI 令牌）是**放大器而非根因**：四个 mock 失配文件与三个回归文件在无并发的定向复跑中同样红，ffmpeg 组在 `.wt/ci` 必然红（环境缺口确定性）。修复后预期：mock/回归三组转绿；ffmpeg 组在补齐运行环境后转绿；若仍有零星红则属真并发 flake，按 runbook 串行复跑口径处理。

## 欠账与边界

- `.wt/ci` 只补 `ffmpeg` 一棵子树（证据所需最小集）；若未来测试需要 `运行环境/` 下其它工具，按同法扩 `BUNDLED_TOOL_DIRS`。
- `BUNDLED_TOOL_DIRS` 只补「目标不存在」；ffmpeg 二进制升级后旧硬链接内容不变（硬链接共享 inode，源文件**原地更新**会同步，**替换式更新**会留旧版）——与 `_fill_ignored_inputs` 同语义，ffmpeg 发布节奏下风险可忽略。
- `test_open_https_redirect.py` 仍 patch urllib Handler——它测的是 `platform_tools.open_https`（独立 urllib 实现，非 RequestsJsonOpener），不受影响，未动。
- master 全量真实凭据：本轮合入后由后台 `auto_full_safe` 在新 HEAD 自动复跑；`.wt/ci` 已手工预置 ffmpeg，即便赶在合并前的运行也能吃到环境修复（mock/回归组仍需本提交）。

## 提交

- 分支：`codex/l1-p2-semantics`（领号 R3363）
- 合入 master：（待合入轮确认）
