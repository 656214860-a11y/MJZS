# tasks_round_4024_result
<!-- round-evidence: {"commit_base": "5afe189a", "credential_hits": 0, "evidence_sha256": "77d94fba8840870e", "exit": 0, "failed": 0, "passed": 28, "round": 4024, "tests": "run_selftests.py -k skill_note_render"} -->

> 轮次：R4024　｜　任务卡：CHT-2（《对话区排版接入任务书》§4.2）　｜　车道：codex/chat-render

## 开头三问

- **本轮属于哪种类型**：§3.1 功能轮。文档已由主控先写（REQ-S01-99 / DES-S01-99），本卡不改文档。
- **测试跑了吗、三个基线各是什么结果**：跑了。默认冒烟 9/9 通过（当轮第 10 轮实测 9 项）；架构门禁当轮实测 685 条全过、失败集合为空；全量未跑（任务卡 §4.0 第 7 条：执行者不跑全量，由主控合入时触发，以 `full-safe-receipts.json` 为准）。
- **欠账少了吗**：没有新增欠账；本卡把任务书 §3 的 CHT-B2（排版模块只能整框重画）补上按位置插入能力，属既定拆解，不算欠账变化。

## 改动文件

- `ui/skill_note_render.py`：新增常量 `CHAT_TAG_PREFIX = 'md_'`；新增 `_chat_tag_specs(left, right)`（对话标签取值表，集中一处，全部取自 `ui_tokens` 的 FONTS/COLORS/SPACING）；新增 `configure_chat_tags(text_widget, *, left=0, right=0)`；新增 `insert(text_widget, index, markdown, *, base_tags=(), left=0, right=0)`。`parse()`、`apply()` 与说明栏标签未动。
- `tests/test_skill_note_render.py`：只新增 `ChatInsertTests` 类（T1–T9，docstring 均写 REQ-S01-99）与 `from ui_tokens import FONTS, SPACING` 一行；已有用例一个字未改。

## 改前的失败输出（先红）

测试先行：新增 `ChatInsertTests` 后在隐藏桌面运行，11 个错误全部是新用例找不到 `insert`（T5 的三个 subTest 各计一条），其余 17 条旧用例全过。输出文件：`%TEMP%\cht2_red.txt`，关键尾部：

```
ERROR: test_t1_insert_appends_with_base_tags (tests.test_skill_note_render.ChatInsertTests.test_t1_insert_appends_with_base_tags)
Traceback (most recent call last):
  File "...\tests\test_skill_note_render.py", line ..., in test_t1_insert_appends_with_base_tags
    render.insert(self.widget, 'end', '**粗** 正文\n- 项', base_tags=('b0',))
AttributeError: module 'ui.skill_note_render' has no attribute 'insert'
（T2–T9 同因，略）
Ran 28 tests in 0.629s
FAILED (errors=11)
```

## 每条验收命令的结果

1. `PY -B scripts\gui_hidden.py "$env:TEMP\cht2.txt" . -- PY -B -m unittest tests.test_skill_note_render tests.test_ui_reading_density tests.test_skills -v`
   - `tests.test_skill_note_render`：28 条全过。
   - `tests.test_ui_reading_density`：8 条全过。
   - `tests.test_skills`：按字面命令 `python -m unittest tests.test_skills` 直跑时报 `ModuleNotFoundError: No module named 'skip_reasons'`——该模块只存在于 `tests/` 下、`程序` 根无门面，`python -m unittest` 的 sys.path[0] 是 `程序` 不含 `tests/`；`run_selftests.py` 第 46–49 行会把 TESTS_DIR 插进 sys.path，所以仓库自有运行器不受影响。此为既有怪癖，与本卡无关，未改测试文件。等价补跑（`PYTHONPATH=tests` 后同一命令）：129 条，127 过、2 条红，均为下述已知旧红。
   - 已知旧红（主控补充第 2 条已声明，主干上本来就红，非本卡失败）：`RegistryTests.test_a_temp_program_does_not_blank_out_the_default_registry` 断言 73 实测 71；`RegistryTests.test_skill_distribution_matches_the_split_script_flow` 断言 73 实测 71。
2. `PY -B -m unittest tests.architecture.test_layers tests.architecture.test_layer_relations tests.architecture.test_complexity_ratchet tests.architecture.test_font_boundary tests.architecture.test_requirement_traceability -v`：44 条全过（末尾有两行「LR-09/LR-10 实测 59 < 基线 60，请下调」棘轮提示，非失败，本卡不动基线）。
3. `PY -B smoke_test.py`：9/9 通过。
4. `PY -B smoke_test.py --affected skill_note_render`：选中 165 条用例（test_skill_note_render、test_ui_reading_density、test_skills），除上述 2 条已知旧红外全过。
5. `PY -B smoke_test.py --architecture`：685 条全过，失败集合为空。

## 提交前自查（code-review 技能两轴，当前会话内完成）

- **分叉点**：`git merge-base master HEAD` = `c3d43a7`；相对分叉点的改动为 CHT-1 已提交部分＋本轮未提交两文件，全部审过。
- **Spec 轴**：`CHAT_TAG_PREFIX`、两个函数签名与 R1–R7 逐条对上任务卡；`md_` 标签集合与取值表逐项核对（标题按 CHT-Q2 缩字号、列表三层和引用、代码块的边距以 left/right 为起点、无 md_body、无字体名/字号/颜色字面量）；`insert` 在 `'end'`/`'1.0'`/任意位置保序、`sel` 恒最高、可编辑状态恢复、空输入返回 `[]`；未改 `desktop_idea_bubbles.py`、`skill_panel.py`；标签名不以 `bubble_` 开头。
- **Standards 轴**：中文 docstring、常量置顶与模块既有风格一致；`insert` 的可编辑状态恢复写法同 `apply()`；`_chat_tag_specs` 是任务卡要求的集中取值处；新增函数均 <150 行；无内联字体元组（test_font_boundary 过）；`parse` 层未新增 Tk 依赖。
- **结论**：未发现问题，无当场需改的项。

## 任务卡要求写进结果文件的其他内容

- **复用留痕**（任务书开头复用要求）：`insert()` 的「先存可编辑状态、normal 下写入、写毕恢复」复用 `apply()` 的既有做法；「写完把 sel 提到最高」复用 `ui/desktop_idea_bubbles.py` `add_bubble` 里 `box.tag_raise('sel')` 的既有做法；边距/字号/颜色一律复用 `ui_tokens`。任务卡 CHT-D1 禁止第三方界面库，故未检索 GitHub 库，Tk 自带 `tag_configure`/`tag_raise`/`insert` 足够。
- **新测试登记**（§4.0 第 11 条）：本轮没有新增测试文件（新用例写在既有 `tests/test_skill_note_render.py` 的 `ChatInsertTests` 类里），`governance/structure.json` 与 `architecture.md` 门禁清单无需登记。
- **函数规模**（§4.0 第 12 条）：`_chat_tag_specs` 约 50 行、`insert` 约 30 行，未触棘轮；`test_complexity_ratchet` 通过。
- **提交**：本文件与两改动文件一并提交，commit hash 见提交后补充。

## 提交记录

- 已提交：本轮一批一笔提交，提交号以 `git log -1 --format=%h -- 程序/tasks_round/tasks_round_4024_result.md` 查询
- 提交后 `git status --short`：为空
