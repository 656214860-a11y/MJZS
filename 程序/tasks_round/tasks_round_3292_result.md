# R3292：L1 基础设施层优化任务书 · 轮 4（P2 语义、可观测与进程）结果
<!-- round-evidence: {"commit_base": "c253f8cd", "credential_hits": 0, "evidence_sha256": "b061e22d6baf607c", "exit": 0, "failed": 0, "passed": 156, "round": 3292, "tests": "run_selftests.py -k l1_p2 broadcaster aigc_lint comfy assets native_apps workflow_process workflow_engines"} -->

## 三问

1. **轮次类型**：§3 修复轮（任务书「轮 4：语义、可观测与进程」，runbook §15 修复边界；逐条独立可回滚）。
2. **测试跑了吗、基线过了吗**：定向自检 156 条全绿（含新 `test_l1_p2_semantics` 10 条）；默认冒烟 9/9；`--affected` 由合入轮出口 CI 复核；全量 `--all --safe` 由 master 合入前验收锁串行执行。
3. **欠账少了吗**：少了。播报交错、临时文件泄漏、列表错位、槽位泄漏、孤儿进程、按映像名误杀六类 P2 缺陷闭环；`model_router` 子串判类按任务书留到轮 6；幂等键按 R0-d 结论「全部供应商不发」本轮零改动（见下）。

## 变更清单

| 编号 | 文件 | 改动 |
| --- | --- | --- |
| R4-a | `infra/broadcaster.py` | 每消息 `open/append/close` 改为标准库 `logging.FileHandler`（自带锁与轮转语义）：同路径共享 logger 不重复挂处理器；新增 `close()`/`__del__` 释放句柄。格式 `%(asctime)s %(message)s` 与原「时间戳＋消息」逐字节一致。 |
| R4-b | `infra/app_logging.py` | `faulthandler.log` 超 5MiB 先 `os.replace` 轮转成 `.1` 再打开；导出白名单名不变。 |
| R4-c | `infra/aigc_lint.py` | `_write_temp` 写入抛错时关闭句柄并删临时文件再抛（`_feed_path` 的 try/finally 之外补上创建期窗口）。 |
| R4-d | `infra/comfy_service.py` | `r.read()` 无上限改为 1MiB 分块读、块间 `control.checkpoint()`、累计超 64MB 抛 `ValueError` 中止（参照 `batch_frames_tool/batch_frames.py` 64MB 口径）。 |
| R4-e | `infra/seedream_api.py` | `exc.read()` 无上限改 `exc.read(64*1024)`；错误详情先经 `api_endpoints._scrub_error_detail(detail, headers)`（含 `Authorization: Bearer` 头值替换＋通用脱敏）再进异常消息。 |
| R4-f | `infra/cloud_assets.py` | `graph()` 新增：`paths` 与 `images` 长度不一致报 `ValueError`；逐张 `is_file()` 校验后才 `upload.upload()`，缺失文件明确报错不再静默错位。 |
| R4-g | `orchestrator/workflow_engines.py` | 两处 `reserve_stage_process_slot` 后的启动调用补 `except BaseException: release_process_slot(slot); raise`——`OSError` 等非 `ValueError` 异常不再泄漏预留槽位（全局并发上限 8 不再被不可逆削减）。 |
| R4-h | `infra/workflow_process_registry.py` | 新增 `_job_object()`/`_assign_to_job()`：ctypes 懒建 `KILL_ON_JOB_CLOSE` Job Object（正确设置 `restype/argtypes` 防 HANDLE 截断），`register_process` 登记时把子进程挂入；失败只跳过不影响启动；不含本进程自身，`os.startfile` 打开的用户程序不受影响。 |
| R4-i | `infra/native_apps.py` | `force_close_comfy` 删除 `taskkill /IM` 映像名批量结束；只按 `comfy_server_pids()` 与 `workflow_process_registry.all_processes()` 登记进程号 `/PID /F /T` 结束；都没有时返回手动关闭提示（行为变更：原来 raise `ValueError`，现返回提示字符串）。 |
| R4-j | — | 幂等键：R0-d 已核对全部主流供应商「不发」，按「表里标不发的一律不发」本轮零改动，无供应商被启用。 |

**测试契约同步**：`tests/test_broadcaster.py` 两处显式持有 `Broadcaster` 的用例补 `close()`（logging 处理器持句柄是本轮有意契约变化；内联创建的实例由 `__del__` 兜底）。断言未弱化。

## 验证记录

- `run_selftests.py -k l1_p2_semantics`：10 条全绿（含 Job Object 父死子亡实测、8 线程 100 行无交错、槽位 OSError 释放、`/IM` 零命中）。
- `run_selftests.py -k broadcaster aigc_lint comfy assets native_apps workflow_process workflow_engines l1_p2`：13 文件 156 条全绿（2 条既有登记跳过）。
- `smoke_test.py`（默认冒烟）：9/9 通过。
- `smoke_test.py --affected`／`--architecture`／`--all --safe`：（合入轮出口 CI 与验收锁串行复核）

## 边界与欠账

- Job Object 只覆盖 `register_process` 登记的子进程；ComfyUI 服务端（`comfy_server_pids()` 认的 python main.py）不在登记表，仍按 R4-i 单独结束；用户自启的 Comfy Desktop 窗口不碰。
- `force_close_comfy` 现在会连带结束**所有项目**登记在册的存活进程（登记表即「本应用派发的子进程」全集），语义比原来宽——已在结果文件注明，若后续要收窄到 Comfy 相关可再加过滤。
- `model_router.py:176-187` 子串判类、`native_apps` 的 mbcs 解码与 PowerShell 超时项不在本轮任务书清单，未动（前者任务书明确留轮 6）。
- R5 传输层收敛前置（whitelist 合入）已满足，下一轮执行。

## 提交

- 分支：`codex/l1-p2-semantics`（领号 R3292，`round_claim.py next`）
- 提交：本结果文件随实现同批提交
- 合入 master：（待合入轮确认；本分支同时携带轮 2 R3269、轮 3 R3288 提交）
