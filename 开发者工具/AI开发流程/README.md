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

## DEV-FLOW-01 接力与复验

- **规格与边界**。本次接入服务于漫剧助手的开发者。按场景补足规格，在原任务书记录执行上下文，再分别审查规格符合性和代码质量。沿用 [ADR-0006](../../程序/docs/adr/0006-round-system-no-external-spec-framework.md) 的 REQ、DES、轮次与证据体系。首轮沿文档规则、Skill 生命周期、Git 提交、测试凭据四条链扫描，发现及优先级见 [R4025](../../程序/tasks_round/tasks_round_4025_result.md)。
- **实现与决策记录**。从项目技能进入本页。用上面固定版本的模板、实现提示和审查提示传递上下文。[R4028 验收](../../程序/tasks_round/tasks_round_4028_result.md)及 [R4029 合入凭据](../../程序/tasks_round/evidence/R4029.json)分别记录验收与合入。初次回放以功能车道提交 **5690376d**（R4027，显式提交隔离其他暂存文件）为样本，提交器定向测试历史结果为 13/13。R4027 未进入 **60f0f3af** 的主干历史，在该基线只能把这次回放作为历史证据。
- **复验**。从仓库根核对技能到本页、再到三个模板和上下文、审查入口的相对链接。用 Git Bash 对两个带英文 Task 标题的临时计划运行 `bash 开发者工具/AI开发流程/superpowers/scripts/task-brief PLAN 2 OUT`，确认输出只含第二项。可用 `bash 开发者工具/AI开发流程/superpowers/scripts/review-package PLAN 60f0f3af^1 60f0f3af OUT` 生成本次接入的审查包，分别检查规格和质量，并记录当前命令结果。两个 OUT 都指向仓库外临时文件。审查包需要完整 Git 历史。
- **回滚**。纯只读验收只退出临时克隆。若需撤回正式接入，先用 `git diff --name-status "60f0f3af^1" 60f0f3af` 核对首父差异，评估后续提交对入口的依赖，再按 [runbook §13](../../程序/runbook.md) 在隔离车道通过 Git 反向提交与门禁处理。整轮撤回 R4029 时，首父是主干，需按 merge revert 的主线 1 处理。只撤回某项时以待撤路径为边界。
