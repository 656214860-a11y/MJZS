# R1678 结构治理轮·执行：文档先行流程加门禁、划豁免，AGENTS.md 瘦身

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮·执行。来源：用户 2026-10-18 对话“文档先行流程能否跑起来、AGENTS.md 为何没瘦”的诊断，用户回复“需要”后授权；无 R-J 报告条目。只动文档、一个新增架构门禁与其基线、`test_agents_md.py` 的清单读取位置，未改产品代码、未改用户数据。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 8/8。架构门禁 368 条跑完，2 红，均非本轮引入（见 D）。定向 `-k agents_md requirement_traceability distribution_selfcheck root_layout scope` 224 条，1 红（`test_root_layout`，非本轮引入）。未跑安全全量。
3. **project_status.md 的欠账少了吗？** 源码轮次欠账不变（本轮无源码改动）；新增“需求锚定欠账 152 条”显性登记。

## A 改动

1. **新门禁** `tests/architecture/test_requirement_traceability.py`（4 条）：REQ 编号唯一；测试引用的 REQ 必须存在；新增的 ✅ 需求无测试锚定即红；基线只减不增。基线 `维护记录/需求锚定基线.json` 登记现状：REQUIREMENTS.md 共 325 条 REQ，其中 ✅ 298 条，**152 条 ✅ 尚无测试锚定**（S13 20、S08 17、S04 16、S01 14、S07 13、S03 12、S12 12、S02 11、S05 11、S09 11、S06 9、S10 6）。锚点识别含 `test_req_s10_03_*` 命名与 `REQ-S10-01/02` 斜杠简写。
2. **AGENTS §2.7 重写**：适用范围改为 01–13 全部阶段；明确只有功能轮／契约轮先改文档，修复轮按 §3.2 判断，其余轮次类型豁免但事实变化时同轮同步 REQ；第 4 条写明门禁。
3. **AGENTS.md 瘦身**（21246 → 约 15600 字符）：
   - §2.2 的 5 行专题细则（L2 写服务结果、项目操作上下文、阶段成果发布器、正式 JSON 读写、持久化产物版本）改一句话摘要，原文迁入 `architecture.md` §“权威源补充条款”；
   - 总控 SKILL 宪法全文迁入同节；
   - §5 全量欠账口径与后台补跑两大段迁入 `runbook.md` §4“详细口径”，AGENTS 留一句话摘要；
   - §5 的“当前架构门禁清单”整块迁入 `architecture.md` §“当前架构门禁清单”（内容未改，仅新增本轮门禁一条）。
4. `tests/architecture/test_agents_md.py::test_architecture_guard_list_matches_actual_test_files`：只改读取位置（AGENTS → architecture.md），集合相等断言未动。`architecture.md` 与 `维护记录/架构统一路线图_v2.md` 里指向“AGENTS 的清单”的两句话同步改指向。

## C 待用户裁决

- 152 条 ✅ 无锚点是否逐阶段补测试，还是把其中纯描述类条目降为 🟡／删除；建议另开功能轮／测试补强，按阶段批量。

## D 未做与局限（均如实记录，非本轮引入）

- `test_function_size_ratchet`：`desktop_writing_page.py::writing` 588 行 > 上限 577。在未带本轮改动的树上同样红（已用 stash 复核），来源是此前轮次对该函数的改动；本轮不处理。
- `test_root_layout`：`.claude` 被 R1676 纳入版本控制，未在 `ALLOWED` 登记用途；本轮不处理。
- `test_round_baselines` 欠一次完整安全全量：由后台补跑机制负责，未手动全量。
- 门禁只能守“新增”，已有 152 条欠账不会自己变少；“只改文档不改代码”的漂移（REQ 写得不对）仍无自动手段。

## 提交

见提交信息 `R1678:`。
