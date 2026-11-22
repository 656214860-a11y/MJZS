# R4009 — CHT-1 parse() 加「对话口径」：前置未满足，按 §4.6 停止

## 三问

1. **类型**：功能轮（《对话区排版接入任务书》CHT-1）。因任务卡前提在本树不成立，按 §4.6 停下，只提交本结果文件。
2. **测试**：跑了，先红后绿流程已走完——9 组新用例先红（`CHAT` 常量与 `profile` 参数不存在），实现后全绿；说明栏口径输出与改前一致（10 条旧用例未改且全过、T8/T9 逐片段相等）。三个基线：默认冒烟 9/9 通过；架构门禁 685 条、失败集合 = {`test_requirement_traceability.test_tests_do_not_reference_unknown_requirements`}（唯一失败，原因见下）；全量未跑（执行者不跑全量，`full-safe-receipts.json` 无变化）。
3. **欠账**：没有新增也没有减少。CHT-1 的代码与测试已按卡写好并验证，但留在工作树未提交；等主控补齐前置后直接续跑。

## 停下的原因（§4.6：任务卡条款互相矛盾 / 需改允许范围外的文件）

任务卡三条要求在本树无法同时成立：

- 测试一节强制「docstring 写 REQ-S01-99」；
- 禁止事项写明「不改 docs/stages/S01_剧本准备.md」，且允许修改文件只有 `ui/skill_note_render.py`、`tests/test_skill_note_render.py`、本结果文件；
- 验收命令含 `tests.architecture.test_requirement_traceability`，其守卫 `test_tests_do_not_reference_unknown_requirements` 拒绝测试引用 `docs/stages` 里不存在的编号。

实测：`REQ-S01-99`、`REQ-S01-100`、`DES-S01-99`、`DES-S01-100` 只存在于尚未合入的 taskbooks-batch3 工作树的 `docs/stages/S01_剧本准备.md`（该文件 25、26、144、145 行）；本工作树与 master（95c9f7b）的 `docs/stages/` 全部文件里都没有这些编号。要让守卫过，只能往阶段文件补需求行——超出允许修改范围，也会与 taskbooks-batch3 待合入的同名条目冲突。

## 失败报告（§4.6 格式）

```yaml
失败报告:
  任务卡: CHT-1
  轮次: R4009
  停在哪一步: 验收命令第 2 条（架构单测里的需求追踪守卫）
  命令: PY -B -m unittest tests.architecture.test_layers tests.architecture.test_layer_relations tests.architecture.test_complexity_ratchet tests.architecture.test_requirement_traceability -v
  退出码: 1
  关键输出: |
    FAIL: test_tests_do_not_reference_unknown_requirements (tests.architecture.test_requirement_traceability.RequirementTraceabilityTests.test_tests_do_not_reference_unknown_requirements)
    Traceback (most recent call last):
      File "D:\漫剧制作助手\.agents\worktrees\chat-render\程序\tests\architecture\test_requirement_traceability.py", line 152, in test_tests_do_not_reference_unknown_requirements
        self.assertEqual(unknown, [], '测试引用了阶段文件里不存在的编号')
    AssertionError: Lists differ: ['REQ-S01-99'] != []
    First list contains 1 additional elements.
    First extra element 0:
    'REQ-S01-99'
    - ['REQ-S01-99']
    + [] : 测试引用了阶段文件里不存在的编号
    ----------------------------------------------------------------------
    Ran 41 tests in 42.363s
    FAILED (failures=1)
  试过的做法: [
    确认 REQ-S01-99/100、DES-S01-99/100 在本树 docs/stages 全部文件与 master:程序/docs/stages/S01_剧本准备.md 中均不存在，只在未合入的 taskbooks-batch3 工作树里有,
    完整跑 smoke_test.py --architecture（685 条）确认失败集合只有这一个用例，实现本身无架构问题,
    核对守卫实现 tests/architecture/test_requirement_traceability.py：它按正则扫描 tests/*.py 里的 REQ-Sxx-nn 字样，无法在不动阶段文件的前提下绕过]
  已提交: 本轮仅本结果文件一笔提交，提交号以 git log -1 --format=%h -- 程序/tasks_round/tasks_round_4009_result.md 查询
  工作树状态: 2 行（ui/skill_note_render.py 与 tests/test_skill_note_render.py 两处按卡写好的修改未提交）
  判断: 代码与测试已就绪且自验全绿，唯一缺口是 REQ-S01-99 等编号尚未合入 docs/stages，属前置未满足
  需要主控决定: 先把 S01 阶段文件的 REQ/DES 条目合入本车道（或与任务书一起合入 master 后重跑本卡），还是授权本卡在阶段文件补写同样条目
```

