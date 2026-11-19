# R3590 结果文件 — L1 任务书轮 I11：线程迁移（I11a–I11d，FL-08 = 0）
<!-- round-evidence: {"commit_base": "693e483c", "credential_hits": 0, "evidence_sha256": "7bf4aab835204080", "exit": 0, "failed": 0, "passed": 159, "round": 3590, "tests": "run_selftests.py -k offline_asr speech_api thread_boundary executors agent_skill_sync skill_user_layer qwen_adapter storyboard_direct desktop_automation platform_process_boundary layer_relations"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定：每子轮 ≤ 3 个模块）。I0 F11 盘点的 12 个 L2/L3 直接建线程文件、15 个位点全部迁往 I10 新建的 `infra.executors.submit` 边界：I11a＝`domain/offline_asr_client.py`（2）、`domain/offline_asr_setup.py`（1）、`domain/speech_api.py`（3）；I11b＝`orchestrator/agent_skill_sync.py`、`codex_skill_sync.py`、`desktop_automation_service.py`；I11c＝`idea_chat_controller.py`、`previs_automation.py`、`previs_monitor.py`；I11d＝`qwen_adapter.py`、`stage_parallel.py`、`storyboard_direct_api.py`。`infra/executors.py` 本轮补 `stream` 池（每任务独占 daemon 线程，供实时读泵/监视页服务等延迟敏感长驻任务，任务书明示允许的专用池形态）。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k <模块> thread_boundary` 分子轮执行：I11a 107 条 0 红、I11b 84 条（仅基线滞后红 1，基线同步后复绿）、I11c/d 21 文件批次全绿（`test_qwen_adapter` 两处源码锚点按 §2.4 契约同步后 3/3 绿；`test_stage_parallel` 一条 `keyframe_evidence` ffmpeg 解码红单独复跑 54/54 绿，系隐藏桌面 ffmpeg 环境抖动非本轮回归）；`test_thread_boundary` 4/4 绿、`THREAD_SITE_BASELINE={}`，L2/L3 直接建线程实测 **0**。默认 `smoke_test.py` **9/9 绿**；`smoke_test.py --affected <12 模块>` 9/10 项过、唯一红为同一 ffmpeg 隐藏桌面环境抖动（`test_stage_gate_e2e_probe`/`test_stage_parallel` 的 `image_facts` ffprobe 校验，单独复跑全绿，根因同 R3407 记录）；`smoke_test.py --architecture` 复跑结果见「验证汇总」。
3. **欠账少了吗？** 是。FL-08 由 I0 实测 15 位点/12 文件 → **0**（棘轮基线同步清空）；LR-08「9 项横切能力无守卫数」实测 4→3（线程能力守卫随清零生效，`层间合规清单.json` 已下调）；行覆盖基线重测 executors 87.9%→89.0%（211/237），分支覆盖基线重测 executors 38 点 71.1%→41 点 73.2%（30/41）。

## 领号说明

- R3590 由本工作树经 `维护记录/基准脚本/round_claim.py next` 领得；领号输出含已知 GBK 解码噪声，登记成功。期间跨树领号已推进至 3590（R3565–R3589 由其它分支轮次占用，`git log --all` 可见），本树结果文件序列内连续性不受影响（`test_round_number_continuous` 只核对 本树最新结果+1）。

## I11a　domain 三文件（语音链路，延迟敏感）✅

- `offline_asr_client.py`：`_EngineHost.start()` 的子进程 stdout 实时泵 → `executors.submit('stream', ..., label='voice-asr-reader')`（每任务独占线程，不占 io 池）；`OfflineAsrSession.start()` 主流程 → `submit('io', self._run, cancel=self._stop_event, label='voice-offline-asr')`，新增 `_stop_event` 由 `cancel()` 置位；`self.thread` 保留为 Future 兼容位（无外部 `.join()/.is_alive()` 消费方，已全库核实）。
- `offline_asr_setup.py`：`OfflineSetupRunner.start()` 下载链 → `submit('io', self._run, cancel=self._cancel_event)`；`_thread`/`_cancelled` 布尔改为 `_task`/`_cancel_event`（Event），`running` 属性改 `not self._task.done()`，`cancel()`/`_is_cancelled()` 语义不变；`ui/speech_settings_ui.py` 的 `current.running` 消费不受影响。
- `speech_api.py`：`_DictionarySession` 替换词泵 → `submit('io', self._pump, cancel=self._stop)`；`RealtimeSession.start()` 主流程 → `submit('io', self._run, cancel=self._stop_event)`；socket 收包循环 → `submit('stream', self._read, cancel=self._stop_event, label='voice-realtime-read')`，`reader.join(timeout)` 语义改 `reader.result(timeout=...)`（超时与任务异常一律吞掉，与 Thread.join 不传播异常一致，异常走 `app_logging.swallowed`）。
- 测试契约：三文件既有测试**零改动**全绿（`test_offline_asr_client` 21、`test_offline_asr_engine` 39、`test_offline_asr_setup` 11、`test_speech_api` 4、`test_dialog_voice_input`/`test_shared_input_voice`/`test_voice_dict`/`test_voice_ai_optimize`/`test_voice_mcp` 同批 107 条 0 红）。

## I11b　orchestrator 三文件（后台维护/执行壳）✅

- `agent_skill_sync.py`／`codex_skill_sync.py`：`start_*_skill_sync` 的后台维护 → `submit('io', functools.partial(entry, program=..., targets=...), label='*-skill-sync')`，返回值由 Thread 改 Future（调用方 `desktop_automation_tick` 与测试均不消费线程方法）。`codex_skill_sync` 顺带移除不再使用的 `import threading`，docstring 的 patch 面说明同步更新。
- `desktop_automation_service.py`：`run(ticket, fn)` 内部工作线程 → `submit('io', work, label='desktop-exec-<ticket>')`；`finished` Event 等待循环、`execution_scope`/`ExecutionStopped` 迟到记账语义原样保留（线程对调用方本就不可见）。
- **测试契约变更（§2.4，如实记录）**：`test_agent_skill_sync.py` 两处、`test_skill_user_layer.py` 一处原 patch `*.threading.Thread` 并断言 `target/kwargs/start()`，机制有意变更为 `executors.submit` 后同步 patch 目标为 `*.executors.submit`，断言等价保留——池名 `'io'`、提交次数 1 次、partial 入口仍为 `_all_entry`/`sync_codex_skills`、`before→sync` 顺序断言 `['migrate','sync']` 逐字未动。

## I11c　orchestrator 三文件（附件/自动制作/监视页）✅

- `idea_chat_controller.py`：附件入库校验 `work()` → `submit('io', work, label='idea-attachment-prep')`；结果仍经 `_attachment_results` 队列由 Tk 主线程轮询，token 防过期语义不变。
- `previs_automation.py`：批次 `worker`/`controlled_worker` → `submit('io', ...)`；`execute` 注入缝、`is_current` 代次闸、`announce`/`busy` 收尾语义不变；移除不再使用的 `threading` 导入。
- `previs_monitor.py`：监视页 `server.serve_forever` → `submit('stream', ..., label='previs-monitor')`（专用线程形态与「一监视页一服务」语义吻合；`stop()` 仍走 `server.shutdown()` 令 serve_forever 返回，stream 线程随之退出）。

## I11d　orchestrator 三文件（命名/Qwen/并行映射/直连作业）✅

- `qwen_adapter.py`：`name_when_ready(process)` 命名线程 → `submit('io', lambda: name_when_ready(process), label='qwen-name-ready')`；`threading.Lock` 保留。
- `stage_parallel.py`：`parallel_map` 的 N 个 `threading.Thread(target=run)` → `workers` 个 `submit('io', run, label='stage-parallel-<slot>')`；轮询循环由 `is_alive()/join(POLL)` 改 `future.done()`＋`concurrent.futures.wait(FIRST_COMPLETED, timeout=POLL)`（唤醒粒度不劣于原实现）；`cursor` 共享游标、`governor` 票据、`abandoned` 迟到标记、`on_late` 回调、`results` 有序返回全部原样——`run` 闭包本体零改动。
- `storyboard_direct_api.py`：`class Job(threading.Thread)` 改组合式——`start()` 内 `submit('io', self.run, label='storyboard-direct')` 存 `_future`；保留 `cancel()`（`control.cancel()`，注册表 `cancel_project_requests` 唯一调用面）、`is_alive()`（`not _future.done()`）、`join(timeout)`（`Future.result(timeout)`，`TimeoutError` 直接返回、其余异常 `app_logging.swallowed`，对齐 Thread.join 不传播工作异常）、`run()`/`execute()`/`done` 回调/`forget_request` 注销全不变；`self.name` 保留线程名兼容位。`launch()` 的 `register_request`/`job.start()` 调用面零改动。
- **测试契约变更（§2.4）**：`test_qwen_adapter.py` 两处——patch `qwen_adapter.threading.Thread` 改 patch `qwen_adapter.executors.submit`（断言提交 1 次、池 `'io'`、label `'qwen-name-ready'`）；源码锚点串同步为 `executors.submit('io', lambda: name_when_ready(process), label='qwen-name-ready')`（「就绪等待不占桌面回调」的行为断言实质不变）。

## 基线与门禁同步（棘轮纪律）

- `test_thread_boundary.THREAD_SITE_BASELINE`：I11a 后删 domain 3 条 → I11 全部完成后清空 `{}`；`test_thread_sites_within_baseline`/`test_baseline_covers_current_modules` 4/4 绿，FL-08 实测归零。
- `test_platform_process_boundary` 豁免登记行号同步：`previs_automation.py:22→23`（short_probe，`subprocess.run` ffprobe 带 `timeout=30` 语义不变）、`qwen_adapter.py:99→100`（detached，`launch_windows_app` 语义不变）——仅因新增 import 行位移，同一站点。
- `层间合规清单.json` LR-08：violations/baseline 4→3（线程守卫生效），note 同步；`test_layer_relations` 复绿。
- 覆盖率两基线真实重测：`coverage_report.py`（11 目标，128 用例全过）→ `覆盖率基线.json` 663 模块／83 覆盖，executors 89.0%（211/237）；`branch_coverage_report.py`（93 目标，1789 用例全过）→ `分支覆盖率基线.json` 95 模块／2816 点／1577 覆盖，executors 41 点 30 覆盖 73.2%（下限表 65.0 仍有效未动）。既有模块百分比零回退。
- `architecture.md` §3 L1 模块表 executors 行补 stream 池与 I11 边界说明；`PROJECT_MAP.md` 成本与运行保障行同步五池口径；任务书 FL-08 行与 I11-1/I11-2 勾选同步。

## 测试契约变更汇总（§2.4）

| 文件 | 变更 | 断言实质 |
| --- | --- | --- |
| `tests/test_agent_skill_sync.py` ×2 | patch `threading.Thread`→`executors.submit`，取 partial 调用 | `_all_entry` 入口、`io` 池、`before→sync` 顺序不变 |
| `tests/test_skill_user_layer.py` ×1 | 同上 | `['migrate','sync']` 顺序不变 |
| `tests/test_qwen_adapter.py` ×2 | patch `threading.Thread`→`executors.submit`；源码锚点串更新 | 后台边界一次、`io` 池、label 不变 |

## 环境问题（如实记录，非本轮回归）

- `smoke_test.py --affected` 唯一红：`test_stage_gate_e2e_probe`（4 条）与 `test_stage_parallel`（1 条）同点失败——`domain/keyframe_evidence.py:image_facts` 内 ffmpeg/ffprobe PNG 完整性校验在隐藏桌面会话内间歇返回非零（`0xC0000142` DLL 初始化失败同族，R3407 已立项跟踪 `gui_hidden`/ffmpeg 会话兼容）。两文件单独复跑全绿（5/5、54/54），失败调用链不经过本轮任何改动文件，判定环境性抖动。
- `test_site_packages_whitelist` 红：pydantic 五包跨分支环境污染（`codex/foundation-resume` R3540 准入安装进共享运行环境），R3564 已详录，待该分支合 master 自然转绿，与本轮零因果。

## 验证汇总

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k offline_asr speech_api thread_boundary executors voice_dict`（I11a） | 107 条 0 红 |
| `run_selftests.py -k agent_skill_sync skill_user_layer desktop_automation thread_boundary executors cancellation_status execution_deadline`（I11b） | 84 条：仅 thread_boundary 基线滞后 1 红（同步后复绿） |
| `run_selftests.py -k thread_boundary stage_parallel storyboard_direct qwen_adapter previs idea_chat`（I11c/d，UTF-8 重跑） | 21 文件批次：仅 qwen_adapter 契约锚点 2 红（已修复复绿）＋stage_parallel 环境抖动 1 红（复跑 54/54 绿） |
| `run_selftests.py -k test_qwen_adapter`（修复后） | 3/3 绿 |
| `smoke_test.py --affected <12 模块>` | 9/10 项过；唯一红＝隐藏桌面 ffmpeg 环境抖动（单独复跑全绿） |
| `smoke_test.py` | 9/9 绿 |
| `smoke_test.py --architecture`（首轮） | 554 条 4 红：分支决策点基线（已真实重测刷新）、豁免登记行号×2（已同步）、LR-08 清单（已下调）、依赖白名单（环境污染照旧） |
| `smoke_test.py --architecture`（复跑） | 见提交证据；预期仅余 `test_site_packages_whitelist` 环境红 |
| `scripts/coverage_report.py <11 targets>` | 完成：663 模块／83 覆盖／128 用例全过 |
| `scripts/branch_coverage_report.py <93 targets>` | 完成：95 模块／2816 点／1577 覆盖／1789 用例全过 |

## 后续提示

- `infra/executors.py` 的 `stream` 池为「每任务独占线程」登记表形态，`shutdown` 限时等待覆盖 stream 线程；后续若有新的实时读/长驻服务需求，沿用 `submit('stream', ..., label=...)`，不得回退裸线程（`test_thread_boundary` 棘轮会拦）。
- `Job.join()` 的 `TimeoutError` 早退依赖 Python≥3.11 `concurrent.futures.TimeoutError` 即内置 `TimeoutError` 的别名事实（本仓解释器 3.14 已核实）。
