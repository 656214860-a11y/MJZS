# R3114 功能轮结果：文件卡片与 HITL·轮 2/8——两层状态机 + 流式增量 + 取消令牌（停止/继续/重新生成）+ 发送排队
<!-- round-evidence: {"commit_base": "a5a9811b", "credential_hits": 0, "evidence_sha256": "4327800501acb6ea", "exit": 0, "failed": 0, "passed": 18, "round": 3114, "tests": "run_selftests.py -k chat_status idea_chat_controller"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 2/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`tests/test_chat_status.py`（9/9）、`-k idea_chat_controller writing_api chat_status idea_request_lifecycle writing_cancellation` 全绿（ALL TESTS PASSED）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；把「会话级 ChatStatus + 取消令牌 + 继续/重新生成计划 + 发送排队 + 副作用幂等」落进 L3 控制器。

## 改动

- `orchestrator/idea_chat_controller.py`：
  - 新增 `ChatStatus` 枚举（`submitted/streaming/ready/error`，借鉴 AI SDK 会话级状态；与 part 级 `PartState` 解耦）。
  - `begin_request(cancellable, request=None)`：进入 `SUBMITTED`、清空上一轮 `stop_reason/can_continue/副作用标记`、记录最近请求快照。
  - `mark_streaming(token)`：首增量 `SUBMITTED → STREAMING`；`progress_callback` 自动调用。
  - `finish_request(token, *, error=False, stop_reason='')`：正常 → `READY`，失败 → `ERROR`，`max_tokens` → `can_continue=True`。
  - `cancel_request()`：置取消令牌（显式 `Event.set()`）、`READY`、`stop_reason='cancelled'`、`can_continue=True`（可继续/重发）。
  - 发送排队：`enqueue_send/pending_sends/pop_pending_send/undo_pending_send/clear_pending_sends`（生成中排队、可撤销、turn 结束 flush 的 L3 状态）。
  - 继续/重新生成：`last_request/regenerate_plan/continue_plan(partial_text=)`（复用最近请求；继续带已产出前缀）。
  - 副作用幂等：`mark_side_effects_done/side_effects_done`，每个新请求重置（中断恢复不重复执行）。
- `tests/test_chat_status.py`：新增 9 条用例（状态迁移、错误态、取消令牌、max_tokens、重新生成、继续生成、进度推进流式、发送排队、副作用标记）。
- `PROJECT_MAP.md`：核心模块与验证地图补 `ChatStatus` 状态机与 `test_chat_status.py`。

## 测试证据

- `python -B tests/test_chat_status.py` → `Ran 9 tests ... OK`。
- `python -B run_selftests.py -k idea_chat_controller writing_api chat_status idea_request_lifecycle writing_cancellation` → `ALL TESTS PASSED`。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`）。
- 说明：`test_round_baselines.test_round_number_continuous` 要求状态页轮次 = 最新结果 + 1；本分支为非 master，`project_status.md` 按「仅 master 可提交」未入本轮提交，工作树内已临时抬到 3104 供架构门禁通过，合并轮在 master 提交。

## 契约变更（§2.4）

- `IdeaChatController.begin_request` 增加可选 `request=`；`finish_request` 增加 `error`/`stop_reason` 关键字参数（均向后兼容）。
- 新增 `ChatStatus`、`mark_streaming`、发送排队、继续/重新生成、副作用幂等方法。
- 既有测试断言未改动，新增用例覆盖；零第三方依赖不变。

## 范围外 / 已知缺口

- UI 端「停止/继续/重新生成」按钮与 `max_tokens → 继续提示` 的接线留给轮 3（消息工具栏与渲染层）；本轮只落 L3 状态与计划 API。
- 发送排队的 UI 消费（生成中排队提示、撤销）留给轮 3/8。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3101`（R3101/R3102/R3114 同链）；commit hash 见回填。
