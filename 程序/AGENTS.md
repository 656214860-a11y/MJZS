# AGENTS.md — 项目入口

> 本文件须在加载上限（16 KB）内读完：新增规则前先删旧规则，细则写进 `runbook.md`，这里只留触发条件和指针。
> 状态权威：`程序/project_status.md`；结构权威：`程序/architecture.md`；路径均相对仓库根。

## 0. 任务开始时必读

- **范围明确的小任务**：读本文件和任务点名的文件；`architecture.md`、`PROJECT_MAP.md`、`project_status.md` 用标题或 grep 定位相关节。
- **自主开工的会话**：读本文件；`project_status.md` 只读轮次头、新对话接续协议、检查点、验证基线、已知阻塞与待办；`architecture.md` 读 §3 分层表和与本轮模块相关的节；`PROJECT_MAP.md` 读相关节。历史条目只在涉及本轮任务或追溯凭据时读取，旧记录不当作当前验收。

读完前只定位和读取，修改、测试、认领放到读完之后；事实冲突时继续定位。接续依据文件系统，不依赖旧对话历史。

## 1. 项目速览

- 产品：Windows 桌面应用「漫剧助手」；Python + Tkinter，零第三方依赖
- 解释器：`运行环境\Python\python.exe`（仓库根下，不用全局 Python）
- 工作流：13 个制作阶段（初步分镜之后为 Animatic 分镜预演）
- 执行链路：`skill_orchestrator`
- 三虎：进度界面、阶段日志、自动化等级、暂停恢复、资产跨重启续跑台账

## 2. 硬约束

### 2.1 通用硬约束

1. 密钥不写入文件、不进日志。
2. 保护用户项目数据，只做明确授权的数据操作；页面或注册表类改动后提示重启。
3. 产品交付脚本不引入 shell 依赖。
4. 交付物是实际写入或修改的文件（只读诊断轮除外）。
5. 复用现有模块。
6. 每轮只做本轮任务，只改范围内文件。
7. 轮次接续与结果归档按 §2.5 规则 27、§7；验证按 §5，提交按 §2.6。

### 2.2 权威源（唯一真源）

| 类别 | 唯一权威 |
| --- | --- |
| 阶段顺序 | `pet_bus.STAGES` / `STAGE_NAMES` |
| 并行与重试 | `stage_parallel.CONFIG` |
| 模型池 | 模型管理保存的模型池 |
| SKILL | `skills/01—13 阶段目录/*.skill.md`（内置层）＋ `data/skills/<同名阶段目录>/`（用户导入层，同名用户优先）与 `skill_registry.py` |
| 总控 SKILL | 清单 `skills/00全流程SKILL/总控.json`（`workflow_settings.MASTER_MANIFEST`）；宪法四条见 `architecture.md` §“总控 SKILL 宪法” |
| 分层依赖 | `architecture.md` 第 3 节分层表 |
| 路径 | `stage_layout` / `storyboard_paths` / `script_contract` / `asset_contract` / `model_pool.env_file` |
| 事件与前缀 | `pet_bus` 事件表 / `broadcaster` 前缀表 |
| 缓存与索引 | `file_cache` / `asset_thumbs` / `hash_backend` / `*_manifest` / `*_lifecycle` |
| 删除与回收 | `storage_maintenance.recycle_paths()` |
| 阶段命令入口 | `stage_handler_registry.start()` |
| 动态导入 | `ui_plugin_registry.module()` |
| 阶段路径 | `stage_path_service.write_dir()` / `read_dirs()` |
| 阶段完成核验 | `stage_completion_service`；剧本准备顺序确认用其 `preparation_progress()`（设定→大纲→角色卡，三虎监控共用） |
| UI 组件与弹窗 | `ui_widgets`（组件与全局 Style）／`ui_tokens`（视觉 token）／`ui_shortcuts`（快捷键登记） |
| L2 写服务结果 / 项目上下文 / 阶段成果发布器 | `service_contract` 四字段结果、L3 注入的 `project_context.ProjectContext`、`stage_execution_service.publish_stage_*()`；每轮最多迁 3 个 service，细则见 `architecture.md` §“权威源补充条款” |
| 正式 JSON 读写 | 读 `file_cache.read_json()`；写 `agent.core.save()`／`save_text()` 或 L3 发布器；L2 写服务只接收注入的发布器 |
| 持久化产物版本 | `artifact_schema`：新写入写 `schema_version`，读取侧容忍缺版本 |

