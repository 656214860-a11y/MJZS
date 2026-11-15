# R2599 结果：修复双重回车（\r\r\n）剧本被「字段表格」闸门误杀，导致无法采用此剧本
<!-- round-evidence: {"commit_base": "4ef75047", "credential_hits": 0, "evidence_sha256": "a4dacd905dee3fd7", "exit": 0, "failed": 0, "passed": 61, "round": 2599, "tests": "run_selftests.py -k test_script_contract"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。R2497/R2501 修复后同一症状仍在：用户报告「采用此剧本」仍报
   「当前选择的剧本文档已不存在，请刷新页面」。按规则 32 补复现证据后重新诊断，
   根因与上轮不同：外部工具（Gemini Desktop 落盘）把文件每行写成 ``\r\r\n``
   双重回车，``splitlines``/通用换行把行间伪空行送进 `has_foreign_field_table`，
   节拍表整块豁免遇到伪空行即终止，紧随的分隔行 ``|---|---|`` 被判外来字段表格。
   需求不变，修代码（唯一改动模块 `script_natural_gate`，L0 闸门）。

2. **测试跑了吗、三个基线过了吗？**
   - 先红后绿：`tests/test_script_contract.py` 新增
     `test_beat_table_with_blank_separated_rows_is_still_natural`，改动前红
     `('字段表格',) != ()`，与线上症状完全一致；改动后 `NaturalScriptSaveTests` 5/5 绿。
   - 真实复现：`D:\漫剧下载\项目\摄影侠_20260930\01剧本准备\Google\Gemini desktop\创意_20261107\项目剧本\摄影侠_自然剧本_Google_20261107.md`
     （78931 字节，全部行尾 ``\r\r\n``）。改动前 `natural_script_violations` 返回
     `('字段表格',)`、`natural_script_paths` 为 0；改动后返回 `()`、含 2 份自然剧本，
     `selected_workspace_document` 与 `require_natural_script` 全链路通过。
   - 默认冒烟 8/8 通过。
   - `smoke_test.py --affected script_contract`（`script_natural_gate` 唯一消费者；
     该模块本身无独立测试文件、`--affected script_natural_gate` 命中 0 文件）：
     53 个测试文件 1520 条，**仅 1 条红**
     `test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display`
     （创意回显断言）。已用 `git stash` 在改动前的树上同条件复跑，**同样 1 红**——
     既有/环境性失败，与本轮无关，未改。
   - 架构门禁、全量：未跑（单模块 L0 修复，非跨层/契约变更；分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；闭环 R2497 遗留的同一用户可见阻断。`test_ui_edges` 既有红登记为本轮
   观察项，不在范围内扩修。

## 根因与复现

- 触发路径：剧本准备页右键「采用此剧本」→ `desktop_writing_page.adopt_script` →
  `stage_execution_service.adopt_natural_script` → `script_workspace_service.adopt_natural_script`
  → `selected_workspace_document(script_contract.natural_script_paths(root), path)`。
- `natural_script_paths` 只收录 `is_natural_script` 通过的文件；该文件被判
  `('字段表格',)` 剔除，右键采用时报「当前选择的剧本文档已不存在」。而列表页
  `iter_script_documents` 无条件列出「项目剧本」目录文件，形成「看得见、不能采用」。
- 文件字节级证据：全部行尾为 `\r\r\n`（LF 1582 个全部带前缀 CR，另有 1581 个
  独立 CR）。`str.splitlines` 把 `\r`、`\r\n` 都当行界，`row\r\r\n` → `['row', '']`，
  每个表格行后多出一条空行；`read_text` 通用换行模式同样译成 `\n\n`。
- R2497 的豁免逻辑「表头之后连续 ``|`` 行整块豁免」遇首条空行即终止，下一条
  `|---|---|` 命中外来表格正则 → `字段表格`。

## 改动清单

- `程序/script_natural_gate.py`：
  - 新增 `_BEAT_TABLE_ROW`（恰好 6 单元格／7 个 `|` 的节拍表行）。
  - 节拍表块内遇空行时向前看：下一个非空行仍是六列节拍行则桥接跨过，
    否则块终止——伪空行不杀节拍表，空行之后的异列字段表格仍被拦截。
  - 连续 ``|`` 行的吸收行为与 R2501 保持一致，未收紧。
- `程序/tests/test_script_contract.py`（`NaturalScriptSaveTests`）：
  - `test_beat_table_with_blank_separated_rows_is_still_natural`：按真实文件
    `\r\r\n` 行尾构造正文，断言 `natural_script_violations` 为空、
    `natural_script_paths` 收录该文件、空行后接异列字段表格仍判 `字段表格`（REQ-S01-16 锚点）。

## 验证

- 改动前（红）：
  ```
  FAIL: test_beat_table_with_blank_separated_rows_is_still_natural
  AssertionError: Tuples differ: ('字段表格',) != ()
  ```
- 改动后（绿）：`NaturalScriptSaveTests` 5/5 OK；真实项目文件 violations → `()`，
  `natural_script_paths` → 2 份，`selected_workspace_document` / `require_natural_script` 通过。
- 默认冒烟 8/8；`--affected script_contract` 1520 条 1 红（既有，改动前后同红，证据见上）。

## 未运行项与说明

- 架构门禁、全量未跑：本轮为单 L0 模块修复，不涉分层/契约/删除语义；分支欠账口径见 §5。
- 已知边界：节拍表单元格内若出现未转义的额外 `|`（行内超过 7 个 `|`）或空行之后
  紧跟同为六列的外来表格，仍会误判/漏判；真实文件无此形态，不扩大本轮范围。
- 建议用户侧顺带检查 Gemini Desktop 落盘工具的换行写出（`\r\r\n` 属异常双重回车），
  但应用侧已兼容。
