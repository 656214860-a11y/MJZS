# 任务书 · Skill 体系重构：删总控 → 共享输入框 + `/` 命令调用完整 Skill

> 本任务书自包含，执行者无需本会话上下文。这是一个**跨 5 轮的架构重构**，每轮一个可独立回滚的变更集，
> 按顺序执行；每轮单独领号、验收、提交（`AGENTS.md` §2.5–§2.6、§7）。
> 开工前必读：`程序/AGENTS.md` §0、§2（硬约束）、§5（测试）；分层见 `程序/architecture.md` 第 3 节。

---

## 1. 总目标与架构蓝图

把当前的「总控分层映射 + 每阶段"手动制作XX"按钮」改成：

```
┌───────────────────────────────────────────────┐
│ 左侧：13 阶段目录（切换页面 = 切换当前阶段/可用 skill）│
│ 中部：当前阶段内容                              │
│ 01 页：保留创意对话气泡区（单线程，不按模型隔离）      │
│ 02–13 页：无对话气泡，模型只输出对应阶段的文件       │
│ 底部：一个【共享输入框】（固定、跨 13 页复用同一个）   │
│   [skill 图标][附件图标] [输入框] [模型图标][发送]  │
└───────────────────────────────────────────────┘
  /skill名 或 /阶段别名 或 /子引擎 → 调用已装 skill 全部功能
  自由聊天（默认）与 / 命令（混合）
  三虎自动 → 按阶段配置里默认勾选的 skill 跑（子引擎天然对应阶段）
```

**上下文模型（已拍板）**：共享**事实**（`ProjectContext`：已确认设定/自然剧本/结构剧本/清单），**不共享对话**。
取消"按模型隔离对话"：同一阶段的对话是单线程，切模型续用同一历史。

**关键不变**：13 阶段顺序与"下阶段依赖上阶段产物"规则不动（由 `stage_parallel`/`confirm_gates`/`stage_completion_service` 强制，与 UI 无关）；阶段 skill 文件夹保留；零第三方依赖；git 是唯一复用依赖。

---

## 2. 已确认决策清单（执行者必须遵守，不得自行变更）