`stage_layout.validate_stage_contract()` 守卫目录阶段契约；变更 `pet_bus.STAGES` 或 `stage_layout.STAGES` 的轮次必须使它通过。

### 2.3 新增结构硬约束（第 118 期起）

编号保留原值，缺号为已删除条款，不复用。

11. **分层依赖唯一权威**：`architecture.md` 第 3 节。只允许 `L5 入口 → L4 UI → L3 编排 → L2 业务 → L1 模型/存储 → L0 契约`；反向 import 一律禁止。
12. **路径唯一权威**：文件路径由 2.2 表中“路径”那一行的模块产出；其他模块不字符串拼接路径。
13. **事件与前缀唯一权威**：阶段事件只由 `pet_bus` 定义，播报前缀只由 `broadcaster` 定义。
14. **删除唯一权威**：用户可见删除统一经 `storage_maintenance.recycle_paths()`；临时文件、缓存和已验证的本轮临时产物可受控清理。
15. **测试文件唯一位置**：新测试一律放 `tests/`；现有测试位置由文档一致性门禁检查。
16. **测试搬家轮**：只移动文件和修 import 路径，测试逻辑、断言与 fixture 保持原样；验收见 §3 与 §5。
17. **阶段启动唯一入口**：手动、自动和三虎阶段启动都走 `stage_handler_registry.start()`。
18. **动态导入唯一入口**：L4 走 `ui_plugin_registry.module()`，L3 走 `stage_handler_registry`；动态 `import` 先登记。
19. **阶段路径新写旧读**：新写入走 `stage_path_service`；旧目录只读兼容。
20. **完成事件以产物核验为准**：由 `stage_completion_service` 核验产物；模型文字和 UI 提示不算完成证据。
22. **事件发送边界**：跨模块状态只经 `pet_bus.emit_safe()`；仅 `pet_agent._emit()` 与 `pet_ui._emit()` 可作受控转发，不直调 `Bus.emit()`。`broadcaster` 只记录用户可见文本日志。

### 2.4 测试契约变更

接口、模块、路径或用户明确要求的 UI 契约发生有意变更时，可同步测试定位和预期；未变行为的断言保持原样，弱化、删除断言或跳过测试都不用来制造通过。结果报告说明契约变化与回归证据。

## 2.5 轮次与执行纪律

25. **任务范围优先**：治理和审计由实际风险或用户任务触发，不为凑固定轮次插入无关改动。
26. **新规则必须配测试**：2.3 节每新增一条硬约束，同一轮或下一轮补一个自动化测试；没有测试的约束降级为「建议」，不列入 2.3 节。
27. **轮次与队列跨树唯一**：开工先运行 `维护记录/基准脚本/round_claim.py next` 领取轮次，有匹配队列任务时再 `claim <队列ID> --owner <署名>`；有效租约属于他人时不覆盖。每轮结束检查 `N == M + 1`（N 为 project_status.md 当前轮次，M 为最新结果文件轮次）。一轮＝一个可独立回滚的完整变更集，同类改动批量成轮。并行车道、租约、检查点细则见 `runbook.md` §12。
28. **一个动作一个入口**：新增功能前先搜已有入口能否复用；本轮范围内存在重复入口时，先核验消费者与兼容要求再统一；范围外重复项只记录。
29. **三个基线数**：每轮结束报告：默认冒烟基线 8/8；架构门禁的当轮实际总数、失败集合及改前后比较（历史绿色结果不等于当前树通过）；全量回归与欠账以 Git common-dir 的 `full-safe-receipts.json` 真实 `{tree, round, seconds, at}` 为唯一权威。
30. **桌面主动后台任务**：`Desktop.async_()` 的提交、逻辑取消、成功／失败收尾与迟到结果拒绝经 `BackgroundTaskLifecycle`；已取消或被新代次替换的结果不触发 UI 回调。
30a. **欠账如实记录**：本轮产生的欠账在授权范围内闭环；历史欠账先核验影响，保留记录、不扩大任务。
32. 连续两次修复未解决同一问题时，先补充复现、堆栈或测量证据并重新诊断，再继续修复。
33. **启动路径零递归扫描**：窗口出现到可交互之间不 rglob / walk 任何目录；文件列表来自缓存、后台线程加载后更新，或用户点按钮时懒加载。
34. **UI 设计唯一权威**：`design_tokens.md` 与 `ui_components.md`。`padx` / `pady`、颜色、字号、圆角从 token 取值，不写魔法数字与内联 hex。
34a. **功能工作树开发**：新功能与 Bug 修复在专用 `codex/<任务>` 工作树进行，主工作区只做同步、合并、提交。动手改 `程序/` 源码之前，第一步是 `dev.py claim` 或确认已在功能工作树分支上；`pre-commit`、`round_claim`、`commit-msg` 三道闸兜底。流程见 `runbook.md` §12。

