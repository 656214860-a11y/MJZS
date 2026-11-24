# tasks_round_4353_result — SANHU-PROACTIVE-STATS 阶段停滞检测
<!-- round-evidence: {"commit_base": "e0f94779c", "credential_hits": 0, "evidence_sha256": "0edca9f9a65292e9", "exit": 0, "failed": 0, "passed": 654, "round": 4353, "tests": "run_selftests.py -k pet_ui pet_state"} -->

- 本轮类型：§3.1 功能轮（三虎新增一类主动提示：阶段在跑、子进度满 10 分钟没动时说一次「卡住了」，只提醒不处置）。
- 测试跑了吗：跑了。定向 `run_selftests.py -k pet_ui pet_state` 改前 13 条新用例全红、改后 654 条全绿；`smoke_test.py --architecture` 702 tests OK。三个基线中本卡验收只点名这两条；默认冒烟未跑（卡面未要求）。
- 欠账少了吗：补上了「在跑但不前进」这一类主动提示的空白（三虎框架评估「缺能力：没有阶段停滞检测」），未新增欠账。

## 缺陷复现方式

在 `tests/test_pet_ui.py` 末尾新增 `StallWatchTests`（7 条纯用例）与 `StallVoiceTests`（6 条三虎侧接线用例），方法名全部 `test_stall_watch_` 前缀。用假时钟推进：阶段 running + detail 3/40 满 600 秒不动 → 期望 `StallWatch.sample` 返回停滞、`Pet.stall_note` 给出含阶段名／分钟数／完成数的人话、`pump()` 每 200 拍问一次并经 `announce` 播报一次。

## 改前红的条数与原因

- `run_selftests.py -k pet_ui pet_state`（改前）：共 654 条用例，1 个文件有红（test_pet_ui），退出码 1。
- 红的 13 条全部为新增用例，原因与缺陷一致——能力不存在：
  - 7 条 `AttributeError: module 'ui.pet_context_facts' has no attribute 'StallWatch'`（另 1 条为 `format_stall_note` 缺失）；
  - 4 条 `AttributeError: 'Pet' object has no attribute 'stall_note'`（经 `orchestrator/pet_broadcast_state.py:120` 的 `__getattr__` 抛出）；
  - 2 条 AssertionError：`pump()` 未在 200 拍时调用 `stall_note`（`0 != 1`）、`announce` 未收到停滞文案（`[] != ['【阶段停滞】…']`）。

## 改了哪几处

- `ui/pet_context_facts.py:11-84`：`import time`、`import contract.pet_bus as pet_bus`；`STALL_SECONDS = 600.0`；`StallWatch`（`sample(stages, at=None)`：running/retrying 且 detail 非空才起表，done 变化清零重计，满 seconds 命中一次并闩锁）；`format_stall_note`（文案「【阶段停滞】「NN 名」已经在跑 M 分钟没有新进度（完成 d/t），要我看看吗？」，阶段名走 `pet_bus.stage_label()`）；`stall_note(voice, at=None)`（quiet/snoozing 闸门里不动表、只记账；machine 更换时重建 watch；异常记 `errors` 后返回空串）。
- `ui/pet_ui_voice.py:1156`：单行转发 `def stall_note(self, at=None): return pet_context_facts.stall_note(self, at=at)`；删去类末与 `_startup_page_busy` 间一对空行之一（文件仍为 1201 行＝棘轮上限）。
- `ui/pet_ui.py:459`：`self._stall_tick = 0`；`:658-662`：pump 心跳每 200 拍（约 30 秒）调一次 `stall_note`，非空走 `self.announce()` 失败播报同一出口。不加线程／定时器／事件。

## 改后命令输出尾部原文

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_ui pet_state` → 退出码 0：

```
共 654 条用例，246.7 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新
最近 5 轮自检中位基线：155.8 秒
ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0：

```
Ran 702 tests in 276.661s
✅ 架构治理测试：tests/architecture
OK
```

## 没有验证的地方

没有开真实窗口看云朵框实际冒出停滞提醒（用例走的是 `announce`→transcript 记账路径与计数桩）。多阶段同时在跑时只报 `stages` 表里第一个满时限的命中项，下一波按序再报（卡面边界例子只要求单阶段）。
