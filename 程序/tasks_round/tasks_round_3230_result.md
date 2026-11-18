# R3230 结果：L0 契约层只读诊断

## 三问

1. **本轮属于 §3 哪种类型？** §3.5 只读诊断轮。保持 `.py` 不变，不搬目录、不重命名、不删文件；只新增本文件。用户授权范围为「只读诊断，避免改动」。
2. **测试跑了吗、三个基线过了吗？** 未运行。仅新增一份只读归档文件，不改任何产品或测试代码；§5「只读诊断默认不跑测试」适用。默认冒烟 8/8 与架构门禁总数本轮未复测，未运行项如实标注。
3. **欠账少了吗？** 没有减少。本轮只做诊断与记录，新增的开发欠账见 §7，均为后续轮次的整改项，未进入本轮范围。

---

## 0. 本轮结论摘要

对 L0 契约层 33 个模块 / 5990 行做了只读审计，重点覆盖用户点名的五个门类（接口契约、数据契约、时序契约、失败契约、启动校验），并补充「L0 缺少哪些协议会导致启动失败」。

**最重要的三条：**

1. **启动链没有任何契约自检**。`validate_stage_contract()` 生产零调用；启动路径三个入口 `validate_*` / `assert` 命中数全为 0。唯一的兜底是 `启动漫剧制作助手.pyw:110` 的 `except Exception`，它只覆盖构造期抛异常，契约撕裂、设置回落、模型池缺失都不会抛。
2. **分层门禁对 L0 → agent 完全失明**。`agent`/`core`/`media` 未登记进 `_layers.py` 的 `LAYERS`，而 `test_layers.py` 的判据是 `if target_layer is not None`，未登记即短路。`contract/*.py` 有 8 个文件 9 处反向 import 长期全绿。
3. **契约文本指向不存在的文件且已进入真实提示词**。`storyboard_contract.py:12` 的 `with_name('writing.py')` 算出 `程序\contract\writing.py`（实测不存在），经 `workflow_tasks.py:6` → `:167,213,268` 进入分镜阶段提示词，模型照做会 import 失败并跳过校验。

---

## 1. 接口契约

### 1.1 四字段结果契约只有 `ok` 被消费（高）

`contract/service_contract.py:15-18` 声明 `ok / reason / recoverable / data`。实测：

- `.recoverable` 生产代码**零读取**（全仓 grep 只命中 `tests/`）；
- `is_failure()`（`:47`）生产代码**零调用**；
- 实际消费方只读 `ok` / `data` / `reason`。

影响：编排层无法据 `recoverable` 区分「重试」与「放弃」，只能一律按失败处理。附带缺陷：`success()` 传 `recoverable=False`（`:44`），语义上把「成功」标成不可恢复；`UserError` 与 `SystemError` 默认值完全相同（`:24-25` / `:31-32`），字段层面无差别。

### 1.2 唯一的解包点主动放弃契约强制力（高）

`orchestrator/stage_asset_gateways.py:130-137`：

```python
if not hasattr(result, 'ok'):
    return result
```

而契约开头明写「服务不再以裸布尔值、字符串或元组表达业务结果」（`service_contract.py:3-5`）。契约的强制力在唯一的解包点被放弃。

覆盖度：`维护记录/架构统一基数.json` 第一项 adopters 29 个、`exempt_count` 48——契约只覆盖少数写服务。

### 1.3 位置元组构成隐性契约（高）

`infra/cloud_assets.py:12-13`：

```python
NODE_TYPES = dict(zip(production_model_contract.ASSET_CLOUD_MODELS, ('ByteDanceSeedreamNode', 'GeminiImage2Node', 'OpenAIGPTImage1')))
LIMITS = dict(zip(production_model_contract.ASSET_CLOUD_MODELS, (10, 14, 16)))
```

`ASSET_CLOUD_MODELS`（`production_model_contract.py:16`）的**下标顺序**决定节点类型与参考图上限。在 L0 插一个模型或调整顺序，L1 会静默错配节点类型与张数上限，无任何报错。

### 1.4 契约文本指向不存在的文件（高）

见摘要第 3 条。`storyboard_contract.py:12` 用 `Path(__file__).resolve().with_name('writing.py')`，实体在 `程序/writing.py` 而非 `程序/contract/writing.py`。`:40-42` 把错误路径写进 `rules()` 文本。

同一文件 `:19-44` 还把镜头字段集与 `2-15 秒` 规则写死在自然语言里，与 `shot_batches.py:36,282-307`、`episode_contract.py:57,123` 三处各存一份。

### 1.5 极薄模块：不是可删的浅模块，但占了 L0 特权（中）

| 模块 | 行数 | 判定 |
| --- | --- | --- |
| `app_metadata.py` | 4 | 14+ 消费者横跨 L1–L4 与 scripts，不可删，是有效的中央事实 |
| `pet_settings_contract.py` | 9 | 三方共用，删了会造 L4→L4 横向依赖，非纯搬家 |
| `model_protocol.py` | 15 | 仅 `infra/model_secrets.py` 一个消费者，是极小但有效的接缝 |
| `production_model_contract.py` | 16 | 消费者跨四层，不可删 |

结论：**都不是应删的浅模块**。问题在于它们没有任何校验函数，却与真契约同享 L0「人人可依赖」的特权。

