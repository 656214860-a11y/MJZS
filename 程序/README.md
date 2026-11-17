# 漫剧助手 · SKILL / 模型路由说明

这一版把「每个阶段用哪个模型、跑哪几个 SKILL」从各页面里散落的勾选框，收成一套统一的
**SKILL 规范 + 阶段配置面板 + 编排器**，并且交给宠物 Agent「三虎」用自然语言驱动。

- SKILL 规范与注册表：`skill_registry.py`（读 `skills/*.skill.md`，热加载，免重启）
- 模型适配与路由：`model_router.py`（GPT / Qwen / DeepSeek，三级覆盖，预算先过）
- 阶段配置面板：`skill_panel.py`（13 个制作阶段共用一块面板）
- 编排器：`skill_orchestrator.py`（校验 → 分层 DAG → 执行 → 汇总 → 只重试失败项）
- 工具落地表：`skill_tools.py`（SKILL 里的 tools 名字 → 现有子模块）
- 阶段配置存储：`stage_config.py`（`<项目>/skill_config.json` 与预设文件）
- 预算：`skill_budget.py`（Token / 生图 / 视频三本账）

---

## 开发验证

日常开发先执行 `python smoke_test.py`，它只检查本轮登记的快速项，不会启动大批 Tk 测试窗口。
改动活跃逻辑时，再定向执行 `python smoke_test.py --affected <模块名>`（例如
`--affected idea_chat workflow`）；需要按变更台账回归可用 `--gate`。发布前的完整隔离回归为
`python -B run_selftests.py --all --safe`；`smoke_test.py --all` 只负责调度门禁，不代替完整用例。
外部模型／视频接口仍以带有效账号和素材的人工验收为准。

---

## 一、配置

### 1. 在哪儿配

每个制作页面的标题栏右上角都有一颗 **「阶段配置」** 按钮（01～13 页），点开就是那一阶段的
面板；01 剧本准备与 09 配音与字幕这两个页面的控制行里还有一份内嵌的同款面板，改完即存。

面板上有：

- **模型**：默认 **自动**；选项＝**模型管理**里的每一条（第 43 期起不再写死那五档），加一条就多一项；
- **SKILL**：本阶段的 SKILL 勾选框（多选），**全选**、**重置**；
- **预设**：下拉套用已存预设，**保存为预设** 存一份当前组合；
- 面板**只做配置**（第 54 期附件一）：模型、SKILL 勾选、预设、SKILL 说明都在这里；
  **不留执行入口**——「执行选中」那颗按钮已删，要跑这一步请按同页的「手动制作XX」，
  那一条路同样走编排器（校验 → 分层 → 执行 → 汇报）。

### 2. 配置存在哪

| 内容 | 位置 |
| --- | --- |
| **模型池 ＋ 三虎四个维度的模型** | `配置/宠物/配置.json` 的 `models` 与 `agent.models`（**模型管理是唯一入口**）|
| **名字／贴片动画／免打扰时段／自动化等级／预算上限** | 同一份 `配置/宠物/配置.json`（`level`／`dnd`／`anim`／`budget_limits`）——「设置」那颗齿轮改的就是这几项 |
| 某一条模型的本机加密密钥 | `private/密钥/<名字>.dpapi`（DPAPI，明文不落盘；`.env` 那种只存变量名）|
| 某个项目的阶段配置 | `<项目>/skill_config.json`（形状 `{"<阶段>": {"model": "auto", "skills": [...]}}`）|
| 预设组合 | `配置/SKILL/预设.json` |
| 生图／视频用量计数 | `<项目>/工作流任务/SKILL/预算.json` |
| Token 用量 | 复用宠物台账（`pet_llm.Ledger`），不另记一本 |

### 3. 模型选择的优先级

阶段配置挑的是**这一阶段让谁干活**（只选模型、不配 API，选项来自模型管理）。优先序
**单次 > 项目**：上下文里给的 `model`（单次）最优先，其次是 `projectModel`；都为空或「自动」时，
`ModelRouter.select()` 按四步挑：

