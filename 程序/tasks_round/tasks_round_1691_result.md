# R1691 功能轮（源码轮）：接入 DeepSeek Search／Fetch，采风从「模型自觉」变成「可机检」

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（源码轮）。新增 L2 `recon_service` 与 L1 `model_pool` 的两个工具接口，把「③对标爆款／④热点速成」的采风检索接成程序能力；按 §2.7 先改 `docs/REQUIREMENTS.md`／`docs/DESIGN.md` 的 S01 条目（REQ-S01-40～45、DES-S01-40～42）再写代码。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；架构门禁 **368/368**（含全量欠账门禁，跑完整安全全量后转绿）；定向 `-k recon_service model_pool skill_tools stage_layout script_contract artifact_schema idea_brief_form` **200/200**；新增用例 38 条（`tests/test_recon_service.py` 29 条、`tests/test_model_pool_tools.py` 9 条）全绿；**完整安全全量 5806 条、726.6 秒、0 文件有红、凭据已写入**（见 D 节）。**联网实测未做**——本机没有 `DEEPSEEK_API_KEY`（详见「未验证」）。
3. **project_status.md 的欠账少了吗？** 少了：本轮触发并执行完整安全全量（开工实测 `source_rounds_since=20`、`risk_overdue=True`，早已过门禁线 8）；开工前后台自动全量在 `c9326e8` 上是**假红**（`.wt/ci\程序\run_selftests.py` 不存在，78 秒即退，不是测试失败）。本轮以主干人工全量接续并写入凭据 `round=1691`，`full_safe_required` 复算为 **False**。

## A 改动

- **L1 `model_pool.py`（新增 Search／Fetch 工具接口）**：`tools_search()`／`tools_fetch()`／`tools_base()`／`tools_headers()`／`tools_error_kind()`／`tools_retryable()` 与常量块。复用既有 `_http_transport`／`_request_headers`／`_http_opener`（禁跟重定向）与 `credential('DEEPSEEK_API_KEY')`，不新开网络栈、不新增密钥来源。`tools_base()` 优先取模型池里 DeepSeek 那条的地址（用户换代理时跟着走），取不到退回 `https://api.deepseek.com`。`transport`／`headers` 是自检注入点。
- **L2 `recon_service.py`（新，约 390 行）**：`plan_queries()`（③找单剧／④找选题方向）、`collect()`（检索→抓正文→出卡，含预算与重试）、六条证据机检 `evidence()`、来源分级 `tier_of()`（现算：`summary` 封顶 T2，`content`+`authority≥3` 或官方域名才 T1）、独立信源按注册域去重、`save_card()`（`artifact_schema` 版本＋`agent.core.save` 原子发布）、`render()` 人读版、`run()` 端到端。**不 import urllib、不读密钥**，网络只经 L1。
- **L4 `skill_tools.py`**：新增 `recon.card`（ready 表），素材来源不是③④时**跳过**、缺对标对象时按「还缺输入」返回（不阻断阶段）；`_recon_topic()` 只从简报取「故事题材」一个方向词，梗概不外传。
- **L0 `stage_layout.py`**：`DOCS['01剧本准备']` 增 `intel_card.md`；`json_md_rows()` 增 `recon_card.json ↔ intel_card.md` 一条。
- **L0 `artifact_schema.py`**：登记 `recon_card`（version 1，必备 `target`／`sources`，owner `recon_service`）。
- **`tests/architecture/_layers.py`**：`recon_service` 登记为 L2。
- **`skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md`**：frontmatter `tools` 增 `recon.card`；采风引用那条补「检索→落卡」两步与产物位置。
- **`docs/REQUIREMENTS.md`／`docs/DESIGN.md`**：新增 S01「素材采风」小节 6 条需求 + 3 条设计；非目标补「不做图片检索／平台内部数据／定时抓取／评分门槛」。
- **测试**：`tests/test_recon_service.py`（29 条）、`tests/test_model_pool_tools.py`（9 条）。
- **台账**：`维护记录/覆盖率基线.json` 重跑工具刷新（281→284，见下）；`维护记录/架构统一基数.json` 第四项行号平移与两条新增豁免、第一项 `scope_audit_pending` 登记 `recon_service`；`runbook.md` §11 数字同步。

### 与接口文档的对齐

