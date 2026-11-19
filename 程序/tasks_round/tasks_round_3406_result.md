# R3406 结果 — A2 文档、规则与事实真源冲突诊断
<!-- round-evidence: {"commit_base": "9cd99807", "credential_hits": 0, "evidence_sha256": "391f5acbdd58e2b3", "exit": 0, "failed": 0, "passed": 0, "round": 3406, "tests": "docs-only"} -->

## 三问

1. 类型：AGENTS §3.5 只读诊断。只新增本结果（兼诊断报告）及标准提交证据，不修改生产源码、现行规则、状态页、任务书或其他车道文件。
2. 验证：定向 4 文件、19 用例、0 红、0 skip；默认冒烟、全架构和全量本轮未运行。三种基线的历史/现时边界见 §6，不能把定向绿色称为全部通过。
3. 欠账：没有修复生产欠账；已把规则漂移、守卫盲区及资产缺口转为可定位清单。A2 诊断完成不表示整份任务书完成或已合入 master。

## 1. 基线、方法及所有权

日期：2026-11-18。开工 HEAD `9cd998079666679b4079c7a15e1004630922abb0`，含 R3398 任务书、R3402 A0、R3405 A1；master `3a97b184cedc1fffeea2ac148e9507e4341fe429`。当前树最初 detached HEAD，已建立 `codex/architecture-a2-audit` 后领号 R3406；中央 round-claims 登记工作树 b95a 与此分支，未覆盖他人轮次。领号命令有 GBK 子线程解码警告，但已返回轮次并核对登记；后续工具设 PYTHONUTF8=1。

当前 HEAD 与 master 的生产 .py 差集为空；本报告只对上述快照成立。已读 A0 报告与 A1 结果，不沿用其旧车道状态；中央 lanes/queue/receipts 仅只读检查，不改其他任务租约。队列未认领无关项目。

| 车道 | master 左独有 / 分支右独有提交 | 本轮处置 |
|---|---|---|
| codex/l0-constitution | 0 / 1 | 相比 A1 的 0/0 已继续演进；不视为所有权释放 |
| codex/l1-enterprise | 3 / 2 | 在途，只读 |
| codex/l2-maturity-taskbook | 3 / 2 | 在途，只读；术语核查使用分支文件，未当成主干规则 |
| codex/foundation-hardening | 16 / 19 | 在途，不抢改基础契约 |
| codex/foundation-api-disk | 45 / 17 | 在途，不抢改 HTTP 边界 |

`dev.py scope 程序/tasks_round/tasks_round_3406_result.md`：另 88 个活跃分支无重叠。这里“活跃”是 scope 的工作树分支口径，不是确认 88 条车道都在运行。未执行主树 sync、提交或合并，未复制其未跟踪/忽略资产。

核查方式：读取权威文档相关节、13 份阶段 REQ/DES；静态定位实现与守卫；对阶段契约、版本分类、冒烟计数和欠账函数做只读探针；Markdown 链接检查后逐项判别示例与真实链接。没有运行产品 UI、外部模型、收费 API、ASR 下载或用户数据迁移。

## 2. 信息类别与裁决原则

| 类别 | 来源 | 使用边界 |
|---|---|---|
| 现行规则 | AGENTS §2/§5/§8、runbook 相关节、architecture §3、阶段 REQ/DES | 规定目标和触发条件；冲突须记录，不能以实现偏离自动废除规则 |
| 实现事实 | pet_bus、stage_layout、artifact_schema、各入口及测试执行器 | 说明绑定提交实际行为；不是授权扩大实施范围 |
| 机器登记/守卫 | 规则守卫基线 JSON、_layers、架构统一基数、测试代码 | 判定覆盖边界；通过只能证明已建模条件 |
| 生成视图 | 维护记录/规则守卫对照.md 首行明确生成；阶段目录 README 由 stage_layout 生成 | 对照表由 scripts/rule_guard_map.py --write 刷新，不手改；stage_layout.py:329 的 README 为“只补不改”，旧项目副本不是最新真源 |
| 历史证据 | project_status 历史轮次、tasks_round/归档、A0/A1、基准历史、旧全量凭据 | 保留当时提交与口径，不把历史 8/8、旧扫描计数改写成今天的结论 |
| 当前状态摘要 | project_status 当前轮次头与检查点 | 应由 master 合入轮接续；正文夹有历史叙述，不能每句都当成当前实现 |

建议权威是后续 A4/A9/A14 的裁决输入，不是本轮修改规则的决定。特别是需求与实现不一致时，仍按 AGENTS §2.7 走需求/设计裁决。

## 3. 冲突及歧义矩阵

