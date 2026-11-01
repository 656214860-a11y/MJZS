# R624 只读诊断轮——桌面引擎自动升级行为核实

## 开头三问（AGENTS.md 第 7 节）

- 本轮是功能轮还是整理轮？都不是；本轮为只读诊断轮，未实施功能或整理。
- 测试跑了吗？三个基线过了吗？未跑。只读轮不执行会写入临时项目数据的验证，故无基线结果。
- `project_status.md` 的欠账少了吗？没有；本轮只新增诊断证据，不消除台账欠账。

编号依据：`tasks_round/` 中已有 R616–R623，R624 未占用；按连续编号新增本文件。

## A. `workflow_settings.current()` 的实际路由

### A1. 是否会把 API 模型自动转到桌面引擎

会，但范围不是所有 API 模型，更不是 DeepSeek。`workflow_settings.py:317-329` 的原始代码如下：

```python
def _local_engine_for_selected_model(value, selected, item, stage):
    """已选 OpenAI/Anthropic 模型有本机 Agent 时，优先回到对应本机客户端。"""
    import model_pool
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

`workflow_settings.py:333-352` 每次 `current()` 调用都会读取阶段已选模型并调用该函数：

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
        # 模型池中的任意 API 模型都必须交给兼容调用器。此前仅 GPT／Anthropic
        # 会走这里，选 DeepSeek V4 Flash 时便错误沿用默认 Codex，导致三虎
        # 自动打开的是 Codex 而阶段按钮却显示 DeepSeek。
        engine = 'qwen'
```

结论：

- 显式选 `chatgpt-desktop` / `claude-desktop`（`model_pool.desktop_engine()` 非空）是用户直接选择桌面引擎，不是自动升级。
- 选 provider 显示为 `GPT` 或 `Anthropic` 的普通 API 记录，且 `find_program()` 成功时，会自动改为 `codex` 或 `claude`。
- 选 DeepSeek 时映射表没有匹配项，`local_engine` 为空，随后 `item` 分支固定为 `qwen`。所以“DeepSeek 被自动重定向 chatgpt-desktop / claude-desktop”在当前源码中不成立。

`workflow_settings.py:355-366` 还会清空本机桌面客户端的模型参数，并仅把 API 作为启动失败时的兜底：

```python
if local_program:
    profile['program']=local_program
    profile['model']=''
    selected_model, selected_api = stage_model(project,stage)
    if selected_api:
        profile['api_fallback']={'model':selected_model,'api':selected_api,
                                 'profile':validate_stage_profile(value['profiles']['qwen'],stage)}
# 阶段配置里挑了 API 模型就以它为准；qwen 是兼容 API 调用器，见 stage_model.
model,api=stage_model(project,stage) if engine=='qwen' else ('','')
```

### A2. 触发条件、可感知性与历史项目

触发条件是：阶段配置的 `model` 是模型池记录、其 `provider_name()` 为 `GPT` 或 `Anthropic`，并且该阶段对应 `codex` / `claude` profile 经 `find_program()` 找到可启动程序。找不到程序时，`find_program()` 的 `ValueError` 被捕获，回到 `qwen` API 调用器；不会强制要求安装桌面客户端。

该改路由不写回阶段配置。`current()` 只构造并返回运行时 dict；`stage_config.py:165-202` 的 `load()/get()` 是读取阶段配置，`stage_config.py:85-93` 的 `clean_model()` 保留传入的合法/未知模型文本，未见把 API id 改成 `chatgpt-desktop` 或 `claude-desktop` 的写入路径。因此用户在阶段配置下拉中仍可能看到原 API 模型；实际启动结果才会体现实际引擎。对非“自动”选择，`skill_panel.py:306-342` 优先显示所选记录的 provider 文案，未提供“已自动升级”标记。

按任务要求只读检查当前安装根 `D:\漫剧制作助手` 下的用户项目配置，命令及原始输出：

```powershell
Get-ChildItem -LiteralPath 'D:\漫剧制作助手' -Recurse -File -Filter 'skill_config.json' -ErrorAction SilentlyContinue | Select-Object -First 40 FullName
```

