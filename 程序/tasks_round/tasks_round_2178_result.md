# R2178 全项目模块加深候选诊断（只读诊断）

本轮属于 §3.3 结构治理轮·只读诊断（写入边界按 §3.5）：未改任何 `.py`，未改用户数据，仅新增本结果文件。
测试：按 §5 只读诊断默认不跑测试；本轮未运行测试。下文行号、计数来自本轮在本树上的静态读取与 AST 统计，不是测试结果。
欠账：本轮不改源码，全量欠账计数不变；状态页只能在 master 更新，本分支不动。

基线：`claude/relaxed-chatelet-951d14` @ 5d7c581e（R2173）。日期：2026-11-01。
来源：用户 2026-11-01 指令「全面扫描项目架构，输出可优化清单」（只读诊断）与「自动完成 01–11 项的优化」（按本报告 J 节逐条执行）。临时 HTML 版报告在系统临时目录，不入库；本文件是入库的唯一来源。

## A 结论

- 11 个加深候选（01–11），按收益排序：01 工作流设置 Tk 下移 > 02 越层台账收口 > 05 密钥读取单入口 > 04 模型调用计量 > 08 引擎适配器去重 > 06 无人值守决策 > 03 剧本准备会话 > 11 换页决策 > 09 路径与回收 > 10 发布器注入 > 07 Mixin 共享状态。
- 01 收益最大：`workflow_settings`（L4，1158 行）只有 `show_settings` 一处用 Tk，却因此被钉在 L4，让 6 个 L3 调用方各占一条越层豁免；下移后连带 `qwen_setup`、`qwen_adapter`、`legacy_compat`、`pet_state` 可按真实依赖重登记，层级台账 35→21，动态越层登记 5→3。
- 05 含一处现存缺陷：`cloud_assets.get_key()` 先读环境变量，旧环境变量会盖过用户新保存的密钥。
- 04 含一处口径冲突：`pet_llm` 把 HTTP 500 当可重试，`model_router.failure_policy` 把 500 当「可能已受理、不重试」。两者面向的请求性质不同（对话可重放；媒体提交可能已计费），收口时两种口径都保留并显式命名，不单方裁决。

## B 证据与范围

- 热点：近 300 次提交的改动集中在剧本准备页、模型管理、资产批量、工作流设置与三虎自动化。
- 分层口径：`tests/architecture/_layers.py` 的 `LAYERS`（`ast.walk` 扫全部 import，懒加载也算；常量字符串 `import_module`／`__import__` 由 `dynamic_import_rows` 计入）。
- 豁免口径：`维护记录/架构统一基数.json`「层级」节，当前 `count` 35、`baseline_exempt` 35，35 项原因均为「既存越层，待专项收口」。
- 统计脚本未入库（只读轮不新增 `.py`）。

## C 度量

| 指标 | 当前值 | 来源 |
| --- | --- | --- |
| 层级豁免项 | 35 | `架构统一基数.json`「层级」 |
| 动态越层登记 `KNOWN_DYNAMIC_UPWARD` | 5 | `tests/architecture/test_layers.py` |
| 手拼「工作流任务」 | 23 个模块共 37 处 | `tests/architecture/test_workflow_dir_ratchet.py` |
| Mixin 多写者属性 | Desktop 48／Pet 59／Cloud 15／Panel 5 | `tests/architecture/test_shared_state_ratchet.py` |
| `workflow_settings.py` 行数上限 | 1176（实际 1158） | `tests/architecture/test_module_size_ratchet.py` |
| `stage_execution_service` 内 `'publish_json': save` | 17 处 | 本轮 grep |
| `NoRedirect` 同名实现 | 5 份 | 本轮 grep |

## D 具体耦合点（逐项）

**01 工作流设置**：`workflow_settings.py:8-9` 导入 tkinter／ttk，`:17-20` 导入 `ui_dialogs`／`ui_widgets`／`ui_tokens` 共 13 个 UI 名称，全部只在 `show_settings`（`:1052-1158`）里用；唯一生产调用方是 `desktop.py:831-835` 的 `flow_settings`。解析半部另导入 `qwen_setup`（`:250`）与 `qwen_adapter`（`:749`），二者也只因 Tk／`pet_state` 被钉在 L4。另有顺序约束散落：`writing_api.capture_request`（`:54-67`）按 `validate_selected_skills` → `current` → `freeze_skills` 执行，`desktop_idea_chat.py:548`、`:867-872` 各自重排一遍。

