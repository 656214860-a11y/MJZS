# R1433 结果：统筹 SKILL 改为总控（清单化、指纹自动同步、体检、手动＋自动门禁）

- 本轮属于 §3.1 **功能轮**，含治理变更：`AGENTS.md` 统筹宪法由用户授权改写为总控宪法。工作位置：独立工作树分支 `codex/r1432-skill-master`；开发与测试在 Linux 副本（Python 3.12，非随附解释器）。
- 测试跑了吗：跑了定向测试与架构目录，见下；随附解释器冒烟与全量未跑。
- 欠账：全量回归欠账未减少。

## 用户决定（2026-10-14）

1. 各阶段 SKILL 勾选由用户自由决定，总控不锁勾选。
2. 00全流程SKILL 更新后，检测到即自动同步并提示。
3. 门禁阻断在手动与自动路径都生效。

## 内容

- **总控清单** `skills/00全流程SKILL/总控.json`：取代写死在 `workflow_settings` 里的对应表。
  - 清单放在上游 git 包之外，不会被 `git pull` 冲掉。
  - `refresh_workflow_presets()` 按文件指纹原地刷新 `WORKFLOW_PRESETS`。对象身份不变，既有调用与 `patch.dict` 不受影响。
  - 清单缺失或损坏时退回 `BUILTIN_WORKFLOW_PRESETS`，原因记入 `MASTER_MANIFEST_PROBLEMS`。
  - 出厂清单与原内置表逐项相等（有测试守卫）。
- **`master_skill.py`**（L4，无 Tk）：
  - `fingerprint`：只读固定文件表，不递归扫描。覆盖清单、全流程包 SKILL.md、各阶段总控 SKILL 及其直接 Markdown 引用。
  - `sync`：总控模式下指纹一变，逐阶段只替换上次总控给的项。合并规则：
    - 用户自加的 SKILL 保留；
    - 用户取消勾选的总控项不重新勾上；
    - 整体弃用总控建议的阶段不追加。
    - 首次检查只记录基线，不改动任何阶段。
    - 同步基线写入 `workflow.applied`。
  - `health`：报告以下问题：
    - 全流程包入口不存在；
    - 总控登记的 SKILL 不在注册表；
    - 按真实发送流程冻结失败（引用缺失／越界、正文为空、超上限）。
- **门禁** `workflow_settings.master_gate`（`master_skill.gate` 转调）：
  - 总控模式下，本阶段必填制作锁缺失或已勾选 SKILL 引用不可加载就阻断。
  - 接在 Agent 任务提示（`workflow_engines.prompt_with_settings`）与冻结发送（`freeze_skills`）两个入口。
  - `stage_handler_registry` 的制作锁检查扩展到所有有必填锁的阶段，手动触发也阻断，原因直接返回调用方。
  - 剧本准备的简报采集对话不受制作锁门禁影响，由既有简报门禁负责。
- **自动同步触发**：
  - 打开项目后，随既有阶段模型对账线程在后台执行，结果经状态栏提示；
  - 打开或刷新阶段配置时执行；
  - 套用总控后立即登记基线。
- **界面改名**：「统筹 SKILL」→「总控」、「不使用统筹」→「不使用总控」，以及套用／切换对话框、恢复默认等提示文字。"浏览本地…"提示改为指向 `总控.json`。
- **文档**：`AGENTS.md` 权威源表与总控宪法；`architecture.md` 总控预设契约（含 `applied` 投影与两个新模块）。

## 契约变化（§2.4）

- `test_skills`、`test_stage_prompt_governance` 中三处用户可见文字从"统筹"改为"总控"。属用户要求的 UI／提示词措辞变更，断言的其余部分未动。
- `stage_handler_registry._workflow_lock_error` 原规定"手动路径永远不拦"，按用户授权改为手动也拦。手动剧本准备仍不拦（`test_stage_command_contract` 原断言保留并通过）。

## 测试

- 新增 `tests/test_master_skill.py` 17 项：
  - 清单驱动与兜底；
  - 合并三规则；
  - 首检只记基线；
  - 清单变化后同步并保留用户项；
  - 引用文件内容变化可被指纹发现；
  - 体检；
  - 非总控模式不动作；
  - 门禁（锁、剧本豁免、无总控放行、引用缺失、两个发送入口、手动阶段启动）。
- 相关 20 个测试文件：除下列项外全部通过。以下均在未改动副本上同样失败：
  - `test_workflow` 两项 `gate_level`，来自另一任务 R1431；
  - `test_claude_program_detection` 商店版路径一项。
- 架构目录 341 项：失败集合与 R1432 相同（4 项既有／环境项）。
  - `master_skill` 登记为 L4。
  - `workflow_engines.py` 两处 `json.loads` 登记行号顺延 2 行，未放宽规则。
  - 门禁实现放在 `workflow_settings` 内，避免 `workflow_engines → master_skill` 越层与循环依赖。
- 未运行：随附解释器冒烟、全量、真实应用实机（打开项目后的状态栏提示与阶段配置刷新）。

## 自审

- 勾选自由、编辑入口不变灰：满足用户第 1 条。
- 范围：只动总控相关模块、文案与文档。
- 同类风险：自动同步写 `skill_config.json` 发生在后台线程。与既有阶段模型对账同一模式，经 `agent.core.save` 原子写。
