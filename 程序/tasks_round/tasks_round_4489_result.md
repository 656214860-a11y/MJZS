# tasks_round_4489_result — SANHU-FIX-2 三虎提问部件 pet_ask、页面问句带阶段与半自动付费确认（S-03/S-05/S-10）
<!-- round-evidence: {"commit_base": "930f3bc7a", "credential_hits": 0, "evidence_sha256": "603f8f13464e93d8", "exit": 0, "failed": 0, "passed": 839, "round": 4489, "tests": "run_selftests.py -k pet_ui pet_agent pet_cloud sanhu_mode stage_command_contract"} -->

- 本轮属于 §3.1 功能轮（SANHU-FIX-2 卡面 W3 收口：S-03/S-05/S-10，同步 master 930f3bc7a 后刷新覆盖率基线并正式提交）。
- 测试跑了吗、三个基线过了吗：跑了。卡面两条验收命令退出码均 0——定向 `run_selftests.py -k pet_ui pet_agent pet_cloud sanhu_mode stage_command_contract`（839 条 0 红）；`smoke_test.py --architecture`（708 条 OK）。
- 欠账少了吗：S-03/S-05/S-10 三项落地；`ui/pet_ask.py` 登记 `_layers`（L4）并随 15 目标实测刷新覆盖率基线 691→692。无新增欠账；文档同步见末节清单。

## 先红 → 后绿

### 先红原文摘要（上一尝试实现期，本树未复采）

本树是迁移收口轮：代码与测试随上一尝试一并到位，先红证据未在本树重采，以下为按新用例断言内容还原的先红形态（上一尝试实测先红）：

- `from ui import pet_ask` → `ModuleNotFoundError: No module named 'ui.pet_ask'`（新部件尚未建）。
- S-10 断言问句为「要不要我把这份剧本原稿整理成结构化正稿？」→ 旧实现回「现在制作分镜吗？」断言失败。
- S-05 断言半自动付费步骤先弹「现在做吗」→ 旧实现直接 `approve('stage.run', paid=…)` 拒跑、无问句，断言失败。
- S-03 断言 `propose(..., stage=…)`/`route(..., stage=…)` → 旧签名无 `stage` 参数，断言失败。

### 改后绿（本树实测，两条验收命令真实尾部）

```
run_selftests.py -k pet_ui pet_agent pet_cloud sanhu_mode stage_command_contract
…
共 839 条用例，43.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED        （exit 0）

smoke_test.py --architecture
…
----------------------------------------------------------------------
Ran 708 tests in 309.837s

OK
✅ 架构治理测试：tests/architecture        （exit 0）
```

## 旧/新问句变更表

| 场景 | 旧 | 新 |
| --- | --- | --- |
| 剧本自动保存后（非全自动档） | 【下一阶段】剧本已保存。现在制作分镜吗？ | 【下一阶段】剧本已保存。要不要我把这份剧本原稿整理成结构化正稿？——问句先把「执行选中·script_structure」递给回复框，空回车按剧本结构派发；全自动档不问（S-10）。 |
| 半自动档付费步骤启动 | 无问句：`approve('stage.run', paid=…)` 不放行就只把轮询提前叫醒 | 弹「是/否」小窗「「<阶段名>」这一步要花钱，现在做吗？」；点头先 `grant_paid` 再 `approve(..., confirmed=True)` 派发；没点头/超时回「「<阶段名>」要花钱，等您点头再开始」并记被拒集合，本档不再追问（S-05）。 |
| 页问句空回车派发 | 按状态机当下停着的阶段路由 | 问句记下本页阶段（`PAGE_STAGES`/`page_stage_for` → `Cloud.choice_stage` → `dispatch(stage=)` → `route(stage=)`），空回车按问句带来的阶段路由；手打的句子照旧按状态机（S-03）。 |

## 改动表（git diff --numstat 口径）

