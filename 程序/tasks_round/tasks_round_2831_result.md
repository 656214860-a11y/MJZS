# R2831 结构治理轮结果：剧本准备轮棘轮收口——模块/类/函数拆分、循环依赖、静默吞错与口径基线
<!-- round-evidence: {"commit_base": "5d680418", "credential_hits": 0, "evidence_sha256": "0a374f15840eaf4f", "exit": 0, "failed": 0, "passed": 28, "round": 2831, "tests": "run_selftests.py -k test_idea_send_gate test_writing_unconfirm test_preparation_parallel"} -->

- 轮次类型：结构治理轮（§3.3，范围 ≤3 个模块族：剧本准备写作链 + 桌面页两簇弹窗 + 静态门禁配套）。
- 触发：R2813 后 `local_ci.py exit` 静态门禁红——`desktop_idea_chat.py` 1081>1000、`writing_api.py` 1403>1372、`writing_api._preparation_step` 161>150、`ui_usage_detail.py` 静默吞错未登记；复跑又暴露 `_WritingPage` 703>600、覆盖率基线口径 372≠374、`writing_api ↔ writing_preparation_ledger` 循环依赖、`desktop_writing_page` 数字 pady、`writing_quality.adopted_quality` 未登记裸 `json.loads`、runbook §11 口径数字滞后。按棘轮规则「拆模块不抬上限」收口。

## 改动

- `desktop_idea_send_gate.py`（新，L4）：从 `IdeaChatMixin` 迁出发送键实时门禁一簇（`refresh_idea_send_state`/`_apply_idea_send_state`/`_idea_live_missing`/`_idea_live_attachment_fields`），方法体未改；`desktop_idea_chat.py` 继承该 mixin，998 ≤ 1000。
- `desktop_writing_snapshots.py`（新，L4）：从 `_WritingPage` 迁出「历史快照／对比」与「按段落采用」四个弹窗方法，方法体未改；`_WritingPage` 继承 `WritingSnapshotsMixin`，575 ≤ 600。顺带修复快照弹窗里 `padx=SPACING`（dict 误传）与裸 `pady=2` → token 取值（§2.4 规则 34）。
- `writing_preparation_ledger.py`：收进 `PREPARATION_STAGES`／`_PREPARATION_STAGE_WORDS`／`_preparation_stage_alias` 常量与 `_preparation_work_index`／`_preparation_draft_is_parallel` 等草稿路由原语；`writing_api.py` 以同名 import 继续转发，`writing_unconfirm` 等 `from writing_api import` 调用点不变，`writing_api.py` 1331 ≤ 1372、`_preparation_step` 150 ≤ 150；`ledger` 不再 import `writing_api`，循环依赖消除。
- `ui_usage_detail.py`：`except Exception: pass` → `app_logging.swallowed()`（R2774 引入的未登记吞错，按登记口径收口）。
- `writing_quality.py`：`adopted_quality` 报告读取改 `file_cache.read_json`，消未登记裸 `json.loads`。
- `tests/architecture/_layers.py`：登记 `desktop_idea_send_gate`、`desktop_writing_snapshots` 两个 L4 新模块。
- `维护记录/覆盖率基线.json`：按 §11 口径重跑 `scripts/coverage_report.py`（9 组定向用例 97 条全过后写入），模块口径 372→374；`runbook.md` §11 同步「374 个／其余 313 个」。

## 三问

- 本轮属于 §3.3 结构治理轮。
- 测试跑了：`smoke_test.py --affected`（9 个改动模块）9/9 全绿，47 测试文件含全部消费者（test_idea_send_gate、test_writing_unconfirm、test_preparation_parallel、test_writing_quality、test_writing_edited_restart 等），0 红；`--architecture` 466 条中除 `test_round_baselines.test_round_number_continuous` 外全绿——该红为分支固有欠账（`project_status.md` 仅 master 可提交，当前抬头 2775 < 最新结果 2813+1），合并轮抬头由 `merge_round.py` 推进到 R<N>+1 时自然闭环；`test_coverage_baseline` 复跑 5/5 绿。
- 欠账少了：静态门禁 6 类红项收口 5 类，余下轮次基线一项随合并轮闭合。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