路径均相对 `程序/`。P1 表示可能误导合入/实现边界，P2 表示文档与可追溯性风险。每项列双方来源、实现证据、建议权威与受影响守卫。

| ID / 类别 | 双方来源 | 实现证据与现时结论 | 建议权威 / 后续归属 | 受影响守卫 |
|---|---|---|---|---|
| C01 P2 阶段数量漂移 | AGENTS §1/§2.2 的 13 阶段；project_status.md:33–34 的 12 阶段 | contract/pet_bus.py:19、stage_layout.py:36 均 13 项，validate_stage_contract() 返回 True；状态摘要滞后，不能解释成两套合法阶段 | 阶段顺序以 pet_bus.STAGES；目录以 stage_layout 对齐；A14 改当前摘要，保留历史轮次原数 | test_agents_md.py:111 只检查 AGENTS/PROJECT_MAP/architecture，未含状态页；阶段契约守卫 |
| C02 P2 SKILL 扫描范围漂移 | architecture.md:116 写 01—12；AGENTS §2.2 与 skill_registry 模块说明写 01—13 | orchestrator/skill_registry.py:494–503 按 stage_from_path 识别目录，STAGES 含 delivery；其 :267 注释也残留 01—12；test_skill_reference_injection.py:150 明列 13质检交付 | pet_bus + stage_from_path/注册器为实现依据；A14 同步说明，生产注释留给授权执行轮 | test_agents_md 三文档数字匹配不一定捕获范围写法；test_skill_reference_injection、SKILL 注册测试 |
| C03 P1 测试触发歧义 | AGENTS §5“只读诊断默认不跑测试”对表格“每轮 smoke”；§2.5/§7 的领号新报告对 §7“只读诊断保留既有编号” | runbook §15 允许诊断结果与管理元数据例外；round_claim/commit-msg 仍按新结果核验归属。本轮用户明确要求领独立轮次，已 R3406；选择证据相关定向，不扩大全量 | AGENTS §5 为触发权威，按轮次类型明确例外；领号按用户授权及 §2.5，A9/A14 消除措辞冲突 | test_agents_md、test_round_baselines、round_claim、commit-msg；现有文字守卫未证明所有触发规则互斥一致 |
| C04 P2 冒烟计数口径 | AGENTS 规则29 与 测试分层基线.json:217 为 8/8；A0 实跑 9/9 | smoke_test.py:193 ROUND_CHECKS[10] 为 8 条，:740 后额外执行隐藏桌面 probe，合计 9。不是已证实增加第九条业务检查，也不应改历史 8/8 | 分别记录业务检查8、探针1、执行总数9；阈值键含义由 round_gate/执行器裁定后再同步 A14 | smoke_test、test_round_baselines、round_gate；不能机械把 smoke_checks_expected 从8改9 |
| C05 P1 全量/架构数字混用 | AGENTS 规则29 的当轮真实结果；测试分层基线 JSON 与 receipts 的 architecture 快照 466 条/132单元；A0 532 条且3红 | 本轮只跑19条。common-dir 最新真实全量记录 R3293/tree b9a06070…；当前 master 源码轮22，full_safe_required=True。缓存字段不证明本树绿色 | 当次执行终态＋受测内容树＋真实 full-safe-receipts；A16/合入轮闭环全量，不以静态阈值当实测数 | selftest_receipts.full_safe_required/risk_overdue、test_round_baselines、round_gate |
| C06 P1 HTTP 入口职责歧义 | AGENTS §2.3 规则42 指 http_client.request_json；runbook §13 末段及 test_outbound_http_authority.py:1 指 open_https | infra/http_client.py:70 实际注入 platform_tools.RequestsJsonOpener；platform_tools.py:493 保留 open_https，:652 后是 requests 传输。两套守卫本轮均通过；这不是证实存在两套违规网络栈，而是“业务传输封装”与“底层建连”混称唯一入口 | A4 澄清 L1 请求门面与底层适配边界；A9 同步规则及守卫说明，先协调 foundation/API 车道；不强行把 JSON 调用全部改成 open_https | test_http_boundary（白名单含 http_client/存量）与 test_outbound_http_authority（底层只许 platform_tools），两者约束层次不同 |
| C07 P2 版本适用范围歧义 | AGENTS §2.2“正式 JSON / 新写 schema_version”；docs/stages/S03_初步分镜.md:96 DES-S03-52 明言分镜 JSON 未登记、不加 schema_version | contract/artifact_schema.py:25–44 仅9类，未含 storyboard；orchestrator/storyboard_direct_api.py:189–221 发布分镜。已登记 desktop_queue 的旧 version=1 分类 legacy，新 schema_version=1 分类 current；不能把旧 version 全局替换 | artifact_schema.REGISTRY/各阶段已批准契约裁定覆盖范围；A3 列未登记产物及消费者，A4 决定扩登记；A14 写明“已登记正式产物”与待迁移范围 | tests/test_artifact_schema.py；schema 写入/迁移守卫需按登记域覆盖；test_stage_doc 相关需求锚点不能替代数据兼容验证 |
| C08 P2 权威表损坏 | architecture.md:104 正确 artifact_schema；同文件:270 字节为 U+0007 + rtifact_schema | contract/artifact_schema.py 存在；:270 无法作为可靠模块名检索。这是可复现的控制字符损坏，不是新模块 | A14 修现行表文本，登记源仍 artifact_schema；不改历史证据 | test_agents_md 的权威表检查不覆盖此处所有字节；文档预算/链接检查不会识别控制字符 |
| C09 P1 依赖政策漂移 | project_status.md:33 及 PROJECT_MAP.md:27“零第三方依赖”；AGENTS §1 白名单依赖 | requirements.txt:3–8 锁定 requests、urllib3、certifi、charset-normalizer、idna、Pillow；platform_tools.py:557/652 实际 import requests。独立 ASR venv 隔离也不能推出主运行时零依赖 | requirements锁定＋依赖白名单为现行政策；A14 更新当前产品摘要，历史零依赖结论不改；A8/A15 复核打包 | test_dependency_whitelist、分发/运行时闭包守卫 |
| C10 P1 历史资产与干净检出守卫冲突 | runbook §10 称基准历史仅历史参考；test_agents_md.py:191 无条件读该文件；A0 已记录失败 | 本树 维护记录/基准历史.json 不存在且不在 Git tree；缺失会阻断“当前规则”检查，不代表性能回归。未读取或复制主树私有副本 | A14/A15 决定使用受版本管理的无敏感 fixture 或明确资产交付契约，保留性能阈值守卫，不跳过制造绿 | test_performance_history_is_declared_as_historical_only、auto_full_safe/分发干净检出 |
| C11 P1 SKILL 引用缺交付 | test_skill_reference_injection.py:14/19 要求 screenplay-gate-engine.md；本/master Git tree 无文件 | 当前 skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md 不存在；A0 指向在途 skill 交付，本轮仅复核缺口，没有重判其内容 | A14/A15 协调 skill 车道接收已审核资产，禁止复制忽略文件冒充修复 | test_script_stages_name_only_their_approved_00_references、分发与引用注入测试 |
| C12 P2 入口/层级规则与机器覆盖不等价 | AGENTS 规则11“反向 import 一律禁止”；architecture §3/统一基数中的存量迁移口径及 A1 异常边 | R3405 绑定同一生产树，指出包内未登记、子模块解析、同名stem覆盖与 TOOLS 注释不符；不能把门禁过等同于全部依赖合规 | architecture §3 定目标；_layers/基数只记录过渡事实，不提升为新反向依赖许可；A4/A9 设计守卫迁移，A3 查真实接线 | test_layers、test_layer_relations、test_no_circular_import、_scan；本轮未重复 A1 全图 |

