# R1983 desktop.py 及同类组合类解耦诊断（只读诊断）

本轮属于 §3.3 结构治理轮·只读诊断（写入边界按 §3.5）：未改任何 `.py`，未改用户数据，仅新增本结果文件并同步状态页轮次头。
测试：按 §5 只读诊断默认不跑测试；本轮未运行测试，也未重跑全量。下文度量均为本轮在本树上的 AST 静态统计，不是测试结果。
欠账：本轮不改源码，全量欠账计数不变。

基线：`claude/bold-ardinghelli-d6a54d` @ 2e745d21（R1982）。日期：2026-10-24。

## A 结论

- `desktop.py` 需要继续解耦，但目标要换：行数已经达标（1454 行；全仓库生产模块都 ≤1500 行，`tests/architecture/test_module_size_ratchet.py` 的 `OVERSIZE_CAPS` 已空），问题在共享状态。
- R1618–R1622 的拆法是把方法搬进 Mixin 文件。所有 Mixin 仍读写同一个 `self`，耦合换了文件，没有变少。
- 同类组合类还有 `Pet`（pet_ui.py）、`Cloud`（pet_cloud.py）、`Panel`（skill_panel.py）。按多写者属性比例，Pet 最差，Desktop 绝对量最大，Panel 健康。
- 建议顺序：J0 门禁 → J1 Desktop 自动化状态 → J2 页面服务注入 → J3 媒体页下沉 → J4 导航与计时器 → J5 Pet 播报状态 → J6 Cloud 定位任务。

## B 证据与范围