| 文档要求 | 落地 |
| --- | --- |
| `query` 1～128 字符、非全空白 | `tools_search` 先校验，非法直接 `kind='invalid'`，不发出请求 |
| `count` 1～50，默认 10 | 夹取到区间；非数字回退 10 |
| `url` ≤8192、含 host 的 http(s)、不带用户名密码 | `_tools_url_problem()` 三条判定 |
| 计费只在成功且非空 | `budget` 分开记 `search_used`（发起）与 `search_billed`（可能计费），`fetch_*` 同理 |
| 408／429／5xx 重试，402 充值，其余 4xx 不重试 | `tools_retryable()`＋`_attempt()`（3 次、1/2/4 秒退避）；402／401 立即停并写进 `not_found` |
| QPS 5（账号级） | 串行逐条请求；预算上限 6 检索／6 抓取／45 秒，超时按 `clock` 截断 |

## B 验证（本轮实测）

| 项 | 结果 |
| --- | --- |
| 默认冒烟 `smoke_test.py` | **8/8**（第 10 轮） |
| 架构门禁 `smoke_test.py --architecture` | **367/368**，唯一红＝`test_full_safe_all_is_required_after_eight_source_rounds`（全量欠账门禁，由本轮安全全量闭环） |
| 定向 `run_selftests.py -k recon_service model_pool skill_tools stage_layout script_contract artifact_schema idea_brief_form` | **200/200**，0 文件红 |
| 新增用例 | **38/38**（离线注入传输，不联网） |
| 覆盖率基线刷新 | `scripts/coverage_report.py`（同一组 8 个目标）→ **49/284**，`tests_ok` 真 |
| 联网实测 | **未做**（缺 `DEEPSEEK_API_KEY`，见下） |

### 顺手闭环的两处历史红（如实记录）

- **覆盖率基线已过期**：开工前基线 281 个模块，实际生产运行时已是 283（`script_view_style.py` R1690、`skill_note_render.py` R1685 新增后没重跑工具），`test_coverage_baseline` 的「基线模块集合＝生产运行时口径」原本就红。本轮重跑工具后为 284（含新模块），集合相等。
- **第四项（裸 `json.loads`）行号漂移**：`model_pool.py` 852→863、898→909（本轮插入工具接口导致）；另发现 `workflow_engines.py` 的登记项 146 已失效、实际在 143 与 196（前者 OpenCode 事件流逐行解码，后者读 OpenCode CLI 自己写出的 `.response.json`）。四项均按 `exempt` 登记原因，未放宽语义。

### 全量安全回归

**5806 条用例 / 726.6 秒 / 0 个文件有红 / 实际跳过 1 条（`test_core.test_stage_profile_wrong_preset_rejected`，既有登记位：发行包未含受测 bundled skill）**，命令 `run_selftests.py --all --safe --jobs 4 --gui-jobs 2`，内容树 `ee4df14091950a16cb21670815fd3a263435d0b4`（＝提交 `e44f4c86:程序`），凭据写入后 `last_full_safe_all_round=1691`，`full_safe_required()` 复算 **False**。

### 全量首跑红：三批收口（都不是本轮新代码）

首跑（620.7 秒）8 个文件红，全部是 R1624 以来「改过实现但没同步测试资产」的欠账；本轮逐条核实根因后收口，**没有放宽任何断言**：

| 红项 | 根因 | 收口 |
| --- | --- | --- |
| `test_skills.test_the_panel_shows_the_skill_markdown` | R1685 把说明栏改成 Markdown 排版，测试仍比对原文 | 比对面改为 `skill_note_render.parse()` 的可见文字（正文仍逐字比对） |
| `test_version_pin` 2 条 | `Studio.pin_version` 现在重发交付清单，替身缺 `publish_manifest` | 替身补该接缝，并**新增**一条「采用后必须重发清单」断言 |
| `test_edit_adoption` 4 条 | `publish_edit_bundle` 现在写 `edits.json.inputs`，测试拿 `None` 当 self | 换 `BundleStudio` 替身，并**新增**「inputs 已记入 edits.json」断言 |
| `test_critical_chains` / `test_pet_ui` 各 1 条 | 镜头夹具没有 `location`／`title`，程序派生的 `scene_breakdown` 因此缺 `name`（manifest 契约要求） | 夹具补成真实形状（`SH001`＋`LOC_001`＋标题），断言未动 |
| `test_copy_rules` 1 条 | R1688 的 OpenCode 弹窗 62 字，超 45 字上限 | 文案压到 34 字，语义不变 |
| `test_ui_edges` 1 条 | R1690 改了 `wrap`（≤20 万字符按词换行），测试仍期待 `none` | 改为断 `word`＋全文保留；阈值与横向滚动条联动本已由 `test_script_view_style` 覆盖 |
| `test_soak_light` 1 条 | 8 路并行时逐轮 10.95 秒超 10 秒记录上限；单独跑与 4 路并行均绿（34.4 秒／4 条） | 不改阈值，改验收并行度（`--jobs 4 --gui-jobs 2`）；本机另有一个 4.6 CPU-小时的空命令行 python 进程（PID 37328，父进程已退出），属既有环境负载，未擅自处置 |
| `architecture.test_round_baselines` 1 条 | 结果文件 1691 存在后轮次头仍是 1691 | 状态页轮次头置 **1692** |

