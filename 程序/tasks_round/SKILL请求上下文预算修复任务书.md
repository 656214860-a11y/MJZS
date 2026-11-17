# SKILL 请求上下文预算修复任务书

> 编写日期：2026-11-18　｜　来源：`tasks_round/tasks_round_3269_result.md`（只读诊断轮）
> 适用：修复轮　｜　建议轮次：R3270 起（开工前用 `round_claim.py next` 领号，见 §8 阻塞说明）
> 本文件自包含，执行者无需会话上下文即可开工。

## 执行复核补充（2026-11-18，R3273 起；本节优先于下文失实时描述）

用户已授权自主裁定实现细节、逐轮子会话接续及最终合入 master。下文轮次号为原建议号，实际号由当前功能工作树的 `round_claim.py next` 分配；第一轮实际领取 R3273。主树 R3248 已提交并合入，原 §8 的在途改动不是当前阻塞；不得在主树反复领号或改共享忽略规则。本树以 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8` 运行现有工具即可解决中文 Git 输出解码失败。

1. **预设来源**：五个前缀数值是用户指定的应用回退值，并非已核实的厂商标准、所有版本的真实容量保证；显式配置窗口优先，未知型号提示补填。只凭 `FIELDS` 不包含字段不能断言字段丢失（`record()` 后续单独处理 `context_length`）。不联网猜测或写入其他容量。
2. **路径与快照**：`contract.script_contract.program_root()` 默认是 `程序/contract`，禁止按 §4 直接使用其缺省值。复用现有 `model_pool` 默认程序根或显式注入。`writing_api.capture_request()` 已取得模型 record，`current → resolve_for_send → freeze_skills` 必须复用同份记录，不能再查池并吞异常；明确区分未提供 `None` 与已提供空记录 `{}`。不在 frozen 配置写入模型密钥或完整敏感记录。
3. **API 与 CLI**：未知窗口阻断适用于直连 API 的长文本 SKILL 注入。CLI／桌面原有可读路径模式不因无模型窗口误阻断；不得把 L0 的 `0` 当作 API 无限预算。
4. **两阶段预算完整性**：预留全部去重技能正文、标签与包装、制作锁头、质量规则等不可省文本；引用与 skipped 提示也占预算；最终按完整冻结快照重算，不能只比较主体或把正文 content 的局部计数当作最终输入。只读一次并复用同一快照，避免预留/发送之间文件变化。保留正文，不自动减少用户勾选。
5. **引用职责**：保留既有 skipped 记录，但 DeepSeek 直连不能读取这些本地路径。结果必须区分完整正文与未发送引用，不能声称模型能按路径补读；如技能执行必需文件未发送，验收不得声称完整执行了该技能。完整发送请求还必须计入任务、历史、工具、实际输出预留及余量并在网络调用前预检。
6. **真实验收**：原 §4 轮4“再次正文超预算也算通过”不成立。128K 有效场景必须到达受控传输；超大正文负例必须拒发。分别用可重复的合成场景、真实入口与桩传输验证，测试不得动用户项目、生产模型池或产生收费 API。未实发远端须明确标记，旧日志历史错误无需删除或要求全文件无匹配。
7. **轮次依赖**：第一轮只能完成纯函数预设与 T7；T1 的发送链路和 T2 依赖第二轮。每轮以实际测试数报告，不把固定 8/8 当作测量结果。不得宣称回归或并发安全已由历史分支检查证明，合入前重查 scope、最新 master 并重新测试。
8. **现有报告证据限定**：R3269 是未经中央认领的历史诊断草稿，原型脚本已删除，其模拟值只能作调查线索；部分“未修改/未删任何 .py”与实际临时探针创建清理不一致。新回归必须保存可复跑测试与原始红绿输出，不以该草稿作为绿色凭据。原报告包含用户项目名称，本次归档必须先脱敏，不将用户项目内容或名称提交进 Git。


---

## 0. 总目标

修复 `剧本准备 → DeepSeek V4.1 FLASH API → /short drama director → 发送失败: SKILL请求上下文超过 300,000 字符（当前 334,580）`。

**根因不是上限太低，是预算机制从未生效。** 上轮 R1434／R1435 只把上限从 96,000 抬到 300,000（调阈值），未修机制，故技能体量增长后必然再越线。

**目标状态**：SKILL 冻结时按发送模型的**真实上下文窗口**（token 口径）预算，正文优先、引用次之，超限时给出**分项可辨认**的拒绝理由；不再依赖 300,000 字符硬闸做主要保护。

---

## 1. 已确认决策（不得自行变更）

| # | 决策 | 定值 |
|---|---|---|
| D-1 | 是否引入 `tiktoken` 等分词器 | **不引入**。修 `estimate_tokens` 的**用法**，不动其精度口径。零依赖白名单改动 |
| D-2 | 空 `context_length` 的默认值按什么分档 | **按模型 ID 前缀**（非 provider）。理由见 §3.2 |
| D-3 | 预设表之外的模型 | **报错提醒用户填写**，不猜值、不静默放行 |
| D-4 | `deepseek-v4.1-flash-1017` 的真实窗口 | **128,000** |
| D-5 | 预设表取值 | `deepseek→128000`、`gemini→128000`、`qwen→32000`、`claude→200000`、`gpt→128000`；其余不预设 |

---

## 2. 现状盘点（行号基于诊断时工作树实测）

### 2.1 缺陷清单

| # | 缺陷 | 位置 | 现状行为 |
|---|---|---|---|
| **D1** | 模型记录 `context_length` 为空时，预算返回 `None`＝不设限 | `orchestrator/skill_inline.py:21-35`（`_skill_inline_budget`） | `deepseek-v4.1-flash-1017` → `budget=None` |
| **D2** | 预算只对**引用**计费；SKILL 顶层正文从不计费 | `orchestrator/workflow_settings.py:634-735`（`_skill_blocks`）只对引用调 `_charge_inline` | 正文 78,991 token 却 `charged=0` |
| **D2b** | 6 个 SKILL **共享同一个 budget 字典**；先到的引用吃光预算，后续技能正文分不到 | `workflow_settings.py:760` 单次 `budget = _skill_inline_budget(frozen)`，`:761` 循环复用 | 实测首个技能后仅剩 306 token，后续技能失败 |
| **D3** | 窗口拿不到时 `skill_inline_token_budget(0)` 返回 `None`（不设限），与 D1 叠成双重静默失效 | `contract/workflow_context_budget.py:37-48` | 只剩字符闸兜底 |
| **D4** | 报错把整份 SKILL 正文标成「阶段文档/任务说明」 | `workflow_settings.py:782` 调 `prepare_request_context` 未传 `sections`，回退 `{'stage': prompt}`（`workflow_context_budget.py:201-203`） | 413,105 token 实为 SKILL 正文 |
| **D5** | 预算来源依赖 `Path(__file__).resolve().parents[1]` 相对锚点，异常被 `app_logging.swallowed()` 吞掉后静默退回 `None` | `skill_inline.py:29-33` | L1 包化若挪层级会**无报错**复发 D1 |

### 2.2 关键量化（修复必须满足的算术）

- 反推比例：334,580 字符 = 413,105 token ⇒ **每字符约 1.235 token**（中文为主）。
- 300,000 字符硬闸 ≈ **370,409 token**。对照窗口：32K 时是窗口 **11.6 倍**、64K 时 **5.8 倍**、128K 时 **2.9 倍**、200K 时 **1.9 倍**、1M 时 **0.4 倍**。
- **字符闸只在 1M 级窗口起保护作用**；32K–200K 下它允许量远超模型可吃量。这是 D3 存在的原因，也是必须修的原因。
- 用户 6 个 SKILL 仅正文合计 **58,414 token**（44,183 字符）。按 `skill_inline_token_budget`：32K→21,184、64K→46,464、**128K→93,440**、200K→146,000。
- ⇒ **只有 ≥128K 窗口才能容纳该 6 技能组合的正文**；64K/32K 必然正文就放不下。此结论已实测。

---

## 3. 设计

### 3.1 目标数据流

```
freeze_skills(config)
  ├─ 阶段一 正文预留：取全部所选 SKILL 的 content token 之和 → 从总预算扣出
  │    └─ 不足 → 立即拒绝，文案点名「哪个技能正文太大」+ 建议减少勾选
  └─ 阶段二 引用分配：剩余预算建成 budget 字典，按既有顺序内联引用
       └─ 装不下 → 该引用记 skipped + 留本地路径提示（既有行为，不改）