## 2.6 Git 提交门禁

提交与领号由当前执行 agent 执行；复核全绿后提交，一批一轮，只暂存本批文件，提交信息带轮次号（`R745: 说明`；失败检查点 `R745-FAIL:`），涉及需求的带 `REQ-`／`DES-` 编号。

- 提交前查 `git status` 与暂存清单；命中凭据形态或受忽略运行路径即拒绝提交，并在结果文件记录。私有数据、日志、用户项目内容保持在暂存区之外。
- 提交用 `scripts\dev.py commit -m "R<N>: 说明" [文件...]`，自动暂存并生成白名单；非默认文档的 `程序/` 文件须设置 `CODEX_STAGE_ALLOWLIST`。
- 只在用户明确要求时 `git push`；回滚优先 `git revert`。
- 结果文件记录是否已提交及 commit hash；仅 master 可提交 `project_status.md`。hooks、合并核对命令等见 `runbook.md` §13。

## 2.7 文档先行：需求 → 设计 → 实现

适用 `docs/stages/` 已建阶段。功能轮与契约轮改变阶段行为时，先改需求（`REQ-`）、再改设计（`DES-`）、最后改代码与测试；需求与代码冲突时标 🟡 或 ❓，由用户拍板。测试锚定 `REQ-xx` 由门禁强制。全文见 `runbook.md` §14。

## 3. 轮次类型

每轮开工前声明类型；各类型边界全文见 `runbook.md` §15。

| 节 | 类型 | 要点 |
| --- | --- | --- |
| 3.1 | 功能轮（默认） | 先改文档再写码；跑 `--affected` |
| 3.2 | 修复轮 | 先定位根因；只改根因所在模块 |
| 3.3 | 结构治理轮 | 每次最多 3 个模块；子场景（只读诊断／按报告执行）由用户指定，未指定先反问 |
| 3.4 | 契约轮 | 见下 |
| 3.5 | 只读诊断轮 | 见下 |
| 3.6–3.11 | 测试搬家／性能／可靠性／兼容／验证基线／状态接续 | 见 runbook §15 |

### 3.4 契约轮

- 只改 `pet_bus` / `script_contract` / `asset_contract` / `stage_layout` / `storyboard_paths`。
- 不动 L1 以上。
- 跑全量自检。
- 更新 `AGENTS.md` 硬约束与 `architecture.md`。

### 3.5 只读诊断轮

只诊断：保持 `.py` 不变，不搬目录、重命名、删文件；仅新增未占用的 `tasks_round/tasks_round_N_result.md`，等用户确认后再进入修复。写入边界例外见 `runbook.md` §15。

## 4. 执行方

当前执行 agent 自己完成改代码、跑测试、领号、提交。用能满足验收的最简改动，不多加模块、抽象、配置项或文件。含 Tk 的测试经 `工作流任务/gui_hidden.py` 在隐藏桌面运行。提交前自检验收标准、改动范围与 §5 适用验证；未运行的写「未运行」。

## 5. 自检规则

本节是测试触发规则的唯一文档定义；命令用随附解释器，工作目录 `程序`。只读诊断默认不跑测试，除非用户要求。Animatic 阶段契约变更须覆盖 SG-A/SG-B、13 阶段顺序、旧编号目录只读兼容和发布失败回滚。

**写测试**：修复与可判定的设计规则先红后绿（结果文件贴改动前失败输出）；断言检验行为而非源码字符串，UI 用真 Tk 量几何；skip 只引用 `tests/skip_reasons.py` 常量并登记 `维护记录/skip台账.json`。

