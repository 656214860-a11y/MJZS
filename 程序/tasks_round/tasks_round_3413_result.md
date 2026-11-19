# R3413 — A5 废弃、重复、文件分类与命名审计
<!-- round-evidence: {"commit_base": "25608acf", "credential_hits": 0, "evidence_sha256": "160d0ad204ad444f", "exit": 0, "failed": 0, "passed": 0, "round": 3413, "tests": "docs-only"} -->

## 三问
1. 类型：AGENTS §3.5 只读诊断，仅新增本报告与标准提交证据；不改生产代码、规则、状态页、任务书或其他车道数据，不删除任何候选。
2. 验证：兼容台账 3/3、分发构建器 13/13，均 exit 0、0 skip。默认冒烟、完整架构、完整安全全量未运行，不能宣称三个基线全绿，详见 M。
3. 欠账：没有修复生产欠账；完成 A5 分类及退役条件交付。A5 交付不代表整个六层架构任务完成，不创建下一阶段。

## A. 基线、授权与方法
日期 2026-11-18。工作树 `C:/Users/LAIBIAO/.codex/worktrees/1700/漫剧制作助手`；从 detached 绑定用户预建 `codex/architecture-a5-audit`；受审 HEAD `25608acf`（A3 R3409）。未向主工作树写入源码或交付文件。标准领号/测试入口维护共享 Git 元数据属于项目标准流程。

已读取 AGENTS、runbook §12–15、任务书 A5/§8/§9，以及 R3402/A0、R3405/A1、R3406/A2、R3409/A3 相关基线、依赖、兼容与分发证据。中央领号 R3413 的归属已复核为本树/本分支；scope 对报告和证据路径检查，另 91 个活跃分支无重叠。没有另领无关维护队列任务。

只读方法：Git 跟踪文件清单；Python AST import 检查；字符串/注册/子进程/复制脚本入口核查；SHA256 非空 Python 文件完全相同比较；旧死代码映射逐项检查。扫描排除 tasks_round、维护记录，文档和测试引用与生产调用分别解释。不扫描用户项目、私有配置或未知文件内容。完全相同不等于语义重复；无 import 不等于无消费者。

## B. master 最新事实与所有权
审计时 master 为 `0e3fc763`（R3408 合入 R3404 K9）；`309cfa3d` 已登记 L0P 层值 0.5，`foundation/` 为 K11 待建包，明确不得命名 `platform/` 遮蔽标准库。L0 只能依赖其允许范围，不能反向依赖 L0P；L0P 可依赖 L0，L1 以上可依赖 L0P。K9 纯度基线 136 是历史违规棘轮，不是清理授权。本树未合入 K9，报告不能冒称测试覆盖其实现；A4 先吸收主干事实再设计。

master 左独有/车道右独有：l0-constitution 0/0，l1-enterprise 5/3，l2-maturity-taskbook 5/3；foundation-hardening 18/19、api-disk 47/17、asset-disk 47/17、image-disk 47/18。其余 foundation：config-health-cas 20/3、config-project-profile 20/4、config-schema 20/2、config-write-safety 20/1、context-policy 47/1、context-preflight 47/1、diagnostic-fixture 49/1、dpi 47/1、ffmpeg-runtime 49/1、http-tests 49/1、import-contracts 20/2、l0-docs 20/1、l0-stage-extension 18/1、ui-regressions 49/1；rebase-preview 47/15 仅是分支观察，不认作正式交付。

共享 lanes.json 仍登记 foundation 子车道；名称、最后活动时间、ahead=0 都不代表所有权释放。L0/L1/L2/foundation 的契约、平台、网络、磁盘、配置和回归工作继续由原车道负责。本轮不搬其文件、不改其基数或规则。A4/A13/A15 在实施时重查当次分支及 scope，以上是时间点快照。

## C. 既有死代码报告复核
输入为 `tasks_round/任务完成/死代码与无效功能·任务完成.md` 与 `维护记录/代码腐烂审计/deadcode_20261116/` 的既有分类/映射；不重新执行其中修改脚本。

- `facade_map.json` 的 entities 共 123 项：当前顶层旧文件存在数 0、替代包实体缺失数 0。结论为既有退役已落地，不再次登记为待删，也不恢复旧壳。映射完整保存在该既有 JSON。
- 旧报告中的 voice_engine、voice_mcp_server、optimizer_mcp_bridge、app_shortcut、engine_probe、blender_previs_template 仍按下表保留；旧报告 E1b 没有可靠清单、E3 无廉价自动判据，不能转写为已排除全部死方法或死回调。
- 当前 Git 跟踪非空 `.py`（排除上述审计/轮次目录）按字节 SHA256 比较，完全重复组为 0。空包初始化文件不计。此结果不证明不存在近似实现、重复业务职责或运行时无效功能。
- A1 的 6 组同 stem 文件是门面与实体，不是 6 组重复实现。当前 AST 扁平 import 指向这 6 个旧名均为 0，但包路径、文本及外部入口仍需分别处理。

