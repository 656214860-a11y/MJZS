# R626 只读诊断轮——桌面引擎“自动改走”行为核实

## 开头三问（AGENTS.md 第 7 节）

- 本轮是功能轮还是整理轮？**只读诊断轮**（AGENTS.md 3.5）。
- 测试跑了吗？三个基线过了吗？**未跑**；本轮禁止改代码，证据来自源码、既有测试和只读配置检查，不能把既有基线重新表述为本轮结果。
- `project_status.md` 的欠账少了吗？**没有**；本轮只新增诊断证据。

编号自检：`project_status.md:3` 记录“626 待执行”；只读检查 `tasks_round/tasks_round_626_result.md` 返回 `False`，故连续新增 R626，未覆盖既有文件。

## A. 触发逻辑

### A1. 完整条件

自动改走的入口是 [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:334) 的 `current()`。其原始关键代码为：

```python
selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
item = model_pool.pool(program=Path(__file__).resolve().parent).get(selected, {})
explicit_engine = model_pool.desktop_engine(selected)
if explicit_engine:
    engine = explicit_engine
else:
    local_engine, local_program = _local_engine_for_selected_model(value, selected, item, stage)
    if local_engine:
        engine = local_engine
    elif item:
        engine = 'qwen'
```

其中显式 `chatgpt-desktop` / `claude-desktop` 是用户直接选桌面模型，不属于本轮所说的“自动改走”。自动分支的完整判断在 [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:318)：

```python
def _local_engine_for_selected_model(value, selected, item, stage):
    """已选 OpenAI/Anthropic 模型有本机 Agent 时，优先回到对应本机客户端。"""
    engine = model_pool.desktop_engine(selected)
    if not engine:
        engine = {'GPT': 'codex', 'Anthropic': 'claude'}.get(
            model_pool.provider_name(selected, item), '')
    if not engine:
        return '', ''
    try:
        profile = validate_stage_profile(value['profiles'][engine], stage)
        return engine, find_program({'engine': engine, 'program': profile['program']})
    except (KeyError, ValueError):
        return '', ''
```

所以条件是：阶段已保存非桌面模型 ID；该 ID 在模型池中有记录；`provider_name()` 结果恰为 `GPT` 或 `Anthropic`；且已载入的对应 profile 可校验、`find_program()` 找到 Codex/Claude 程序。任一条件不成立时返回空对，随后有模型池记录的 API 模型走 `qwen`（兼容 API 调用器）。没有配置开关；源码中只有上述硬编码映射表和 `if local_engine` 分支。

`find_program()` 的可执行文件判定在 [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:372)：先接受已配置 `program`，再 `shutil.which(engine+'.exe')`；Codex 再查 `%LOCALAPPDATA%/OpenAI/Codex/bin/*/codex.exe`，Claude 再查 `~/.local/bin/claude.exe`，否则抛 `ValueError`。该 `ValueError` 被上面的 helper 捕获，因而回落 API。

### A2. 会触发与不会触发的模型/协议

[model_pool.py](D:/漫剧制作助手/程序/model_pool.py:110) 的原始识别规则：

```python
if model_id == 'chatgpt-desktop' or model.startswith('gpt-'):
    return 'GPT'
if desktop_engine(model_id):
    return 'Anthropic'
...
if 'deepseek' in url:
    return 'DeepSeek'
if 'openai' in url:
    return 'OpenAI'
...
if configured == 'anthropic':
    return 'Anthropic'
```

- `gpt-*`（例如内置 `gpt-4o`，其 `provider` 虽是 `openai-compatible`）会得到 `GPT`，程序可用时自动成为 `codex`。
- API 记录明确配置 `provider: anthropic` 会得到 `Anthropic`，程序可用时自动成为 `claude`。
- DeepSeek 的 URL 得到 `DeepSeek`，不在 helper 的映射表，故 [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:349) 走 `engine='qwen'`；不是“因协议是 chat 就改走”。
- 非 GPT/Anthropic 的其它 API 记录也同样走 `qwen`；桌面 ID 则是前述显式选择。

既有 [tests/test_workflow.py](D:/漫剧制作助手/程序/tests/test_workflow.py:731) 直接锁定 DeepSeek：断言 `engine == 'qwen'`、`model == 'deepseek-v4-flash'`、API 根地址为 `https://api.deepseek.com`。

### A3. 运行时返回值与存档差异

当本机程序命中时，[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:356) 原始代码会改运行时 profile：

```python
profile['program']=local_program
profile['model']=''
selected_model, selected_api = stage_model(project,stage)
if selected_api:
    profile['api_fallback']={'model':selected_model,'api':selected_api,
                             'profile':validate_stage_profile(value['profiles']['qwen'],stage)}
```

故返回给执行器的 `engine` 被替换为 `codex`/`claude`，`program` 换为本机程序，主 `model` 清空；原 API 的模型 ID、接口/协议/密钥字段不作为主执行配置，而放入 `api_fallback`。只有本机启动抛由 `OSError` 导致的 `ValueError` 时，[workflow_engines.py](D:/漫剧制作助手/程序/workflow_engines.py:197) 才取该字段组装 `engine='qwen'` 的回退配置；`wire_api` 非 `chat/responses` 时不给该回退。

