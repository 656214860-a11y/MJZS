# R1683 验证基线轮：为阶段 S06 连贯性清单补齐 9 条需求锚点测试

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证/基线轮。只新增测试文件与缩减需求锚定基线，未改任何产品代码，不算源码轮。

2. **测试跑了吗？三个基线过了吗？**
   - 定向 `run_selftests.py -k req_anchor_s06 requirement_traceability`：17 条 / 0 红（`test_req_anchor_s06` 13 条、`architecture.test_requirement_traceability` 4 条；其中 `test_baseline_only_shrinks` 与 `test_new_done_requirement_needs_a_test_anchor` 均通过）。
   - 默认冒烟 `smoke_test.py`：8/8。
   - `run_selftests.py -k agents_md`：15 条 / 0 红（新测试文件未引起架构门禁变化，无需登记）。
   - `run_selftests.py -k round_baselines`：5 条中 4 绿，唯一红为 `test_full_safe_all_is_required_after_eight_source_rounds`（R1682 欠一次完整安全全量，系既有欠账，由 post-commit 后台自动补跑，与本轮无关）。
   - 未跑架构门禁全量与安全全量（本轮仅测试与文档，不算源码轮，不触发全量欠账）。

3. **project_status.md 的欠账少了吗？** 需求锚定欠账减少：`维护记录/需求锚定基线.json` 的 `untested_done` 从 146 条减为 137 条（删除 REQ-S06-01/10/12/13/14/15/17/21/31 共 9 条）。

## A 改动

- 新增 `tests/test_req_anchor_s06.py`（13 条用例，锚定 REQ-S06-01/10/12/13/14/15/17/21/31 共 9 条需求）：
  - REQ-S06-01：读不到分镜／资产时按空分镜／空资产计算，不报错（`build([], {})` 等返回 version=1 空台账）。
  - REQ-S06-10：台账由 `build` 按规则现场计算，不调用模型（`patch('pet_llm.Client.ask')` 断言未调用，输出确定、`prompt` 为字面常量）。
  - REQ-S06-12：冻结锚点逐字取自资产（角色含服装状态覆盖、场景拼光源／空间锚点／尺度、道具拼材质／尺度）；资产里没有的字段不补、不改写。
  - REQ-S06-13：参考图冲突两类（职责自相矛盾／多图抢同一件事）与裁决规则（先出现的负责身份、其余只补风格与光影）。
  - REQ-S06-14：三元组每批一行；同批内出现多种三元组即不通过、提示重切批次；本阶段不改批次划分。
  - REQ-S06-15：同一锚点跨批次字符串一致即通过；`continuity_flags` 记为「全程必须保住」。
  - REQ-S06-17：本阶段不改分镜、不改资产、不重新描述锚点（输入深拷贝前后一致、锚点为资产原文）。
  - REQ-S06-21：问题编号稳定 `CI-<类型>-<范围>`、状态待处理／已忽略／已解除、忽略必须写理由并记证据摘要、证据变化或复现则重开、修好自动解除、只有 L3 注入发布器才落盘否则只读预览。
  - REQ-S06-31：`continuity.*` 工具在 `skill_tools` 登记（`buildLedger` 为 ready、其余为 page）；`continuity.buildLedger` 经 `skill_tools.call` 调 `build/write` 本地落盘。
  - 断言均针对真实代码行为（真实函数/真实常量/真实 SKILL 注册表），未用 mock 造被测事实、未用 `assertTrue(True)` 或空断言；新测试在 `tempfile.TemporaryDirectory()` 隔离环境运行，不写仓库内项目/data/logs 目录。
- `维护记录/需求锚定基线.json`：`untested_done` 删除 9 条 REQ-S06-* 编号（JSON 格式不变、编号保持升序）。

## C 待用户裁决

无降级：9 条需求原文与代码一致，无纯描述/无法自动验证的条目，未改动 `docs/REQUIREMENTS.md`。

透明观察（非降级）：REQ-S06-15 的「跨批次字符串不一致即不通过」检测分支（`cross_batch` 里 `len(seen) > 1 → ok=False`）在单次 `build` 内恒不触发——因为锚点字符串由固定 `assets` 字典确定性生成，同一「类型＋编号＋状态」键恒得同一字符串。该分支实现正确但当前只在「已落盘台账 vs 当前资产」的漂移检查（G-09 `drift`，即已降为 🟡 的 REQ-S06-16）里才有意义，与本轮锚定的 flags 记录、跨批次一致性两条真实行为无冲突。本轮不据此降级 REQ-S06-15。

## 提交

见提交信息 `R1683:`。