---

## 2. 数据契约

### 2.1 `schema_version` 永远通过（高）

三重叠加形成永久静默：

- **读侧兜底**：`artifact_schema.py:62-68` 在缺 `schema_version` 时回退读 `legacy` 键；
- **登记表给老键开绿灯**：`:19,21,23,25,27` 五类产物 `legacy: 'version'`；
- **写方至今仍写老键**：`continuity_ledger.py:236,585,610`、`domain/animatic_service.py:172` 写 `{'version': 1, ...}`。

于是 `validate()` 里 `found != item['version']`（`:84`）恒为假——老键读出 1，等于当前版本 1。

更要紧：`validate()` **没有任何读取路径调用它**。全仓仅 `domain/recon_service.py:142` 在**写入**时 stamp+validate；`orchestrator/desktop_send_ledger.py:41` 读时调用。其余读取路径一律不校验。

`stamp(kind, payload, *, version=None)`（`:52-59`）允许写入方任意传 `version=7`，当前版本 1 也照写不误，无越界断言。

### 2.2 同名常量不同集合（高）

```
contract/asset_contract.py:38            KINDS = ('character', 'scene', 'prop')
contract/script_manifest_contract.py:9   KINDS = ('character', 'scene', 'prop', 'scene_breakdown', 'emotion_curve')
```

两者都在 L0、都被广泛 import。从错误模块 import `KINDS` 不报错，只是集合少两项，校验静默漏项。

### 2.3 其余重复定义（中）

| 事实 | 重复位置 | 漂移后果 |
| --- | --- | --- |
| 阶段别名 | `stage_layout.py:67-80` / `stage_path_service.py:10-15` | 后者多出 `structure`/`frames`/`editing` 三个别名，`pet_bus.STAGES` 里没有 |
| 阶段中文名 | `script_manifest_schema.py:20-22` / `stage_layout.py:37-41` | 硬编码只覆盖前 3 个阶段 |
| manifest→阶段归属 | `script_manifest_contract.py:15-19` / `stage_layout.py:38,40,42` | 两处各写一遍 |
| 模型记录字段 | `api_models.py:4` / 7 处内联元组 | 契约常量形同废设 |

### 2.4 校验函数会静默放行（高）

- `asset_contract.py:255-258`：`if not kind: return problems`——`problems` 为空列表即视为通过。认不出类别的资产直接放行，编号拼错、类别字段缺失都算合规。
- `shot_batches.py:165` docstring 自认：「这一镜的九个新增字段有没有毛病（空列表＝通过）。**老字段不查**。」
- `error_codes.lookup`（`:41-42`）对未登记码返回 `E-UNKNOWN`，不抛错，静默吞掉码表漂移。

### 2.5 三个 `schema()` 生成器零生产消费者（中）

`asset_contract.py:340`、`script_manifest_schema.py:407`、`shot_batches.py:277` 合计约 130 行 JSON Schema 生成，全仓 `.schema()` 只命中 `tests/`。`stage_layout.schema_path()`（`:281`）同样只有测试调。

结果：「Schema 说必填 9 字段」与「手写 validate 只查子集」各自演进。

---

## 3. 时序契约

### 3.1 幂等键不含时间，重复事件被静默吞掉（高）

`pet_bus.py:87-91` 的 `identify()` 只用 `kind` + `payload` 算 sha256；`at` 是 `event()` 在 `:104` 才加进字典的，**参与不了 id**。`pump` 在 `:237-239` 命中 `_known` 就 `continue`。

影响：同一阶段以相同错误文本二次失败（重试耗尽后用户再次点运行），第二个 `stage.failed` 算出同一个 id 被当重复丢弃 → 状态机停在旧的 `failed`，自动链不重启。`stage.completed` 同理。

### 3.2 `_write` 无异常保护，写失败永久丢事件（高）

`pet_bus.py:299-304` 的 `_write` 直接 `open('a')`，无 `try`。而 `pump` 次序是 `_dequeued`(236) → `_remember`(240) → `_write`(243) → `_deliver`(244)。异常冒到 `pet_ui.py:904-908` 被吞成 `return 0`。

影响：磁盘写满或日志被占用（杀软锁 `.jsonl`）时，事件已记入 `_known` 却从未送达订阅者，**永久丢失**；`_deliver` 不执行，UI 停在上一拍，后续每拍都丢。

### 3.3 背压与去重分支的返回值失真（中）

`pet_bus.py:208-215` 两个分支都 `return item`；`emit_safe`（`:134`）原样返回。调用方（`skill_orchestrator.py:569,621,627`、`usage_snapshot.py:182`）无法区分「已入队」与「被 shed／去重」。

### 3.4 入队顺序无锁保护（中）

`pet_bus.py:207-219` 的 `with self._lock` 只护 `_queued` 与 `water`；`self.queue.put(item)`（`:220`）与 `self.touched += 1`（`:221`）在锁外。并行阶段并发 publish 时 `stage.executing` 可能晚于 `stage.completed` 入队。

### 3.5 播报前缀校验不在 emit 路径上（高，违反规则 13）