统计方法：用 `ast` 解析组合类及其全部基类（同在 `程序\` 顶层）。

- 写入：`self.X = …` 等 Store 上下文；读取：其余上下文。
- xAttr：本类读取、但只由别的类写入的属性数。
- xMeth：本类读取的、由别的类定义的方法数。
- 多写者：被 ≥2 个类赋值的属性。

统计脚本未入库（只读轮不新增 `.py`），J0 会把它做成门禁。范围只含 Mixin 组合类；纯函数大模块单列在 F。

## C 组合类度量

| 组合类 | 基类数 | 共享 self 属性 | 多写者属性 | 比例 |
|---|---|---|---|---|
| `Desktop`（desktop.py） | 15 | 245 | 81 | 33% |
| `Pet`（pet_ui.py） | 5 | 93 | 64 | 69% |
| `Cloud`（pet_cloud.py） | 4 | 44 | 18 | 41% |
| `Panel`（skill_panel.py） | 3（另继承 ttk.Frame） | 67 | 5 | 7% |

Desktop 各 Mixin（方法数／自写属性／自读属性／xAttr／xMeth）：

| Mixin | 文件（行数） | 方法 | 写 | 读 | xAttr | xMeth |
|---|---|---|---|---|---|---|
| AutoFlowsMixin | desktop_auto_flows.py（676） | 30 | 51 | 102 | 26 | 23 |
| MediaPagesMixin | desktop_media_pages.py（1028） | 52 | 10 | 84 | 19 | 25 |
| AutomationTickMixin | desktop_automation_tick.py（294） | 16 | 8 | 48 | 10 | 26 |
| ProjectPagesMixin | desktop_project_pages.py（531） | 33 | 12 | 55 | 12 | 15 |
| ScriptPagesMixin | desktop_script_pages.py（791） | 15 | 8 | 34 | 8 | 14 |
| LayoutMixin | desktop_layout.py（430） | 29 | 20 | 39 | 14 | 2 |
| IdeaChatMixin | desktop_idea_chat.py（1148） | 33 | 19 | 59 | 12 | 9 |
| AsyncTasksMixin | desktop_async_tasks.py（139） | 12 | 7 | 29 | 12 | 4 |
| AssetPagesMixin | desktop_asset_pages.py（801） | 39 | 9 | 38 | 7 | 6 |
| 其余 6 个 | — | — | — | — | ≤6 | ≤9 |
| Desktop 本体 | desktop.py（1454） | 67 | 170 | 151 | 0 | 63 |

Pet 各 Mixin：PetStagesMixin xAttr 14／xMeth 28，PetViewMixin 9／20，PetSettingsMixin 9／11，PetVoiceMixin 11／10。被 ≥3 个类写的属性：`_advance_at`、`_announced`、`_held_broadcast`、`_last_broadcast`、`last_status`、`notice`。

Cloud：CloudTimingMixin xAttr 6／xMeth 9；被 ≥3 个类写的属性：`_position_callback`、`_position_job`。

## D Desktop 具体耦合点

1. **自动化状态**：前缀 `auto_`／`_auto_` 的属性 66 个，写入分布在 7 个文件（desktop.py 65、desktop_auto_flows.py 44、desktop_automation_tick.py 5、desktop_async_tasks.py 3、desktop_media_pages.py 3、desktop_asset_pages.py 2、desktop_script_pages.py 1）。初始化在 `Desktop._initialize_automation_state`（desktop.py:357，53 行）。被 ≥3 个类写的典型属性：`auto_final_*`、`auto_keyframe_*`、`auto_asset_*`、`_auto_edit_result_poll_id`。
2. **页面全局宿主**：`desktop_page_support.py` 用 `bind_host` 和 `_HostAttribute("Desktop")` 让页面在调用时回取 desktop 模块里的 confirm／open_path／FileDialog／ContextMenu 等。R1606 只把剧本页改为注入 `ScriptPageServices`；writing、storyboard、project、asset、media、idea_menus 仍走全局宿主（architecture.md「R1606 / O8」节已登记）。
3. **Desktop 本体大方法**：`show` 91 行、`load` 86、`cancel_timers` 81、`_show_reset_page` 64、`_init_body_and_status` 63、`poll_flow_processes` 50。`cancel_timers` 逐个列出各 Mixin 的 after id，任一 Mixin 新增计时器都要回改 desktop.py。
4. **已有可复用件**：`desktop_automation_service.py`（`DesktopAutomationScheduler`、`BackgroundTaskLifecycle`、`RetryRegistry`）、`desktop_page_registry.py`、`DesktopStartupController`，以及 14 个 `*_controller.py`（如 `storyboard_page_controller.py`、`editing_page_controller.py`）的「控制器不持 Tk 控件」模式。

## E 测试依赖

- 23 个测试文件直接读写 Desktop 的 `auto_*`／`_auto_*` 属性（最多的是 `auto_keyframe_busy` 30 处、`auto_final_busy` 24 处、`auto_asset_busy` 16 处）。J1 必须保留旧属性名转发，否则就是改测试迁就实现。
- 21 个测试文件引用 `cancel_timers`。
- 引用 `desktop_page_support` 的测试：`tests/architecture/_layers.py`、`test_button_consistency.py`、`test_script_page_services.py`、`test_script_structure_edit.py`。
- Pet 多写者属性仅 2 个测试文件直接触碰，J5 风险较低。

## F 只有行数风险的模块（不列入整改）

`app.py` 1499 行（离 1500 上限差 1 行，下一次在其中加功能就会撞门禁）、`stage_execution_service.py` 1447、`ui_widgets.py` 1383、`writing_api.py` 1373、`pet_cloud.py` 1361。这些不是 Mixin 共享状态问题，新增功能应放进新模块；`app.py` 建议在下次触碰前先拆。

## G 文档

architecture.md 第 3 节分层表与「R1606 / O8」节的剩余依赖清单与本诊断一致。本轮不改 architecture.md；各执行轮落地时按 §3.3 更新。

## H 门禁现状

- 行数：`test_module_size_ratchet.py`（模块）、`test_function_size_ratchet.py`（函数）已有。
- 共享状态：无门禁。Mixin 之间新增交叉读写不会被发现，这是 J0 要补的口子。

## J 整改路线（待确认，不自动执行）

每项单独一轮「结构治理轮·执行」，≤3 个模块，零行为变更，写明来源 R1983 与条目号。

- **J0 共享状态棘轮门禁**：新增 `tests/architecture/test_shared_state_ratchet.py`，按 B 节口径对 Desktop／Pet／Cloud 统计多写者属性数，登记当前值（81／64／18），只许下降。写法照 `test_module_size_ratchet.py`，扫描复用 `tests/architecture/_scan.py`。
- **J1a Desktop 自动化状态收口（一）**：先把 66 个 `auto_` 前缀属性逐个分类（前缀相同但不属于自动化的，如 `_auto_save_script_raw`、`auto_batch`、`auto_variable`，先核实归属）。属于自动化的放进新建 L3 模块 `desktop_auto_state.py`（无 Tk）的 dataclass，`_initialize_automation_state` 迁为其工厂函数，Desktop 持有 `self.auto`。改 desktop.py、desktop_auto_flows.py、desktop_automation_tick.py。旧属性名用 property 转发到 `self.auto`。复用 `desktop_automation_service` 的调度器与生命周期类，不另造。
- **J1b Desktop 自动化状态收口（二）**：迁 desktop_async_tasks.py、desktop_media_pages.py、desktop_asset_pages.py（及 script_pages 的 1 处）的写入。转发 property 在生产调用方清零后保留给测试，另立契约轮决定是否退役。
- **J2 页面服务注入**：按 R1606 模式每页一轮，顺序 writing → storyboard → project → asset → media（idea_menus 随 project 一起）。每页只定义它实际用到的 `*PageServices` 字段。全部迁完后删除 `desktop_page_support` 的 `bind_host`／`_HostAttribute`，常量保留。不建包含整个 Desktop 的万能接口。
- **J3 媒体页逻辑下沉**：MediaPagesMixin 跨类调用最多。无 Tk 的状态与决策迁入新 `media_page_controller.py`，Mixin 只留控件与事件绑定。
- **J4 Desktop 导航与计时器**：`show`／`_show_cached_page`／`_page_cache_for`／`go_page` 的决策部分迁入 `desktop_page_registry.py`；`cancel_timers` 改为计时器登记表（各 Mixin 登记自己的 after id，关闭时统一取消）。
- **J5 Pet 播报状态**：`_advance_at`、`_announced`、`_held_broadcast`、`_last_broadcast`、`last_status`、`notice` 收进一个 `PetBroadcastState`，只由一个 Mixin 写。涉及 pet_ui.py、pet_ui_stages.py、pet_ui_voice.py。
- **J6 Cloud 定位任务**：`_position_job`／`_position_callback` 只由 CloudPlaceMixin 写，pet_cloud_timing.py 改调它的方法。
- **J7 行数上限收紧（可选，排在 J0 之后）**：本树 302 个生产模块中，超 1200 行 10 个、超 1000 行 17 个（超出共 4285 行）、超 800 行 26 个、超 500 行 54 个（超出共 20586 行）。建议把新模块上限从 1500 降到 1000，17 个现存超限模块按现值登记进 `OVERSIZE_CAPS` 只许下降；不建议 500，那会逼出 54 个模块的机械拆分，重演 Mixin「换文件不降耦合」的问题。行数门禁只防继续堆，内聚与耦合由 J0 衡量。
- **不做**：Panel（多写者仅 5 个）；F 节纯行数模块。

## K 测试迁移／补充计划

- J0 本身是新测试，放 `tests/architecture/`。
- J1：E 节 23 个测试文件不改；靠 property 转发保持替换点。新增 `tests/test_desktop_auto_state.py`，在不构造 Tk 的情况下验证工厂函数产出的初始值与原 `_initialize_automation_state` 逐项一致。
- J2：每页仿 `tests/test_script_page_services.py` 新增一条「注入假服务、不建 Desktop 主窗口」的用例。
- J4：21 个引用 `cancel_timers` 的测试文件不改；新增一条用例验证登记表取消全部已登记 after id。
- 所有执行轮：断言不动；若因契约有意变更需改 mock 或导入路径，在结果文件注明。
- 每轮验证：架构门禁、`run_selftests.py -k ui_edges timers desktop_startup_perf`（Pet／Cloud 轮改为 `-k pet_ui`），含 Tk 的测试经 `工作流任务\gui_hidden.py`；默认冒烟；复算多写者属性数并下调 J0 登记值。

## L 风险与限制

- 多写者口径按属性名统计，不区分「初始化时写一次」和「运行中反复写」，会高估部分属性的耦合；J0 门禁只比较趋势，不当作绝对评分。
- `auto_` 前缀的 66 个属性未逐个核实语义（见 J1a 第一步）。
- 只统计 `self.X` 直接访问，`getattr(self, 'X')` 动态访问未计入，实际耦合可能更高。
- 本轮未运行任何测试；E 节计数来自 grep，未区分注释与字符串。

## M 完成状态

- 已完成：度量、耦合点定位、J 整改路线、K 测试计划。
- 未做：任何代码改动、测试运行、architecture.md 更新。
- 下一步：用户指定执行哪一条 J（建议 J0），另起执行轮。
