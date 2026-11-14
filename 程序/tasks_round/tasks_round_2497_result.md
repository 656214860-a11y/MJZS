# R2497 结果：修复自然剧本节拍表被「字段表格」闸门误判，导致无法采用此剧本

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。根因是代码偏离需求：`script_contract.natural_script_violations` 里「字段表格」检测用 `(?m)^\s*\|.+\|\s*$` 拦截**任意** Markdown 管道表格，而 REQ-S01-16（R1695）明确规定自然剧本每集正文前**必须**带「本集节拍表」（`| 场次 | 节拍＃ | 情绪关键词 | 服务的剧本动作 | 权重 | 强度 |` 六列，本身就是管道表格）。两者冲突，导致带节拍表的自然剧本被 `is_natural_script` 判为不合格，从 `natural_script_paths` 中剔除，右键「采用此剧本」时 `selected_workspace_document` 找不到该文件，报「当前选择的剧本文档已不存在，请刷新页面」。修复代码，需求不变。

2. **测试跑了吗、三个基线过了吗？**
   - 先红后绿：`tests/test_script_contract.py` 新增两条用例，改动前 `test_beat_table_is_not_a_forbidden_field_table` 红（`('字段表格',) != ()`），`test_foreign_pipe_table_is_still_rejected` 绿；改动后两条全绿。
   - 定向：`NaturalScriptSaveTests` 4/4 通过（exit 0）；`test_script_contract`＋`test_script_workspace_service`＋`test_script_structure` 共 99 条，仅 1 条失败 `test_the_audit_covers_every_script_skill`，该失败为**既有**技能登记漂移（`script-forging`／`编剧技能集` vs `短剧编剧搭子`），与本轮无关，未改。
   - 默认冒烟／架构门禁／全量：**未完整运行**。`smoke_test.py --affected script_contract` 跑 403 秒退出码 1，根因是**本工作树缺 submodule** `程序/skills/00全流程SKILL/AIGC创作全流程`（gitlink 160000 未检出，`sd-decision-engine/SKILL.md` 不存在），触发 `workflow_settings.freeze_skills` 抛「SKILL 引用缺失」，属环境问题非本轮引入。
   - 真实复现：`D:\漫剧下载\项目\摄影侠_20260930\01剧本准备\...\摄影侠_自然剧本_Google_20261114.md`（含 218 行、带节拍表）修复前 `natural_script_violations` 返回 `('字段表格',)`、不在 `natural_script_paths`；修复后返回 `()`、已包含于 `natural_script_paths`。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；本轮修复一个真实阻断（带节拍表的自然剧本无法采用）。既有欠账（技能登记漂移、submodule 未检出）登记为已知环境问题，不在本轮扩大范围。

## 根因与复现

- 触发路径：剧本准备页右键「采用此剧本」→ `desktop_writing_page.adopt_script` → `stage_execution_service.adopt_natural_script` → `script_workspace_service.adopt_natural_script` → `selected_workspace_document(script_contract.natural_script_paths(root), source_path)`。
- `natural_script_paths` 只收录通过 `is_natural_script`（即 `natural_script_violations` 为空）的文件；带节拍表的自然剧本因「字段表格」被剔除，`selected_workspace_document` 抛 `ValueError('当前选择的剧本文档已不存在，请刷新页面。')`。
- 而列表页 `iter_script_documents` 对「项目剧本」分类无条件列出该文件，于是「列表可见、采用报不存在」的自相矛盾。

## 改动清单

- `程序/script_contract.py`：
  - 新增 `_BEAT_TABLE_HEADER` 正则，按 REQ-S01-16 规定的六列表头识别节拍表（场次／节拍＃／情绪关键词／服务的剧本动作／权重／强度）。
  - 新增 `_has_foreign_field_table(value)`：逐行扫描，节拍表整块（表头＋分隔行＋数据行，直到空行或非 `|` 起始行）豁免；其余任何 `| … |` 表格行仍判「字段表格」。
  - `natural_script_violations` 的「字段表格」检测由 `re.search` 改为调用 `_has_foreign_field_table`。
- `程序/tests/test_script_contract.py`（`NaturalScriptSaveTests`）：
  - `test_beat_table_is_not_a_forbidden_field_table`：带节拍表的自然剧本 `natural_script_violations` 返回空、`save_natural_script` 可落盘（REQ-S01-16 锚点）。
  - `test_foreign_pipe_table_is_still_rejected`：分镜表／镜头表等其它字段表格仍被「字段表格」拦截，豁免不放大。

## 验证

- 改动前（红）：
  ```
  FAIL: test_beat_table_is_not_a_forbidden_field_table
  AssertionError: Tuples differ: ('字段表格',) != ()
  ```
- 改动后（绿）：`NaturalScriptSaveTests` 4/4 OK（exit 0）；`test_foreign_pipe_table_is_still_rejected` 通过。

## 未运行项与说明

- 默认冒烟、架构门禁、全量未完整通过：受本工作树 submodule 未检出影响（`AIGC创作全流程` 为空目录），非本轮代码引入；须在 submodule 就绪的树内补跑。
- 未改动需求/设计文档（代码偏离需求，需求本身不变，符合 §2.7 第 3 条「前者修代码」）。