1. 用户偏好（上面两级覆盖）；
2. SKILL 声明的 `preferredModels` 里**可用且在预算内**的；
3. 按 `capabilities` 匹配（标签取自池里那条记录：long-context / structured-output /
   creative-writing / reasoning / vision / fast / cheap）；
4. `fallbackModels[0]`，都没有就 `deepseek-v4-flash`。

阶段工作流另有一条本机优先规则：在模型管理中选择 OpenAI 或 Anthropic 的 API 模型时，若本机
Codex 或 Claude Code 已配置且能启动，优先打开对应本机 Agent；API 配置只作为**本机程序无法启动**
时的兼容回退。回退仅支持 OpenAI 兼容的 chat/responses 协议；Anthropic 原生 messages 协议不伪装
成 Qwen 接口，无法启动时会明确提示检查本机客户端或模型配置。

**SKILL 不绑定模型**：`preferredModels` 只是优先序，`fallbackModels` 只是兜底，真正挑谁由
路由按能力、成本与可用性决定。

### 4. 密钥与接口

**模型管理是 API 配置的唯一入口**（阶段配置与「设置 → 模型配置」都只选模型、不配 API）。密钥
**不入库、不写死、不打日志**，两种放法：

| 放法 | 怎么填 | 存在哪 | 谁认 |
| --- | --- | --- | --- |
| 从 .env 读 | 「密钥名」填变量名，如 `DEEPSEEK_API_KEY` | `.env`／`private/.env` 或同名环境变量 | `pet_llm.credential` |
| 直接输入 | 在「直接输入密钥」那一栏粘进来，点「保存到本机」 | `程序/private/密钥/<名字>.dpapi`，DPAPI 加密，**明文不落盘** | 同上（最后一处兜底）|

出厂那条 `DEEPSEEK_API_KEY=...` 就写在 `程序/.env` 里；密钥短的、想省事的直接输进模型管理
也行，界面与日志里只露 **前 4 位 ＋ ******（`model_pool.redacted`），清除走模型管理的
「清除本机密钥」。判据只有一处（`pet_llm.credential`）：界面说这个模型能用，三虎那条链与
阶段执行就都发得出去。

| 提供方 | 环境变量 | 模型 |
| --- | --- | --- |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-v4-pro / deepseek-v4-flash |
| OpenAI | `OPENAI_API_KEY` | gpt-4o / gpt-4o-mini |
| 通义千问 | `DASHSCOPE_API_KEY`（也认 `QWEN_API_KEY`）| qwen-max / qwen-plus |

接口默认 OpenAI 兼容的 `chat_completions`，`wire_api` 保留切换位（`chat` → `/chat/completions`，
`responses` → `/responses`）。

### 5. 「设置」这颗齿轮

窗口左上角、版本号 **V0.7** 旁边那颗**齿轮**就是「设置」（第 44 期：原来的右键头像 →
「三虎设置」，现在提到台面上、做得醒目，点一下直接开窗；**第 45 期起齿轮旁边不再写字**——
那句「设置」在侧栏里放不下、整句会被裁掉，剩下半截反而碍眼）。右键菜单里那一栏也跟着改名
「设置」——**四格与齿轮开的是同一扇窗**，落在哪一格看点的是哪一项：

| 那一格 | 管什么 |
| --- | --- |
| **基础功能** | 宠物名字（出厂就叫「三虎」，只读）、贴片动画开关、免打扰时段、立刻安静、开机自启 |
| **模型配置** | 三虎那颗脑袋四个任务维度的模型（下一节）|
| **自动化等级** | 只提醒／半自动／全自动三档，**出厂＝半自动** |
| **预算** | 五类硬限制（Token／生图／首帧／视频／配音）与现在用了多少 |

附件那张菜单里还列着一格「SKILL 管理」——这一轮不做，所以菜单里也不摆（不留空占位）。