```text
（无输出，0 个 skill_config.json）
```

因此当前可访问安装树中没有“当前项目”的 `skill_config.json` 可供检查，已写入桌面模型的条数为 0。历史运行是否曾发生运行时重定向无法由配置证明，因为此分支没有持久化路由结果；不能把“0 个当前配置文件”误报成历史从未发生。源码注释（A1 的 348–351 行）明确记载过 DeepSeek 曾沿用默认 Codex 的旧行为，而当前分支已将任意 API item 导向 `qwen`，故该旧 DeepSeek 症状不属于当前代码路径。

## B. 模型池中两项桌面模型的安装状态处理

`model_pool.py:62-107` 定义了：

```python
DESKTOP_ENGINES = {'chatgpt-desktop': 'codex', 'claude-desktop': 'claude'}
# BUILTIN 中的两项标签：
# chatgpt-desktop -> 'ChatGPT Desktop · Codex'
# claude-desktop  -> 'Claude Desktop · Claude Code'
```

模型池没有探测本机安装状态。`model_pool.py:403-420` 的原始实现对任意桌面项无条件返回可用：

```python
def status(value, program=None):
    """这条记录现在能不能发得出去：(可用?, 一句话说明)。"""
    item = record(value)
    if item['provider'] == 'desktop':
        return True, '桌面 Agent'
    # 以下才检查模型、地址、Key
...
def available(value, program=None):
    return status(value, program)[0]
```

`model_pool.py:264-270` 无条件将所有池记录送进下拉：

```python
def options(records=None, config=None, program=None, with_auto=True):
    items = records if isinstance(records, dict) else pool(config, program)
    out = [(AUTO, AUTO_LABEL)] if with_auto else []
    out.extend((model_id, item['label']) for model_id, item in items.items())
    return tuple(out)
```

`skill_panel.py:457-475` 将 `model_pool.options(..., with_auto=True)` 用作控件 choices。结论：未安装时两项仍显示为可选，既不禁用、也不显示“未安装”；本轮未发现 UI 或模型池读取注册表、进程名、可执行文件或安装目录来改变该展示。

## C. Codex 专属功能的 UI 可见性

| 功能 | UI 入口与可见性 | 是否“检测到 Codex 才显示” |
|---|---|---|
| `token_saver` | `pet_settings_contract.py:2-3` 的固定 `TABS` 含 `('token', 'Token 节省')`；`pet_settings_ui.py:75-103` 对所有 tab 建页并调用 token 页。它在设置中心固定可见，不是按客户端存在条件出现。 | 没有。Token 页虽有“写入项目/写入全局”这类 Codex 配置动作，构造时未先作安装检测。 |
| `codex_tasks` | 没有独立按钮。`desktop.py:4146-4260` 的通用阶段启动 `open_flow_agent()` 无条件可由阶段操作进入；当 `engine == 'codex'` 且未指定 program/model（`use_cli` 为 false）才调用 `codex_tasks.prepare_task()`。 | 没有“显示前检测”；仅执行该路线时由任务/RPC 建连失败或成功。 |
| `codex_paste` | 同样没有独立入口。`desktop.py:4255` 之后的 `done()` 仅在 `prepare_task()` 成功返回 Codex 目标后导入并调用 `codex_paste`，把内容粘贴给该目标。 | 没有；它由已成功的 Codex 任务结果触发，不是 UI 选择项。 |

可见性判断的直接代码条件为 `desktop.py:4155-4164`：

```python
from codex_tasks import prepare_task
use_cli = config['engine'] != 'codex' or config['program'] or config['model']
if use_cli:
    return launch_cli(...)
result = prepare_task(...)
```

因此目前的“检测”是在执行后段，而非 UI 的显示/隐藏决策。没有发现 `if 检测到 Codex: 显示按钮` 的实现。

## D. 对 R623 J-1 表述的准确性判断