## 4. 失效链接与误报排除

对五份现行入口文档和 13 份 docs/stages Markdown（共18文件）检查本地 Markdown 路径，命中9项；人工排除 S01:72 的行内代码示例 `[名称](链接)`，真实失效8项。未检验 HTTP 可用性、标题锚点及全部反引号路径；不称“所有链接已通过”。

| 双方来源（失效引用 → 已跟踪目标） | 实现/验证证据 | 建议权威与受影响守卫 |
|---|---|---|
| architecture.md:140 的 tasks_round_1441/1442_result.md → tasks_round/归档/2026-10/ 同名文件 | git ls-files 精确定位；原相对路径不存在 | A14 只更新链接，不重写历史内容；test_agent_doc_budget.py:49 仅遍历三份入口预算文件，不覆盖 architecture |
| project_status.md:59/61 的 R1693/R1691 → tasks_round/归档/2026-10/ 同名文件 | 同上 | master 状态维护/A14；历史测试数保持原样；现有链接守卫未覆盖状态页 |
| project_status.md:94/96 的 R1041/R1376/R1381 → tasks_round/归档/2026-10/ 同名文件 | 同上 | 同上 |
| project_status.md:89 的 ../说明/账户会员云端立项前清单.md → 说明/账户会员云端立项前清单.md | Git 跟踪目标位于 程序/说明；引用多退一级 | A14/master 修相对链接；文档链接守卫扩面时须识别行内代码和示例 |

历史 `.agent-handoff` 反引号引用另需按根 AGENTS 的归档声明追踪；本轮未把所有旧文本引用一律标为失效超链接。生成视图不得靠手工修表掩盖基线源变化。

