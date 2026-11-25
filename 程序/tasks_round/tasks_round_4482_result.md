# tasks_round_4482_result — UX-REPLY-AREA 返工：过程与回话区用户标签改敬称「您」过文案门禁
<!-- round-evidence: {"commit_base": "d21866405", "credential_hits": 0, "evidence_sha256": "ba3ee15cced8f07b", "exit": 0, "failed": 0, "passed": 226, "round": 4482, "tests": "run_selftests.py -k stage_reply copy_rules shared_send shared_input part_renderers desktop_compact_layout"} -->

- 本轮属于 §3.2 修复轮（UX-REPLY-AREA 卡面 W3 续跑收尾）：出口 CI 静态门禁 `test_interface_copy_speaks_to_you_with_the_polite_pronoun` 报红，根因是 `ui/stage_reply_area.py:33` `_KIND_LABEL["user"]` 用了非敬称「你」。
- 测试跑了吗、三个基线过了吗：跑了。卡面两条验收命令退出码均 0——定向 `run_selftests.py -k stage_reply copy_rules shared_send shared_input part_renderers desktop_compact_layout`（226 条 0 红，exit 0，含 copy_rules；上轮已跑通，本轮提交时 dev.py 自动复跑并落凭据）；`smoke_test.py --architecture`（708 条 OK，347.9s，exit 0，本轮实测）。
- 欠账少了吗：改前 copy_rules 1 项红 → 改后清零；无新增欠账。

## 改动清单与行数核实

- `ui/stage_reply_area.py`：仅第 33 行 `_KIND_LABEL` 内 `'user': '你'` → `'user': '您'`，总行数不变；`git diff` 仅此一处。

## 先红 → 后绿

### 先红输出（改前，出口 CI 静态门禁原文）

```
FAIL test_interface_copy_speaks_to_you_with_the_polite_pronoun (tests.test_copy_rules.SecondPersonTests): ['ui/stage_reply_area.py:33 你'] != []
```

### 改后绿（两条验收命令）

```
run_selftests.py -k stage_reply copy_rules shared_send shared_input part_renderers desktop_compact_layout
共 226 条用例 0 红 → ALL TESTS PASSED（exit 0）

smoke_test.py --architecture
Ran 708 tests in 347.920s → OK（exit 0）
```

## 三个基线数

- 默认冒烟基线：未单跑 `smoke_test.py`（无参）；卡面只要求 `--architecture` 与定向自检，如实记「未运行」。
- 架构门禁当轮实际：708 条，失败集合 0 项（本轮实测 347.9s OK）。
- 全量回归 `--all --safe`：未跑（分支车道不累计）。

## 提交状态

- `dev.py claim` → 轮次号 **4482**。
- 提交命令：
  `dev.py commit -m "R4482: UX-REPLY-AREA 返工：过程与回话区用户标签改敬称「您」过文案门禁" ui/stage_reply_area.py tasks_round/tasks_round_4482_result.md --tests stage_reply copy_rules shared_send shared_input part_renderers desktop_compact_layout`
- commit hash 以 `git log` 为准。

## 没有验证的地方

- 226 条定向验收为上轮会话跑通结果（exit 0），本轮在 `dev.py commit` 内自动复跑并生成 `tasks_round/evidence/R4482.json` 凭据；本轮未在提交前单独重跑定向命令。
- 真实桌面人工看屏未做（隐藏桌面 Tk 单测覆盖文案与几何）。