保存值没有被 `current()` 改写：它只调用 `stage_config.get()`；实际写入函数是 [stage_config.py](D:/漫剧制作助手/程序/stage_config.py:214) `put()`，且仅由调用者传入的 `model` / `skills` 更新后调用 `save_all()`。`current()` 中不存在 `put/save/save_all/write_text` 调用。

### A4. 开关

在 `workflow_settings.py`、`stage_config.py` 和模型池配置字段中未找到控制自动桌面优先的布尔/枚举设置；该行为是硬编码，用户不能在阶段配置页关闭。

## B. 引入历史与登记

### B1–B2. 可证明的历史边界

源码 [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:295) 的 `effective_model()` docstring 写“第 62 期任务 3”，但当前 `tasks_round/` 中不存在 `tasks_round_062_result.md`；按全文检索，最早保留且直接涉及此链路的结果是 [tasks_round_191_result.md](D:/漫剧制作助手/程序/tasks_round/tasks_round_191_result.md:1)。它明确写：

> `summary()` 改为读取 `current()` 和 `effective_model()`，与实际派发共用同一模型/引擎解析链。

并在审查节明确“仅统一摘要的读取来源；**不改模型选择规则**”。因此 R191 是**显示链路接入既有路由**，不是自动改走的引入轮。保留的结果文件不足以把 `_local_engine_for_selected_model()` 的首次引入精确归因到某一 R 号；能直接证明的最早设计来源是代码中的“第 62 期任务 3”标记，不能把它伪报成有结果文件佐证的轮次。

### B3. 文档登记

- [PROJECT_MAP.md](D:/漫剧制作助手/程序/PROJECT_MAP.md:13) 对 `workflow_settings.py/workflow_engines.py` 登记为“**本机 Codex/Claude 优先、兼容 API 回退**”。
- [tasks_round_182_optimization_checklist.md](D:/漫剧制作助手/程序/tasks_round/tasks_round_182_optimization_checklist.md:166) 登记“阶段配置的模型名必须与实际执行器一致”，下一行描述 DeepSeek 走兼容 API、桌面 Claude/Codex 走客户端。
- 但 [architecture.md](D:/漫剧制作助手/程序/architecture.md:144) 写的是“显式选择的本机 Agent，**不参与 API 自动抢占**”，与当前 A1 的硬编码自动抢占直接矛盾；[project_status.md](D:/漫剧制作助手/程序/project_status.md:449) 又写“阶段按所选厂商/协议/模型/密钥/SKILL 直连 API，不回退到 Qwen”，也不足以说明 GPT/Anthropic 的桌面优先条件。

结论：有高层登记和测试，但没有一份当前权威架构文档准确描述这个自动条件；`architecture.md` 甚至给出相反契约。

## C. 用户可见性

### C1. UI 提示

阶段配置本体读取并显示保存的 `stage_config.get(...)["model"]`；[skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:308) 的按钮逻辑在“已选模型”分支直接从模型池按 `chosen` 取显示名，并没有展示 `local_engine`、`local_program` 或“将改走桌面引擎”的提示。R625 的“未安装”后缀只适用于桌面 ID，不是 API 模型会被自动改走的标注。

存在一个非阶段配置本体的摘要：[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:434) 的 `summary()` 返回 `调用：{引擎} · {effective_model()} · {skill}`，且 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:301) 说明阶段入口在 `auto` 时会显示实际引擎。它不能在用户已手选 GPT/Anthropic API 的“阶段配置”选择控件中提前说明自动改走。

### C2. 日志/诊断

`_local_engine_for_selected_model()`、`current()` 和 `workflow_engines.launch_interactive()` 的改走/回退分支没有日志调用、诊断事件或用户提示文案。`launch_interactive()` 仅在失败时抛“本机 Agent 无法启动；未配置可兼容的 API 回退……”错误。因此成功的改走没有可检索运行日志记录。

### C3. 用户能否从阶段配置页看出

**不能。** 页面保存/显示的是原 `model` ID；A3 所述 `engine/program/model/api_fallback` 仅是 `current()` 组装的内存返回值。用户只有经摘要/执行行为间接发现，不会在该页看到“DeepSeek/GPT/Anthropic → Codex/Claude”的映射说明。

## D. 历史项目只读检查

检查对象为 `D:\漫剧下载\项目\摄像头3_20260924\skill_config.json`，只读取 JSON；未调用 `workflow_settings.current()`，避免 `stage_config.get()` 的同步清理路径产生任何写入可能。

原始脱敏输出：

```text
EXISTS=True
MODELS={'script': 'claude-opus-5.5', 'script_structure': 'deepseek-v4-flash', 'storyboard': 'deepseek-v4-flash', 'assets': '本地 FLUX.2 Klein / 自定义工作流', 'continuity': 'auto', 'final': 'auto', 'keyframe': 'auto', 'previs': 'auto', 'video': 'auto', 'audio': 'auto', 'edit': 'auto', 'delivery': 'auto'}
RUNTIME_FIELDS=[]
```

