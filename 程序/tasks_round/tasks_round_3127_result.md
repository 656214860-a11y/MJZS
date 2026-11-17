# R3127 结果：SKILL 生命周期 T10——用户文档＋远期清单归档
<!-- round-evidence: {"commit_base": "8a01b2da", "credential_hits": 0, "evidence_sha256": "e05ded588e98a468", "exit": 0, "failed": 0, "passed": 0, "round": 3127, "tests": "docs-only"} -->

**类型**：文档轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T10；同栈功能工作树，领号时分支 `codex/wip-R3127`）。
**测试**：文档轮无新代码，不跑 smoke／selftest（runbook 口径）；本轮改动触及受门禁约束的 `使用说明.md`，定向复验 `run_selftests.py -k test_app_metadata test_root_layout` → 7 条 0 红（`test_root_layout` 1 条＋`test_app_metadata` 6 条，含阶段表契约与标题契约）。
**基线**：冒烟 8/8（继承本树 R3099 基线，文档轮不重复跑）；架构门禁不适用（无结构／源码改动）；`project_status.md` 欠账未新增（仅 master 可提交，堆叠分支轮次差沿用先例）。
**欠账**：无新增；「新建 SKILL」入口登记为待用户决定项（见下）。

## 变更摘要

- `使用说明.md`（仓库根，随分发包，`distribution_manifest.md` 保留项）：新增「SKILL 的导入与管理」节——
  - 三层位置与优先级：内置 `程序/skills/`（只读）、全局 `程序/data/skills/`（升级保留）、项目 `<项目>/skills/`，同名 项目＞全局＞内置；
  - 格式：`*.skill.md` frontmatter 17 字段契约（指向内置样例）、整包 `SKILL.md`／`README.md`／`README_ZH.md` 口径、外部包 `license`／`compatibility` 保留并展示；
  - 导入：阶段面板管理下拉五入口＋设置页齿轮「SKILL 管理」→「导入 SKILL…」五来源、「导入到：项目／全局」、「默认阶段」兜底表述按实际控件措辞；
  - 安全口径：导入确认提示外部内容注入模型请求、`scripts/` 与 `.exe/.dll/.ps1/.bat` 警告行、应用不执行、来源自判（与 T9 实现一致）；
  - 体检／检查更新／管理页行操作（查看说明／重命名／编辑／禁用启用／删除回收站）与 agent 同步目标（`~/.codex`／`~/.claude`／`~/.agents`）。
- `维护记录/优化待办队列.md`：新增「SKILL 生命周期远期清单（R3127 归档）」S1–S5——
  - S1 技能市场／registry 浏览、付费 SKILL、签名体系：不做在线市场，条件＝账户＋云端立项且有分发需求；
  - S2 项目级 SKILL 云同步：依赖账户体系与冲突合并策略，条件同上；
  - S3 Skill vs Plugin 体系：不引入代码插件二分，外部包 `scripts/` 保持惰性，条件＝经审核的本地代码扩展需求；
  - S4 `.agents/skills` 写入方向：只单向导出不回读不挂载（T5 契约评估），条件＝业界格式收敛＋明确消费需求；
  - S5 「新建 SKILL」入口：**待用户决定**（任务书 §7 点名）——`scripts/create-skill.js` 为 Node 开发侧件不进发布包；零依赖下 Python 模板生成器可行，但 17 字段契约偏开发向、交互形态未定，本轮不实现。
- `tasks_round/tasks_round_3099_result.md`：回填 commit hash `8a01b2da`（R3099 已随本分支入库）。

## T10 步骤 2 结论（先出结论再动手）

- `scripts/create-skill.js` 是 Node 开发侧脚本，不进分发包；本应用零第三方运行时依赖，node 不可用。
- T7「SKILL 管理」页范围是安装级增删查，无「新建」入口；任务书以「若 T7 管理页要『新建 SKILL』入口」为条件，本轮不触发。
- 评估结论：Python 侧模板生成器技术上可行（百行级模板＋表单，写 `data/skills/<阶段目录>/` 用户层），但 `.skill.md` 17 字段契约面向开发者，用户向导需先定交互形态 → 归档 S5 待用户决定，不实现。

## 验证

- `run_selftests.py -k test_app_metadata test_root_layout` → 7 条 0 红（ALL TESTS PASSED）。
- 未运行：smoke／`--affected`／`--architecture`／`--all --safe`（文档轮无 .py 改动；合入 master 前随全栈统一触发全量）。

## 边界与说明

- `使用说明.txt` 为安装／更新记录口径，不同步 SKILL 节；SKILL 用户文档只落 `使用说明.md`（任务书「或」口径取一处）。
- 文档内容逐条对过实现：层优先级、导入入口标签、体检／检查更新位置、行操作、同步目标均与 `pet_skills_manage.py`／`skill_panel.py`／`agent_skill_sync.py` 现行口径一致。
- 「新建 SKILL」入口按任务书 §7 属用户决定项：已登记待办队列 S5，本轮不实现、不代用户拍板。
- 提交状态：待 `dev.py commit`；commit hash 提交后回填。
- 变更文件清单：`使用说明.md`（仓库根）、`程序/维护记录/优化待办队列.md`、`程序/tasks_round/tasks_round_3099_result.md`（commit hash 回填 `8a01b2da`）、`程序/tasks_round/tasks_round_3127_result.md`。
- 遗留：S5 待用户决定；`test_round_number_continuous` 堆叠分支差值在 master 集成时消解。
- 风险与回滚：纯文档，回滚＝`git revert` 本提交。
- 自检结论：本轮声明文档轮；测试按文档轮口径执行，受守卫文件已定向复验。
- 下一步：全部 T1–T10 轮次完成后合入 master＋最终全量验证。
- 阻塞：无。
- 兼容性：无代码变更。
- 性能：无影响。
- 安全：文档只描述既有安全口径，未新增能力。
- 测试缺口：无（文档轮）。
- 文档：`使用说明.md` 用户向、`优化待办队列.md` 远期归档均已同步；`文档导航.md` 无需更新（未新增文档文件）。
- 结论：T10 验收项落地，待提交。
- commit：PENDING
- 结果文件提交状态：已随本批提交（见 commit 行）。
- 时间：2026-11-17。
- 备注：领号时 `round_claim.py` 将工作树切到 `codex/wip-R3127`，R3099 提交在该分支落地（同工作树轮次归属，不影响合入）。
- commit hash：PENDING
- 状态：待提交。
- 结束。