`PREFIX_PATTERNS` 只在 `broadcaster.py:28` 与 `pet_ui_voice.py:658` 用；校验发生在 L4 的 `_record_output`（`pet_ui_voice.py:680-687`），且 `ValueError` 被吞进 `self.errors`。`pet_bus.emit_safe` → `Bus.emit`（`:224-225`）全程不碰前缀表。

### 3.6 阶段完成事件只有 L4 一个真实出口（高，违反规则 20）

`emit_verified_completion` 的唯一非测试调用方是 `pet_ui_stages.py:35,99`。L3 侧 `skill_orchestrator.py:626-627` 只在 `verified_stage_output()` 为真时发 `stage.completed`，而该函数（`:57-58`）恒只认 `script`/`script_structure`。

影响：其余 11 个阶段（资产、连贯性、首帧、视频…）的完成事件只能由 UI 发。无人值守或页面未打开时产物已落盘但事件不发，状态机与交付链停在原地。

**正面证据**：顺序本身是对的——`stage_completion_service.py:781`(核验) → `:786`(写清单) → `:789-790`(before_emit) → `:791`(emit)。产物先落盘，事件后发。

### 3.7 `completion_evidence(None)` 判「完成」（中）

`stage_completion_service.py:711-712` 的 `if root is None: return True, ''`。无项目（新建空窗口、旧插件宿主）时任何阶段都被判完成，自动链可推进到空项目。fail-open 与规则 20 冲突。

---

## 4. 失败契约

### 4.1 错误码几乎只定义不用（高）

全仓 `from contract.error_codes import` 仅 3 处，**生产代码只有 1 处**：`infra/http_client.py:14`。`describe` / `code_of` / `from_http_result` 生产调用数为 0。

16 个码里真正被消费的约 6 个（`_CLASS_TO_CODE` 覆盖的 4 个 + 429 + timeout）。`E-ASSET-MISSING` / `E-CONTRACT-VIOLATION` / `E-STAGE-BLOCKED` / `E-CANCELLED` / `E-PATH-UNSAFE` / `E-FILE-TOO-LARGE` / `E-TOOL-MISSING` 全是死码。

### 4.2 「可重试」判据有两套权威源（高，违反 §2.2 单一权威）

- A 套：`error_codes.py:12` 的 `retryable` 字段，仅 `http_client.py:150` 用；
- B 套：`ui/pet_agent_rules.py:83-101` 的 `PATTERNS`/`VERDICTS`（字符串匹配 401/429/timeout…），由 `pet_agent.py:331-346` 消费，决定阶段是否 `stage.retrying`。

同一异常：HTTP 层判「不可重试」（`E-NET-CLIENT` retryable=False），阶段层判「退避重试」（`VERDICTS['params'] = True`）。

### 4.3 重试配置与错误码无连接（中）

`pet_agent.py:832` 的 `retry_limit` = `min(settings['max_attempts'], stage_parallel.retry_attempts(stage))`；`stage_parallel.py:89` 各阶段一律 `attempts: 2`，**不读** `error_codes.retryable`。

影响：`E-AUTH-REJECTED`（不可重试）照样被重试 2 次，白花配额。

### 4.4 静默异常规模（中）

实测口径（`程序` 下排除 `tests/`、`skills/`、`维护记录/`）：`except` 下一句为 `pass` = **194**；`except` 直接 `return False/None/''/0` = **300**。

契约层本体 9 处 `pass`：`platform_tools.py:122,222,237,295,593,597`、`script_contract.py:317,632`、`stage_layout.py:426`。

### 4.5 失败记录无用户可见出口（高）

- `emit_safe` 的异常只写 `errors.append`（`pet_bus.py:135-137`）；
- `ErrorLog`（`:107-123`）与 `self.errors` 在**全部生产代码中无读取方**（grep `.[]` 只命中 tests）；
- `pet_ui.py` 11 处 `errors.append` 同样无人展示。

影响：事件发布失败、订阅者异常（`:270-278`，仅 `errors_total ≤ 128` 时落盘）、前缀缺失、日志写入失败，用户全都看不到。`stats()`（`:312-316`）暴露了计数但只在测试与面板里被调，不构成告警。

### 4.6 编排器 errors 是无界 list（中）

`skill_orchestrator.py:156` `self.errors = errors if errors is not None else []`；而 `pet_ui.py:201,358` 传的是有界 64 的 `pet_bus.ErrorLog`。单独使用编排器（脚本、自动补跑）时长跑会话里 `errors` 无限增长。

---

## 5. 启动校验

### 5.1 `validate_stage_contract()` 生产零调用（高）

`stage_layout.py:252-257` 定义；调用方只有 `tests/test_stage_layout.py:126` 与 `tests/test_animatic_service.py:165`。`app.py`（1486 行）、`desktop.py`（964 行）、`启动漫剧制作助手.pyw`（119 行）均无调用。

启动路径关键字实测：

| 文件 | `validate_*` | `assert` | `rglob` | `os.walk` | `messagebox.showerror` |
| --- | --- | --- | --- | --- | --- |
| `app.py` | 0 | 0 | 0 | 0 | 0 |
| `desktop.py` | 0 | 0 | 0 | 0 | 0 |
| `启动漫剧制作助手.pyw` | 0 | 0 | 0 | 0 | 0（有 1 处 `MessageBoxW`） |

