# R1734：结构治理轮——架构门禁登记点从行号改为按内容定位（LINEKEY）

执行者：Codex（中途额度用尽）→ DeepSeek（LINEKEY2 完成代码，三次续做均因供应商中断/额度用尽未交结果文件）→ Claude 补性能修正与本结果文件。

## 按行号登记的门禁（已改）

- `test_unification_ratchet.py` 第四项裸 `json.loads`：`文件:行号` → `文件:作用域:json.loads:AST摘要16位:同键序号`。
- `test_coverage_audit_ratchet.py` 审计 20–26 与 23：`文件:行号` → `文件:作用域:类别:AST摘要:序号`。
- `test_todo_comment_snapshot.py`：快照去掉 `line`，按 `file`（改为相对路径）＋`scope`＋`comment` 比对。

## 迁移前后条数（disposition／reason 逐条一致）

第三项 65→65、层级 35→35、第四项 77→77（74 条原为数字 point）、审计21 11→11、审计24 27→27、审计20 4→4、审计26 3→3，其余 0；TODO 快照 3→3。

## 自证（Claude 在主树真代码上做，做完 git checkout 还原）

- desktop.py 首行插入无关注释：三门禁 12 条全绿（改前同样操作会让 TODO 快照与第四项变红，见 R1733 的 1087→1089）。
- desktop.py 末尾新增 `json.loads` ＋ `# TODO`：`test_bare_json_load_debt_is_a_nonincreasing_subset`、`test_keyword_comments_match_the_reviewed_snapshot` 2 红。
- 夹具：`tests/architecture/test_stable_registration.py` 5 条 OK。

## 耗时（三门禁 12 条）

改前（2e13291a）55.2 秒；DeepSeek 版 69.5 秒（每文件预算作用域区间＋排序全部 Call）；Claude 改为命中才算作用域、先筛 json.loads 再排序后，两条覆盖率用例 30.2→24.3 秒，与改前持平。

## 计数

`smoke_test.py --architecture`：373 条，仅 `test_full_safe_all_is_required_after_eight_source_rounds` 1 红（全量欠账，后台补跑项）。

## 独立验收（Claude）

见上文自证、耗时与计数，均为 Claude 本人在主树实测。