改哪一格都**立刻生效 ＋ 立刻写盘**（`配置/宠物/配置.json`），不用重启。

### 6. 三虎那颗脑袋用哪个模型

**设置 → 模型配置…**（齿轮或右键头像那一栏都开这一格），四个任务维度各选一条（选项同样来自模型管理）：

| 维度 | 用途 | 出厂值 |
| --- | --- | --- |
| 默认模型 | 意图路由、参数抽取、通知生成、简单决策 | 自动 |
| 对话模型 | 闲聊、解释、建议、追问 | DeepSeek V4 Pro |
| 升级模型 | 复杂推理、Bug 诊断、多步规划 | DeepSeek V4 Pro |
| 降级模型 | 上一档限流／超时／503 时的容错 | DeepSeek V4 Flash |

「默认模型」可以是 **自动**：`model_router.resolve_agent_model` 按复杂度挑（简单→池里最便宜
的可用模型、中等→贵一档、复杂→「升级模型」那一条，池里没配好密钥就不选它）；挑中的那条
用不了（缺密钥／没登记）时自动降级到「降级模型」，降级也不行就报错并说清原因。右键 →
**切换模型** 只切「默认模型」，当前那条前面打 ✓，最后一项「+ 新增模型…」跳模型管理，切完
三虎用气泡说一句（「已切换到 Qwen-Max」），改完不用重启。

### 7. 预算与免打扰

- 硬限制出厂值：**Token 日 200 万**、**生图 200 张/项目**、**视频 100 镜/项目**，另外两档同一套机制：
  **首帧 200 张/项目**、**配音 200 条/项目**；
- 这五档在 **设置 → 预算** 里改（落在 `配置/宠物/配置.json` 的 `budget_limits`），改完立刻生效：
  阶段编排那本账（`skill_budget`）读的就是它；越线的步骤会被拦下并报一声；
- 自动化等级**出厂＝半自动**：付费步骤先确认再跑，免费步骤全自动——**设置 → 自动化等级** 换档；
- 免打扰时段 **23:00–07:00**：这段时间的付费确认不弹气泡，先排队，到点再问。

---

## 二、扩展一个新 SKILL

### 1. 用生成器（推荐）

```bash
node scripts/create-skill.js
```

一路问答（SKILL id、中文名、说明、阶段、capabilities、tools、依赖、输入输出、约束、是否付费、
能否并行），回车取默认值；也可以带参数一次生成：

```bash
node scripts/create-skill.js --name firstframe-retry --display 首帧补生成 \
  --stage 首帧管理 --capabilities structured-output --tools firstframe.retry \
  --depends firstframe-batch --paid
```

生成的文件落在 `skills/<id>.skill.md`，`feedback` 默认就是「三虎」那三条（进度／异常／收尾）。
同名文件默认不覆盖，要覆盖加 `--force`。

### 2. 手写一份

`skills/` 下一个 SKILL 一个 Markdown，frontmatter 字段固定这 17 个：

| 字段 | 说明 |
| --- | --- |
| `name` | SKILL id（小写连字符，必须与文件名一致）|
| `displayName` | 面板与气泡里显示的中文名 |
| `description` | 一句话说明 |
| `stage` | 所属阶段（中文名或 id：剧本准备/初步分镜/资产管理/分镜定稿/首帧管理/白模预演/视频生成/配音与字幕/后期剪辑/质检与交付）|
| `capabilities` | 能力标签，取值：long-context / structured-output / creative-writing / reasoning / vision |
| `preferredModels` | 首选模型（优先序，不是绑定）|
| `fallbackModels` | 兜底模型 |
| `tools` | 调用的子模块（见下）|
| `dependsOn` | 依赖的 SKILL id（编排器会自动展开并分层）|
| `conflictsWith` | 互斥的 SKILL id（同时勾上会被校验拦下）|
| `parallelizable` | 能不能和同层一起并行 |
| `paid` | 是否付费步骤（付费要用户点头）|
| `input` / `output` | 输入输出字段 |
| `constraints` | 约束说明 |
| `feedback` | 三条回调：onProgress / onError / onComplete |
| `examples` | 用户怎么说 → 调什么 |