**02 越层台账**：除 01 能清掉的 11 项外——
- 按真实依赖重登记可清 3 项：`ui_plugin_registry`（L4，24 行，只依赖 L0）、`integrations`（L3，只依赖 L1）、`artifact_lineage`（L1，只依赖 L0）。
- Tk 尾巴可清 13 项：`project_settings:61` 的 `ask_confirmation`（5 项）、`cloud_assets:103-107`（3 项）、`asset_prompt_rules:64` 的 `notify`（3 项）、`asset_reference_prompts:98` 的 `prompt_window`（2 项）。
- 余下 8 项（`confirm_gates`／`idea_document_paths` → `legacy_compat`，`engine_probe` → `workflow_engines`，`idea_chat` → `pet_agent`，`native_apps` → `white_model`，`skill_orchestrator` → `skill_tools`，`asset_batch_execution`／`asset_batch_service` → `asset_reference_images`）逐条复核后写具体原因。

**03 剧本准备会话**：状态机放在 Tk Mixin `desktop_idea_chat.py`（1114 行）里；`desktop_idea_deferred.py`（91 行）的 16 ms 轮询、3 次稳定、2 s 超时判定与 Tk `after` 调度写在一起；无 Tk 的 `idea_chat_controller.py`（L3，201 行）只覆盖提交准备与附件。`tests/test_idea_chat.py` 2349 行、125 条，`settle_script_page`（`:726-751`）直接读 `_idea_view_model_cache`、`_idea_page_update_job` 私有字段。

**04 模型调用计量**：`pet_llm.py:423-448` 的 `_attempt` 走 估算 → `authorize_model` → `settle_model`，`writing_api.py:255-278` 复制了一份；诊断目录两处口径不同（`pet_llm.py:421` 用 `self.project`，`writing_api.py:103-109` 用 `project/'logs'`）。`edit_habits.py:258`、`skill_notes.py:153` 直接调 `PoolAdapter`，不计量。`model_router.py:576` 的 `ModelRouter.chat` 计量但无生产调用方。重试口径见 A 节。

**05 密钥读取**：`model_pool.credential()`（`:374-392`）按 DPAPI → `.env` → 环境变量，`:378-379` 注释写明原因；`cloud_assets.get_key()`（`:30-38`）先读环境变量；`tts_api.unified_key()`／`load_key()`（`:106-126`）走 `named_key` → 旧加密设置；`api_endpoints.configured_key()`（`:16-41`）另有 5 个调用方。

**06 无人值守决策**：下一阶段表有两份（`desktop_pet_bridge.py:17-23` 的 `PET_STAGE_POLL`／`UNATTENDED_SWITCH`，`desktop_auto_flows.py:26-32` 的 `UNATTENDED_NEXT`）；剧本结构完成判据有两份（`skill_orchestrator.py:46-65`、`stage_completion_service.py:606-611`）；续跑状态分在 `pet_state.py:16`、`asset_batch_state_service.py:22`、`asset_resume.py:28`。

**07 Mixin 共享状态**：`Desktop`（20 个 Mixin）、`Pet`（6 个）、`Cloud`（4 个）共用一个 `self`；`tests/test_core.py:77-90` 在 `Desktop.__new__` 后手工补 11 个属性。Pet 的多写者属性最多（59）。

**08 引擎适配器**：子进程 `_run` 在 `workflow_engines.py:156-170` 与 `qwen_adapter.py:136-149` 各一份；`NoRedirect` 在 `local_video.py:24`、`model_pool.py:964`、`seedream_api.py:122`、`tts_api.py:513`、`agent/volcengine.py:18` 各一份；`agent/video.py:5` 定义 `VideoAdapter(ABC)`，`agent/wan.py:9` 的 `WanAdapter` 没有继承它。

**09 路径与回收**：「工作流任务」在 23 个模块手拼 37 处，`stage_layout`／`stage_path_service` 至今没有该目录入口；`storyboard_recycle_service.py:88`、`:131` 自建回收目录，`:101` 自行 rename，未走 `storage_maintenance.recycle_paths()`；`<项目>/skill_config.json` 路径在 `stage_model_value.py:13` 与 `skill_panel.py:642` 各拼一次。

**10 发布器注入**：`stage_execution_service.py` 有 19 个 `*_gateway()`，其中 17 处重复写 `'publish_json': save`。近 300 次提交里只改过 2 次，收益低，按最小改动处理。

