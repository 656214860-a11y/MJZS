# R525 结构治理轮（只读诊断）：架构登记与文档漂移

## 轮次结论

- 本轮为只读诊断：未修改 `.py`、测试、`project_status.md`、SKILL 或用户项目数据；仅按轮次契约新增本结果报告。
- 未执行默认冒烟、架构门禁或全量回归。可引用的最近验证基线为 R501：默认冒烟 8/8、架构 92/92、全量安全回归 3,230/3,230。
- 发现 1 项 P1、2 项 P2 治理问题；它们不会立刻改变运行行为，但会使架构门禁和维护决策失真。

## A. 诊断范围

检查模块分层登记、架构门禁覆盖、阶段 SKILL 实际目录与文档、验证基线的单一权威来源；不评审产品功能正确性。

## B. 现状基线

- `skills/` 已实际存在 `00全流程SKILL` 和 `01 剧本准备SKILL` 至 `12质检交付SKILL` 阶段目录；例如 `script-dialogue-polish.skill.md` 位于 `skills/01 剧本准备SKILL/`。
- `architecture.md` 已声明注册器递归扫描 `skills/**/*.skill.md` 并按 `01`—`12` 阶段目录归类。
- 架构测试只对 `tests/architecture/_layers.py` 中登记的模块做依赖方向检查。

## C. 已证实问题

### [P1] `idea_attachments` 未纳入分层登记，依赖方向完全跳过

- 位置：`tests/architecture/test_layers.py:10-13`、`tests/architecture/_layers.py:18-27`、`idea_attachments.py:1-46`
- 证据：门禁使用 `source_layer = LAYERS.get(source)`，随后 `if source_layer is None: continue`；`_layers.py` 的 L2 登记含 `idea_chat`，但无 `idea_attachments`。实际附件模块为桌面端模型提交提供受控读取与上下文组装。
- 影响：该模块即使未来导入 L3/L4，也不会被架构门禁报告；附件边界从架构治理中脱落。
- 最小修复：在 `_layers.py` 将 `idea_attachments` 登记为 L2，并在 `architecture.md` / `PROJECT_MAP.md` 标注其为剧本准备的文本附档领域服务。
- 置信度：高。

### [P2] SKILL 清单仍写旧的扁平路径，与阶段目录事实冲突

- 位置：`architecture.md:35-51`
- 证据：同一文档先说明递归扫描并按阶段目录归类，表格随后却将剧本 SKILL 标为 ``skills/script-*.skill.md``，分镜标为 ``skills/storyboard-*.skill.md``；实际文件为 ``skills/01 剧本准备SKILL/script-dialogue-polish.skill.md`` 等阶段路径。
- 影响：维护者按架构清单定位/清理 SKILL 会找不到文件，且难以核对阶段配置的自动归类是否正确。
- 最小修复：由注册器扫描结果生成或校对架构清单，表格改为阶段目录路径；保留“递归扫描”作为唯一事实来源。
- 置信度：高。

### [P2] 分层文档与架构门禁对 `skill_panel` 的层级定义相反

- 位置：`architecture.md:62-63`、`tests/architecture/_layers.py:22-27`
- 证据：`architecture.md` 将 ``skill_panel`` 列在 L4 UI；`_layers.py` 却通过 ``_register(3, ..., "skill_panel", ...)`` 将它登记为 L3。
- 影响：文档设计评审与自动门禁按不同依赖方向判断；一次合法的 L4 调用可能被文档误判，或反之。
- 最小修复：依据 `skill_panel.py` 是否直接持有 Tk 控件确定唯一层级；同步修改文档或登记表中的一处，并添加该模块的边界测试。
- 置信度：高。

### [P2] `AGENTS.md` 内部存在两个相互冲突的全量基线

- 位置：`AGENTS.md:148`、`AGENTS.md:330`
- 证据：前者写“全量回归：当前基线 3,205 条”，后者写“全量安全自检为 3,230 条（R501）”；`project_status.md:59` 也记录 R501 为 3,230/3,230。
- 影响：执行者可能以过时的 3,205 条作为验收阈值，掩盖收集缺失或错误地判定回归结果。
- 最小修复：将第 2.5 节的数值更新为 3,230，并只保留一处“当前验证基线”正文，其他位置引用该处。
- 置信度：高。