```

### 3.2 预设表为何按模型 ID 前缀而非 provider

实测用户模型池：`deepseek-v4.1-flash-1017` 与 `gemini-3.5-flash` 的 `provider` 字段**同为「OpenAI 兼容」**。按 provider 分档无法区分厂商，给不出有意义默认值。按模型 ID 前缀可区分。用户已确认此调整（D-2）。

### 3.3 三处落点

| 落点 | 文件 | 层 | 改动 |
|---|---|---|---|
| **L-1** | `contract/workflow_context_budget.py` | L0 | 新增 `PRESET_CONTEXT_BY_PREFIX` 表 + `preset_context_length(model_id)`；`skill_inline_token_budget(0)` 不再返回 `None` |
| **L-2** | `orchestrator/skill_inline.py` | L3 | `_skill_inline_budget` 改为**注入式**（收 `record`/`program`，不自己相对定位）；新增正文预留辅助 |
| **L-3** | `orchestrator/workflow_settings.py` | L3 | `freeze_skills` 改**两阶段**；`prepare_request_context` 传真实 `sections` |

---

## 4. 分轮拆解

### 轮 1（R3270）：L-1 预设表与去静默（修 D3、D1 的数据来源）

**改动文件**：`程序/contract/workflow_context_budget.py`

1. 新增模块级常量（放在 `REQUEST_CONTEXT_MAX_CHARS` 附近，附中文注释说明来源与用途）：
   ```python
   # 模型未填 context_length 时按模型 ID 前缀取预设窗口（用户 R3269 裁定：按前缀而非 provider）。
   # 表外一律不预设，由调用方报错要求用户填写，不猜值。
   PRESET_CONTEXT_BY_PREFIX = (
       ('deepseek', 128_000), ('gemini', 128_000), ('qwen', 32_000),
       ('claude', 200_000), ('gpt', 128_000),
   )
   ```
2. 新增函数 `preset_context_length(model_id)`：前缀匹配（`casefold`），命中返回 int，未命中返回 `''`（与 `model_pool.context_length_of` 的「没填」表示一致）。
3. `skill_inline_token_budget(context_limit)`：`limit <= 0` 时**不再返回 `None`**。改为返回 `0`，并在 docstring 写明「0 表示窗口未知，调用方必须自行决定拒绝或取预设，不得据此放行」。

> ⚠ **不改** `skill_inline_token_budget` 的既有算式（`reserved` 6% / `fixed_share` 16% / `default_safety_margin`）。现有测试 `tests/test_skill_deep_inline.py:145-151` 的 `:147` 断言 `skill_inline_token_budget(0)` 为 `None`，**该断言按本任务书 §5 T7 有意变更**，需同轮改为断言 `0`，并在结果文件注明契约变化。

**验收**：
- [ ] T1、T2、T7 转绿
- [ ] `python run_selftests.py -k context_budget_model skill_deep_inline` 全绿
- [ ] 未新增第三方依赖；`requirements.txt` 不变

---

### 轮 2（R3271）：L-2 注入式预算 + 两阶段正文预留（修 D5、D2、D2b）

**改动文件**：`程序/orchestrator/skill_inline.py`、`程序/orchestrator/workflow_settings.py`

1. `_skill_inline_budget(config, *, record=None, program=None)`：
   - 保持对 `config['model']` 的读取；
   - **删除** `Path(__file__).resolve().parents[1]`，改由调用方传入 `program`（缺省用 `contract.script_contract.program_root()`）；
   - **删除** `except Exception: swallowed(); return None` 的静默退回——取不到窗口时返回 `{'remaining': None, 'unknown': True}`，由 `freeze_skills` 统一报错；
   - 窗口解析顺序：`model_pool.context_length_of(record['context_length'])` → 空则 `preset_context_length(model)` → 仍空则 `unknown`。
2. 新增 `_body_tokens(path)`：读 SKILL、`skill_registry.parse`、对 `content` 求 `estimate_tokens`；返回 `(tokens, content)`。**只算正文，不含引用**（这是证伪 2 的教训：不能对组装后的 body 计费，否则引用被扣两次）。
3. `freeze_skills`（`workflow_settings.py:751-788`）改两阶段：
   ```
   阶段一：先收集全部 path；对每个求 _body_tokens；sum 与 budget['remaining'] 比较
           → 不足：抛 _closure_blocked，文案含「所选 SKILL 正文合计 N token，超出本次窗口预算 M」
             + 点名 token 最大的前 3 个技能 + 「请减少勾选或换更大窗口的模型」
   阶段二：budget['remaining'] -= 正文合计；循环内联引用（既有 _inline_skill_report 不变）
   ```
   - `budget` 为 `unknown` 时：**抛错**要求用户在模型管理填 `context_length`（D-3），不是放行。

**验收**：
- [ ] T3、T4、T5、T8 转绿
- [ ] T1–T2 仍绿（轮 1 不回归）
- [ ] `python run_selftests.py -k skill_deep_inline skill_reference_closure workflow_settings` 全绿

---

### 轮 3（R3272）：L-3 报错分项（修 D4）

**改动文件**：`程序/orchestrator/workflow_settings.py`

`freeze_skills`（`workflow_settings.py:782`）调 `prepare_request_context` 时补 `sections`：

```python
prepare_request_context(frozen['frozen_skill_prompt'], 'SKILL',
                        sections=budget_sections(skills=frozen['frozen_skill_prompt']))