1. 删除 `总控.json` + `master_skill.py` + `master_import_service.py` + 总控模式开关；制作锁移到**弹窗预选**。
2. 完整安装 skill（不按阶段拆分），`/` 命令调用 skill 全部功能；命令形态**三者都支持**：`/skill名`、`/阶段别名`、`/子引擎`。
3. 共享输入框：混合模式（自由聊天 + `/` 补全）。
4. 阶段配置面板：**只留 skill 勾选 + 技能说明**；点击技能说明查看完整技能文档；其他内容删除。
5. 共享输入框左下角 = skill 入口图标（附件图标右侧，参考 Devin desktop command skill）；右下角 = 模型选择器图标（发送图标左侧，参考 DSH）。
6. 其他阶段（02–13）**不需要聊天气泡**、不显示模型对话，只有输入框；模型输出 = 对应阶段文件。
7. 取消按模型隔离对话（单线程），并保留两个防护：请求在途**锁定模型快照**（切选择器只影响下一次请求，现有 `writing_api` 机制保留）；可选切模型插系统标注（默认不做）。
8. skill 安装：**自写薄 git 层**（不引 uv/Node），接口对齐 [skill-mgr](https://pypi.org/project/skill-mgr/) 的 `install/update/uninstall/validate/list`；支持**仓库地址 + 本地导入**；**无网络搜索/市场**。
9. 发送路径必须补**上游完成门禁**（删总控门禁后留下的唯一洞）：当前阶段上游空白 → 拒绝发送并提示。
10. 三虎自动：按阶段配置**默认勾选的 skill** 跑流程。

---

## 3. 现状盘点（执行者必读文件）

| 文件 | 现状 | 本次动作 |
|------|------|---------|
| `skills/00全流程SKILL/总控.json` | 总控清单（presets→stage_skills/locks） | 轮 1 删除 |
| `master_skill.py` | 总控指纹/自动同步/体检/门禁 | 轮 1 删除 |
| `master_import_service.py` | 总控包导入 | 轮 1 删除 |
| `workflow_settings.py` | `MASTER_MANIFEST`、`master_gate`、`WORKFLOW_PRESETS` | 轮 1 清理；`resolve_for_send` 保留（发送冻结入口） |
| `skill_registry.py` | 扫描 01–13 目录+用户层、解析/校验/索引（`STAGE_DIRECTORY_IDS`） | 保留；`/` 补全的 skill 来源 |
| `skill_import_service.py` | 本地导入：预检→暂存→换入→试冻结→登记 | 轮 2 增加 git 仓库地址导入源 |
| `skill_panel*.py`（`skill_panel/skill_panel_workflow/skill_panel_presets/skill_panel_support`） | 阶段配置面板（skill 勾选/模型/总控/锁） | 轮 1 精简为 skill 勾选+技能说明；锁移弹窗 |
| `desktop_idea_chat.py`（`idea_input/idea_send/idea_attachment_button`） | 01 页对话输入框 | 轮 3 提炼为共享输入框组件的原型 |
| `desktop_idea_bubbles.py`、`idea_chat*.py`、`idea_document_paths.py` | 01 对话气泡/按模型隔离目录（`模型会话/<模型ID>/创意对话/`） | 轮 4 取消按模型隔离（单一创意对话目录，旧目录读取迁移） |
| `stage_parallel.py`（`UPSTREAM_BLANK/BLOCKED/upstream_exempt`）、`stage_completion_service.completion_evidence()`、`confirm_gates.py` | 上游依赖/阶段完成规则 | **保留不动**；轮 3 发送门禁复用 |
| `pet_bus.STAGES/STAGE_NAMES` | 13 阶段权威 | 保留；`/阶段别名` 映射来源 |
| `ui_widgets.py`（`TextArea/ContextMenu`）、`ui_shortcuts.py`、`ui_tokens.py` | UI 组件/快捷键/token | 保留；共享输入框复用 |

---

## 4. 分轮拆解（5 轮，按序执行）

### 轮 1：删总控机制 + 阶段配置面板精简

**改动**
- 删除：`skills/00全流程SKILL/总控.json`、`master_skill.py`、`master_import_service.py`。
- `workflow_settings.py`：移除 `MASTER_MANIFEST`、`WORKFLOW_PRESETS`、`master_gate` 及总控同步/体检调用链；`resolve_for_send` 保留（仍是发送边界唯一入口），只去掉总控部分。
- `skill_panel_workflow.py` 等：删除总控模式开关（`NO_MASTER` 相关）、"导入本地总控包"按钮；面板只保留：**skill 勾选 + 技能说明查看**（点击技能说明 = 打开该 `*.skill.md` 完整文档）；模型选择控件删除（轮 3 移到输入框图标）；制作锁保留但入口改为**弹窗预选**。
- 删除 `00全流程SKILL` 目录下仍被引用的总控专属文件（只删总控层；`AIGC创作全流程` 包与各子引擎保留）。

**验收**
- [ ] 全仓库无 `MASTER_MANIFEST`/`master_skill`/`master_import_service` 残留 import；`smoke_test.py` 8/8。
- [ ] 阶段配置面板可勾选 skill、点"技能说明"看完整文档、弹窗预选制作锁；无总控开关。
- [ ] 删除受影响测试（`test_master_skill.py`、`test_master_import_service.py`）或改写断言；`test_storyboard_final_scope.py` 等对 `MASTER_MANIFEST` 的引用同步修正（契约变更，不得跳过/弱化）。
- [ ] `python -B smoke_test.py --architecture` 全绿（总控相关架构门禁条目同步移除）。

### 轮 2：skill 安装器 git 导入（薄 git 层）

**改动**
- `skill_import_service.py` 增加 `import_from_repo(url_or_ref, ...)`：
  - 解析 `owner/repo` 简写与完整 URL（支持 `https://github.com/a/b`、`a/b`、可带 `@ref`）；
  - `git clone --depth 1` 到隐藏暂存目录 → 扫描 `SKILL.md`/`*.skill.md` → **复用现有**"预检→暂存→换入→试冻结→登记"管线（含回收站回滚）；
  - 失败清理暂存；clone 用 `subprocess` + 超时，日志脱敏（不写凭据）。
- 接口对齐 skill-mgr 生命周期：`install`（=新增/覆盖导入）、`update`（同来源刷新）、`uninstall`（回收站移除）、`validate`（现有试冻结）、`list`（`skill_registry.getAll`）。
- 阶段配置面板加"从仓库地址导入"输入框（无搜索、无市场、无网络技能列表）。

**验收**
- [ ] `a/b`、完整 URL、`@分支` 三种写法都能导入并出现在对应阶段；损坏/无 SKILL.md 的仓库明确报错且不留暂存。
- [ ] update 覆盖旧版走回收站可恢复；uninstall 走 `storage_maintenance.recycle_paths`。
- [ ] 新增测试 `tests/test_skill_repo_import.py`（解析/clone 失败/扫描/复用管线/回滚，clone 用 mock 或本地裸仓，不依赖外网）；`-k skill_import skill_registry` 全绿。

### 轮 3：共享输入框组件（核心轮）

**改动**
- 新建共享输入框模块（建议 `desktop_shared_input.py` + 无 Tk 解析模块 `skill_command.py`）：
  - **布局**（底部固定、跨页复用同一实例）：`[skill 图标][附件图标] | [TextArea 输入框] | [模型图标][发送]`；图标语义色/尺寸走 `ui_tokens`，不写内联 hex。
  - **`/` 命令解析**（纯标准库，无 Tk 单测）：输入以 `/` 开头 → 解析为 `skill名`｜`阶段别名`（`pet_bus.STAGE_NAMES` 反向映射）｜`子引擎`（`AIGC创作全流程` 内子引擎目录名）三者之一；`/` 弹出补全列表（当前阶段已装 skill 优先，其余靠后）；非 `/` 开头 = 自由聊天。
  - **发送路径门禁**：发送前按当前阶段查上游完成状态（复用 `stage_parallel` 上游判定 + `stage_completion_service.completion_evidence`）；上游空白 → 拒绝发送 + 状态栏提示"请先完成/确认 XX 阶段"；剧本准备简报门禁保留（收集制作锁）。
  - **模型选择器图标**：点击弹出模型选择（复用现有模型选择逻辑）；**请求在途锁定模型快照**，切换只影响下一次请求（沿用 `writing_api` 校验输入版本及模型选择机制）。
  - **发送**：复用现有发送/取消/结算生命周期（`model_metering.metered` 链路不动）。
- 阶段配置面板的 skill 入口图标 = 打开"只含 skill 勾选 + 技能说明"的面板（轮 1 的产物）。

**验收**
- [ ] 组件底部固定、跨页同实例；四图标位置正确（skill/附件左，模型/发送右）；`ui_shortcuts` 登记 `/` 触发与 `Esc` 关闭补全。
- [ ] `/剧本` `/分镜` `/skill名` `/子引擎` 三种形态都能解析到目标 skill 并进入发送；自由聊天照常发送。
- [ ] 上游空白阶段发送被拒且提示明确；上游就绪后放行。
- [ ] 在途请求切换模型不改变本次请求模型（快照锁定）。
- [ ] 新增测试：`tests/test_skill_command.py`（无 Tk 解析/补全排序/别名映射）+ `tests/test_shared_input_ui.py`（真 Tk 隐藏桌面：布局几何/图标位置/发送门禁/快照锁定）；`-k idea_chat writing_api` 回归全绿。

### 轮 4：13 阶段接入共享输入框 + 取消按模型隔离

**改动**
- 01 剧本准备：输入区替换为共享输入框（复用同一实例），**对话气泡区保留**；`desktop_idea_chat.py`/`desktop_idea_bubbles.py` 只改输入源，不动气泡渲染。
- 02–13：接入共享输入框；**不渲染对话气泡、不显示模型对话**；模型回复的处理路径 = 写对应阶段文件 + 状态栏提示 + 阶段文件列表刷新（沿用各阶段现有"成果发布"逻辑 `stage_execution_service.publish_stage_*`）。
- 取消按模型隔离：`idea_document_paths.py` 的 `模型会话/<稳定模型ID--摘要>/创意对话/` 改为**单一创意对话目录**；旧目录首次读取迁移（只迁移不删旧文件，PROJECT_MAP R1247 口径）。
- 阶段切换 = 改变"当前阶段"（影响 `/` 补全列表与发送门禁的上下文），**不新建输入框实例**。

**验收**
- [ ] 13 页共用同一个底部输入框；01 有气泡、02–13 无气泡。
- [ ] 在 03 页发送命令后，模型输出落到 03 的成果目录并刷新文件列表；状态栏反馈。
- [ ] 切模型后对话历史仍在同一线程（不再按模型分目录）；旧模型目录内容首次读取迁移成功。
- [ ] 新增/改写测试：`tests/test_shared_input_stages.py`（各页接入/气泡有无/输出落目录）+ `test_idea_download_import`/`test_idea_chat*` 中按模型隔离断言同步改写（契约变更）。

### 轮 5：三虎自动适配"默认勾选 skill"

**改动**
- 三虎全自动：每阶段执行"阶段配置里**默认勾选的 skill**"（可能多个，按面板顺序），子引擎天然对应阶段；不再依赖总控清单。
- `stage_flow.py`/`stage_handler_registry.py` 的自动编排：把"取总控 skill"改为"取该阶段已勾选 skill 列表"；无勾选 skill 的阶段自动跳过并提示。
- 自动模式下沿用发送门禁与成果核验（`stage_completion_service`），不因删总控放宽。

**验收**
- [ ] 阶段勾选单个/多个 skill 时自动流程按序执行；未勾选阶段跳过并提示。
- [ ] 自动跑完仍满足阶段完成核验（产物核验为准，模型文字不算完成）。
- [ ] `-k stage_flow automation` 回归全绿；`smoke_test.py` 8/8。

---

## 5. 跨轮共享规则（不得破坏）

- **阶段依赖规则**：始终由 `stage_parallel`/`confirm_gates`/`stage_completion_service` 强制；UI 只做"发送前提示"，不复制判定逻辑。
- **零第三方依赖**：不引 uv/Node/npm/typer/rich；git 是既有依赖（工作树功能在用）。
- **事件与播报**：新交互的事件走 `pet_bus.emit_safe`，播报前缀走 `broadcaster`；不动事件契约。
- **正式 JSON 读写**：读 `file_cache.read_json`，写 `agent.core.save/save_text` 或 L3 发布器。
- **右键菜单/快捷键**：经 `ContextMenu`/`ShortcutRegistry`（架构门禁）。
- **每轮三个基线**：默认冒烟 8/8；改动跨层跑 `--architecture`；全量欠账按 `AGENTS.md` §5 口径如实报告。

## 6. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 删总控后阶段无默认 skill，三虎空跑 | 轮 1 保留 pipeline-* 文件与面板勾选；轮 5 把"勾选列表"作为默认 |
| 共享输入框跨页实例生命周期 | 单实例挂在 `Desktop`，页面切换只换上下文；测试覆盖切页不重建 |
| 取消按模型隔离丢历史 | 只迁移不删旧目录；迁移失败读旧目录兜底 |
| git 导入网络/超时 | `--depth 1` + 超时 + 暂存清理；失败不留垃圾 |
| 发送门禁误伤自由聊天 | 只拦"当前阶段上游空白"，不拦纯问答（01 简报门禁口径不变） |

## 7. 交付与留痕

- 每轮：`tasks_round/tasks_round_N_result.md` 开头回答三问（轮次类型/测试与三基线/欠账），§7 收尾；提交信息 `R<N>: skill体系重构·轮X 说明`。
- 每轮更新 `PROJECT_MAP.md` 相关行；轮 5 后整体更新"三虎与自动化""模型与安全"两节。
- 涉及 `AGENTS.md` §2.2 权威源表的变更（删总控行）在轮 1 同步。