R623 J-1 的“读取配置时不自动把 API 模型升级到本机 Codex”，描述的是**当前存在的路由策略，应作为待修正行为处理**，不是纯预防性建议：A1 的 `_local_engine_for_selected_model()` 文档字符串和 321–328 行是直接证据。

但该措辞应收窄：当前自动路由只覆盖识别为 `GPT` / `Anthropic` 的 API 模型，并非 DeepSeek；DeepSeek 当前明确进入 `qwen`。所以它不能被描述为“DeepSeek 仍被升级到 Codex”的现存 bug。显式选择 `chatgpt-desktop` / `claude-desktop` 也不应算作自动升级。

## E. 根因归纳与替代解释排除

根因是 `current()` 把“API 模型的 provider 类型”与“本机桌面执行引擎”耦合：GPT/Anthropic API 只要本机程序可找，就覆盖 `engine`。直接证据是 A1 的映射表和 `if local_engine: engine = local_engine`。

已排除的替代解释：

- 不是模型池按安装状态选择桌面项：模型池桌面 status 无条件 `(True, '桌面 Agent')`，没有安装探测。
- 不是 DeepSeek 的当前分支：provider 映射只有 GPT/Anthropic，且任意其他有效 API item 落入 `engine = 'qwen'`。
- 不是读取时篡改了 `skill_config.json`：`current()` 无写入，当前可访问安装树中亦无该文件。

## J. 建议（待办 B 的具体行动项；本轮不实施）

1. **自动升级：移除。** 修改 `workflow_settings.current()`，只保留显式 `desktop_engine(selected)` 的分支；普通 GPT/Anthropic API 与 DeepSeek 一样走 `qwen`。影响面为阶段启动引擎选择和 API fallback；不改用户已有模型 id。
2. **桌面模型：保留但标注并禁用不可用项。** 不隐藏显式 `chatgpt-desktop` / `claude-desktop`，以免抹去用户主动选择；增加独立、可 mock 的可执行客户端可用性检测，未检测到时在下拉明确标“未安装”且不让新选择提交。历史已选值保持可读取，并在编辑页标明不可启动。
3. **`token_saver`：保持设置页，但标注外部作用域。** 保留通用 Token 节省页面；将“写入项目/写入全局”明确命名为“写入 Codex 项目/全局配置”，标为可选集成，避免被理解为本应用自身配置。
4. **`codex_tasks` / `codex_paste`：保持执行后成功门控。** 不新增常驻入口；仅在用户显式选择桌面 Codex 且任务创建成功后调用。配合第 2 项，客户端不存在时应在配置期阻止而不是运行后才失败。

## K. 测试计划（后续修复轮）

1. 在既有 `tests/test_workflow.py` 增加/强化参数化回归：mock `find_program()` 为可用时，DeepSeek、GPT、Anthropic 的**显式 API**选择都应得到 `engine == 'qwen'` 和原 API 参数；显式 `chatgpt-desktop` / `claude-desktop` 仍分别得到 `codex` / `claude`。
2. 在既有模型池/UI 测试中 mock 桌面客户端探测：已安装项可选；未安装项显示“未安装”且不能新选；不得读取真实机器注册表、进程或用户目录。
3. 用临时项目配置调用 `current()`，断言调用前后 `skill_config.json`/阶段模型值字节不变，证明路由不静默写回。
4. 在既有桌面阶段启动测试中 mock `codex_tasks.prepare_task` 与 `codex_paste`：API 模型路线不得调用二者；显式且可用的 Codex 桌面路线成功后才调用。
5. 在 pet 设置测试中断言 Token tab 始终存在，并断言 Codex 写入动作的文案/提示包含外部集成属性。

## 自审

- 本轮只读取源码、台账和指定安装根下的配置文件名；未修改任何 `.py`、测试、配置、用户数据或既有结果文件。
- 唯一新增文件为本报告 `tasks_round/tasks_round_624_result.md`。
- A–E 每项均给出了源文件:行号、原始代码或原始命令输出；未把当前无配置文件的观察扩张为不可证实的历史结论。
