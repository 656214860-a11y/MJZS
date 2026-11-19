# R3460 结果文件 — L1 任务书轮 I8：进程监督器（spawn／Job Object／错误归类／边界补盲）
<!-- round-evidence: {"commit_base": "6ecf2b1d", "credential_hits": 0, "evidence_sha256": "a273e3ae0854ebfd", "exit": 0, "failed": 0, "passed": 39, "round": 3460, "tests": "run_selftests.py -k workflow_process_registry process_supervisor platform_process subprocess_timeout gate_selfaudit"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定，1 个模块＋门禁）；范围 `infra/workflow_process_registry.py`（新接口加既有函数门面）、`tests/test_process_supervisor.py`（新增）、`tests/architecture/test_platform_process_boundary.py`（补 F10 盲区、存量登记棘轮），另按 I8-3 需要在 `contract/error_codes.py` 追加 `E-TOOL-TIMEOUT`、在 `contract/infra_errors.py` 的 `ProcessError._allowed` 放行该码。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k workflow_process_registry process_supervisor platform_process subprocess_timeout gate_selfaudit` **39 条 0 红**（5 个文件）；默认 `smoke_test.py` **9/9 绿**；`smoke_test.py --affected workflow_process_registry error_codes infra_errors` **10/10 绿**；`smoke_test.py --architecture` **548 条 0 失败**（首轮 2 红＝skip 台账漏登新测试 skip＋状态页轮次头未同步，均已修复后复跑全绿）；分支覆盖率基线已按当前代码重测（`workflow_process_registry.py` 61 决策点／78.7%，棘轮下限 41.0）。
3. **欠账少了吗？** 少了。FL-07 从「1 类（引擎 CLI）」扩为监督器登记的全部 8 个种类（7 类进 Job Object＋`detached` 显式例外）；FL-06 的 28 处存量启动点全部按「文件:行」登记进 `SPAWN_SITE_BASELINE` 棘轮（只减不增，迁移归 I9）；B-08 门禁盲区四种写法全部纳入识别。

## 领号说明

- R3460 由本工作树（`devin-l1-enterprise`／`codex/l1-enterprise`）经 `round_claim.py next` 领得（claims 登记约 2026-11-18T23:19:45+08:00）；领号子进程输出有一次 GBK 解码告警，登记本身成功并已核验。

## I8-1　进程种类登记＋spawn 契约 ✅

- `PROCESS_KINDS` 登记 L1-H9 全部 7 个种类的默认超时（沿用各调用方现值：engine_cli 7200／comfy 90／ffmpeg 120／asr 15／blender 1800／optimizer 125／test_runner 300），外加任务书点名的 `detached` 例外种类（`job=False`，不设默认超时——它要在应用退出后继续运行，监督超时无意义；`spawn` 仍要求显式给 timeout）。
- `spawn(kind, command, *, project, stage, timeout=None, health=None, **popen_kwargs)`：未登记 `kind`、缺省/None/0/负数/布尔/非数值/NaN/无穷 `timeout` 一律抛 `ConfigError`（`E-CONFIG-INVALID`，兼容 `ValueError`）。
- 启动失败归类：`FileNotFoundError` → `ProcessError(code='E-TOOL-MISSING')`；其余 `OSError` → `ProcessError(code='E-TOOL-FAILED')`。均先于登记返回，失败不产生孤儿登记。
- `popen_kwargs` 原样透传 `subprocess.Popen`；`stderr` 缺省 `PIPE` 供尾部留存，`cwd` 缺省项目目录，`creationflags` 缺省 `hidden_console_flags()`（调用方显式给值时不覆盖）。
- 测试：`ProcessKindRegistryTests` 3 条（种类表全等断言、六类非法 timeout、未知 kind 的 ConfigError/InfraError 兼容）。

## I8-2　Job Object 兜底与 detached 例外 ✅（含一处存量缺陷修复）

- 既有 `_job_object()`（KILL_ON_JOB_CLOSE）与 `register_process(..., job=True)` 沿用；`spawn` 经 `register_process(job=spec['job'])` 挂接，`detached` 只登记不挂 Job。
- `JobObjectSupervisionTests.test_job_close_kills_supervised_but_not_detached`：真实假子进程（`python -c sleep`）经 `spawn('ffmpeg')` 与 `spawn('detached')` 启动 → 关闭 Job 句柄模拟应用退出 → 受监督进程被系统结束、detached 仍存活随后手动清理。测试宿主为 Windows 实跑，非 mock。
- **存量缺陷修复（本轮实测发现，属任务书 R2 风险的真实命中）**：`_assign_to_job` 的 OpenProcess(pid) 回退路径可把**任意 pid 包括宿主自身**挂进 Job。全量覆盖率套件中 `test_l1_p2_semantics` 的 `Mock(pid=os.getpid())` 用例让追踪宿主把自己挂进 Job，随后本轮新增的关 Job 测试一关句柄就把宿主一起杀掉——套件三次在同一位置静默退出（PYEXIT=0、无 unittest 汇总）。已加 `_is_direct_child()`（Toolhelp32 快照核对父进程号）：`_handle` 与 pid 两条路径都先 `GetProcessId` 再做父子校验，**只允许本进程直接子进程入列**；自身、父进程、无关 pid 一律跳过。回归测试 `test_assign_to_job_refuses_self_and_non_children` 断言成员集合不变。
- 附带加固：`SupervisedProcess._pump_stderr` 改为兼容二进制/文本流的双哨兵读取，EOF 后关闭管道（消除 ResourceWarning）；`stderr_tail()` 对 bytes/str 行统一解码。

## I8-3　退出码与 stderr 归类 error_codes ✅

- `classify_exit(returncode, *, timed_out, stderr_tail)`：超时 → `E-TOOL-TIMEOUT`；stderr 命中「not recognized／不是内部或外部命令／no such file or directory」→ `E-TOOL-MISSING`；其余非零 → `E-TOOL-FAILED`；零退出或仍在运行 → 空串。
- `contract/error_codes.py` 新增 `E-TOOL-TIMEOUT`（degraded、可重试）；`ProcessError._allowed` 同步放行。
- `SupervisedProcess` 提供 `pid/poll/wait(timeout 缺省用登记值,超时返回 None)/terminate/kill/stderr_tail()/error_code(timed_out)`；stderr 由守护线程异步抽进 200 行有界 deque。
- 测试：`ExitClassificationTests` 6 条（超时／缺执行文件两种措辞／非零／成功与运行中／三码在 `error_codes.CODES` 可解析／真子进程 stderr 尾部取证）。

## I8-4　进程门禁补盲区 ✅

- `test_platform_process_boundary.py` 新增 `ProcessSpawnBoundaryTests`：AST 递归扫描全部生产模块，识别四种绕过写法——`(x or subprocess.Popen)(`（含 BoolOp）、`popen=subprocess.Popen` 关键字、`subprocess.run(...)`、`platform_tools.launch_*`（模块与 from-import 裸名均覆盖）。
- 存量按「文件:行」登记 `SPAWN_SITE_BASELINE`（28 条，与 I0/FL-06 口径一致），只减不增；扫描结果超基线即红，基线条目消失时打印棘轮下调提示；条目格式 `^[\w./-]+\.py:\d+$` 自检；`platform_tools` 与 `workflow_process_registry` 豁免。
- 坏样本自审 5 条全覆盖四种写法；好样本（`run_process`、监督器 `spawn`、裸 `subprocess.PIPE`）不误报。
- `test_coverage_audit_ratchet.py` P21 白名单登记 `workflow_process_registry`（监督器本体＝受信进程边界，与 `platform_tools` 同类），`覆盖率审计判据_20261001.md` 第 21 条同步注明 R3460 登记理由。

## 验证汇总

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k workflow_process_registry process_supervisor platform_process subprocess_timeout gate_selfaudit` | 39 条 0 红（5 文件；test_process_supervisor 14 条含新增回归） |
| `run_selftests.py -k process_supervisor workflow_process_registry l1_p2_semantics` | 46 条 0 红（父子校验不破坏既有 _assign_to_job 用例） |
| `run_selftests.py -k branch_coverage_floor coverage_audit` | 11 条 0 红（基线重测后一致） |
| `smoke_test.py` | 9/9 绿 |
| `smoke_test.py --affected workflow_process_registry error_codes infra_errors` | 10/10 绿（门禁内定向 47 条 0 红） |
| `smoke_test.py --architecture` | 548 条 0 失败（301.6s；首轮 2 红＝skip 台账漏登＋轮次头滞后，修复后复跑全绿） |
| `scripts/branch_coverage_report.py <92 targets>` | 完成：94 模块／2766 决策点／1543 覆盖／目标用例全通过；`workflow_process_registry.py` 61 点 78.7%（下限 41.0） |

## 分支覆盖率基线重测说明

- 起因：I8 给 `workflow_process_registry.py` 新增约 24 个决策点（37→61），基线「决策点数＝当前 AST」校验必红，须重测。
- 过程：全量 92 目标套件前两次在同一位置静默退出（套件尾部、unittest 无汇总、PYEXIT=0）。经无监督器对照组（92 目标不含 test_process_supervisor）完整跑通＋verbose 复现定位到 `test_job_close_kills_supervised_but_not_detached`＋`_assign_to_job` 逐条日志实证宿主自挂 Job，根因为 R3292 遗留的 pid 回退路径可挂任意进程；修复后第三次全量跑通并写入基线。
- 基线 `tests_ok: true`、`targets` 92 项、模块 94 个，与 `_layers` L0/L1 实体集合一致；`分支覆盖率下限.json` 未动（棘轮只升不降，本轮未触发）。

## 欠账与后续

- FL-06 存量 28 处迁移到 `spawn`/豁免清单属 I9 范围，本轮只登记棘轮；`detached` 种类的具体调用点清单由 I0/I9 按需登记。
- `health` 探针参数已留位，ComfyUI `/system_stats` 与 ASR 握手探针属 I9-2。
- `spawn` 尚无生产调用方（I9 迁移时接入）；`register_supervised/supervised_info` 元数据为 I9 统一取消与计量预留。
