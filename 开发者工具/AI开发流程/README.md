# 按规格开发与审查

从仓库根进入本目录。开发者或 Codex 在任务中引用本文件即可启动。所有路径按本文件所在目录解析。应用发布包和制作阶段无需加载这些文件。

1. 探索。找出当前用户入口、现有 REQ、DES、对应测试和适用架构契约。在原轮次任务书记录受审版本、涉及目录、兼容要求和未知事项。
2. 规格。用 [Spec Kit 规格模板](spec-kit/spec-template.md) 的场景、边界和成功条件补全该任务书。沿用原 REQ/DES 编号，产品决策由负责人确认。中大型任务参考[计划](spec-kit/plan-template.md)和[任务拆分](spec-kit/tasks-template.md)，为每项写可独立验证的行为、文件和命令。模板中的示例路径替换为项目实际路径。
3. 实施。依赖明确后按任务执行。授权使用子代理时，依照 [Superpowers 工作流](superpowers/SKILL.md) 分派互不冲突的任务，通过 [实现提示](superpowers/implementer-prompt.md) 传递该任务所需规格、上下文和验收条件。涉及相同文件的写操作串行。单人执行时同样保留任务边界。
4. 验证。按程序/AGENTS.md §5 选择检查。在结果文件写受测提交、命令、实测结果、未验证范围。文档计数和历史通过记录都不能替代当次验证。
5. 审查。使用 [任务审查模板](superpowers/task-reviewer-prompt.md)，分别回答规格是否满足、代码质量是否可接受。对存量功能，用当前入口、实现、对应测试代替本次 diff，注明抽查范围。每项写证据位置、复现条件、用户影响、优先级和回归验证。负责人决定修复顺序及是否接受剩余风险，再按项目入口提交。

## 上游与更新

Spec Kit 采用官方三份模板，固定版本 a4d571229e164e440f8950cac034607bae7b7518。Superpowers 采用 subagent-driven-development 技能目录，固定版本 22f0b463e7a5e579904dd6211a520321035526f7。两份许可证随各自目录提供。更新时比对上述目录的上游差异，复核提示词、脚本和项目门禁后再替换。按需读取模板即可开展工作，配套 Bash 脚本仅供采用上游自动化的环境使用。

上游依据：[Spec Kit](https://github.com/github/spec-kit/tree/a4d571229e164e440f8950cac034607bae7b7518/templates) · [Superpowers](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development) · [Anthropic 工作方法](https://code.claude.com/docs/en/best-practices)

需要自动抽取子任务时，用 Git Bash 运行 scripts/task-brief PLAN 2 OUT（脚本在 superpowers 下）。计划用英文标题前缀例如 ## Task 2 Skill 生命周期；将 Spec Kit 的 T001 等任务编号保留在标题下，输出路径显式指定到临时目录。
