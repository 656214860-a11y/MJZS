# R1435 结果：请求与 SKILL 内联字符硬上限 96,000 → 300,000

- 本轮属于 §3.7 **性能/资源轮**（资源边界调整，用户 2026-10-14 明确要求"提高上限"）。工作位置：独立工作树分支 `codex/r1432-skill-master`；开发与测试在 Linux 副本（Python 3.12，非随附解释器）。
- 测试跑了吗：跑了定向测试与架构目录，见下；随附解释器冒烟与全量另见本轮之后的验证记录。
- 欠账：全量回归欠账在本轮之后由 Windows 全量处理（结果另记）。

## 背景

R1433 总控体检实测：连贯性、分镜定稿、视频生成、质检交付 4 个总控 SKILL 连同直接引用分别为 97,370、134,553、117,238、129,231 字，超过 96,000 字硬上限。用 API 或 Claude Desktop 跑这 4 个阶段时，发送一律被拦（R1360 已记录为既有限制）。

## 改动

- `workflow_context_budget.REQUEST_CONTEXT_MAX_CHARS`：96,000 → 300,000，作为唯一常量。
- `workflow_settings._inline_skill_report`／`_inline_skill` 的默认 `cap` 改用同一常量，不再写死 96000。
- `hollmwood_roles.REQUEST_CONTEXT_MAX_CHARS` 由独立定义改为引用同一常量（消除第三份 96000）。
- `writing_api.DIRECT_REQUEST_CONTEXT_MAX_CHARS` 本就引用该常量，随之生效。
- 未改：
  - 按模型上下文窗口的 token 判断（`context_budget_report` 的 `context_limit`），超出模型窗口照样阻断，不截断正文；
  - 三虎对话的 `pet_llm.REQUEST_CONTEXT_MAX_CHARS = 16000`，属不同用途。

## 契约变化（§2.4）

- `test_stage_prompt_governance.test_missing_reference_and_total_budget_block_freeze`：两份 SKILL 的长度原写死 6 万字，改为按常量取一半，合计必超。断言未动。
- `test_master_skill.test_oversized_skill_is_reported_as_inline_only_limit`：超长样本按常量 +1000 生成。

## 测试

- 真实 skills 目录下总控体检：4 个问题 → 0。
- 定向 280 项：除 `test_workflow` 两项 `gate_level`（另一任务 R1431 引入，未改动副本同样失败）外全部通过。
- 架构目录 341 项：失败集合与 R1432／R1433 相同（4 项既有或环境项）。

## 自审

只动常量来源与两处默认参数；模型窗口保护仍在。风险：放宽后单次请求更大、费用更高；超过模型窗口的仍会在发送前阻断。