```

> 说明：此处只有 SKILL 正文一个分项可用（任务、历史在更外层拼装）。目的是让报错标签从错误的「阶段文档/任务说明」变为 `SECTION_LABELS['skills']`＝**「SKILL/阶段指令」**。

**验收**：
- [ ] T6 转绿
- [ ] `python smoke_test.py` 8/8
- [ ] 结果文件贴改前后同一超限场景的报错文案对比

---

### 轮 4（R3273）：配置补全与端到端确认（用户动作 + 验证）

1. 用户在「模型管理」为 `deepseek-v4.1-flash-1017` 填 `128000`（或依赖 D-5 前缀预设）。
2. 复跑原场景：剧本准备 → DeepSeek V4.1 FLASH → `/short drama director` → 发送。
3. **预期**：不再出现 300,000 字符报错；若正文仍超预算，报错应点名具体技能。

**验收**：
- [ ] 真实发送成功，或报错为「正文超预算」且点名技能（二者都算本轮通过，后者说明机制生效）
- [ ] `程序/logs/app.log` 不再出现「SKILL请求上下文超过」

---

## 5. 测试方案（TDD：先红后绿）

**新增文件**：`程序/tests/test_skill_context_budget_prestage.py`
**复用模式**：`tests/test_skill_deep_inline.py:27-28` 的 `patch('skill_registry.skill_roots', return_value=(临时根, 临时根))`

> **强制约束（防后期失效）**：全部测试必须用 `tempfile.TemporaryDirectory()` 内自建 SKILL 文件，**禁止读取真实 `程序/skills/`**。理由：`程序/skills/00全流程SKILL/AIGC创作全流程` 是 **gitlink 子模块**（git mode 160000），worktree 中不填充，依赖真实目录的测试在 worktree 必挂。

| # | 测试 | 断言 | 修前 |
|---|---|---|---|
| T1 | 空 `context_length` + `deepseek-v4.1-flash-1017` | `preset_context_length(...) == 128000`；`_skill_inline_budget` 返回非 `unknown` | 红（`None`） |
| T2 | 空 `context_length` + 表外模型（如 `mystery-x`） | `freeze_skills` 抛 `ValueError`，文案含「未填写上下文窗口」且点名模型 | 红（静默放行） |
| T3 | **多技能共享预算**：两个技能各带大引用 | 第二个技能的**正文**仍完整内联；`skipped` 只落在引用上 | 红（剩 306 token，第二技能正文失败） |
| T4 | 单个技能正文即超预算 | 抛错，文案含「正文合计」+ 点名该技能；**不静默截断正文** | 红（`charged=0` 放行） |
| T5 | 正文放得下、引用放不下 | 正文完整；超预算引用记 `skipped` 且含「本地路径」提示 | 红 |
| T6 | 超限报错文案分项 | 文案含 `SECTION_LABELS['skills']`＝「SKILL/阶段指令」，**不含**「阶段文档/任务说明」 | 红 |
| T7 | `skill_inline_token_budget(0)` | 返回 `0`（契约变更，同步改 `test_skill_deep_inline.py:147` 的 `assertIsNone` 为 `assertEqual(..., 0)`） | 红（`None`） |
| T8 | **不依赖真实 skills 目录** | 全部上述测试在无子模块的临时目录内通过 | — |

**跑法**（工作目录 `程序`）：
```powershell
& '..\运行环境\Python\python.exe' -B run_selftests.py -k skill_context_budget_prestage skill_deep_inline
& '..\运行环境\Python\python.exe' -B smoke_test.py --affected workflow_settings skill_inline workflow_context_budget
& '..\运行环境\Python\python.exe' -B smoke_test.py
```

---

## 6. 风险与回滚

| 风险 | 说明 | 处置 |
|---|---|---|
| **R-1 只修 D1 会让情况变坏** | 实测仅补窗口时 128K/200K 都能"发出去"，但估算 150,945／207,563 **仍在窗口外** → 把"被拦住"变成"发出去后被模型拒" | **必须 D1+D2 同轮或相邻轮完成**，不得只落轮 1 就宣布修复 |
| **R-2 正文先扣会饿死后续技能** | 实测"正文先扣"若在循环内做，首个技能引用吃光预算，剩 306 token，后续 5 技能失败 | 采用**两阶段**（先汇总正文预留，再分配引用），不得逐技能先扣 |
| **R-3 重复计费** | 若对组装后 `body`（含引用）计费，引用被扣两次，报"正文超预算"假错 | `_body_tokens` 只算 `skill_registry.parse(...)` 的 `content` |
| **R-4 L1 包化破坏相对锚点** | `skill_inline.py:29` 的 `parents[1]` 若因包化失效，异常被吞 → 静默复发 D1 | 轮 2 改注入式，并用 T8 锁住 |
| **R-5 worktree 缺子模块** | 已在诊断中实际发生（首次复现报「SKILL 引用缺失」） | 测试全 hermetic（T8） |
| **R-6 128K 下仍跳过 10 个引用** | 6 技能组合在 128K 下内联 3、跳过 10 | 属**预期行为**（引用可按需读取，正文不可省）；引导用户减少重叠勾选，不作阻塞 |

**回滚**：每轮独立可回滚（§2.6 一批一轮）。轮次顺序保证任一轮回滚后仍可发送（最坏回到现状）。回滚优先 `git revert`。

---

## 7. 并发重构共存约束（用户明确要求）

诊断时核过全部 **29 个本地分支** + 主树未提交改动：

| 对象 | 结论 | 约束 |
|---|---|---|
| `contract/workflow_context_budget.py` | 无分支改过 | 轮 1 独占，安全 |
| `orchestrator/skill_inline.py` | 无分支改过 | 轮 2 独占，安全 |
| `orchestrator/workflow_settings.py` | 无分支改过 | 轮 2/3 独占，安全 |
| `codex/wip-R3248` 改 `infra/model_pool.py` | 只动 `http_transport`／`_http_transport` 签名 | **不得**改动 `pool()` 与 `context_length_of()`；只**调用**它们 |
| L1 任务书 R3-c 改 `model_pool.py:748` `record_health` | 只加锁 | 与本任务不相交 |
| 主树未提交 R3248 改动 | 不含上述三落点 | 开工前先 `git status` 复核，若已变则重新评估 |

**若 L1 重构把 `infra/model_pool.py` 迁包或改名为其他路径**：只改 `skill_inline.py` 顶部的导入名，不改语义；`_skill_inline_budget` 已改注入式，不再依赖层级。

---

## 8. 开工前置（阻塞项，必须先解决）

**主工作区当前有未提交改动**，`round_claim.py next` 拒绝领号：

```
拒绝领取轮次：master 分支存在未提交对象（程序/infra/api_endpoints.py、model_metering.py、
model_pool.py、pet_llm.py、request_ledger.py、project_status.md、writing_api.py、
tasks_round/evidence/R3248.json、tasks_round_3248_result.md、维护记录/分支覆盖率基线.json）
```

另有未跟踪目录 `.agents/`（会话 worktree 根），同样会被判定为未提交对象。

**开工前必须**：
1. 由 R3248 责任人提交或暂存其改动，使 `git status` 干净；
2. 或用户明确授权在本任务内一并处置（仅在用户书面确认后）；
3. `.agents/` 是否加入 `.gitignore` 由用户决定（属仓库卫生，不在本任务范围）。

**未解决前**：按 AGENTS §2.5 规则 27 不得强领轮次；可先写测试（T1–T8）但不得提交。

---

## 9. 交付留痕

按 AGENTS §7，每轮：
- 新增 `程序/tasks_round/tasks_round_<N>_result.md`，开头答三问（§3 类型／测试与三基线／欠账增减）。
- 提交用 `scripts\dev.py commit -m "R<N>: 说明"`，改 `.py` 须带 `--tests`。
- 全部轮次完成后，输出 `程序/tasks_round/任务完成/SKILL请求上下文预算修复任务书·任务完成.md`，逐条列 §4 勾选项与证据。

**必报三个基线**（AGENTS §2.5 规则 29）：
- 默认冒烟：基线 8/8
- 架构门禁：当轮实际总数、失败集合、改前后比较
- 全量回归：以 `full-safe-receipts.json` 真实凭据为准

---

## 10. 明确不做的事

- 不引入 `tiktoken` 或任何新依赖（D-1）。
- 不提高 `REQUEST_CONTEXT_MAX_CHARS`（300,000）——调阈值已被证明是无效修法。
- 不改 `estimate_tokens` 的保守估算公式。
- 不删除或弱化既有 `skipped` 本地路径提示机制。
- 不改 `short-drama-director` 等 SKILL 的内容或拆分技能包（属内容决策，需另行授权）。
- 不把「减少勾选」做成自动行为——只提示，不替用户选。