**11 换页决策**：`page_navigation_controller.py:43-104` 拆成 7 个零散判定函数，`desktop_page_nav.py` 在 `:59/:100/:122/:149/:153/:160/:254` 用 `getattr` 逐个拉状态再传入；决策的整体仍在 Mixin 里。

## E 测试依赖

- 01：7 个边界测试按文件名登记了 `workflow_settings.py`（button、card、file_dialog、notification、module_size、workflow_dir、workflow_settings_json），`test_agents_md.py:144-153` 要求 `workflow_settings.py` 保留字面量 `{'GPT': 'codex', 'Anthropic': 'claude'}`。
- 02：`test_dynamic_import_registry.py` 要求 L4 动态导入经 `ui_plugin_registry.module()`，且 `UI_PLUGINS` 含 `workflow_settings`。
- 03：`tests/test_idea_chat.py`、`tests/test_idea_chat_controller.py`。
- 04：`tests/test_pet_llm*.py`、`tests/test_model_router*.py`、`tests/test_writing_api*.py`。
- 06：`tests/architecture/test_stage_command_contract.py`、`tests/test_stage_completion*.py`。
- 07：`tests/architecture/test_shared_state_ratchet.py`。
- 09：`tests/architecture/test_workflow_dir_ratchet.py`、`tests/architecture/test_recycle_service.py`、`test_remove_authority.py`。

## F 不列入整改

- 模块行数本身（全仓库已 ≤1500 行，R1983 已说明行数不等于耦合）。
- `skill_panel.Panel`（多写者仅 5）。

## G 文档

各执行轮同步 `architecture.md`（分层表、维护边界）；新增或删除架构测试时同轮更新「当前架构门禁清单」。

## H 门禁现状

`test_layers.py`（台账 35、动态登记 5）、`test_no_circular_import.py`（`KNOWN_DYNAMIC_CYCLES` 4 组）、`test_dynamic_import_registry.py`、`test_workflow_dir_ratchet.py`（37）、`test_shared_state_ratchet.py`、`test_module_size_ratchet.py`、`test_recycle_service.py`、`test_remove_authority.py`。

## J 整改路线

每项单独一轮，≤3 个模块；结构治理轮零行为变更，行为变化的单列修复轮（先红后绿）。执行时若发现口径与本节不符，在该轮结果文件写明并按实际收口，不扩大范围。

**01**
- **J1**（结构治理轮·执行）：`show_settings` 与 13 个 UI 名称迁到新 L4 `workflow_settings_dialog.py`；`desktop.flow_settings` 改从新模块导入；7 个边界测试的登记文件名跟随，断言不动。模块：workflow_settings、workflow_settings_dialog、desktop。
- **J2**（结构治理轮·执行）：`qwen_setup.show()` 迁到新 L4 `qwen_setup_dialog.py`，`qwen_setup` 只留解析与密钥读写。模块：qwen_setup、qwen_setup_dialog、调用方。
- **J3**（结构治理轮·执行，层级登记）：按真实依赖重登记 workflow_settings、qwen_setup、qwen_adapter、legacy_compat、pet_state、ui_plugin_registry、integrations、artifact_lineage；台账删已不越层的项并下调基数，`KNOWN_DYNAMIC_UPWARD` 删已不越层的行；architecture.md 分层表同步。不改生产代码；合入 master 前须全量。
- **J4**（结构治理轮·执行）：`workflow_settings` 提供一个入口按 校验 → 取当前设置 → 冻结 SKILL 的固定顺序完成，`writing_api` 与 `desktop_idea_chat` 的 4 处改调它。模块：workflow_settings、writing_api、desktop_idea_chat。

**02**
- **J5**（结构治理轮·执行）：`project_settings` 的确认弹窗改由调用方注入或移到 L4 对话模块，`project_settings` 按真实依赖重登记，清 5 项。
- **J6**（结构治理轮·执行）：`cloud_assets` 的 Tk 尾巴同法，清 3 项。
- **J7**（结构治理轮·执行）：`asset_prompt_rules`、`asset_reference_prompts` 的 Tk 尾巴同法，清 5 项；余下项逐条写具体原因。

**05**
- **J8**（修复轮）：`cloud_assets.get_key()` 改经 `model_pool.credential()`，修复旧环境变量盖过新保存密钥。
- **J9**（结构治理轮·执行）：`tts_api`、`api_endpoints` 的取钥改经同一入口，来源顺序与现行为一致的部分直接委托，不一致处在结果文件列明。

