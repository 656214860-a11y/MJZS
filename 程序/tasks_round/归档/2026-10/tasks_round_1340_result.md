# R1340：O16 四角色审核结果可定位的依据与修订范围

类型：功能轮（§3.1；本项为「建议」，交付为实现＋测试）。承接 R1267 清单 O16（O01—O15 已完成）。中央轮次 1340。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k hollmwood` 51/51、关联 `-k writing` 139/139、`-k idea_chat` 全绿、`-k stage_prompt_governance` 15/15、`-k copy_rules` 14/14、`-k todo_comment` 2/2、`-k unification_ratchet` 3/3（台账平移复验）、默认冒烟 8/8，全 0 红。
- 欠账：O16 关闭，清单剩 O17—O48；1340 − 1336 = 4 < 5，且未命中 §5 升级条件（未动启动路径／Tk 控件生命周期／删除语义／层级登记表），本轮不跑全量。

## 目标（R1267 清单 O16）
- 建议：审核结论记录所用 brief／SKILL 摘要、问题位置、违反规则、修订建议、通过条件；明确「规则合格」与「创意满意」差别。保持 `ROLE_ORDER`、`MAX_REVISIONS` 与既有串行接力，避免再次硬编码对白字数与时长。
- 验收：同一冻结输入可追溯审核依据；返工只针对明确问题；不因报告建议重新注入重复节奏规则。

## 实现
### 1）审核依据可追溯（同一冻结输入 → 同一组摘要）
- `hollmwood_roles._run` 新增 `_review_basis(brief, skill_instructions, rhythm_constraints, review_system)`，落四组 sha256：`brief_sha256`（已确认简报正文）、`skill_sha256`（本轮实际发送的 SKILL 指令正文）、`rhythm_sha256`（本轮节奏约束正文，空模板记空串摘要）、`review_system_sha256`（审核 system：审核规则＋导演规则＋共享约束）。
- 摘要只记录「依据了哪份正文」，不复述规则正文，也不把节奏/SKILL 正文再塞进请求。

### 2）逐条留痕：位置／违反规则／修订建议／通过条件
- 审核 system 的收口由「逐条指出位置、问题及可执行修改」改为「逐条指出位置、问题（违反的规则，若适用）、可执行修订建议和通过条件」，保留 `不复述剧本`、300 字软上限、不代写完整剧本。
- 每次审核都写入 `_review_record`：`role`／`attempt`／`verdict`（approved／revise）／`rule_compliant`／`creative_signoff`／`resumed`／`review_text`（审核原文逐字保留）。结果字典新增 `review_audit = {basis, scope, records}`。

### 3）「规则合格」与「创意满意」分开
- 每条记录 `creative_signoff='pending_user_confirmation'`；整份 `review_audit.scope = REVIEW_SCOPE`：「模型审核只判定规则层面是否合格；创意满意由用户在阶段面板确认。」
- `APPROVED` 只等于规则合格，不等于创意满意；桌面 HOLLMWOOD 完成状态文案改为「导演：已通过 · … · 演员：已通过（规则合格；创意满意由您确认）」。

### 4）返工只针对明确问题、不重复注入节奏
- `_revision` 的 prompt 改为：只修改退回意见中逐条指出的问题及其直接影响范围；未指出的保持原样；不要顺带重写、改写，也不要重复粘贴节奏规则或角色规则。仍保留 `<director_review>`／`<previous_script>` 结构。
- 节奏／SKILL／阶段契约仍只出现在同一份角色 `system` 里且仅一次（返工请求的 prompt 不含节奏正文）。

### 5）失败可追溯
- `RoleExecutionError` 新增 `review_basis`／`review_records`；最终判退时随异常带出（仍保留 `review_failed_role`／`response_text`）。
- `writing_api._hollmwood_reply` 成功与失败结果都带 `hollmwood_review_audit`（basis＋scope＋records）；失败另带既有 `hollmwood_review_failed_role`。

### 6）边界保持
- `ROLE_ORDER`、`MAX_REVISIONS`、串行四角色与三次导演门禁、断点指纹逻辑不变：新增字段只在 `_run` 返回前附加，不写入 `hollmwood_resume.json`，恢复语义不受影响。
- 未改 `hollmwood_rules.py` 规则常量；未硬编码对白字数或时长。

## 验证
- 新增 `tests/test_hollmwood_roles.py::ReviewTraceabilityTests` 5 条：同一冻结输入 `review_basis` 四键一致且为 64 位摘要；记录区分规则合格/创意满意并保留退回原文与通过条件；返工 prompt 只含明确问题、节奏正文只在 system 出现一次、prompt 不含节奏；最终判退异常带 basis 与 records；断点恢复前缀记为「上一轮已审核通过」。
- `tests/test_hollmwood_performance.py` 新增 2 条：成功结果透出 `hollmwood_review_audit`；失败结果带 basis/scope/records。
- `tests/test_hollmwood_ui_queue.py` 新增 1 条：完成状态文案区分规则合格与创意满意且仍用「您」。
- 定向/关联/冒烟见三个必答，全 0 红。

## 风险与边界
- `review_basis` 只能证明「用的是同一份冻结输入」，不等于模型判定本身正确；审核仍可能漏判，创意满意度仍需用户确认。
- `review_records` 只覆盖本次调用实际发生的审核；断点恢复的前缀以「上一轮已审核通过」登记（无历史审核原文），因为断点只保存已通过正文、不保存历史审核文本。
- 桌面文案与状态变量是只读提示，不是采用或验收凭据。
- 未实发模型请求、未重启应用、未真实点击界面。
- `writing_api.py` 加行后第 4 项 `json.loads` 台账 486→490（已同步）；`desktop.py` 只改一行文案，行数不变，TODO 注释快照 2753 未平移。

[TASK_COMPLETE] 审核结论可追溯（brief／SKILL／节奏／审核 system 四组 sha256）＋逐条留痕（位置／违反规则／修订建议／通过条件）＋规则合格与创意满意分开（APPROVED 只等于规则合格，桌面文案点明、`creative_signoff` 待用户确认）；返工 prompt 只针对明确问题且不重复注入节奏；失败异常与 API 结果都带 `hollmwood_review_audit`；保持 ROLE_ORDER／MAX_REVISIONS／串行接力，未硬编码字数时长；定向 51/51、关联 139/139、冒烟 8/8，全 0 红。
