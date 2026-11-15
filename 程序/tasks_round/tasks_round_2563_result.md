# R2563 结果：功能轮——阶段模型选择器（仅模型名＋可调推理等级）

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）。用户指令：把「阶段配置」右侧的模型下拉框改成 DeepSeek Harness
   式模型选择器，可调推理等级；删除选择器里的 provider 信息只留模型名。
   用户拍板：档位「自动／低／中／高」，存配置＋真实下发，等级以菜单内嵌子菜单调整。

2. **测试跑了吗、三个基线过了吗？**
   - `smoke_test.py` 默认冒烟：**8/8**（基线不变）。
   - `smoke_test.py --affected stage_model_picker model_router writing_api
     storyboard_direct_api stage_config stage_model_value`：门禁串行 82 个测试文件
     **1822 条用例 0 红**（518.4 秒），含新增 `test_stage_reasoning` 18 条、
     改过的 `test_skills` 154 条、`test_idea_chat`、写作域与模型域全部消费方。
   - 架构门禁随 `--affected` 内的 architecture 用例一并通过
     （`test_writing_api_stage_config_boundary` 等 5 个 architecture 文件全绿）。
   - 全量 `--all --safe`：本轮未跑（功能轮按 §5 只跑 affected＋冒烟；
     主干全量欠账由 master 出口档统一记账，与本轮无关）。

3. **`project_status.md` 的欠账少了吗？**
   未减少也未新增。本轮无结构治理内容；工作树里并存 R2551 车道的未提交改动
   （`skill_inline.py`/`workflow_settings.py`/`error_codes.py` 等）与本轮无关，
   未触碰、未暂存。

## 交付内容

### 需求/设计（文档先行）

- `docs/stages/S01_剧本准备.md`：REQ-S01-82 新增（模型选择器契约），DES-S01-82
  新增（字段/映射/注入点全链说明），测试锚定表加 `test_stage_reasoning`＋`test_skills`。

### 实现

- **L1 `stage_config.py`**：阶段项新增 `reasoning` 字段；`REASONING_LEVELS`
  ＝auto/low/medium/high，`clean_reasoning` 把缺省/未知值归一为 auto；
  `default_entry`/`load`/`get`/`save_all`/`put(..., reasoning=…)` 全链带上，
  旧项目无该字段读出即 auto（向后兼容）。
- **L1 `stage_model_value.py`**：新增 `reasoning()`/`reasoning_options()` 只读口，
  auto/缺失/坏配置返回空表。
- **L1 `model_router.py`**：`ModelAdapter.payload` 按 `wire_api` 映射——
  chat→`reasoning_effort`，responses→`reasoning.effort`，messages→
  `thinking.budget_tokens`（low 1024／medium 8192／high 32768，截到
  `max_tokens-1` 且低于下限不下发）；仅对带 `reasoning` 能力标签的模型下发，
  auto 与无能力模型不附加任何参数。
- **L3 `writing_api.py`**：`WritingRequestAdapter._call` 把本阶段
  `reasoning_options` 以 `setdefault` 并入 options（调用方显式给的不覆盖）。
- **L3 `storyboard_direct_api.py`**：`_ask` 主请求与候选组回落请求同样并入。
- **L4 `stage_model_picker.py`**：`SelectBox` 换 `ttk.Menubutton`＋`tk.Menu`
  （`postcommand` 展开时重建）；菜单项 `label=模型名`（去掉「供应商 · 」前缀），
  带推理能力的项右侧 `accelerator=推理·<档位>`；「推理等级：X」cascade 子菜单
  四档单选经 `stage_config.put(reasoning=…)` 落盘；「+ 添加模型…」仍是尾项；
  `set_model`/`set_model_label`/`labels()`/`refresh_models` 契约保留，
  模型目录条同步（REQ-S01-80）与生命周期（attach/destroy）不变。

### 测试

- 新增 `tests/test_stage_reasoning.py`（18 条）：配置持久化/归一/兼容、
  options 注入、三种 wire_api 映射、能力门禁、预算截断、选择器菜单
  （仅模型名、档位标记、cascade、尾项、档位落盘）。
- `tests/test_skills.py`：四处旧断言同步新契约（`values`→`labels()`、
  供应商前缀断言改为「无前缀」断言、菜单尾项断言改 `entrycget`、
  `set_model_label` 断言改为当前项＝纯模型名）。断言语义未弱化。

## 已知边界

- 推理等级对不带 `reasoning` 能力标签的模型（含生产模型/CLI 引擎）不下发参数；
  「自动」档任何模型都不附加参数。
- 档位映射为线协议档位字符串（low/medium/high），各服务商是否真正执行由其
  服务端决定；OpenAI 兼容端不支持的档位由服务端按其能力处理。
- `skill_panel.Panel` 内部不再有模型下拉（既有契约），本轮未新增等级控件到面板。

## 提交

- 分支 `codex/wip-R2563`；`dev.py commit` 只暂存本轮 9 个文件
  （S01 文档、stage_config、stage_model_value、model_router、writing_api、
  storyboard_direct_api、stage_model_picker、test_skills、test_stage_reasoning），
  commit hash 见 git log（R2563）。
- R2551 车道的未提交改动与 `tasks_round_2551_result.md` 未纳入本轮提交。