**04**
- **J10**（结构治理轮·执行）：计量序列（估算 → 授权 → 结算）与诊断目录收进 `pet_llm` 一个入口，`writing_api` 改调。
- **J11**（修复轮）：`edit_habits`、`skill_notes` 直连 `PoolAdapter` 改走计量入口。
- **J12**（结构治理轮·执行）：重试口径收进一处，「对话可重放」与「提交可能已受理」两种口径显式命名；`ModelRouter.chat` 按调用方核实结果处理。

**08**
- **J13**（结构治理轮·执行）：`NoRedirect` 收成一份，其余模块改用。
- **J14**（结构治理轮·执行）：子进程 `_run` 去重；`WanAdapter` 接到 `VideoAdapter`。

**06**
- **J15**（结构治理轮·执行）：下一阶段表收成一份 L3 定义，`desktop_pet_bridge`、`desktop_auto_flows` 改用。
- **J16**（修复轮或结构治理轮，视两判据是否一致）：`skill_orchestrator` 的剧本结构完成判据改委托 `stage_completion_service`。
- **J17**（只在三处续跑状态确属同一概念时执行）：续跑台账收口；不是同一概念则在结果文件说明并关闭。

**03**
- **J18**（结构治理轮·执行）：`desktop_idea_deferred` 的稳定判定迁入 `idea_chat_controller`，时钟注入，Tk 只留 `after` 调度。
- **J19**（结构治理轮·执行）：请求生命周期的状态与判定迁入 `idea_chat_controller`，`desktop_idea_chat` 只留控件与事件绑定。

**11**
- **J20**（结构治理轮·执行）：`page_navigation_controller` 一次接收状态快照、返回完整换页决策，`desktop_page_nav` 改为一次调用。

**10**
- **J21**（结构治理轮·执行）：`stage_execution_service` 的网关字典收成一个基础构造，各 `*_gateway()` 只补差异字段，对外接口不变。

**09**
- **J22**：路径权威加「工作流任务」入口（落 L0 时按契约轮）。
- **J23 起**：23 个模块每轮 ≤3 个改用入口，棘轮登记逐轮下调直至清空。
- **J-回收**（结构治理轮·执行，合入前全量）：`storyboard_recycle_service` 的回收写入改走 `storage_maintenance.recycle_paths()`。
- **J-配置**（结构治理轮·执行）：`skill_config.json` 路径收成一个入口。

**07**
- **J-Pet／J-Cloud**（结构治理轮·执行）：各挑一簇多写者属性收进只由一个 Mixin 写的状态对象（仿 `pet_broadcast_state`），棘轮下调。

## K 测试迁移／补充计划

- 所有执行轮断言不动；契约有意变更只同步 mock 与导入路径，并在结果文件注明「断言未动」。
- J1／J2：边界测试登记的文件名跟随迁移；新增一条用例证明 `workflow_settings`／`qwen_setup` 导入后 `sys.modules` 不含 tkinter。
- J3：`test_layers.py` 台账与动态登记按实际下调，不加新豁免。
- J4、J10、J18–J20：新测试直接打新入口（无 Tk、注入时钟／执行器），旧用例保留作回归。
- J8、J11、J16：先写失败用例贴出改前输出，再实现。
- J13／J14：新增用例证明各适配器共用同一实现（行为层面：重定向被拒、子进程超时）。
- J22 起：棘轮登记每轮下调。
- 每轮验证：默认冒烟；结构治理与跨层改动跑 `--architecture`；改了被导入模块跑 `--affected <模块>`；定向 `run_selftests.py -k`；含 Tk 的测试经 `工作流任务\gui_hidden.py`。层级登记表、删除语义改动在合入 master 前跑全量。

## L 风险与限制

- 并行会话：剧本准备页（`desktop_idea_chat.py`、`desktop_writing_page.py`）与已删分镜相关文件有其他会话在改，J4、J18、J19、J-回收开工前先同步 master 再复核行号。
- 04 的重试口径与 05 的取钥顺序涉及行为，结构轮只做等价委托，行为改动只在修复轮做。
- 本轮未运行测试；D 节行号以 R2173 树为准，后续轮次以当轮实测为准。

## M 完成状态

- 已完成：11 个候选的耦合点定位、J 整改路线、K 测试计划。
- 未做：任何代码改动、测试运行、architecture.md 更新。
- 下一步：按用户「自动完成 01–11 项」指令从 J1 开始逐轮执行。