| 文件 | 改动 | 内容 |
| --- | --- | --- |
| `ui/pet_ask.py` | 新增 155 行（L4） | `ask_yes`（复用 `ask_confirmation`，非界面线程经 `win.after`/`_PENDING` 队列回切主线程，`pump_asks()` 由 `poll_test_mode` 心跳领走，`wait` 超时回 None）；`ask_choice`（BaseDialog＋DataTable 列表选一个）；`declined_set`/`confirm_paid`/`approve_stage` 半自动付费放行裁决。 |
| `ui/pet_ui_support.py` | +22 | `PAGE_STAGES`（13 阶段，与 `PAGE_ASKS` 等长对齐 `pet_bus.STAGES`）；`page_stage_for(index)`；`script_structure_offer(pet)`（S-10 问句与 propose 接线）。 |
| `ui/pet_cloud.py` | +14/−10 | `propose(text, label, stage=None)` 记 `choice_stage`；`submit()` 空回车带 `choice_stage` 派发、手打不带；`dispatch(text, stage=None)` 签名认得才传；`ask(text, stage)` 接力。 |
| `pet_agent.py` | +5/−5 | `route(..., stage=None)`：给了 stage 就盖过 `context['stage']`；`Agent.dispatch(..., stage=None)` 一路下传。 |
| `ui/pet_ui_stages.py` | +15/−14 | `start_stage` 放行裁决改走 `pet_ask.approve_stage`，被拒照旧叫醒轮询并回「等您点头」；`resume` 意图与 `clear_paid_grants` 清被拒集合；`poll_test_mode` 调 `pump_asks()`；`script_downloaded` 问句改口（全自动不问）；`note_stage`/`chat.propose`/`cloud.propose` 带 `page_stage_for`。 |
| `ui/pet_ui_voice.py` | +2/−2 | `offer` 答复里 `cloud.propose(command, stage=page_stage_for(...))`。 |
| `tests/architecture/_layers.py` | +5 | `_register(4, 'pet_ask')`；同层边 `('pet_ask','pet_ui_support')`、`('pet_ask','ui_widgets')`、`('pet_ui_stages','pet_ask')`。 |
| `tests/test_pet_ui.py` | +246/−7 | `PetAskTests`（ask_yes 主线程/worker 回切/超时/ask_choice 选中与取消）；S-03 页问句带阶段与手打不带；S-05 问一次/被拒不再问/超时同拒/「继续」与切档复问；S-10 新文案/带 script_structure/全自动不问。另按 R4394(DES《05》§15.2) 同步「关闭」→「取消」按钮契约（断言强度未变）。 |
| `tests/test_pet_agent.py` | +14 | `route`/`dispatch` 的 `stage` 参数覆盖 `context['stage']`；不给照旧。 |
| `tests/test_pet_cloud_contract.py` | +45 | `propose` 记/清 `choice_stage`；`dispatch` 对认 `stage` 与不认 `stage` 的 sink 都兼容。 |
| `维护记录/覆盖率基线.json` | 刷新 | 同 15 个定向目标实测（195 条全过）：`modules_total` 691→692、`modules_covered` 134→135（`ui/pet_ask.py` 被触达 16/97）、未触达 557。 |
| `runbook.md` | §11 三处 | 692 模块／135 触达／557 未触达与派生 19.5%，与新基线逐字一致。 |

## 待文档同步清单（不在本轮允许清单，如实留账）

- `docs/stages/S01_剧本准备.md:63` 仍写旧问句「现在制作分镜吗？」：待同步为新问句「要不要我把这份剧本原稿整理成结构化正稿？」并注明全自动档不问（S-10）。
- `docs/process/三虎框架评估.md:21` 半自动审批语义段：待补记付费步骤先弹「是/否」小窗、被拒记集合且「继续」/切档复问的裁决（S-05）。

## 三个基线数

- 默认冒烟基线：未单跑 `smoke_test.py`（无参）；卡面只要求 `--architecture`，实测 708 条 OK。如实记「未运行」。
- 架构门禁当轮实际：708 条，失败集合 0 项（改前未采；本树实测全绿）。
- 全量回归 `--all --safe`：未跑（分支车道不累计）。

## 提交状态

- `dev.py claim` → 轮次号 **4489**（R4479 草稿未随迁移入本树，按新号写本结果文件）。
- 提交命令：`dev.py commit -m "R4489: SANHU-FIX-2 三虎提问部件 pet_ask、页面问句带阶段与半自动付费确认(S-03/S-05/S-10)" ui/pet_ask.py ui/pet_ui_stages.py ui/pet_ui_voice.py ui/pet_cloud.py ui/pet_ui_support.py pet_agent.py tests/test_pet_ui.py tests/test_pet_agent.py tests/test_pet_cloud_contract.py tests/architecture/_layers.py 维护记录/覆盖率基线.json runbook.md tasks_round/tasks_round_4489_result.md --tests pet_ui pet_agent pet_cloud sanhu_mode stage_command_contract`
- commit hash 以 `git log` 为准。

## 没有验证的地方

- 真实桌面人工看屏未做（隐藏桌面 Tk 单测覆盖弹窗回切、问句路由与付费裁决）。
- 先红输出未在本树复采（见上节说明），上一尝试的先红原文随旧工作树草稿，未核实。
- 文档同步两项见清单，待后续文档轮。
