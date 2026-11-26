# tasks_round_4494_result — REL-09-SYNC 全自动档付费步骤一次一授权护栏与三虎五类配额接线（N769/N796 闭环）
<!-- round-evidence: {"commit_base": "377cd201a", "credential_hits": 0, "evidence_sha256": "d8144215ccd0db9c", "exit": 0, "failed": 0, "passed": 876, "round": 4494, "tests": "run_selftests.py -k pet_agent budget skill_budget pet_ui"} -->

- 本轮属于 §3.1 功能轮（REL-09-SYNC 卡面 W2：基于 master 377cd201a，兼顾已合入的 SANHU-FIX-2 pet_ask 半自动机制，实现全自动档付费步骤授权护栏，一次闭环退回项 N769 P1 与 N796 P2）。
- 测试跑了吗、三个基线过了吗：跑了。卡面 3 条验收命令退出码均 0——`run_selftests.py -k pet_agent budget skill_budget`（234 条 0 红）；`run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（34 条 0 红）；`smoke_test.py --architecture`（708 条 OK）。另按卡面加跑 `run_selftests.py -k pet_ui`（642 条 0 红，SANHU-FIX-2 半自动零回归）。
- 欠账少了吗：上一尝试 codex/rel-09（R4262，d90630966）被退回的两个缺口一次闭环——N769（Token 检查改用当次估算消耗，剩余 ≤0 或 < 估算都不弹窗直接转人工，覆盖 0/1 边界）；N796（确认框四要素齐备：步骤名＋当次数量／秒数原单位＋估算 Token＋剩余额度，并声明授权仅本次有效）。无新增欠账。

## 先红 → 后绿

### 先红原文（本树实测：先写测试后跑 `-k pet_agent budget skill_budget`，exit 1）

```
共 234 条用例，4.5 秒；2 个文件有红

### test_pet_agent（1 条红）

===== test_auto_runs_paid_steps (test_pet_agent.ApprovalTests.test_auto_runs_paid_steps) =====
AssertionError: True is not false : 全自动档付费步骤授权前绝不放行

### test_pet_agent（11 条红）

===== test_a_broken_dialog_counts_as_unauthorized =====
AssertionError: Lists differ: ['assets'] != []
===== test_authorized_paid_stage_spends_quota_and_dispatches =====
AssertionError: 0 != 1 : 先问一句再放行
===== test_no_answer_within_the_wait_is_unauthorized =====
AssertionError: Lists differ: ['assets'] != []      （该条中间行在会话日志中截断，断言同型，实测红）
===== test_refusal_pauses_the_chain_and_never_dispatches =====
AssertionError: Lists differ: ['assets'] != [] : 没授权绝不派发
===== test_start_stage_prefers_the_desktop_authorize_paid_stage =====
AssertionError: 0 != 1
===== test_the_authorization_is_valid_for_one_step_only =====
AssertionError: 0 != 2 : 一次一授权：第二个付费步骤要再问一遍
===== test_the_dialog_lists_all_four_facts_and_the_one_step_rule =====
AssertionError: 0 != 1
===== test_token_edge_blocks_the_step_without_a_dialog (used=2000000) =====
AssertionError: Lists differ: ['assets'] != []
===== test_token_edge_blocks_the_step_without_a_dialog (used=1999999) =====
AssertionError: Lists differ: ['assets'] != []
===== test_the_desktop_authorize_paid_stage_is_the_real_path =====
AttributeError: '_BridgeFakeDesktop' object has no attribute 'authorize_paid_stage'

Exit code: 1
```

### 改后绿（本树实测尾部）

```
run_selftests.py -k pet_agent budget skill_budget
共 234 条用例，4.0 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED        （exit 0）
```

## 有意契约变更说明（§2.4）

- `tests/test_pet_agent.py` `ApprovalTests.test_auto_runs_paid_steps`：卡面明确要求 auto 档付费动作与 semi 同口径——授权前 `run=False, confirm=True`。原断言「全自动档付费步骤直接放行」按有意契约变更改为断言 `confirm=True`、`run=False`，理由文案「全自动：付费步骤需您点一下确认」。semi 档断言与文案逐字未动（`LEVEL_NAMES['semi']='半自动'`，`pet_agent.py:35`）。
- 桩宿主回退是设计内行为而非契约弱化：`pet_ui_stages._authorize_paid_stage` 在桌面没有 `authorize_paid_stage`（自检 FakeDesktop，`tests/test_pet_ui.py` 不在允许清单、一行未动）时回退调用同一份实现 `skill_budget.paid_stage_guard`——同口径问一句、记一格、开开关；`-k pet_ui` 642 条零回归佐证 SANHU-FIX-2 半自动与旧 auto 用例均未破坏。

## 3 条验收命令＋pet_ui（全部 exit 0，尾部原文）

```
..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_agent budget skill_budget
共 234 条用例，4.0 秒；0 个文件有红        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage
共 34 条用例，1.5 秒；0 个文件有红        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture
Ran 708 tests in 356.209s
OK
✅ 架构治理测试：tests/architecture        （exit 0）