### 3. tools 写什么

`tools` 里的名字对应 `skill_tools.py` 里的两种去处：

- **ready**：本机跑得完的（校验、登记、版权过滤、字幕对齐、媒体质检、报表、交付清单、导出规格…），
  编排器直接调；
- **page**：只能在页面上按的（生成分镜、批量生成首帧、白模搭建、视频提交…），编排器不会代按，
  汇报里会说「这一步得回 XX 页面按」；
- 还缺用户手上的东西（没选项目／没选分镜）时归到 `input` 类，同样不算失败，汇报里写清楚。

自检可以一眼看出有没有漏：

```python
import skill_registry, skill_tools
tools = [t for s in skill_registry.default_registry().getAll() for t in s.tools]
print(skill_tools.missing(tools))      # 正常是空列表
```

### 4. 生效方式

`Registry` 在每次查询前比对文件的 mtime 与大小，**新增或改过的 `.skill.md` 下一趟就进表，
不用重启**。改完可以跑一遍自检：

```bash
python -B run_selftests.py
```

---

## 三、新增一个模型

**平时不用改代码**：右键头像 →「切换模型 → + 新增模型…」，或「设置 → 模型配置… → 打开模型管理」，
在**模型管理**里点「新建一条」，填这几项就够了（规格那张表单）：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| 显示名 | ✓ | 下拉框里显示的名字，如「我的本地模型」 |
| Provider | ✓ | `openai-compatible`（默认）／`anthropic`／`自定义`；只登记「是谁家的」 |
| API 根地址 | ✓ | 如 `https://api.deepseek.com`、`http://localhost:11434/v1` |
| 密钥名 | | `.env` 里的变量名；本地模型没有密钥就留空 |
| 直接输入密钥 | | 不想写 `.env` 就粘进来点「保存到本机」（DPAPI 加密，明文不落盘）|
| 模型 ID | ✓ | 发给服务商的模型名，如 `deepseek-v4-flash`、`qwen2.5:14b` |
| 协议 | ✓ | `chat/completions`（默认）／`responses` |
| 能力标签 | | 多选：long-context／structured-output／creative-writing／reasoning／vision／fast／cheap |
| 上下文长度、备注 | | 可选，只作记录 |

存下来都落在同一份池子里（`程序/配置/宠物/配置.json` 的 `models`，密钥从不写进去）：

```json
{
  "models": {
    "my-local-model": {
      "label": "我的本地模型",
      "provider": "openai-compatible",
      "model": "qwen2.5:14b",
      "base_url": "http://localhost:11434/v1",
      "path": "/chat/completions",
      "wire_api": "chat",
      "key_env": "",
      "capabilities": ["long-context"],
      "context_length": 32000,
      "note": "",
      "cost": 1
    }
  },
  "agent": {"name": "三虎",
            "models": {"default": "auto", "chat": "deepseek-v4-pro",
                       "escalate": "deepseek-v4-pro", "fallback": "deepseek-v4-flash"}}
}
```

加完之后：右键 →「切换模型」立刻多一项，阶段配置的下拉也立刻多一项（都从这份池子长出来），
不用重启；点「测试连接」发一次最小请求（`max_tokens=1`），不消耗业务预算。

**要改代码的情况**（内置档位这类：模型池里没有、又想让它参与自动路由）才需要写适配器：

1. 写一个适配器（`model_router.ModelAdapter` 的子类），至少给出：

```python
class MyAdapter(model_router.ModelAdapter):
    provider = 'my'
    key_env = 'MY_API_KEY'          # 从 .env 读，不落库
    models = {'my-model-pro': {'capabilities': ('reasoning',), 'cost': 3}}
```

  基类已经实现好 `credential() / available() / supports() / capabilities() / cost() /
  headers() / payload() / chat()`；只认 OpenAI 兼容协议的提供方通常只需要
  `provider / key_env / models` 这几项。