## D. 不做事项

- 不为让门禁变绿而把模块加入忽略名单，或弱化任何测试断言。
- 不移动 SKILL、测试或业务模块；本轮不把文档漂移与功能改动混做。
- 不更新 `project_status.md`：本轮遵循只读诊断例外，仅写结果报告；状态台账留待后续执行轮统一刷新。

## E. 风险分级

- P1：`idea_attachments` 的依赖方向没有自动防线。
- P2：SKILL 路径、`skill_panel` 层级和全量基线三处事实源不一致。
- P0：未发现可由本轮静态证据确认的数据写入、密钥暴露或运行时阻断问题。

## F. 验收口径

后续整改轮须满足：

1. `idea_attachments` 在层级登记中可见，且其到 L3/L4 的违规导入能被门禁捕获；
2. `architecture.md`、`PROJECT_MAP.md` 与 `skill_registry.py` 的阶段路径一致；
3. `AGENTS.md` 和 `project_status.md` 对当前全量基线仅有一个相同数值；
4. 仅运行受影响架构测试、附件测试和默认冒烟；不因文档修订伪造全量回归。

## G. 结构影响边界

- 建议整改文件仅限：`tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md`、`AGENTS.md`，以及必要的新/迁移测试文件。
- 不触及阶段配置面板逻辑、SKILL 内容、用户项目目录或模型提交行为。

## H. 复现条件

- 解释器：`D:\漫剧制作助手\运行环境\Python\python.exe`。
- 静态证据可直接由上述文件行号复核；本轮没有创建 Tk 窗口，也没有执行测试。

## I. 建议实施顺序

1. 先确定 `skill_panel` 的实际职责，统一 L3/L4 定义。
2. 登记 `idea_attachments` 为 L2，并增加最小架构边界测试。
3. 以注册器扫描结果刷新两个结构文档的 SKILL 路径。
4. 最后统一 AGENTS 与状态台账中的全量基线文字。

## J. 整改路线

- J1（结构治理轮，子场景：执行，P1）：完成 `idea_attachments` L2 登记；新增只验证“已登记且不越层”的边界测试，保持附件解析行为不变。
- J2（文档治理轮，P2）：将 SKILL 清单替换为 01—12 阶段目录事实，统一 `skill_panel` 层级说明，并人工抽样校对各阶段一个 SKILL。
- J3（基线治理轮，P2）：把 `AGENTS.md` 的过时 3,205 更正为 R501 的 3,230，并把未来基线更新收敛到单一段落。
- J4（验证轮）：执行受影响的架构/附件测试及默认冒烟；只有实际运行的结果才能刷新基线。

## K. 测试迁移计划

- K1：本轮不迁移测试文件。
- K2：执行 J1 时，将 `tests/test_idea_chat.py` 中纯 `idea_attachments.prepare()` 的测试移至新增 `tests/test_idea_attachments.py`；仅调整导入与收集位置，不改断言、fixture 或测试数据。
- K3：保留 `test_idea_chat.py` 中桌面选择附件、状态刷新、发送集成测试，避免把 UI 行为与无 Tk 的附件服务混在同一模块。
- K4：迁移后依次运行新模块、`test_idea_chat.py`、架构门禁和默认冒烟；全量测试不作为文档整改的默认门槛。

## L. 本轮自审

- 功能开发：否；本轮未改变产品行为。
- 测试执行：否；符合只读诊断范围。
- 代码/测试/状态台账修改：否；唯一写入为本轮结果报告。
- 欠账减少：否；已给出可执行的 J 路线，待后续执行轮闭环。

## M. 下一步建议

进入一次“结构治理执行轮”，按 J1→J3 的最小文件集收敛三类事实源，再按 J4 做受影响验证。不得将本只读诊断报告视为功能或基线验收通过。
