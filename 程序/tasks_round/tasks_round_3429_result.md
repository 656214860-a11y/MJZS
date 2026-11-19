# R3429 — A9-3 包限定身份严格影子扫描与未知拒绝
<!-- round-evidence: {"commit_base": "a076ba21", "credential_hits": 0, "evidence_sha256": "1ecdce1fa90dac49", "exit": 0, "failed": 0, "passed": 35, "round": 3429, "tests": "run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理轮（执行）。来源《六层架构收口与企业级演进任务书》A9、R3424 F、R3411 G/I/J/K、R3416 J、R3419 F。只做本子批，不启动下一轮，不宣称 A9/整本任务书完成。
2. 测试：先负例后正例；冒烟8/8＋隐藏桌面探针通过，定向104/104、0 skip；完整架构改前549项/546通过、改后556项/553通过，同一2 failures＋1 error；新增7项全过，整体未绿。
3. 欠账：新增可运行的包身份分类和严格拒绝入口；仓库默认强制切换、权威层级登记与工具边界仍未完成，不把影子验证说成全仓已强制启用。

## A. 基线、领号、范围
- 基线 `a076ba21c04e8ed06ed8c2fd0ba746b4f9933be3`，含A9-1/A9-2；开工树干净、detached HEAD，新建 `codex/architecture-a9-package-audit`，领取R3429。首次领号子进程读取出现GBK解码异常；核对中央claims确认R3429已属于本树，未重复领号，后续统一PYTHONUTF8/PYTHONIOENCODING。队列show为空，无匹配任务，不冒领他人租约。
- `dev.py scope` 返回27条重叠分支、errors为空。涉及扫描器的12条逐一核对，均无本批限定身份实现；A9-1/A9-2已纳入基线。保留L0/L1/L2/foundation等原owner生产交付，不覆盖其他车道代码。
- 实施模块严格为3个：`tests/architecture/_scan.py`、`tests/architecture/test_layers.py`、`architecture.md`；本结果及evidence是轮次记录。未改 `_layers.py`、环消费者、五个生产环模块、project_status、忽略的基准历史、缺失skill、任何豁免或阈值；不接触master，不推送。
- 本工作树无随附解释器，核实并复用 `D:/漫剧制作助手/运行环境/Python/python.exe`，未复制运行数据。全架构改前运行完毕才改代码，避免基线被污染。

## B. 缩小范围的依据与交付边界
- 完整强制启用需扫描器＋实际消费者＋权威登记 `_layers.py`＋architecture至少4模块。按明确授权缩小为**严格影子扫描/分类/拒绝机制及实际消费者canary**；A9-4负责后续登记及启用。没有借轮次号拆开一个不一致的强制开关。
- `module_scan_files(qualified=True)` 复用现有入口，在六个既定分层包内递归、含初始化文件；`module_name(..., qualified=True)` 返回限定名，`包/__init__.py`规范身份为`包`。扫描到实体不等于它已被权威登记。
- `resolved_module_import_rows(..., qualified=True)` 保留绝对/相对/from-import，`import ui.low`亦包含本地父包`ui`的初始化依赖，保留行号，普通导出符号不伪装成模块，不执行被扫描代码。
- `_module_classifications()`明确输出file/status/registration/layer。精确键优先；非初始化实体只有扫描stem唯一时可绑定既有扁平登记，标`legacy-unique`。这只是已有登记的无歧义绑定，不增加登记、不按目录猜层。包初始化不借父目录或`__init__`同stem推层。
- 原 `LayerDirectionTests.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)` 是实际严格消费入口；未登记源、歧义键、非法层级或扫描外但在本地可定位的导入目标直接AssertionError，不因`None`跳过。已有TOOLS维持显式分类，生产/工具边界另批处理。默认无参数入口仍是旧门禁，严格模式未设为全仓通过条件。
- 实测默认431实体，严格437实体（增加6个初始化文件）。严格分类：精确登记26、旧登记唯一绑定379、显式工具4、未登记22、歧义6；拒绝28。没有把28写成允许清单/阈值；未来解决后应减少，不新增固定数量通过断言。默认扫描、实体列表、静态解析边与环图边逐文件和HEAD旧实现比较431/431一致。
- 注册表保持411层级/5 TOOLS不变，静态18/动态2豁免不变；规则11仍引用同一test_layers文件，生成索引无需重写。薄门面过滤和动态/环入口未迁移。

## C. 精确分类清单（事实与建议分开）
### 六组同stem
| 顶层文件与包实体 | 已核实的顶层责任 | 严格模式处置 / A9-4输入 |
|---|---|---|
| file_index.py / infra/file_index.py | 名称再导出＋静态`__all__` | 顶层登记有效，包实体ambiguous；核验后显式绑定，保留导出兼容 |
| file_index_contract.py / contract/file_index_contract.py | 名称再导出＋静态`__all__` | 同上，不能按contract目录自动当L0 |
| file_naming.py / contract/file_naming.py | 名称再导出＋静态`__all__` | 同上，核验历史导出集 |
| global_library_service.py / domain/global_library_service.py | 名称再导出＋静态`__all__` | 同上，核验共享库服务兼容入口 |
| legacy_migration.py / orchestrator/legacy_migration.py | 事务迁移API再导出＋静态`__all__` | 同上，不删除回滚/迁移API |
| storage_maintenance.py / infra/storage_maintenance.py | `sys.modules`实体别名＋`--cleanup`CLI转发 | 包实体ambiguous；保留别名状态/私有补丁面及CLI责任 |

前五组因现有门面谓词不接纳`__all__`赋值，最后一组因复合main条件未被谓词识别而同时入图。这不是六个相互独立的生产实现；但仅凭stem也不能安全合并，本批不改过滤谓词或门面代码。

### 16个已扫描但未登记包实体
下表每项实际分类均为`unregistered`，不是权威层级批准。职责来自源码说明和导入事实；静态引用缺失不证明死代码、无动态消费者或可删。

| 限定身份 | 已核实职责/引用 | 后续裁定建议（未执行） |
|---|---|---|
| domain.checkpoint_tree | append-only会话checkpoint树；生产源码无名称引用 | 核实未接线原型或运行服务；源码自称L2不足以代替登记 |
| domain.hitl | HITL信封；被ui.ui_hitl引用 | 按信封职责及消费者核定层级；不能当孤立工具 |
| ui.edit_habits_dialog | 修改习惯弹窗，调用orchestrator.edit_habits；无名称引用 | 核实菜单/动态接线后裁定UI归属 |
| ui.project_settings_dialog | 无人值守设置确认弹窗；无名称引用 | 核实设置入口后裁定UI归属 |
| ui.ui_asset_card | Tk资产悬浮卡；无名称引用 | 核实渲染消费者/未接线状态 |
| ui.ui_branch_tree | Tk会话分支树；无名称引用 | 同上 |
| ui.ui_citation | 引用溯源文本标记；无名称引用 | 核实消息渲染接线 |
| ui.ui_code_block | Tk代码块及复制/应用；无名称引用 | 核实渲染消费者 |
| ui.ui_diff | Tk差异视图；无名称引用 | 核实对比入口 |
| ui.ui_hitl | Tk HITL卡片，依赖domain.hitl；自身无名称引用 | 核实审批入口，连同信封一起裁定 |
| ui.ui_media | 缩略图/Lightbox；无名称引用 | 核实媒体渲染接线 |
| ui.ui_media_player | 音视频卡片/播放器入口；无名称引用 | 核实媒体启动责任 |
| ui.ui_multimodal | 多模态参考上传、引用domain消息类型；无名称引用 | 不仅看ui目录；核实UI与领域职责边界 |
| ui.ui_param_panel | Tk参数面板；无名称引用 | 核实配置/渲染消费者 |
| ui.ui_part_renderers | 消息part分派，被ui/desktop_idea_bubbles.py引用 | 已有生产消费者，优先核定UI登记及接线 |
| ui.ui_task_progress | Tk长任务进度卡；无名称引用 | 核实后台任务接线与生命周期 |

六个初始化实体 `contract`、`infra`、`domain`、`orchestrator`、`ui`、`agent` 同为unregistered；当前为文档串/空文件，仍是可导入实体，新增初始化依赖不能继续不可见。不因目前无import就给整包层级豁免。

## D. 负例→实现→正例
- 改前在临时包树直接调用实际 `LayerDirectionTests` 守卫，3测试/3 failures/0 errors（0.021秒）：跨包同stem `contract.shared -> ui.shared`、初始化`contract/__init__.py -> ui.shared`、已扫描未登记模块均漏报。关键错误均为 `AssertionError: AssertionError not raised`；测试runner摘要确认失败，外层探针打印后进程exit0不代表负例通过。
- 永久新增7个`PackageIdentityCanaryTests`方法，实际调用严格消费者而非只测辅助函数：限定名向上拒绝/向下通过、初始化与嵌套相对导入、未知源和未知初始化拒绝、歧义旧键拒绝后精确登记通过、本地扫描外目标拒绝、直接点式import的父包初始化依赖、唯一旧键/外部符号正例及非法层级拒绝。
- A9-1三方法、A9-2四方法保留原断言；坏源内写raise确保源码只被AST扫描。无skip、无新豁免、无测试模块替换。
- 真实仓库严格消费者实测抛 `Unclassified local modules`，包含上述28精确身份；不把当前仓库严格模式失败包装成默认门禁绿色。

## E. 验证与完整架构对照
- 改前 `python -B smoke_test.py --architecture`：549项，546通过，2 failures＋1 error，300.207秒，exit1。
- 首次精确定向 `run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map`：34/34，exit0（随后补1个直接点式import父包初始化测试，纳入最终回归）。
- `smoke_test.py --affected test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map test_branch_coverage_entity test_selftests`：实际7文件104/104、31.0秒、0 skip、exit0；默认冒烟8/8，加隐藏桌面探针与定向门禁10/10。Tk用例由runner迁到隐藏桌面。改动函数的非架构测试消费者按AST检索未新增，完整架构覆盖其余消费者；额外保留branch_coverage_entity/selftests定位与发现器回归。
- 标准evidence精确定向：`run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map` 35/35、exit0；凭据扫描0命中。这次重复仅为标准提交生成机器证据，不重复全量。
- 改后 `python -B smoke_test.py --architecture`：556项、553通过、2 failures＋1 error，264.758秒，exit1。自动比较改前后FAIL/ERROR完整测试ID集合相等（3项），7个新增canary全部ok。状态连续性断言此时为3409 != 3430；其余两个失败的缺失资产与改前一致，无新增失败。未重复全量或修改失败断言。
- 已有失败集合：`test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（缺维护记录/基准历史.json）；`test_round_baselines.RoundBaselineTests.test_round_number_continuous`（改前N3409/M3424）；`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references`（缺screenplay-gate-engine.md）。不改这些权威/私有/忽略资产来消红。
- 安全全量未运行：本批未改层级表条目、生产逻辑、启动/Tk/删除语义；功能分支不触发master累计。`dev.py debt`真实凭据：上次绿R3293，最新R3424，源码轮次23/线8，主干False、后台触发False；最近后台全量HEAD0e3fc76退出1，4历史失败文件test_shared_adapter_infrastructure/test_ui_edges_guards/test_pet_ui/test_perf_baseline。未更改receipts，合入前由主干按AGENTS §5重新判定。

## F. 提交与后续输入
- 三模块、本结果、evidence/R3429.json作为唯一提交白名单。完整架构未绿，使用标准`dev.py commit`保存R3429-FAIL检查点，不标[TASK_COMPLETE]。入口对FAIL标题不能自动匹配轮次的既有问题沿R3424处置：先显式运行原round_evidence.py，再由原stamp_result写机器头，最后通过dev.py commit提交，不改提交脚本、不跳过检查。
- 提交前`git diff --check`通过；暂存清单只含上述5文件，无受忽略运行数据。标准证据35/35、凭据零命中；最终补充验证统计后再次调用原credential_scan检查暂存新增行。提交后以`git status --short`核验干净树，不做额外轮次。
- 提交后哈希可由 `git log -1 --format=%H -- 程序/tasks_round/evidence/R3429.json` 唯一定位，最终交接给完整哈希，避免自引用。状态页N3409，结果M3429，N=M+1不满足；本分支无权修改project_status，主干合入轮按实际最新结果更新（本结果对应3430）。
- A9-4：先裁定上表16项的运行/原型/工具身份与六初始化归属，再按≤3模块安排权威登记与门面alias迁移。不要在当前28拒绝项上加allowlist；精确登记后严格入口可能继续暴露真实越层，须修复/原owner等价交付后再切默认。旧豁免限定身份迁移需保持键集合语义，不新增宽泛豁免。必要时拆更多独立批次，不在本轮启动。
- H03/H09动态注册：继续核验ui_plugin_registry/stage_handler_registry的调用者、常量目标与未知键，变量动态目标闭包另批，不以本批静态身份验收代替。
- TOOLS：codex_tasks/codex_paste/console_submit/batch_frames_tool的实际生产消费者、ASR独立进程闭包/分发边界仍待裁定；现有4个扫描工具和5个登记工具口径不变。
- 五模块环：api_endpoints/diagnostic_capture/model_metering/model_pool/request_ledger由L1 owner提供拆环证据后再迁环扫描；本轮未改环图消费者或五个生产模块。三项历史架构失败继续由主干状态/交付/A14 owner处理。