## D. 候选裁决、消费者与替代路径
以下路径相对 `程序/`。“迁移后删除”是未来条件性建议，当前一律保留；“证据不足”禁止删除。没有获准立即删除的源码、文档、运行数据项。

| ID / 分类 | 候选及消费者证据 | 替代入口、责任与退役门槛 |
|---|---|---|
| D01 证据不足 | file_index.py；本树扁平 import=0；实体由 domain/audio_import_service.py:44 等消费；门面显式 re-export | → infra/file_index.py。L1/文件索引所有者确认外部裸模块 API、补丁路径、插件消费者后再讨论删除；包实体不能删 |
| D02 证据不足 | file_index_contract.py；扁平 import=0；infra/file_index.py:25、tests/test_file_index.py:19 使用契约 | → contract/file_index_contract.py。L0/索引契约负责公开符号、类型及历史脚本兼容；不能仅凭零 import 退役 |
| D03 证据不足 | file_naming.py；扁平 import=0；contract/script_contract.py:400/407/410 消费命名能力 | → contract/file_naming.py。L0 负责旧调用路径；必须核对持久化文件名和 Windows 大小写行为，不批量改用户文件名 |
| D04 证据不足 | global_library_service.py；扁平 import=0；tests/test_file_origin_provenance.py:16/201 使用实体；只转发4个符号 | → domain/global_library_service.py。文件落 domain 不自动等于 L2，A1 已指出登记 L1；共享库/来源追溯所有者确认外部兼容后再裁决 |
| D05 证据不足 | legacy_migration.py；扁平 import=0；scripts/migrate_legacy_layout.py:17/34/35 为显式 CLI 消费者 | → orchestrator/legacy_migration.py。L3/旧布局迁移负责 apply/rollback 及旧脚本 API；数据备份、引用重写、失败恢复必须单独验收 |
| D06 迁移后删除（条件未满足） | storage_maintenance.py:5/11/13–14 明确旧 CLI、sys.modules 别名和补丁面；零扁平 import 不能覆盖命令行用户 | → infra/storage_maintenance.py 的 main/recycle_paths。L1/存储及分发维护者先提供等价 CLI、更新说明与调用方、确认外部弃用窗口，再以独立提交删除旧入口；本轮不删除 |
| D07 保留 | previs_progress.py → ui.previs_progress；orchestrator/previs_automation.py:158–161 复制旧入口到批次目录并生成 import 指令 | 维持该脚本路径；预演/L3/宿主 Blender 集成负责复制后的 sys.path 与包可达性。任何迁移须在真实隔离宿主场景验证，当前不把兼容转发当死代码 |
| D08 保留 | orchestrator/legacy_compat.py:10–32，5个 FACADE_MANIFEST 入口；engine、confirm_gates、local_previs、idea_document_paths、pet_ui_support 消费 | 旧项目只读兼容责任归 legacy_compat；2027-03-31 是复审/门禁日期，不能按日期自动删。新写走正式契约，旧数据兼容替代及用户迁移证据尚未具备 |
| D09 保留 | voice_engine/**；domain/offline_asr_client.py:26 以文件路径启动 offline_asr_server.py | 独立 ASR 子进程协议，语音/分发所有者负责；无同等替代入口，不搬入主运行时 import 链，不清模型/venv |
| D10 保留 | agent/voice_mcp_server.py:8 自带 MCP 外部配置入口；agent/prompt_optimizer.py:188 启动 optimizer_mcp_bridge.py | MCP/优化器所有者负责客户端配置及 stdio 协议；保留路径，不因少 import 删除外部进程入口 |
| D11 保留 | app_shortcut 被 infra/app_icon.py:13 消费；engine_probe 被 smoke_test.py:333–334 调用；orchestrator/previs_batch_service.py:42 在宿主指令引用 blender_previs_template.py | 快捷方式、诊断和预演所有者各自负责；无等价替代，需保留 CLI/资源路径。blender 模板也受说明/版本文件校验.json 引用 |
| D12 保留 | batch_frames_tool 被 image_agent_runner.py:96、infra/cloud_assets.py:70、infra/comfy_service.py:133/146 使用；codex_tasks/console_submit/codex_paste 的17处消费者见 A1 H | 归生产运行组件，不按 TOOLS 标签当开发废物。A4 重分类，A15 验分发闭包；现阶段不新造另一套入口 |
| D13 证据不足 | 死方法、UI 回调、未确认来源脚本、近似业务重复；既有 E1b/E3 没有可靠可删集合 | A6 行为观察或所有者确认；任意字符串拼接、插件、外部自动化不在静态穷举保证内，不能推断无消费者 |
| D14 可删除 | 本轮满足任务书 §8 全部条件的具体候选为 0 | 不用“清理成果”压力制造删项。生成缓存仅是分类，不形成批量删除授权 |

## E. 动态注册、CLI、分发与外部责任
`infra/ui_plugin_registry.py:19–24` 通过 UI_PLUGINS 白名单做变量 import；`stage_handler_registry.start()` 为阶段入口。A1 G 已列注册图，A3 已列服务注入/发布链。注册目标、回调及配置字符串均需迁移，不能只改 import。

分发清单 `distribution_manifest.md` 必须保留表明确包括生产包、voice_engine、batch_frames_tool、内置模板、codex_paste.ps1 与启动器；排除 tests/scripts/tasks_round/维护记录 是“分发副本排除”，不是“源仓可删除”。`scripts/distribution_build.py:65/113–119` 已解析清单、建立 keep/excluded/undecided 三类；清单开头“供未来构建工具消费”是说明滞后，不表示构建器不存在，交 A14 同步。本轮不构建产品副本、不运行真实模型或 ASR 下载。

外部责任无法由仓内零引用证明：裸模块 API、MCP 配置、宿主脚本复制路径、用户 CLI、旧项目路径、打包资源定位分别由上表所有者签收。未知外部消费者按证据不足保留，不设虚构的无人使用结论。

## F. 文件分类方案
| 类别 | 当前路径/对象 | 处理与权威 |
|---|---|---|
| 生产代码 | contract、infra、domain、orchestrator、ui、agent、顶层入口 | 按 architecture/_layers 的实际职责登记；不能按目录名直接判层级或去留 |
| 生产运行组件 | voice_engine、batch_frames_tool、codex_tasks/console_submit/codex_paste | 保留于分发；独立进程、宿主及平台能力需单独建模 |
| 测试 | tests、smoke_test.py、run_selftests.py | 保留开发验收入口，分发排除不等于删除 |
| 开发工具 | scripts、维护记录/基准脚本 | 开发/构建/迁移工具，显式 CLI 是消费者；历史 codemod 不重跑 |
| 文档与历史证据 | docs、AGENTS、runbook、tasks_round、维护记录/代码腐烂审计 | 权威文档与历史证据分开引用，不按年龄删除；本轮不搬已有报告 |
| 内置分发资源 | assets、skills、workflows、配置及模板 | 保留引用与许可证/校验链；data 中内置项与可变数据须逐项识别 |
| 生成产物 | __pycache__、*.pyc、.selftmp、构建输出 | 仅在拥有范围明确、无活动消费者、可再生验证完成后由既有维护入口处理；本轮不清理 |
| 运行数据 | 用户项目、data 下模型/配置/索引、logs、私有凭据 | 不与源码重复混判；不清用户项目、凭据、活跃工作树或未知来源文件，不记录其内容 |

## G. 路径映射与命名约束
D01–D06 已逐项给出旧→实体映射；这是兼容入口映射，不是本轮移动计划。D07 保持 previs_progress.py→ui/previs_progress.py 的现有别名和复制协议；D08 保持 orchestrator/legacy_compat.py；D09–D12 保持分发与进程路径。历史 123 项完整旧→新映射复用 facade_map.json，不复制一份产生双真源。

A4 可采用 `foundation/` 作为 L0P 命名，实际落地由 K11/原车道负责。不得擅自将 domain/global_library_service 仅为“目录像L2”而改名；不得把六组同 stem 视为必须消除的命名冲突。重命名应先核对导入、注册字符串、相对文档链接、持久化路径、资源定位、打包、Windows 大小写；明确新旧路径桥接期后再落地。

## H. 删除门槛与回滚
每个未来删除项必须逐条满足任务书 §8：静态调用、动态注册/字符串、配置/CLI/插件/分发、旧项目兼容、当前消费者迁移、相关测试、独立可回滚提交。D01–D05 缺外部兼容证明，D06 缺 CLI/补丁面迁移验证，均不得直接进入删除批次。D07–D12 已有正向存活证据，应保留。

代码/门面退役每批单独提交，失败用 git revert 恢复旧文件及注册/测试/文档映射；不能只恢复壳而留下新旧混用。D05 数据迁移另备份、版本检查和恢复验证，代码 revert 不代表数据回滚。用户可见删除继续使用 storage_maintenance.recycle_paths；缓存也必须核对可再生和拥有范围。禁止清活跃锁、重置他树、全局 stash、替换共享运行环境。本报告自身回滚为 revert 本轮提交，不触及生产或用户数据。

## I. 风险与未验证边界
P1：误删动态/外部入口、把运行组件从分发剔除、删除旧项目读取兼容；P2：工具标签、包目录和真实职责不一致，清单说明滞后；P3：纯命名外观。外部实际使用率、任意反射拼接、完整宿主/发布副本行为未验证。静态无重复不是语义去重证明，已有定向绿色也不覆盖全部产品场景。

## J. 交 A4 的整改路线
1. 使用最新 master K9/L0P 与 A1–A3，确定平台基座、装配例外和运行组件职责；不抢原车道实现。
2. A13（依赖 A5/A12）只接 D06 的条件性退役，先完成兼容迁移与签收；D01–D05 在证据不足状态保留，不能将本报告当删除批准单。
3. A14 对齐分发清单的现行构建事实、命名及历史记录链接；A15 在隔离副本验证启动/ASR/批处理/MCP/CLI 资源闭包。
4. 所有实施前重新 scope 和消费者核查，避免把本时间点快照当冻结清单。A4 负责后续调度，本会话不创建下一阶段。

## K. 后续测试迁移计划
门面退役覆盖公开符号、sys.modules 身份、mock.patch 旧路径、CLI 等价与退出码；旧布局覆盖 dry-run/apply/失败恢复/rollback 和引用保持；宿主复制覆盖独立目录 import；分发在临时副本核对 keep/excluded/undecided 与运行依赖。用假供应商和隔离项目，不访问真实收费 API 或用户项目。新测试属于后续实施，本轮没有改断言、删除测试或补造测试通过记录。

## L. A5 验收与提交范围
- [x] 候选分类为保留、迁移后删除、可删除、证据不足，并给出消费者、替代入口、动态/CLI/分发/外部兼容责任。
- [x] 代码、测试、工具、文档、生成物、运行数据分类和路径映射已给出；删除/重命名条件与回滚已给出。
- [x] 明确不清用户项目、凭据、活跃工作树、未知来源文件，不按年龄自动删除。

仅提交本结果及 `tasks_round/evidence/R3413.json`；标准入口 `scripts/dev.py commit -m "R3413: A5废弃重复与文件分类命名审计"`。最终提交哈希以该标题的 Git 记录为准，避免在提交内部自引用未来哈希；对外交接附实际哈希。不写 master 专属 project_status；N=M+1 留合入轮同步。不输出全任务完成文件，不宣称整体完成。

## M. 验证证据与局限
环境：本树程序目录、PYTHONUTF8=1，使用已核实随附解释器 `D:/漫剧制作助手/运行环境/Python/python.exe`，未复制/替换运行环境。
- `run_selftests.py -k legacy_facade_manifest`：1 文件、3 用例、0 红、0 skip、exit 0。
- `run_selftests.py -k distribution_build`：1 文件、13 用例、0 红、0 skip、exit 0；临时目录测试，不执行正式分发。
- `dev.py scope`：91 个其他活跃分支无交集；领号 JSON 复核归属正确。
- 只读 AST/哈希探针正常结束；首次 git ls-files 普通输出遇到中文路径引号，改用 `-z` 后成功，属探针问题，未改源码。领号输出曾有子进程 GBK 解码异常，但中央 R3413 已成功登记；后续统一 UTF-8，不重复领号。
- 默认冒烟本轮未运行；历史 A0 为 9/9（8业务+probe），不作当前绿色。
- 完整架构本轮未运行；历史 A0 532 条、2 failure+1 error（资产/状态接续），本轮不宣称消除。当前改前/改后全架构比较不适用，只读报告不改变源码。
- 完整安全全量未运行；共享 receipts 最新 verified 仍为 R3293/tree b9a0607080796c4b3bc7cdae0f11a605899e4e45，751.495 秒，非本树绿色。A2 已确认全量欠账，本轮没有源码变更，不声称减少或刷新该欠账。
- 提交前执行 git diff --check、检查暂存清单与标准凭据扫描；标准证据记录 docs-only，不把它冒充以上行为测试。
