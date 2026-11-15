# R2562 结果：修复轮——主干自动全量欠账修复（写作域上下文预算＋零散红测）

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮。用户指令「你直接修」：主干出口档 CI 因 `test_full_safe_all_is_required_after_eight_source_rounds`
   （主干欠一次完整安全全量）挡住 R2535 合入；最近一次后台全量红 12 个测试文件。
   复现后定位为多根因欠账，本轮修复其中确认的代码/契约问题，使主干恢复可测状态。

2. **测试跑了吗、三个基线过了吗？**
   - 定向 `run_selftests.py -k test_writing_api test_previs test_copy_rules test_cancellation_status
     test_writing_cancellation test_writing_restart_intent test_writing_restart test_writing_edited_restart
     test_writing_response_preservation test_writing_quality test_distribution_selfcheck
     test_latent_defects_r2175 test_skill_deep_inline test_request_freeze_entries script_structure
     expand_edit`：**389 条 0 红**（修复范围 13 个原红文件全绿＋新增预算用例）。
   - 默认冒烟 `smoke_test.py`：**8/8**。
   - 架构门禁：本工作树实测仍有红，逐条归因——`stage_model_picker.py` 直接构造 `tk.Menu`
     （REQ-S01-82 别车道未提交 WIP）、`error_codes.py`/`test_stage_reasoning.py` 未入库
     （同上）、`test_round_number_continuous`（分支固有：结果文件号超前状态页）。
     以上均为**未提交的并行车道改动或分支固有状态**，不在 master 干净检出上存在；
     本轮自查项 `workflow_settings.py` 行数超限已通过拆分修复（1061→950）。

3. **`project_status.md` 的欠账少了吗？**
   减少：主干自动全量红名单 12 个文件的根因已修（详见下）。剩余欠账＝须在 master 上
   重跑 `--all --safe` 出绿回执后出口档才放行，与合入流程配套。

## 根因与修复

### 1. 写作域约 91 条红：R2450 `depth=-1` 递归内联撑爆上下文预算（主犯）

- 现象：`writing_api` 系列用例 mock 从未被调用，返回缺 `preparation_stage` 等键。
- 定位：`workflow_settings.freeze_skills` 对 `stage=='writing'` 用 `depth=-1` 无限递归内联
  SKILL 引用闭包，单 SKILL 内联体 23K→158K 字符；`workflow_context_budget` 保守估算
  （非 ASCII 2 token/字符）得系统提示约 202,743 token，超 gpt-4o 128K 窗口，
  `_context_budget_error` 在发送前拒绝。
- 修复（预算感知内联）：
  - `workflow_context_budget.py`：新增 `skill_inline_token_budget(limit)`——按模型窗口
    为任务/历史/输出预留与固定规则份额（16%）让路，返回内联预算。
  - 新模块 `skill_inline.py`（自 `workflow_settings` 拆出，后者 1061→950 行）：
    `_skill_inline_budget`（按 `config['model']` 经 `model_pool` 查 `context_length` 推导
    预算，查不到不设限）、`_charge_inline`（估算扣减，装不下不内联）、
    `_skipped_inline_hint`（超预算引用留本地路径提示，CLI/桌面引擎有目录白名单可按需读）、
    `_recurse_references`（原函数迁移，三处内联点超预算记 `skipped` 状态）。
  - `workflow_settings.py`：`_skill_blocks`/`_recurse_references` 调用穿透 `budget`；
    `freeze_skills` 建共享预算，`_one_skill_prompt` 按需取预算。
  - `tests/architecture/_layers.py`：登记 `skill_inline` 为 L3（workflow_settings 同层）。
  - `维护记录/覆盖率基线.json`：按 `scripts/coverage_report.py` 重测刷新
    （88 条目标用例全通过，367→366 模块：含本模块 `skill_inline.py`；
    测量在含并行车道 WIP 的工作树上进行，已剔除非本提交的 `error_codes.py` 行）。
- 测试：`tests/test_skill_deep_inline.py` 新增
  `test_budget_skips_oversize_references_with_skipped_status`、
  `test_skill_inline_token_budget_scales_with_window`（11/11 绿）。

### 2. `test_writing_api` canary：`'APPROVED'` 哨兵词失效

- R1441 加的防泄漏哨兵词之一；R2450 深度内联后 `'APPROVED_R01'` 是引用文档正文合法出现，
  哨兵失效而非泄漏。按「契约有意变更可同步测试、不弱化断言」：从哨兵列表移除该词并注明
  原因，其余哨兵保留同一守护意图。**断言未删、未弱化**（仍断言系统提示不含哨兵词）。

### 3. `api_endpoints.py`：截断/畸形响应体误归 `bug`

- HTTP 200 但 body 半截（`JSONDecodeError`）掉进通用 except 归为 `bug`；按传输未完成语义
  归 `network`、`status: 0`（与探测文案预期一致）。`test_latent_defects_r2175` 14/14 绿。

### 4. `test_copy_rules` 两处文案超长

- `pet_models_ui.py`：复选框名超 16 字上限——压缩为短名，说明挪独立提示标签。
- `scripts/sync_master.py`：`RuntimeError` 文案超 45 字上限——压缩。

### 5. `test_previs.py`：fake 签名同步（契约有意变更）

- R2488 给 `run_background` 加 `on_output` 流式回调；测试假函数补 `on_output=None` 形参。
  **断言未动**。

## 未纳入本提交的并行车道改动（如实声明）

工作树内并存 REQ-S01-82／error_codes／lint 批次等车道的未提交文件
（`stage_model_picker.py`、`stage_model_value.py`、`writing_api.py`、`model_router.py`、
`stage_config.py`、`storyboard_direct_api.py`、`error_codes.py`、`test_error_codes.py`、
`test_stage_reasoning.py`、`test_skills.py`、`tests/architecture/_layers.py` 的 error_codes
登记行、`scripts/dev.py`、`scripts/dev_lint.py`、`pyproject.toml`、`dev-requirements.txt`、
`distribution_manifest.md`、`docs/` 若干）。其中 `stage_model_picker.py` 缺 `CHAR_WIDTH`
导入曾致静态门禁红——补了一行 `from ui_tokens import CHAR_WIDTH` 使门禁可跑，
**该修复留在工作树未入本提交**（属对方车道文件，不代为提交）。

## 验证基线

- 定向：389 条 0 红（清单见上）
- 冒烟：8/8
- 架构门禁（本树）：余红均为上述并行车道/固有项，本轮新增模块已登记 L3 并刷新覆盖率基线

## 提交

- 分支：`codex/wip-R2562`（由 claim 队列自 R2540/R2541/R2551 演进而来，改动原样带入）
- commit：见下方「提交」补记（`dev.py commit` 生成证据后回填 hash）