| 时机 | 命令 | 说明 |
| --- | --- | --- |
| 每轮 | `python smoke_test.py` | 失败后继续修复，不进入完成状态 |
| 改动活跃逻辑 | `python smoke_test.py --affected <模块名>` | 只跑受影响测试模块；被其它模块 import 的模块必须覆盖全部消费者 |
| 增量回归 | `python smoke_test.py --gate` | 按台账串行执行改动过的测试文件 |
| 结构治理／跨层 | `python smoke_test.py --architecture` | 全部架构门禁；跑了 `--all --safe` 则不重复 |
| master 提交点：上次全量后累计 ≥ 8 个改过源码的轮次 | `run_selftests.py --all --safe` | 分支不累计欠账；后台会自动补跑 |
| 发布前／用户要求 | `run_selftests.py --all --safe` | 不通过先修复 |

- 定向用 `run_selftests.py -k <改动模块>`；失败先 `--affected`／`-k` 修到绿，再复验全量。
- 合并到 master 前，启动路径、Tk 控件生命周期、删除语义、层级登记表改动触发当次全量。
- 全量欠账口径、后台补跑、凭据复用见 `runbook.md` §4；唯一实现是 `run_selftests.full_safe_required()`／`risk_overdue()`。凭据七日内同 `HEAD:程序` 内容树可复用，须是真实绿凭据。
- 架构门禁清单在 `architecture.md` §“当前架构门禁清单”；增删架构测试时同轮更新清单、基线和结果报告。

## 6. 进度播报前缀

前缀来源 `broadcaster.PREFIX_PATTERNS`，阶段分母由 `Broadcaster.stage()` 从 `pet_bus.STAGES` 生成。展示格式：

`【阶段 X/13】`、`【步骤 Y/Z】`、`【门禁】`、`【警告】`、`【阻塞】`、`【完成】`、`【恢复】`、`【下一阶段】`、`【模式】`；无前缀消息会被拒绝。

## 7. 每轮结束时

1. 按规则 27 领取编号并新增结果文件，状态页轮次头同步为最新结果轮次加一。只读诊断保留既有结果编号。
2. 结果文件位于 `程序/tasks_round/tasks_round_N_result.md`，开头回答三问：本轮属于 §3 哪种类型？测试跑了吗、三个基线过了吗？`project_status.md` 的欠账少了吗？
3. 按 §2.6 收尾提交。`升级备份/` 与 `.bak_*` 保留为历史证据，回滚靠 Git，不再新增 `.bak_*`。

## 8. 任务执行协议

1. **持续执行直至完成**：持续推进，直到满足用户请求和全部适用验收条件，才标记 `[TASK_COMPLETE]`。写出代码、提交检查点、部分测试通过或报告失败都不等于完成。
2. **失败闭环**：定位原因 → 最小修复 → 复测失败项 → 适用回归，循环到完成；仍有安全、有效且在授权范围内的下一步时继续执行。连续失败按规则 32 补证据。
3. **完成标准**：交付物满足请求，§5 的适用检查通过，§4 交付前自检通过，§7 的报告／状态／提交完成；未运行或阻塞的必要检查如实标注。只读任务按其授权的检查和报告验收。
4. **真实阻塞例外**：用户明确要求停止，或继续必须获得新授权、凭据、外部服务恢复、用户选择，或存在无法安全绕过的环境限制时可暂停。暂停前穷尽范围内的安全检查和替代路径，保存可恢复状态，写明阻塞证据、已尝试方案及所需的最小用户动作；权限、用户改动和改动范围保持原样。
5. **状态真实**：满足第 3 条才输出 `[TASK_COMPLETE]`；真实阻塞输出 `[TASK_BLOCKED]`；`[TASK_FAILED]` 仅表示实测失败。结果、门槛、失败断言和历史凭据都按实际情况报告。
6. **范围不扩张**：范围外缺陷记录影响；修复需要扩大范围时先请求授权。阻断当前验收的历史欠账按第 4 条处理，不自动标为已解决。

## 9. 上下文与接力

上下文不足或被中断时，把目标、已改文件、实际验证、阻塞和下一条安全操作写进本轮结果文件；`.agent-handoff/` 已停更。压缩上下文不代表完成，新会话按 §0 恢复。
