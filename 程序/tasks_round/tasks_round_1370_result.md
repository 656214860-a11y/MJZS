# R1370：O43 自动流程统一检查点版本、幂等与恢复预览

类型：功能轮（§3.1；本项「建议／验证」→ 检查点版本化＋只读恢复预览，未改执行顺序与付费路径）。承接 R1267 清单 O43（O01—O42 已完成）。中央轮次 1370（主树含他人已暂存 WIP，故在干净临时工作树 `o43-claim` 调用 round_claim.py next 领取）。本轮 1370 − last_full_safe_all_round(1369) = 1 < 5，无五轮欠账；改动未命中 §5，收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_resume_preview.py` 12/12；定向 `-k resume_preview skill_registry skill_budget skill_templates skills workflow_settings workflow_tasks pet_agent pet_state stage_flow` 318/318；Tk 消费者 `-k test_pet_ui skill_panel` 586/586；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均 0 红。`test_workflow` 在主树 1 条红（「桌面模型名称保持不变，未安装时仅追加状态标注」）是既知主树环境项（未跟踪 `程序/配置/宠物/配置.json` 的 claude-desktop program 指向本机不存在的路径），与本改动无关，干净工作树全量绿。全量见「全量判定」。
- 欠账：O43 关闭，清单剩 O44—O48；1370 − last_full_safe_all_round(1369) = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O43）
- 依据：`skill_orchestrator.py:388` 已有付费确认、预算、检查点与工具执行；`pet_agent.py` 已有重试、幂等与阶段调度。
- 建议：恢复时先核对项目、采用成果、模型/SKILL 摘要及已执行副作用；显示将续做/跳过/需人工核实的步骤，区分工具调用完成和阶段成果完成。
- 验收：流程中途升级技能、改分镜、断电、部分工具成功后失败，续跑不重付费/重复发布；检查点写失败不得开始付费动作。依赖 O15/O18/O29。

### 前提核对（结论）
- 依据成立，但既有实现只有「问」没有「核对」：`before_step`（`:306`）写下的检查点只有 `stage/step/step_name/completed_steps`，没有格式版本、项目身份或步骤摘要；`recover_from_checkpoint`（`:352`）只把「继续/跳过/重做」问给用户，不核对项目、成果与技能是否还对得上，也没有「续跑会发生什么」的预览。本轮补的正是这层只读核对与预览。
- 「区分工具调用完成和阶段成果完成」在既有代码里有基础事实：`completed_steps` 只说明工具跑过（检查点写在这一步**动手之前**），阶段成果由 `verified_stage_output`（`:44`）独立校验——本轮把这两件事在预览里显式分成两项。
- 「模型/SKILL 摘要」有一层硬约束：`skill_orchestrator` 是 L3，`workflow_settings` 是 L4，L3 不能 import L4（会越层触发 `test_layers`）。故摘要只覆盖编排器自己看得见的范围——**阶段＋步骤序号＋步骤名**；技能集升级若改变这一步的步骤名（重排、改名、模板变化）就会被摘出来，「同名原地替换 SKILL」摘不出来，那种情况以磁盘成果与采用台账为准（见「边界」）。
- 「检查点写失败不得开始付费动作」在既有 `execute`／`run_stage_with_template` 里已成立（`before_step` 先于工具与 `budget.spend`，抛了就收场）；本轮把它固化成断言，并修掉一个副作用：写失败时**内存里也**不该留下一个没落盘的检查点。

## 实现
### skill_orchestrator.py（L3）
- 新增 `import hashlib`、模块常量 `CHECKPOINT_VERSION = 2` 与模块函数 `checkpoint_digest(stage, step, step_name)`（sha256 前 32 位）。
- `before_step(stage, step, skills=None)`：检查点新增 `version`／`at`（`self.clock()`）／`project`／`skills`（这一步要跑的 SKILL 名，供显示）／`digest`；原有键与取值不变。**写成功才认内存状态**：先 `pending = dict(self.status)` 填好、`save_project_status(pending, ...)` 成功后才 `self.status.clear(); self.status.update(pending)`——写失败时内存与落盘都停在动手之前。
- `execute` 传 `skills=[item.name]`；`run_stage_with_template` 传该步分组里的 SKILL 名。
- 新增只读 `resume_preview(context=None)`：返回 `found`／`stage`／`stage_name`／`step`／`step_name`／`total_steps`／`version`／`version_ok`／`project`／`project_ok`／`digest_ok`／`scope_ok`／`skills`／`artifact_verified`／`tools_done`／`steps`（逐步 `verdict` ∈ `continue`／`skip`／`verify` ＋ `reason`）／`continue_count`／`skip_count`／`verify_count`／`paid`／`lines`／`text`。判定：检查点之前的步骤 → `skip`（工具跑过）；格式版本／项目／步骤摘要任一对不上、或步骤越界 → 当前步（越界时全部）`verify`；`verified_stage_output` 为真 → 剩余整段 `skip`；否则 `continue`。`paid` 列出该阶段全部付费 SKILL，`text` 写明「只有标『续做』的才会重新提交」。

## 契约变化与同步
- `before_step` 新增仅关键字可选参数 `skills`（缺省 `None` 等价于旧的 `before_step(stage, step)`）；`checkpoint` 字典**新增**键，旧键与取值不变（`test_skills` 的 `saved['checkpoint'] == 检查点`、`completed_steps == [1, 2]` 照旧通过）。
- `recover_from_checkpoint`／`clear_checkpoint`／`status['checkpoint']` 的消费面（`pet_ui.py:1705-1712`、`1841-1850`）语义未变；`resume_preview` 是纯读方法，不改状态、不写文件、不发事件。
- 旧格式检查点（无 `version`）不当作坏数据删除，只标「需人工核实」；`project` 键缺失时不误报「另一个项目」，交给版本检查提示。
- 未新增顶层模块／裸 `json.loads`／L2 直写盘／`skipTest`；未新增业务 import（只用标准库 `hashlib`），故 `tests/architecture/_layers.py` 与 `维护记录/架构统一基数.json`（按 (file, importer, imported) 记层级豁免、不含行号）都无需同步；`skill_orchestrator.py` 无冻结关键词注释，TODO 注释快照不受新增行影响；架构门禁 312/312。
- **未改 `pet_ui.py`／`pet_agent.py`／`desktop.py`**：本项为「建议／验证」，只读预览未接界面（见「边界」）。

## 测试（`tests/test_resume_preview.py`，12 条）
- 核对与判定：无检查点 → `found=False`、文案「从头开始」；对得上的检查点 → `version_ok/project_ok/digest_ok` 全真、前序步骤 `skip`（理由含「工具调用完成，不等于成果已采用」）、当前步 `continue`、`tools_done == [1, 2]`；旧格式（无 `version`）→ `verify` 且文案含「旧版格式」；项目不一致 → `verify` 且文案含「不一致」；摘要对不上 → `verify` 且文案含「对不上」；步骤越界 → `scope_ok=False`、全部 `verify`。
- 成果与付费：`verified_stage_output` 为真 → 当前步与后续步全 `skip`、文案含「阶段成果完成」「不重复付费、不重复发布」；含付费 SKILL 的阶段 → `paid` 列出该 SKILL、文案含「付费步骤」「只有标『续做』的才会重新提交」。
- 只读与写失败：`resume_preview` 前后 `orch.status['checkpoint']` 与状态文件字节完全一致；`save_project_status` 抛 `OSError` 时 `execute` 返回 `failed`／「检查点写入失败」、`budget.spend` 一次都没被调用、`orch.status` 里不留 `checkpoint`。
- 记录与摘要：`before_step` 写入 `version`／`project`／`skills`／`digest` 且落盘与返回一致；`checkpoint_digest` 同输入同串、换步骤名或换步骤序号或换阶段都换串。

## 边界
- 步骤摘要只覆盖**阶段＋步骤序号＋步骤名**（L3 不能 import L4 的 `workflow_settings` 取模型/SKILL 冻结摘要，越层会被 `test_layers` 拦下）：技能集升级若保持这一步的步骤名不变（同名原地替换 SKILL 实现）就摘不出来，此时以 `verified_stage_output` 与磁盘成果／采用台账为准，不假装检查点能证明技能没变。
- `resume_preview` **未接入界面**：`pet_ui.py` 含需冻结行号的「暂时」注释，在其之上插行会破坏 TODO 注释快照；本轮把它做成只读 API 并测试，界面接线留给后续轮次（与本项「建议／验证」相称）。因此「显示将续做/跳过/需人工核实的步骤」目前是**结构化输出**，不是页面呈现。
- `artifact_verified` 只认 `verified_stage_output` 当前覆盖的两段（script／script_structure）；其他阶段的「阶段成果完成」由各自生成→校验→采用服务判断，编排器这里恒为假 → 那些阶段的剩余步骤一律 `continue`，不会误标「跳过」。
- 断电视角下的真实行为未实机验收（未真的拔电或杀进程）：本轮验的是检查点/预览的数据语义与写失败路径，不是端到端断电恢复体验。
- `paid` 列出的是该阶段**全部**付费 SKILL（不是仅剩余步骤的），文案据此提醒「只有标『续做』的才会重新提交」；未精确到「剩余步骤里哪几个是付费」。

## 全量判定
- 1370 − last_full_safe_all_round(1369) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；改的是纯标准库 L3 编排器）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1369、tree=0ed4726b…（2026-10-12，7 日内），但本轮改了 `skill_orchestrator.py` 并新增测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：待收尾补记。

## 提交
- 本轮改动：`程序/skill_orchestrator.py`、`程序/tests/test_resume_preview.py`（新）、`程序/tasks_round/tasks_round_1370_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 内容提交：待收尾补记（只含 `程序/skill_orchestrator.py` 与 `程序/tests/test_resume_preview.py`；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：待收尾补记。
