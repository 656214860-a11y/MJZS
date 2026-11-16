# tasks_round_2984_result
<!-- round-evidence: {"commit_base": "8fdc0638", "credential_hits": 0, "evidence_sha256": "b0df3cbd3be224e0", "exit": 0, "failed": 0, "passed": 0, "round": 2984, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮·文档先行段（R2984）：输出《统一状态栏》优化任务书并同步 UI 权威文档（`ui_components.md` 新增「统一状态栏」组件契约、`design_tokens.md` 补 `color.success.subtle`）。无 `.py` 改动，未动 `project_status.md`／`AGENTS.md`／`architecture.md`。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8 通过**（smoke_test.py 实跑）；文档轮未跑架构门禁与全量，不填数字。
3. **project_status.md 的欠账少了吗？** 未改（仅 master 可提交）；无欠账变化。

## 本轮内容

- 新增 `tasks_round/任务书_统一状态栏_R2984.md`：事实基线、15 项设计决策、GitHub 调研结论、P0–P3 分阶段计划、G1–G10 缺失功能清单、轮次纪律与风险。
- `ui_components.md`：新增「统一状态栏（文字提示模块）」契约节——左区常驻/右区消息/历史面板、StatusBus 唯一发布入口、四级视觉取值引用 design_tokens、顶部标题行删除与页头等价迁移约定。
- `design_tokens.md`：新增 `color.success.subtle`（#EFFBF1，成功提示底色）。

## 后续轮次（已领 R2984 之外逐轮另领）

R2985 P0 统一模块；R2986 P1 剧本准备页接入+错误分级；R2987 P2 标题行删除+Token 迁移；R2988 P3 路径收敛+文案规范；R2989 收尾全量。