另有一条与本卡无关的既有红：`smoke_test.py --affected skill_note_render` 会带入 `test_skills`，其中 2 条 `RegistryTests` 断言 `reg.count()==73` 实测 71——改前基线即如此（未改的测试文件、与排版无关），即使 REQ 前置补齐，该验收命令仍会因此失败，一并报给主控。

## 已做的工作（留在工作树、未提交）

- `ui/skill_note_render.py`：新增常量 `NOTE='note'`、`CHAT='chat'`、`LIST_L2='list_l2'`、`LIST_L3='list_l3'`；`parse(markdown, *, profile=NOTE)` 加 keyword-only 参数，chat 口径实现 C1–C5（不删文件头、不识别提示前缀、编号列表保留 `数字. `、列表按缩进栈分层 `LIST/LIST_L2/LIST_L3`、块间空行并成一个 `("\n",(BODY,))` 且标题/分隔线相邻与相邻列表项不发）；`_LIST` 正则加一个捕获组取原记号；`apply()` 未动，profile 传其他值一律按 note。
- `tests/test_skill_note_render.py`：文件末尾新增 `ChatProfileTests`（9 个方法对应 T1–T9，docstring 均含 REQ-S01-99）；已有用例一个字未改（`git diff` 只有追加）。

## 改前基线与先红证据

改前（`run_selftests.py -k note_render reading_density test_skills`，共 147 条）：

- test_skill_note_render 10/10、test_ui_reading_density 8/8、test_skills 129 条含 2 条旧红（`test_a_temp_program_does_not_blank_out_the_default_registry`、`test_skill_distribution_matches_the_split_script_flow`，均 `71 != 73`）。

新用例先红（实现前，隐藏桌面跑 `unittest tests.test_skill_note_render`，19 条中 10 条旧用例 ok、9 个新用例全 ERROR）：

```text
ERROR: test_t1_chat_keeps_opening_separator_and_body ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t2_chat_treats_hint_prefix_as_body        ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t3_chat_keeps_ordered_list_numbers        ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t4_chat_list_nests_by_indent              ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t5_chat_list_stack_cleared_by_non_list_lines ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t6_chat_blank_line_rules                  ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t7_chat_malformed_inputs_do_not_raise     ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t8_table_identical_across_profiles        ... AttributeError: module 'ui.skill_note_render' has no attribute 'CHAT'
ERROR: test_t9_unknown_profile_falls_back_to_note     ... TypeError: parse() got an unexpected keyword argument 'profile'
Ran 19 tests in 0.452s — FAILED
```

## 验收命令逐条结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py %TEMP%\cht1_green.txt . -- PY -B -m unittest tests.test_skill_note_render tests.test_ui_reading_density -v` | Ran 27 tests，OK（exit 0）：19 条 render（含 9 条新用例全绿）＋8 条 density |
| `PY -B -m unittest tests.architecture.test_layers tests.architecture.test_layer_relations tests.architecture.test_complexity_ratchet tests.architecture.test_requirement_traceability -v` | Ran 41 tests，FAILED (failures=1)：唯一失败为 REQ-S01-99 未登记（exit 1） |
| `PY -B smoke_test.py` | 通过 9 项、失败 0 项（exit 0） |
| `PY -B smoke_test.py --affected skill_note_render` | 选中 3 文件共 156 条：test_skill_note_render 19/19、test_ui_reading_density 8/8、test_skills 含与基线相同的 2 条旧红 → 门禁 exit 1 |
| `PY -B smoke_test.py --architecture` | Ran 685 tests，FAILED (failures=1)：失败集合 = {test_tests_do_not_reference_unknown_requirements}，原因同上（exit 1） |

## 提交前自查（code-review 两轴，本会话内完成）

- **Standards**：只改允许的 2 个 `.py`；无新文件、无新依赖、无第三方库；parse 层不依赖 Tk 不读写文件；`_list_level`/`_list_marker`/`_chat_blank` 三个小函数分担分支，`parse` 约 100 行低于棘轮 150（`test_complexity_ratchet` 在架构单测中通过）；复用已有 `_inline_fragments`/`_plain_inline`，无重复实现。
- **Spec**：接口契约逐项对得上——常量名与签名一致；note 口径逐片段与改前相同（10 条旧用例原样全过＋T8/T9 片段相等＋density 8/8＋test_skills 无新增红）；C1–C5 五条差别各有用例锚定；任何输入不抛异常（T7）；注释行不算块、空行不清栈、非空非列表行清栈均按卡面规则实现。
- 实现判断无需再改；阻塞只在文档前置。