影响：§2.2 明写它「守卫目录阶段契约」，实际只在 CI 生效。`pet_bus.STAGES` 与 `stage_layout.STAGES` 一旦撕裂，启动不报错；直到用户点操作才在 `stage_path_service.py:50-51` 抛 `ValueError`，错误点离成因很远。

### 5.2 启动到可交互之间零契约自检（高）

`启动漫剧制作助手.pyw:74` `desk=Desktop(...)` → `desktop.py:154-205`（`_init_window_and_sidebar` → `reload()` → `show(0)` → `begin_startup_or_login` → `pet_ui.start` → `setup_tray`）。此路径上无 `stage_contract_errors()`、无模型池自检、无依赖检查、无磁盘检查（全仓 `disk_usage`/`shutil.disk` 生产代码 0 处）。

唯一兜底是 `pyw:110-119` 的最外层 `except Exception`：写 `启动错误.log` + `MessageBoxW`。它只覆盖**构造期抛异常**。

### 5.3 「校验失败静默继续」确实存在（中）

- `desktop_settings_service.py`：设置读取失败 → `LOGGER.exception` + 回落默认值 + 存 `.corrupt` 副本，**UI 无提示**。
- `stage_layout.py:412-433` `link_dir`：`os.symlink` 失败 `pass`（`:426`）后试 `mklink /J`，中间失败无记录。
- `pyw:68-69`：`Splash` 构造失败被 `except Exception` 吞成 `splash=None`，静默降级为无启动画面。
- `pyw:90-92` `track()`：`TclError/ValueError` 吞成 `return None`。

### 5.4 规则 33（启动零递归扫描）：主体守住，有未加护栏的入口（中）

守住的部分：`stage_path_service.py:73-77` 只检查一层；`script_workspace_service.py:111` 明确「不要在启动期用 rglob」；`desktop_automation_tick.py:69-72` 有 `_startup_tick_paused` 闸。

风险点：`desktop.py:696` 置 `auto.adopt_startup=True`，首拍即走 `_tick_auto_adopt`（`desktop_automation_tick.py:78`）→ `auto_final_scan`（`:101`）；`storyboard_catalog_service.discover_files`（`:46` `os.walk`）挂在页面刷新路线上。闸门靠调用顺序约定，**没有测试断言「闸打开前不得 walk」**。

### 5.5 校验逻辑散落消费者

| 应有位置 | 实际位置 | 证据 |
| --- | --- | --- |
| 阶段完成核验（规则 20） | L4 UI | `pet_ui_stages.py:35,99` |
| 未登记阶段处理 | L0 抛、L1 吞 | `pet_bus.py:99-100` `raise` vs `pet_state.py:87-89` `return False` |
| 可重试判据 | L0 + L4 双份 | `error_codes.py:12` vs `pet_agent_rules.py:92-101` |
| 播报前缀判定 | L4 自实现关键词猜测 | `pet_ui_voice.py:655-679` |
| 路径越界校验 | 只在单文件读路径 | `stage_path_service.py:94-95` 有 `is_relative_to`，`write_dir`（`:44-52`）不校验 project 根 |

---

## 6. 补充：L0 缺少哪些协议会导致启动失败

按用户要求，参考企业级项目与成熟框架，列出 L0 当前**没有**、且缺失会直接导致「启动失败但用户看不懂」或「启动成功但一用就炸」的协议。

### 6.1 启动就绪协议（Startup Readiness Protocol）——缺

**参考**：Kubernetes 的 startup/readiness/liveness 三探针分离；Spring Boot 的 `ApplicationRunner` + `ApplicationReadyEvent`；.NET 的 `IHostedService.StartAsync` 有序启动；Electron 的 `app.whenReady()`。

**本项目现状**：`desktop.py:154-205` 构造期一路跑完，没有「阶段化启动」的概念。`pyw:70-75` 只有一个 `step(1)`/`step(2)` 的启动画面进度回调，不构成协议。

**为什么会导致启动失败**：`Desktop.__init__` 里任何一步抛异常，用户看到的是「启动失败，详情已保存到 启动错误.log」——一个笼统的 MessageBox。用户无法知道是阶段契约撕裂、模型池为空、还是磁盘满了。**缺的是「哪一步失败了」的分类能力**，不是「不失败」。

**应有协议**：L0 定义 `StartupPhase` 枚举（`CONTRACT` / `CONFIG` / `RESOURCE` / `UI_SHELL` / `READY`）与 `StartupFailure(phase, severity, code, message, remedy)`；启动器按 phase 报告，用户看得到「配置损坏」而不是「启动失败」。

### 6.2 严重度分级协议（Severity Protocol）——缺

**参考**：所有成熟框架的 `Fatal / Error / Warn / Degraded` 分级；Spring Boot 的 `FailureAnalyzer` 把异常翻译成人话 + `Action`；Kubernetes 的 `PodDisruptionBudget` 式降级。

**本项目现状**：契约层**没有任何 severity/health/readiness 概念**（grep `severity|fatal|degraded|readiness|health` 于 `contract/` 零命中）。

**为什么会导致启动失败**：用户已确认的决策是「甲类 fail-closed，乙类 fail-open」——但 L0 现在**没有任何类型能表达这个区分**。`ServiceResult.recoverable` 是最接近的，但生产零读取（见 §1.1）。

