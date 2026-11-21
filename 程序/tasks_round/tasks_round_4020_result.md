# R4020 — CHT-1 parse() 加「对话口径」：R4009 收尾提交
<!-- round-evidence: {"commit_base": "959d975b", "credential_hits": 0, "evidence_sha256": "cad8f2726ca46f15", "exit": 0, "failed": 0, "passed": 19, "round": 4020, "tests": "run_selftests.py -k skill_note_render"} -->

## 三问

1. **类型**：功能轮（《对话区排版接入任务书》CHT-1）。本轮是 R4009 的收尾：代码与测试在 R4009 已按卡写好并自验全绿，当时唯一缺口是 REQ-S01-99 等编号未进 `docs/stages/S01_剧本准备.md`；主控已把 REQ-S01-99/100、DES-S01-99/100 合入本车道，本轮只复跑验收并提交，代码与测试未再改动。
2. **测试**：跑了，任务卡五条验收命令全部复跑（结果见下）。三个基线：默认冒烟 9/9 通过；架构门禁 685 条全绿、失败集合为空（R4009 唯一失败的 `test_tests_do_not_reference_unknown_requirements` 本轮通过）；全量未跑（执行者不跑全量，由主控合入时补跑，`full-safe-receipts.json` 无变化）。
3. **欠账**：少了。R4009 留下的「CHT-1 代码与测试已写好但未提交」这笔欠账本轮清零；`test_skills` 里 2 条与本卡无关的既有红保持原样（主干本来即红），未新增欠账。

## 改动文件

- `ui/skill_note_render.py`（R4009 写好的实现，本轮未再改动）
- `tests/test_skill_note_render.py`（R4009 新增的 `ChatProfileTests` 9 条用例，已有用例一字未改，本轮未再改动）
- `tasks_round/tasks_round_4020_result.md`（本文件）

`git diff --stat` 确认工作树改动只有前两个文件（+177/-8，测试文件为纯追加）。

## 验收命令逐条结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py %TEMP%\cht1_green.txt . -- PY -B -m unittest tests.test_skill_note_render tests.test_ui_reading_density -v` | Ran 27 tests，OK（exit 0）：render 19 条（含 9 条新用例）＋density 8 条全绿 |
| `PY -B -m unittest tests.architecture.test_layers tests.architecture.test_layer_relations tests.architecture.test_complexity_ratchet tests.architecture.test_requirement_traceability -v` | Ran 41 tests，OK（exit 0）；R4009 唯一失败的 REQ 追踪守卫用例本轮通过 |
| `PY -B smoke_test.py` | 通过 9 项、失败 0 项（exit 0） |
| `PY -B smoke_test.py --affected skill_note_render` | 选中 3 个测试文件共 156 条；test_skill_note_render 19/19、test_ui_reading_density 8/8 全绿；exit 1 只因 `test_skills` 中 2 条与本卡无关的既有红：`RegistryTests.test_a_temp_program_does_not_blank_out_the_default_registry`（`assertEqual(real.count(), 73)` 实测 71）与 `RegistryTests.test_skill_distribution_matches_the_split_script_flow`（`assertEqual(reg.count(), 73)` 实测 71）。改前基线即红，主控已决定不算本卡失败；未改 `tests/test_skills.py` 与技能目录 |
| `PY -B smoke_test.py --architecture` | Ran 685 tests，OK（exit 0），失败集合为空 |

## 做法说明、改前失败输出、提交前自查

均见 `tasks_round_4009_result.md`，本轮代码未变、结论沿用：

- **做法与先红后绿**：该文件「已做的工作」「改前基线与先红证据」两节——9 条新用例实现前全 ERROR（`CHAT` 常量与 `profile` 参数不存在），实现后全绿；说明栏 note 口径逐片段与改前一致。
- **提交前自查**（code-review 两轴）：该文件末节——Standards 轴只改允许文件、无新依赖、函数规模低于棘轮；Spec 轴接口契约（常量、签名、C1–C5 五条差别、异常免疫、note 口径不变）逐项对得上。