## C 未验证／待裁决

- **联网实测未做（本轮唯一实质缺口）**：本机 `.env`／`private/.env`／环境变量／DPAPI 均无 `DEEPSEEK_API_KEY`，`model_pool.credential('DEEPSEEK_API_KEY')` 直接抛「缺少有效 API Key」。因此**没有真实发出过一次 Search／Fetch 请求**：真实返回结构、真实 `authority`／`date`／`rerank_score` 取值、真实 404/403 比例（抖音/红果类 JS 页面抓不动）都只有文档依据。要求用户补钥匙后跑一次 `recon.card` 才能关掉这一条。
- **未打开真实窗口**：本轮不涉及 UI，未验证 `recon.card` 在三虎自动链或页面上的呈现（跳过／待输入两种返回的播报口径）。
- **十三项字段仍需模型填**：程序只把来源、分级、预算与机检做出来（`state='sources_ready'`），字段值要由 SKILL/模型据卡填写后再过 `evidence()`；本轮没有把「填字段」也做成工具，避免在程序里编造字段名（`sd-recon-engine` 的字段清单仍是唯一权威）。
- **`scope_audit_pending` 从空变 1**：新 L2 写服务 `recon_service` 未采用 `service_contract` 四字段结果，按「未审计不能算已迁移」如实登记为待审计项，没有塞进 `exempt_items` 充数。后续迁移是独立一轮。
- **未做**：图片检索（接口只回文本）、平台内部数据（播放量／分账）、定时抓取、评分门槛与聚簇——均与 `sd-recon-engine` 轻量版边界一致，已写进 REQUIREMENTS 非目标。

## D 全量回填

- 命令：`python -B run_selftests.py --all --safe --jobs 4 --gui-jobs 2`（工作目录＝`程序`）
- 结果：**5806 条用例、726.6 秒、0 个文件有红**；实际跳过 1 条（既有登记位，需实机复验 bundled skill）
- 内容树：`ee4df14091950a16cb21670815fd3a263435d0b4`（＝提交 `e44f4c86:程序`）
- 凭据：`D:\repo-meta\漫剧制作助手.git\full-safe-receipts.json`，`last_full_safe_all_round=1691`
- 复算：`run_selftests.full_safe_required(1692, 1691, True, ...)` → **False**（欠账清零）
- 前两次全量：第 1 次 620.7 秒 8 文件红（过期测试资产）、第 2 次 622.4 秒 2 文件红（其中 1 条是本轮我自己引入的 `docs/` 字面路径），均已闭环；日志留在 `程序/.selftmp/`（可弃）

## 提交

| 提交 | 内容 |
| --- | --- |
| `f1a21062` | 本轮内容：`model_pool` 工具接口、`recon_service`、登记表／契约／文档、38 条用例、覆盖率与架构台账 |
| `123227a3` | 全量首跑红收口（一）：`test_skills` 排版比对、`test_version_pin` 替身 |
| `04dec0d9` | 全量首跑红收口（二）：`test_edit_adoption`／`test_critical_chains`／`test_pet_ui`／`test_ui_edges`、OpenCode 弹窗文案、轮次头置 1692 |
| `03918581` | `test_ui_edges` 残留断言（横向滚动条变量） |
| `e44f4c86` | 采风说明段去掉 `docs/` 字面路径（SKILL 作用域门禁） |
| 本报告与状态页 | 回填全量与收尾（见 `git log`） |

未运行：真实 Search／Fetch 请求（缺钥匙）、真实 Tk 窗口、真实用户项目。