**应有协议**：`Severity` 枚举 + `Diagnostic(severity, scope, code, message, remedy)`。没有它，§6.1 的 `StartupFailure` 无法分级，用户决策无法落地。

### 6.3 资源前置检查协议（Resource Precondition Protocol）——缺

**参考**：Docker 的 daemon 启动前置检查；VS Code 的 `--status` 诊断；Node 的 `process.report`。

**本项目现状**：全仓 `disk_usage` / `shutil.disk` 生产代码 **0 处**。随包 FFmpeg 缺失只在 `scripts/distribution_selfcheck.py` 检查——而该脚本只在 `scripts/dev.py`、`scripts/local_ci.py`、`scripts/release_snapshot.py` 里被调用，**产品路径不调**。

**为什么会导致启动失败**：磁盘满时 `_write` 抛异常（见 §3.2）→ 事件永久丢失 → 用户看到的是「界面不动了」，而不是「磁盘满了」。FFmpeg 缺失时第一次点视频阶段才炸。数据目录不可写时 `app_logging.install` 会怎样没有明确契约。

**应有协议**：`ResourceCheck` 协议（`name` / `probe() -> Available|Degraded|Missing` / `remedy`），在启动 `CONFIG` 阶段跑一次，结果进 §6.2 的 `Diagnostic`。候选检查项：数据目录可写、日志目录可写、磁盘剩余、随包 FFmpeg/ffprobe 存在、解释器版本匹配、依赖白名单一致。

### 6.4 版本与兼容协议（Version Compatibility Protocol）——部分缺失

**参考**：Flyway/Liquibase 的 `schema_version` + migrations；Spring Boot 的 `spring.config.import` 版本探测。

**本项目现状**：`artifact_schema` 有登记表与 `stamp`/`validate`/`migrate`，但**读取路径不校验**（见 §2.1），且写方仍写老键。`app_metadata.VERSION = 'V0.7'` 但没有任何「配置文件版本 vs 程序版本」的兼容检查。

**为什么会导致启动失败**：用户从 V0.6 升到 V0.7，配置文件是旧格式——现在不会有任何提示，只会读到默认值（`desktop_settings_service` 静默回落），或读出一个字段缺失的字典，在某个页面深处炸。

**应有协议**：配置文件的 `schema_version` + 启动时 `migrate()` 或拒绝并提示。`artifact_schema` 的骨架已有，缺的是**读取路径强制调用**。

### 6.5 能力协商协议（Capability Negotiation Protocol）——缺

**参考**：MCP 的 `initialize` 握手（`protocolVersion` + `capabilities`）；LSP 的 `initialize`；HTTP 的 `OPTIONS`/`Accept`。

**本项目现状**：`contract/` 里 `probe_http_endpoint`（`platform_tools.py:422`）是唯一的探针，且只探 HTTP 可用性。模型能力（`model_pool.capabilities_of`，`:200`）存在但不在启动时校验。

**为什么会导致启动失败**：登录后模型池为空时的引导（R3202 刚做）是**事后引导**，不是**启动前协商**。用户的模型池里有一个已下线模型，界面显示正常，第一次生成时 404。

**应有协议**：`Capability` 声明 + 启动 `READY` 阶段的轻量协商（不联网，只校验本地声明与实际配置一致）。注意与规则 33「启动零递归扫描」的张力：协商必须不扫目录。

### 6.6 降级运行协议（Degraded Mode Protocol）——缺

**参考**：Chrome 的 `--disable-gpu` 安全模式；Windows 的「上次启动失败，是否以安全模式启动」；Kubernetes 的 `CrashLoopBackOff` 退避。

**本项目现状**：没有「安全模式」。启动失败就是失败，用户唯一出路是看 `启动错误.log`。

**为什么会导致启动失败**：一个坏掉的配置文件、一个损坏的项目索引、一个异常的插件，都能让应用**永远打不开**，而用户不知道「把哪个文件改名就能起来」。

**应有协议**：连续 N 次启动失败 → 提示「以安全模式启动（跳过项目恢复、跳过插件、使用默认配置）」。这需要 §6.1 的 phase 记录来判定「上次失败在哪一步」。

### 6.7 单实例与激活协议——已有，质量不错