`ENTRY_FIELDS` 的全部阶段字段仅为 `model`、`skills`（剧本阶段另有 HOLLMWOOD 文本字段）；不存在 `engine`、`program`、`api_fallback`、`api`、`key_env` 或 `base_url`。因此：

- D1：存档含 `claude-opus-5.5` 与 DeepSeek 选择，但没有“已改走桌面”的历史字段，无法从文件证明过去哪一次运行发生过改走。
- D2：没有写回路径。A3 的 `current()` 只读并构造 dict；唯一项目级写入是 `stage_config.put()` → `save_all()`，不由该路由调用。改走只影响运行时，不改变存档。

## E. 测试覆盖

- **断言改走：**[tests/test_workflow.py](D:/漫剧制作助手/程序/tests/test_workflow.py:693) `test_openai_api_model_prefers_the_available_local_codex_client` 的原始说明是“同厂商本机客户端存在时先走它；API 只保存为启动失败时的兼容回退”，并断言 `engine == 'codex'`、`program == 'C:/Apps/codex.exe'`、主 `model == ''`、`api_fallback['model'] == 'gpt-4o'`。
- **断言不改走/回退：**同文件 [713](D:/漫剧制作助手/程序/tests/test_workflow.py:713) mock `find_program` 抛 `ValueError('not installed')`，断言 GPT API 返回 `qwen/gpt-4o`；[731](D:/漫剧制作助手/程序/tests/test_workflow.py:731) 断言 DeepSeek 永不回落 Codex，返回 qwen 与 DeepSeek API。
- **DeepSeek 防回退断言：**存在，正是上述 731–742 行；不存在覆盖缺口。

## F. 结论判断

### F1. 分类：a) 有意设计，有文档/测试支撑

### F2. 依据与限定

这是有意设计，不是意外副作用：helper 的 docstring 明说“优先回到对应本机客户端”，测试 693–711 明说并锁定“同厂商本机客户端存在时先走它”，PROJECT_MAP 也登记“本机 Codex/Claude 优先、兼容 API 回退”。

但它是**文档表达不一致且用户不可见**的有意策略：`architecture.md:144` 的“不参与 API 自动抢占”与实现/测试相反，阶段配置页也没有提示。故 a) 不等于现有 UX 与架构契约合格；它只回答“是否有意、是否有支撑”。用户观测到 GPT/Anthropic 被改走、DeepSeek 不受影响，与 A1–A2 完全一致。

## J. 整改路线（本轮不实施）

### 路线 1：用户可见，不改变执行行为

- 最小文件集：`skill_panel.py`（阶段模型已选 API 时显示“本机可用将改走 …”）、`workflow_settings.py`（提供纯路由说明/诊断值，不写盘）、`tests/test_workflow.py`、`tests/test_skills.py` 或现有面板测试。
- 影响面：仅展示与诊断；`current()`、启动器、模型 ID、存档格式和已配置项目均不变。程序探测必须按需，不能新增启动期扫描。
- 用户数据：不触及；只读取当前选择。

### 路线 2：用户可控，显式开关

- 最小文件集：`stage_config.py`（新增阶段级或项目级明确字段及默认/迁移读取）、`skill_panel.py`（开关与说明）、`workflow_settings.py`（仅开关开启才调用自动桌面优先）、`tests/test_workflow.py`、`tests/test_stage_config*.py`、`architecture.md` 与 `PROJECT_MAP.md`。
- 影响面：改变 GPT/Anthropic 且本机程序存在时的实际执行默认；已保存项目若默认取“保留旧行为”，兼容但继续不透明；若默认取“API 直连”，行为改变。该默认值须先由产品决策，不能在修复轮自行假设。
- 用户数据：读取旧配置时需定义缺字段语义；不应批量回写 `skill_config.json`。显式修改开关时才由用户操作写入。

## K. 测试计划

1. 对路线 1：mock `find_program` 成功/失败、GPT/Anthropic/DeepSeek 三类，断言提示准确，探测异常不使阶段面板崩溃；断言不会写 `skill_config.json`。
2. 对路线 2：参数化开关开/关 × GPT/Anthropic/DeepSeek × 程序存在/缺失；分别断言 engine、主 model、fallback 与存档原文不变。
3. 保留既有 DeepSeek 731–742 的“qwen + 原模型 + 原 API”断言；新增 Anthropic API 的桌面存在/关闭开关回归，不能仅覆盖 GPT。
4. 新增架构契约检查，使 `architecture.md` 的模型路由描述与 `current()` 的可观察行为一致。

## 自审

- 本轮未修改任何 `.py`、测试、配置、用户项目数据或既有结果文件；仅新增本结果文件。
- D 节对用户项目只进行 JSON 读取并输出模型 ID/字段名，未读取或输出密钥值。
- A–F 每项均提供源码文件:行号、既有测试或只读原始输出；历史引入轮次的保留证据不足已明确说明，未把 R191 错报为引入轮。
