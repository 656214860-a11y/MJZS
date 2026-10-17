# R1687 验证基线轮：为阶段 S02 剧本结构补齐 11 条需求锚点测试

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证/基线轮。只新增测试文件与缩减需求锚定基线，未改任何产品代码，不算源码轮。

2. **测试跑了吗？三个基线过了吗？**
   - 定向 `run_selftests.py -k req_anchor_s02 requirement_traceability`：15 条 / 0 红（`test_req_anchor_s02` 11 条、`architecture.test_requirement_traceability` 4 条；其中 `test_baseline_only_shrinks` 与 `test_new_done_requirement_needs_a_test_anchor` 均通过）。
   - 默认冒烟 `smoke_test.py`：8/8。
   - `run_selftests.py -k agents_md`：15 条 / 0 红（新测试文件未引起架构门禁变化，无需登记）。
   - 未跑架构门禁全量与安全全量（本轮仅测试与文档，不算源码轮，不触发全量欠账）。

3. **project_status.md 的欠账少了吗？** 需求锚定欠账减少：`维护记录/需求锚定基线.json` 的 `untested_done` 从 137 条减为 126 条（删除 REQ-S02-01/03/10/11/12/13/14/20/21/22/24 共 11 条）。

## A 改动

- 新增 `tests/test_req_anchor_s02.py`（11 条用例，锚定 REQ-S02-01/03/10/11/12/13/14/20/21/22/24 共 11 条需求）：
  - REQ-S02-01：唯一输入是 S01 被采用的自然剧本——无原稿时 `resolve_script_source` 返回 `None`、`write_structured_script` 抛错且不产出；仅有项目大纲／项目设定／角色卡时不构成输入；有自然剧本时返回该路径。
  - REQ-S02-03：`stage_flow.DEPENDS['script_structure']==('script',)`；S01 失败时 `blockers` 返回 `['script']`、成功时不拦；`stage_parallel` 配置为单 Agent 并行度 1、重试 2 次、`on_exhaust=block`；自动链即使下游被误标完成也回到失败的 `script_structure`（`Auto.next_stage()`）。
  - REQ-S02-10：`pet_llm.Client.ask` 未被调用，正稿标明「本地规则提取／未调用模型」，同输入两遍一致。
  - REQ-S02-11：`skill_templates` 模板六个动作按序固定、无需逐步确认；以 `execute_action` 记录器确认六步依次执行且 `wait_for_user` 不被调用。
  - REQ-S02-12：`structure_script` 输出含「角色／场景／道具档案＋分场剧本」四区与各字段标签（别名、跨集 ID、物理特征、默认服装、换装需求；空间锚点、光照方向、尺度参考；出场角色、情绪基调、起始／结束状态、正文）。
  - REQ-S02-13：原稿声明的别名逐字采用；原稿没有的角色不补；原稿未明确字段标「待确认」。
  - REQ-S02-14：`review_structured_script` 对缺区块给可展示反馈；同一道具多尺寸给出「互相矛盾的尺寸／先改 script_raw.md」并 `approved=False`，`revise_structured_script` 抛 `ValueError`；端到端 `stage_exec._run_script_structure` 在真实六步链上停在重提取、不写出结构剧本。
  - REQ-S02-20：空正文抛错且不落盘；原稿保持不变；注入发布器时 `script_contract` 只由发布器落盘（自己不写目标）；经真实发布器发布后留下来源血缘（原稿相对路径与 sha256）。
  - REQ-S02-21：`is_structured_script` 认「# 结构化剧本＋档案区且来源非大纲／梗概」；原稿删除后 `structured_script_paths` 不再显示该结构稿，文件不被删除。
  - REQ-S02-22：`stage_completion_service.completion_evidence` 在无结构剧本时为 False；只有三份 manifest 时仍为 False；`emit_verified_completion` 未通过不发出事件，出现合格结构剧本后才发 `stage.completed`。
  - REQ-S02-24：`canonical_structured_script_path` 落在 `02剧本结构/结构剧本/`；旧 `writing/结构剧本/` 结构稿只读可发现、内容不被改写，新稿不写入 `writing/`。
  - 断言均针对真实代码行为（真实函数／真实常量／真实模板加载／真实发布器），未用 mock 造被测事实、未用 `assertTrue(True)` 或空断言；落盘测试一律在 `tempfile.TemporaryDirectory()` 隔离目录内进行，不写仓库内项目／data／logs 目录。
- `维护记录/需求锚定基线.json`：`untested_done` 删除 11 条 REQ-S02-* 编号（JSON 格式不变、编号保持升序）。

## C 待用户裁决

无降级：11 条需求原文与代码一致，无纯描述/无法自动验证的条目，未改动 `docs/REQUIREMENTS.md`。

## 提交

本轮按用户要求不执行 `git commit`（由用户复验后提交），结果文件不记录 commit hash。
