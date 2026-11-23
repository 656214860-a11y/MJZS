# R4158 结果：unknown 预留超时释放（FIX-AUD-SKILL-BUDGET）
<!-- round-evidence: {"commit_base": "6997ae43", "credential_hits": 0, "evidence_sha256": "dc2b536146b4a115", "exit": 0, "failed": 0, "passed": 119, "round": 4158, "tests": "run_selftests.py -k skill_budget budget"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 W7-FIX-AUD-SKILL-BUDGET（波次 W2）；缺陷 AUD-SKILL D2——`finish()` 把执行中途失败的预留置 `unknown`，`reserved()` 把 `unknown` 永久计入占用，全仓库无对账、超时或清扫入口，失败越多额度越少直至误报「额度不够」。车道 `codex/fix-aud-skill-budget`，基准 `6997ae43`。

（二）测试与三个基线：`run_selftests.py -k skill_budget budget` 改前 119 条里 3 条红（均为本卡新增用例），改后 119 条全过，退出码 0。`smoke_test.py --architecture` 700 条全过，退出码 0。默认冒烟与全量未跑。

（三）欠账：D10（Token 按次计）按卡面要求只记录现状、不改，见末节。`reserved` 态预留（reserve 与 finish 之间进程崩溃遗留）仍无超时清扫——卡面范围只含 `unknown`，未扩大。

## 缺陷复现

`orchestrator/skill_budget.py`（改前）：`finish()` 在 `completed=False 且 not_submitted=False` 时置 `state='unknown'`（原 142 行）；`reserved()` 把 `state in ('reserved','unknown')` 全额计入（原 145-147 行）；落盘校验只认四种 state，无时间戳字段（原 210-214 行）。新增 `SkillBudgetUnknownReleaseTests` 4 条用例在未改产品时跑出 3 红，红因即缺陷本身：

- `test_unknown_releases_after_timeout`：`AssertionError: 1 != 0`——时钟推进 32 天后 `reserved('images')` 仍为 1，unknown 永久占额度。
- `test_legacy_unknown_without_timestamp_releases`：`AssertionError: 1 != 0`——无 `unknown_at` 的旧账 unknown 同样永久占额度。
- `test_unknown_stamped_and_still_counts_within_ttl`：`AssertionError: unexpectedly None`——unknown 条目没有 `unknown_at` 时间戳，超时无从判定。
- `test_reserved_and_settled_states_never_expire`：改前即绿（守护用例，锁定 reserved/settled 不受影响）。

## 改了哪些文件

- `orchestrator/skill_budget.py`：
  - :29-31 新增 `UNKNOWN_TTL = 24 * 3600`（unknown 对账窗口一天）。
  - :144-146 `finish()` 落 `unknown` 时补 `entry['unknown_at'] = float(self.clock())`。
  - :149-172 `reserved()` 计数排除已超时 unknown；新增 `_unknown_expired()`（无 `unknown_at` 的旧账视为已超时）与 `_release_expired_unknown()`（超时 unknown 转 `released` 的对账清扫）。
  - :241 `load()` 载入预留账后执行 `_release_expired_unknown()`，下一次写事务把超时 unknown 落盘为 `released`。
- `tests/test_budget.py`：新增 `SkillBudgetUnknownReleaseTests`（:333-395，4 条用例）。
- 本结果文件。

行为边界：`reserved`/`settled`/`released` 三态语义不变；`unknown` 在窗口内（24h）仍照常占额度，超时按未提交释放；公开函数签名未动。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 开工三查 | `status --porcelain` 无输出；`git log -1` = `6997ae43`；分支 `codex/fix-aud-skill-budget` |
| 定向（改前） | 退出码 1；119 条，3 红（`test_budget` 新增用例） |
| 定向（改后） | 退出码 0；119 条；尾部原文：`共 119 条用例，2.5 秒；0 个文件有红` … `ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；尾部原文：`Ran 700 tests in 269.440s` / `✅ 架构治理测试：tests/architecture` / `OK` |
| `scripts\dev.py claim` | 领到 4158 |

改后定向输出尾部原文：

```
  test_skill_budget_send_entries     9 条     1.4 秒

共 119 条用例，2.5 秒；0 个文件有红
最慢 10 路工作单元：
  test_skill_budget_send_entries    1.4 秒 / 9 条
  test_writing_api_output_budget    0.9 秒 / 8 条
  test_skill_context_budget_prestage    0.8 秒 / 19 条
  test_writing_context_budget_guard    0.4 秒 / 15 条
  test_publication_fsync_budget    0.3 秒 / 7 条
  test_idea_attachment_budgets    0.3 秒 / 8 条
  test_budget#1                 0.2 秒 / 16 条
  architecture.test_startup_budget    0.2 秒 / 1 条
  architecture.test_agent_doc_budget    0.2 秒 / 11 条
  test_budget#2                 0.2 秒 / 10 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：52.8 秒

ALL TESTS PASSED
```

## D10 现状（只记录，不改）

Token 额度在 SKILL 编排路径按「次」计、不按真实 token 数：`spend_kind` 对不以 `video.`/`firstframe.`/`asset.`/`edit.export` 开头的工具返回 `tokens`（`infra/model_router.py:226-233`）；`execute()` 预留恒为 `amount=1`（`orchestrator/skill_orchestrator.py:597`）；`finish(completed=True)` 在无 ledger 时 `counters['tokens'] += 1`（`orchestrator/skill_budget.py:141-142`），即每完成一次记 1。仅当 `Budget` 挂 `pet_llm.Ledger` 时 `used('tokens')` 才读台账真实 token（`skill_budget.py:154-158`）；生产调用方 `for_project` 均未传 ledger（`skill_orchestrator.py:900`、`ui/pet_settings_ui.py:461`、`stage_execution_service.py:702`），`spend('tokens', n)` 自身也不计数（`skill_budget.py:180-181`，见 `tests/test_skills.py:435` 注释「Token 那本自己不记：还是台账说了算」）。

## 没有验证的地方

- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面只要求定向＋架构门禁）。
- 真实桌面/三虎链路下 unknown 的端到端表现未验（用例均为临时目录内的账本级验证，未建 Desktop/Tk）。
- `UNKNOWN_TTL = 24h` 为本卡选定值，无既有配置项可调；若审查认为窗口过长/过短需另行裁决。