..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_ui
共 642 条用例，198.7 秒；0 个文件有红        （exit 0）
```

## git diff --numstat 原文

```
3	3	"程序/docs/stages/S10_视频生成.md"
93	1	"程序/orchestrator/skill_budget.py"
2	2	"程序/pet_agent.py"
212	1	"程序/tests/test_pet_agent.py"
13	0	"程序/ui/desktop_pet_bridge.py"
19	19	"程序/ui/pet_ui_stages.py"
```

（numstat 原始输出为八位组转义路径，此处按可读写回中文名；行数原样。）

## 改动表

| 文件 | 改动 | 内容 |
| --- | --- | --- |
| `pet_agent.py` | +2/−2（仍 1046 行上限内） | `Agent.approve`：付费动作判定 `level == 'semi'` 改为 `level in ('semi','auto')`，auto 档付费同样 `run=False, confirm=True`；`confirmed=True` 放行路径不变；semi 文案逐字不变。 |
| `orchestrator/skill_budget.py` | +93/−1 | 文件尾 REL-09 共用实现块（L3 是两侧都进得来的唯一落点：pet_ui_stages 已到 1202 行体量上限，bridge→pet_ui_stages 反向 import 会成 L4→L4 环）：`PAID_STAGE_KINDS`（assets→image/生图、video→video/视频、audio→voice/配音）、`PAID_STEP_TOKENS=500`（正整数安全默认估算）、`PAID_STEP_STEPS`（原单位数量）、`paid_quota_text`（阶段配额与 Token 各列 remaining/limit）、`paid_stage_guard`（先 `sync_tokens` 再按当次估算查配额→见底不弹窗直接 spend/pause+stage.failed 转人工；四要素确认框仅一次有效；拒绝/异常/超时按未授权 pause+stage.failed；授权后 `agent.spend` 记账并校验 `verdict['ok']`，越线同样转人工；通过才 `auto_variable(var).set(True)`）、`run_stage_kick`（自 `start_stage` 抽出的派发与失败收口，宿主无关）。 |
| `ui/desktop_pet_bridge.py` | +13/−0 | `authorize_paid_stage(stage, var=None)` 薄委托 `skill_budget.paid_stage_guard(getattr(self,'pet',None), stage, var)`；新增 `import orchestrator.skill_budget`（L4→L3 合规，无新同层边）。 |
| `ui/pet_ui_stages.py` | +19/−19（净零，仍恰 1202 行） | `start_stage`：`level=='auto' and stage in stage_flow.PAID_STAGES` 走 `_authorize_paid_stage`；其余含 semi 付费照旧 `pet_ask.approve_stage`（SANHU-FIX-2 未动）；派发块抽为 `skill_budget.run_stage_kick`；新增 `_authorize_paid_stage`（桌面有桥走桥、桩宿主回退同一份 guard，返回 (放行, 人话) 与 approve_stage 同形状）。 |
| `tests/test_pet_agent.py` | +212/−1 | 新增 `AutoPaidAuthorizationTests`（11 用例）：授权通过记一格配额＋派发＋开自动开关；真桌面接缝路径；一次一授权；拒绝/弹窗抛错/超时一律 pause+stage.failed 不派发；阶段配额耗尽不弹窗直转人工；Token 0/1 边界（used=limit 与 limit−1）不弹窗不派发；确认框四要素＋仅本次有效文案断言。`test_auto_runs_paid_steps` 契约更新见上节。 |
| `docs/stages/S10_视频生成.md` | +3/−3 | REQ-S10-05、DES-S10-05、IF-S10-47 同步为「semi 弹 pet_ask 半自动确认；auto 经 desktop.authorize_paid_stage→skill_budget.paid_stage_guard 一次一授权，未授权/见底即 pause+stage.failed 不派发」口径。 |

## 三个基线数

- 默认冒烟基线：未单跑 `smoke_test.py`（无参）；卡面只要求 `--architecture`，实测 708 条 OK。如实记「未运行」。
- 架构门禁当轮实际：708 条，失败集合 0 项（改前未采；本树实测全绿，含 `test_class_size_does_not_grow` 体量门——PetStagesMixin 未超登记上限）。
- 全量回归 `--all --safe`：未跑（分支车道不累计）。

## 提交状态

- `dev.py claim` → 轮次号 **4494**。
- 提交命令：`dev.py commit -m "R4494: REL-09-SYNC 全自动档付费步骤一次一授权护栏与三虎五类配额接线(N769/N796闭环)" pet_agent.py orchestrator/skill_budget.py ui/desktop_pet_bridge.py ui/pet_ui_stages.py tests/test_pet_agent.py docs/stages/S10_视频生成.md tasks_round/tasks_round_4494_result.md --tests pet_agent budget skill_budget pet_ui`
- commit hash 以 `git log` 为准。

## 没有验证的地方

- 真实桌面人工看屏未做；隐藏桌面 Tk 单测覆盖授权闸、配额记账、Token 边界与开关置位。
- `PAID_STEP_TOKENS=500` 为卡面允许的正整数安全默认估算；真实消耗以派发后台账为准（`paid_stage_guard` 先 `sync_tokens` 再查）。
- 确认框断言的是四要素文案字段齐备（步骤名／约 1 次生图／预计消耗 Token／生图与 Token（每天）remaining-limit／授权只对这一次步骤有效），真实弹窗样式未验。
- 桩宿主回退路径与真桥路径共用同一份 `paid_stage_guard`；两路径都有用例覆盖，但真桥在真实 Desktop 组合下的端到端派发未人工验。