2. 把它挂进路由：

```python
router = model_router.ModelRouter(adapters=[*router.default_adapters(), MyAdapter()])
```

  注意：**模型池里的记录压过内置适配器**（模型管理是 API 配置的唯一入口），所以同名模型在
  模型管理里改过地址／协议后，以那一栏为准；池里没有的模型才轮到内置适配器
  （`gpt-4o-mini`、`qwen-plus` 这类就属于此列）。

---

## 四、预设

把常用的「模型 + 一组 SKILL」存成预设，换项目或换阶段时一键套用：

- 面板上勾好 SKILL、选好模型 → **保存为预设** → 起个名字（同名覆盖）；
- 下次在 **预设** 下拉里选中它 → 模型与勾选一起写进当前阶段；
- **重置** 回到默认（模型「自动」＋本阶段全部 SKILL）。

预设文件（`配置/SKILL/预设.json`）：

```json
{
  "稳一点出片": {"stage": "video", "model": "deepseek-v4-pro", "skills": ["video-batch-submit", "video-quality-check"]},
  "省钱先跑":   {"stage": "keyframe", "model": "deepseek-v4-flash", "skills": ["firstframe-batch"]}
}
```

代码里也能用：

```python
import stage_config
stage_config.save_preset('稳一点出片', 'deepseek-v4-pro', ['video-batch-submit', 'video-quality-check'])
stage_config.apply_preset(project, 'video', '稳一点出片')
```

---

## 五、跟三虎说一句

阶段配置里的勾选就是三虎的「选中的 SKILL」：

| 你说 | 三虎做的事 |
| --- | --- |
| 「跑一下这一步的 SKILL」 | 跑当前这一步里勾上的 SKILL（面板上那颗按钮第 54 期已删，这句话照旧管用）|
| 「把首帧批量生成跑一下」 | 点名跑某一个 SKILL（含它依赖的那些）|
| 「跑一遍质检与交付」 | 跑这一阶段的 SKILL |
| 「查进度」 | 只报数，不动手 |
| 「重试失败项」 | 只重试失败的那些，成功的不用重跑 |

付费的 SKILL 会**并成一个气泡**问一次；免打扰时段先排队；跑完统一汇报（成了几个、要你回页面
按几个、等你点头几个、没成几个）。

---

## 当前状态摘要

- 13 个制作阶段：01 剧本准备 → 02 剧本结构 → 03 初步分镜 → 04 分镜预演（animatic，本地 ComfyUI 合成预演）
  → 05 资产管理 → 06 连贯性清单 → 07 分镜定稿 → 08 首帧管理 → 09 白模预演 → 10 视频生成
  → 11 配音与字幕 → 12 后期剪辑 → 13 质检与交付。顺序唯一权威是 `pet_bus.STAGES`／`STAGE_NAMES`，
  目录名见 `stage_layout.STAGES`。
- 阶段配置、SKILL 勾选、模型池与三虎的驱动方式见本文第一～五节；各阶段的需求与设计在 `docs/stages/`，
  模块分层见 `architecture.md`，交付清单见 `distribution_manifest.md`，环境与自检命令见 `runbook.md`。
- 生产运行时只交付白名单锁定的第三方包（见 `维护记录/依赖白名单.md`）；含 Tk 的测试由运行器强制经 `scripts/gui_hidden.py` 在隐藏桌面运行，不弹到用户屏幕。
- 账号／会员订阅与云端后端为显式推迟项，本版不实现、不预留接口。

## 界面变更日志（第 45～71 期）

早期逐期界面变更记录（原有第六～三十三节，约 1800 行）已于 2026-11 原文归档到
`tasks_round/归档/2026-11_历史文档/README_界面变更日志.md`；查历史细节以该文件和 git 为准。

