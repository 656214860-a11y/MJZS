# 术语表

- **三虎**：进度界面、阶段日志、自动化等级三件套监控。
- **棘轮（ratchet）**：只许下降的计数门禁（如静默异常、模块行数），防止退化回潮。
- **轮次（R<N>）**：一次可独立回滚的完整变更集；编号由 `round_claim.py` 统一领取。
- **权威源**：某类事实唯一允许的出处（如阶段顺序只看 `pet_bus.STAGES`），见 AGENTS §2.2。
- **分层（L0–L5）**：L0 契约 → L1 基础设施 → L2 业务 → L3 编排 → L4 UI → L5 启动；只允许自上而下依赖。
- **冒烟／架构门禁／安全全量**：三档验证，见 AGENTS §5。
- **验收锁／全量欠账**：`full-safe-selftest.lock` 与「每 8 个源码轮次须一次全量」的欠账机制，见 runbook §4。
- **SKILL**：阶段技能包（`*.skill.md` 清单 + references/assets/scripts），内置层 `skills/`、用户层 `data/skills/`。
- **总控 SKILL**：`skills/00全流程SKILL/总控.json` 清单，约束全流程执行。
- **分发副本**：按 `distribution_manifest.md` 白名单生成的可发布目录，只含白名单锁定的第三方包。