## 5. L4 术语与阶段入口核查

架构 L4＝表现层，依据 architecture §3 与本任务书 §4；不是“企业级成熟度第4级”。只读查看 `codex/l2-maturity-taskbook:程序/tasks_round/L2企业级成熟度提升任务书.md`，其开头已明确使用 M1—M5，避免与架构 L2/L3 混淆。故这是已作区分的在途文档，不能误报为当前 L4 分层缺陷，也不能以其 M4 验收替代依赖门禁。后续报告统一写“架构 L4”及“成熟度 M4（旧称成熟度 L4）”；没有足够证据时不批量改历史术语。

入口职责抽查：AGENTS §2.2/规则17、PROJECT_MAP.md:18 都指向 `orchestrator/stage_handler_registry.py:145 start()`；正式成果发布在 `stage_execution_service` 的 publish_*，完成由 stage_completion_service 核验，两者与“阶段开始”不是同一职责。阶段 REQ/DES 中的 UI 方法、模型直连适配器不单凭名字判成绕过统一阶段入口；完整“手动/自动/恢复/取消”接线交 A3。A1 对 app/desktop_launcher/desktop 调试入口的区别保持，不将调试入口自动认定正式自检漏洞。

版本核查也区分 schema_version 与模型版本、frontmatter 版本、历史 version：本轮证实新旧键分类兼容，而非所有出现 version 的地方都违规。阶段 README 为生成后只补不改，不能拿旧项目 README 覆盖 REQ/DES 或 pet_bus 真源。

## 6. 验证与三个基线

随附解释器采用 `D:/漫剧制作助手/运行环境/Python/python.exe`（本工作树无运行环境副本），cwd 为本工作树 `程序`；只借用已安装解释器，不复制主工作区资产。

- `run_selftests.py -k test_agent_doc_budget test_rule_guard_map test_http_boundary test_outbound_http_authority`：4文件、19用例、0红、0skip，4.9秒；规则预算/现有链接覆盖/生成映射一致、HTTP两层守卫通过。
- 只读探针：pet_bus 与 stage_layout 均13项，validate_stage_contract=True；ROUND_CHECKS[10] 8条＋隐藏桌面probe；artifact_schema 9登记类型、不含 storyboard，旧version分类legacy、新schema_version分类current。
- 第一版 AST 探针对 stage_layout 元组拼接使用 literal_eval 报 ValueError，属诊断方法限制；改为导入官方契约并调用 validate_stage_contract 后成功，未改实现或测试。
- 默认冒烟本轮未运行：A0历史实测9/9；本轮仅核对8业务检查＋1probe结构，不宣称当前运行绿色。
- 全架构本轮未运行：A0历史532条、2 failure＋1 error；A1定向8条绿、本轮定向19条绿均不代替全架构。两项缺资产在本树复核仍缺；状态页3404而最新结果3406，N≠M+1留 master 接续，不在功能树改状态页。
- 全量本轮未运行：common-dir/full-safe-receipts.json 最新 verified 记录 R3293，tree `b9a0607080796c4b3bc7cdae0f11a605899e4e45`，751.495秒；不是当前树绿凭据。以 master最新已合入轮3403计算，source_rounds_since(3293,3403)=22、risk_overdue=False、full_safe_required=True；与A0的21相比增加一个源码轮，未因本轮文档增加源码欠账。

只读诊断适用验证已完成；生产全量欠账、历史失败及未运行边界保留，禁止修改断言、跳过或补造凭据。

## 7. 验收、交接与提交

[x] 区分现行规则、历史证据与生成视图；覆盖13阶段、触发条件、版本、基线、入口、失效链接、L4术语。

[x] 冲突逐项含双方来源、实现证据、建议权威及守卫；未证实事项标歧义/待审计，不覆盖历史。

[x] A2只读范围与适用定向验证完成；修复交 A4/A9/A14/A15，接线缺口交 A3，最终验收交 A16/A17。

标准提交标题：`R3406: 完成A2文档规则真源冲突诊断`；提交后精确哈希由该唯一轮次 Git 记录及最终回复给出，避免结果文件自引用哈希。提交清单仅本结果和 `tasks_round/evidence/R3406.json`；执行 git diff --check、暂存清单与凭据扫描。未 push、未合入 master、未勾改整份任务书，整任务完成文件留 A17。

A3 接续须从本轮提交创建 project target 的 worktree＋新分支，不在 D:/漫剧制作助手 创建 local 会话。先重查 master/活跃车道，再按任务书 A3 做 L0–L2 到上层消费者、注入及失败路径审计；本报告不是批准抢改在途契约。若创建正确工作树失败，交根任务重试，整体目标仍为任务书全部授权范围验收并合入 master。