`启动漫剧制作助手.pyw:18-30` 用命名 Mutex + Event 做单实例与窗口激活，`Local\` 前缀、`sha256(root)` 派生名字、`WinError` 兜底。这是本次审计里**唯一一处达到成熟框架水准的启动协议**。建议保留并在 `architecture.md` 记为正面样例。

### 6.8 小结：优先级

| 协议 | 缺失后果 | 建议优先级 |
| --- | --- | --- |
| 6.2 严重度分级 | 用户已定的 fail-closed/fail-open 决策无法落地 | **P0**（其它协议的前置） |
| 6.1 启动就绪/阶段化 | 启动失败不可归类，用户只看到笼统 MessageBox | **P0** |
| 6.3 资源前置检查 | 磁盘满/FFmpeg 缺失在深处才炸 | **P1** |
| 6.4 版本兼容 | 升级后配置静默回落或深处报错 | **P1** |
| 6.6 降级运行 | 一次坏配置导致永久打不开 | **P2** |
| 6.5 能力协商 | 下线模型首次生成才 404 | **P2** |

**P0 两条是同一件事的两面**：`Severity` 是类型，`StartupPhase` 是阶段，两者合起来才是可用的启动自检协议。这也是架构报告里 C1 候选的具体形状。

---

## 7. 本轮未做的与新增欠账

**未做（本轮范围外）**：

- 未修改任何 `.py`、未启动修复。
- 未运行测试（只读诊断轮默认不跑）。
- 未同步主工作区的依赖白名单 4 个文件（`依赖白名单.md`、`test_dependency_whitelist.py`、`AGENTS.md`、`CLAUDE.md`）——按用户决定走「主区先提交成一轮，再同步」。

**新增欠账（后续轮次整改项）**：

| 编号 | 内容 | 建议轮次类型 |
| --- | --- | --- |
| D1 | `contract/storyboard_contract.py:12` 指向不存在的 `writing.py` | 修复轮（最小 diff） |
| D2 | `_layers.py` 未登记 `agent`/`core`/`media`，门禁失明 | 结构治理轮 |
| D3 | L0 缺 Severity + StartupPhase 协议（§6.1/6.2） | 契约轮 |
| D4 | `artifact_schema` 读取路径不校验版本（§2.1） | 契约轮 |
| D5 | `pet_bus` 幂等键不含时间 + `_write` 无保护（§3.1/3.2） | 契约轮 |
| D6 | `error_codes` 接线 + 删除第二套可重试判据（§4.2） | 契约轮 |
| D7 | 重复定义收敛（`KINDS`、阶段别名、镜头字段）（§2.2/2.3） | 结构治理轮 |
| D8 | `self.errors` 接可见出口（§4.5） | 功能轮 |

---

## 8. 并发提示

本轮开工时 `round_claim.py` 显示多个工作树并发：`codex-whitelist-framework` 领取了 R3224 / R3227 并已提交 `R3224: 锁定生产六包并将开发工具改为可选白名单`、`R3220: JSON默认传输复用requests并保留重试脱敏与响应上限`。

**重要更正**：本报告 §5 之前的初稿判断「requests 未落地」是**错的**。实测该树已实现 `contract/platform_tools.py` 的 `RequestsJsonOpener`，`infra/http_client.py:69` 通过 `from contract.platform_tools import RequestsJsonOpener` 注入，保留了 `_read_limited` 32MB 上限、熔断、错误码映射与脱敏，Session 在 `open()` 内创建并在 `close()` 释放。

这与用户选定的「(b) 引入但只替传输层，骨架不动」**完全一致**，该方案已无需再议。

同时该树正在改 `contract/file_naming.py`、`contract/script_contract.py`、`domain/storyboard_adoption_contract.py`，与本报告 §1.4 的 `storyboard_contract.py` 不冲突，但后续若开 C5 修复轮需先同步主干避免冲突。

---

## 9. 复核更正（2026-11-17，任务书 v2 修订时追加）

以上 §0–§8 为原始诊断记录，保持原文。复核时发现以下几处与实测不符或已过时，以本节为准；对应处置已写入《L0契约层防崩溃与协议补齐任务书》v2。

### 9.1 数字与事实更正

| 原文位置 | 原文 | 复核结果 |
| --- | --- | --- |
| §0 第 2 条 | `contract/*.py` 有 8 个文件 9 处反向 import | **7 个文件 11 处**：`api_models` 1、`artifact_lineage` 1、`episode_contract` 1、`pet_bus` 1、`script_contract` 5、`script_manifest_schema` 1、`stage_layout` 1 |
| §8 | `RequestsJsonOpener` 已实现 | 本工作树与 master 均搜不到；按 §8 所述它在 `codex/whitelist-framework` 分支，该分支仍领先 master 4 个提交未合入 |
| 全文行号 | — | 取自 R3213 基线；master 已到 R3233（领先 23 个提交），`pet_ui_stages.py` 已迁入 `ui/`，`app.py`、`desktop.py`、`continuity_ledger.py`、`pet_agent.py` 等均有改动，行号需重测 |
| §5.1 表 | 启动路径入口为 `app.py`／`desktop.py`／`pyw` | 另有 `desktop_launcher.py:27` 也构造 `Desktop` |

### 9.2 原诊断遗漏的缺陷

1. **启动器的保护有洞**（高）。`启动漫剧制作助手.pyw` 第 9–13 行的 `import hash_backend`、`from contract.app_metadata import APP_NAME`、`app_logging.install` 在 `try` 之外；`except` 分支自身又 `from contract.app_metadata import VERSION`。`contract` 包损坏时 `pythonw` 下无任何提示。§5.2 称最外层 `except` 是「唯一兜底」，实际连这层也覆盖不到契约包损坏。
2. **`agent` 包内部存在跨层依赖**（中）。`agent/core.py:13,36` import `agent.publication`；`agent/prompt_optimizer.py` import `tkinter`／`ui_widgets`／`ui_tokens`／`infra.tk_timers`；`agent/shot_assets.py:118` import `ui.white_model_ref`；`agent/voice_mcp_server.py:136` import `domain.speech_api`。`agent` 不能整体登记为一层，也不能照「core＝L1、其余＝L2」登记。
3. **`agent.media` 不是单消费者模块**。除 `episode_contract` 外还有 `image_agent_runner`、`local_video`、`domain/audio_import_service`、`domain/delivery_import_service`。
4. **`pet_bus` 的去重承担两个职责**（补充 §3.1）。`identify()` 的键既用于 `pump` 去重，也用于 `publish` 的入队背压（`_queued`）。把 `at` 纳入键会同时废掉背压保护。全仓目前没有调用方传 `key=`。
5. **`file_cache.read_json(path)` 没有 `kind` 参数**（补充 §2.1）。版本校验无法在该函数内统一完成，只能由各产物的属主模块在自己的读取点做。
6. **已有的崩溃与启动记录入口未被提及**。`diagnostic_capture` 已提供 `record_crash`、`record_startup_timing`、`record_degradation`、`record_gate_result`、`export`，并已挂为 `app_logging` 的 `crash_sink`。§6.1／§6.6 的协议应并入它，而不是另起账本。
7. **`round_claim.py show` 不带 `-X utf8` 时报错**（低）。复核时在 Git Bash 下运行，`git_common_dir()` 读子进程输出时 GBK 解码失败，`result.stdout` 为 `None`。带 `-X utf8` 后正常退出。

### 9.3 欠账表增补

§7 的 D1–D8 之外，任务书 v2 新增承接：

| 编号 | 内容 | 轮次 |
| --- | --- | --- |
| D9 | §2.4 `asset_contract` 认不出类别即放行 | 轮 7A |
| D10 | §3.6 完成事件只有 L4 出口；§3.7 空项目判完成 | 轮 7B |
| D11 | 启动器保护有洞（§9.2 第 1 条）；§5.3 设置损坏接 DEGRADED | 轮 3B |
| D7 增补 | §2.3 阶段别名重复（原 D7 列了但 v1 任务书漏排） | 轮 6D |

其余未承接项见任务书 v2 §9「明确不做」。

---

## 10. 框架复用与「不重复造轮子」评估（2026-11-18 追加，只读调研）

> **追加说明**：本节纯新增，不改动上文任何结论与行号。对应任务书 §3b（通用库与跨领域框架思想）＋ §3c（同域应用对标）。
> **工具风险如实记录**：本次评估期间 `web_search` 工具持续返回 HTTP 401（凭据无效），全部证据改用 `web_fetch` 直连 `raw.githubusercontent.com` 抓取；两条最关键结论另用 PowerShell 逐字复核。

### 10.1 结论先行：没有可直接复用的「L0 契约层框架」

「L0 契约层」是分层架构（Clean / Hexagonal）里各家自行约定的概念，**不存在对应的发行包**。可复用的只有**局部方案**与**设计思想**。

评估分两档：
- **§3b 通用档**：21 个 Python 库（逐个查版本／stars／传递依赖／3.14 实测）＋ 3 个跨领域框架思想（Spring Boot / Chromium / Flyway）。
- **§3c 同域档**：3 个做同一件事的应用（ComfyUI / InvokeAI / A1111），逐字读取源码。

### 10.2 强烈建议复用（全部零新增依赖）

| # | 来源 | 复用内容 | 落到本项目 |
| --- | --- | --- | --- |
| 1 | **ComfyUI** `main.py` | 失败分级三段式：固定 `kind` 闭集 + `what`（发生了什么）+ `fix`（怎么办）+ **每条附逃生开关** | `contract/diagnostics.py` 的 `Diagnostic` 增 **`escape_hint`** 字段；`contract/error_codes.py` 的 `kind` 用固定闭集 |
| 2 | **InvokeAI** `config_default.py` | 配置版本阶梯：`CONFIG_SCHEMA_VERSION` + 逐级 `migrate_*` 纯函数 + `.bak` 备份 + 失败回滚 + **落盘后 `assert` 版本号** | 改造 `contract/artifact_schema.py` 的 `migrate()` |
| 3 | **Spring Boot** `diagnostics` 包 | `FailureAnalyzer` 派发链：按序遍历、首个非 null 胜出、**诊断器自身异常不掩盖原错** | `error_codes.analyze()` 派发链（复活当前近乎死码的错误码表） |
| 4 | **Chromium** `gpu_process_host.cc` | 崩溃预算：`FORGIVE_MINUTES=5` 时间窗赦免、`CRASH_LIMIT=3`、正常退出清零 | `diagnostic_capture` 的降级判定（安全模式） |
| 5 | **A1111** `modules/scripts.py` | 扩展隔离：每个挂载点各自 `try`，插件坏一个只丢一个功能区 | 13 阶段各自的失败边界 |
| 6 | **A1111** `modules/cmd_args.py` | 开关**按族命名**：`--skip-*`（跳检查）／`--disable-*`（关功能） | 安全模式的 GUI 等价物 |

### 10.3 明确不复用（每条踩到具体约束）

| 候选 | 否决理由 |
| --- | --- |
| `blinker` | **实测不能替代 `pet_bus`**：`connect` 同一函数三次只留 2 个 receiver（按函数身份去重），但无队列、无背压、无 `SHEDDABLE_EVENTS` 的「终态永不丢、只丢中间态」、无异常落审计；`send` 异常直接上抛、接收者顺序未定义。250 行是有效复杂度 |
| `pydantic-settings` | 6 个传递依赖 + `pydantic_core` 二进制，与 `requirements.txt` 的 `# No pip dependencies` 正面冲突 |
| `dependency-injector` | C 扩展、4920 stars 卡在白名单 5000 门槛线下；桌面单进程无多实现替换需求 |
| `lagom` / `punq` | 解决「运行时动态绑定」，而真问题是启动顺序 + 失败分级，20 行常量元组就够 |
| `import-linter` | 依赖 Rust 的 `grimp`；且现有 AST 门禁（138 文件 / 489 测试）表达力更强 |
| `tach` | 14 个传递依赖 + Rust 扩展 |
| `pytest-archon` | 需 pytest（本项目是 unittest），classifier 止于 3.11 |
| `returns` / `result` | `returns` 收益在 mypy 类型流（本项目不用）；`result` 已 archived |
| `alembic` | 强绑 SQLAlchemy + DB 前提 |
| `dynaconf` / `hydra-core` | 解决「多环境多格式合并」，桌面只有一个 `config.json` |
| `healthcheck` / `py-healthcheck` | 前者 GitHub 已 404 且只有 sdist；后者 115 stars 无 classifier。桌面无 orchestrator 轮询探针 |
| `structlog` / `loguru` | 本身不内置脱敏，要自己写 processor；Tk 桌面日志是给人看的滚动文本 |
| `jsonschema` | 引入 `rpds-py` 二进制 + 4 个依赖；且 JSON Schema 表达不了分阶段的业务规则 |

### 10.4 必须如实标注：两项无行业对标，须自研

| 检查项 | ComfyUI | InvokeAI | A1111 | 结论 |
| --- | --- | --- | --- | --- |
| **磁盘空间前置检查** | 零命中 | 零命中 | 零命中 | **行业空白** |
| **L0 契约层自检** | 无独立入口 | 无（仅配置 `assert`） | 无（仅依赖版本检查） | **须自研** |

这两项**不得声称有对标实现**。可借 ComfyUI 的「what + fix + 逃生」**信息格式外壳**，检查逻辑本身是原创。

### 10.5 明确不能照搬的四处

1. **ComfyUI 模型池为空静默返回空列表**（`recursive_search` → `return [], {}`）。那是 Web 假设：前端能渲染空下拉框。Tkinter 流水线跑到第 7 阶段才失败，用户已等几十分钟。本项目按既有决策：**模型缺失 = 乙类 fail-open + 启动即显性横幅**。
2. **ComfyUI 的 `sys.exit(1)` + 启动器匹配日志行**。本项目是 `.pyw` 双击直启，**没有中间启动器**。抄信息结构，不抄「打日志然后死」。
3. **A1111 用 `str(e)` 子串匹配**已崩形态给处方（`errors.py:75` 匹配 `torch.Size([640, 1024])`）。升级即失效。分类要在**抛错侧**定 `kind`，不在收错侧猜字符串。
4. **InvokeAI 的 `scan_models_on_startup`** 默认 `False` 且只「登记孤儿模型」，服务于 `use_memory_db` 测试场景。抄它会得到一个「看着有检查其实没检查」的开关。

### 10.6 核实未果项（不掩盖）

- **ComfyUI 的 ffmpeg 解析**：`cli_args.py`／`main.py`／`folder_paths.py`／`nodes.py`／`model_management.py`／`server.py`／`requirements.txt` 全部**零命中** `ffmpeg|ffprobe|shutil.which`。推断其走 PyAV 内嵌（`nodes.py:1774` 有 pyav 注释、依赖清单无 ffmpeg），**属推断，无直接证据**。本项目随包 ffmpeg 解析仍需自研。
- **InvokeAI 的 `--skip-*` 容错开关**：`config_default.py` 内未找到，不排除其他模块存在。
- **InvokeAI `invokeai_configure` 路径**：原提示路径 404，实际实现位于 `invokeai/app/services/config/config_default.py`。
- **三家 PyPI 月下载量**：未取（`web_search` 不可用）。

### 10.7 对任务书轮次的影响（已并入任务书 §3c-5 与 §8）

| 轮次 | 变化 |
| --- | --- |
| 轮 3A（D3） | `Diagnostic` 增 `escape_hint`；`kind` 用固定闭集 → **接口变更，测试须覆盖** |
| 轮 3B（D3-j） | 无变化（Chromium 崩溃预算三家都没有，确实更完整） |
| 轮 4A（D4） | 方案由 Flyway 换成 **InvokeAI**：新增 `.bak` 备份、失败回滚、落盘后断言三项验收 |
| 轮 7B | 新增「降级开关按族命名」（A1111 的 `skip`/`disable` GUI 等价物） |
| 验收清单 | 新增「调研完整性」一条，含「未能对标的两项已如实标注为自研」 |

### 10.8 本轮（本节）的边界声明

- 本节**只读调研 + 文档追加**，未修改任何 `.py`。
- 未改动本文件第 1–406 行任何内容（§9 复核更正为其他会话所写，保持原样）。
- 未新建源码模块；对任务书的对应改动见任务书 §3b／§3c／§8，与本节互为引用。
