# R1645 结构治理只读诊断：缺陷与缺失清单

## §7 三问

- **本轮类型**：结构治理轮·只读诊断（§3.3，按 §3.5 元数据例外）。未改任何 `.py`／配置／用户项目数据；未搬目录、未改名、未删文件；仅新增本结果文件并同步状态页轮次头（正文未动）。
- **测试跑了吗？三个基线过了吗？** 只跑 1 次 `python smoke_test.py --architecture`＝**356/356 OK（177.9 秒，本轮实测）**；默认冒烟 **8/8**；**未跑全量**（只读诊断口径）。架构门禁含本报告 C–I、L、M 各节的主要机检依据，故不存在「结论无门禁依据」的缺口。
- **欠账少了吗？** 没有，也不应少：本轮不改源码。`scripts/auto_full_safe.py --status`＝上次全量 R1624、最新 R1644、期间改过源码的轮次 2（门禁线 8）、后台触发 False。

## A 诊断范围与命令

1. 轮次：`运行环境\Python\python.exe -B 程序\维护记录\基准脚本\round_claim.py next` → 1645。**用户给出路径 `维护记录\基准脚本\round\_claim.py` 不存在**，实际文件名是 `round_claim.py`（无子目录）。
2. 架构门禁：`python -B smoke_test.py --architecture`（PYTHONPATH=`程序\tests;程序`）→ Ran 356 tests, OK, 177.864s。
3. 默认冒烟：`python -B smoke_test.py` → 8 项通过、0 失败。
4. 独立分层／环扫描（stdin 只读脚本，不落盘）：读 `tests/architecture/_layers.py` 的 `LAYERS`／`TOOLS` 与 `tests/architecture/_scan.py` 的 `production_files()`，`ast` 解析 271 个生产文件的 import，做越层判定与 Tarjan SCC。
5. 权威台账：`维护记录/架构统一基数.json`（层级、第三项、第四项、覆盖率审计 20/21/24/25/26/27、`historical_name_audit`）、`维护记录/skip台账.json`、`维护记录/基准历史.json`、`维护记录/覆盖率基线.json`、`维护记录/覆盖率审计判据_20261001.md`。
6. 权威源：`程序/AGENTS.md §2.2`、`architecture.md §3`、`tests/architecture/_layers.py`、`distribution_manifest.md`、`说明/持久化产物版本清单.md`。
7. 定向文本扫描（只读）：`Bus.emit(`／`emit_safe(`、`stage_handler_registry.start(`、裸 `json.dump/load`、`importlib.import_module`、`rglob`／`os.walk`、`after(`／`after_cancel(`、裸 `tk.*`／`ttk.Treeview`／`messagebox.`／`filedialog.`、`except: pass`。
8. 欠账状态：`python -B scripts/auto_full_safe.py --status`。

未做：不改文件、不搬目录、不跑全量、不实机、不联网。历史记录只作追溯，不作当前验收。

## B 目录与模块现状

- 门禁口径生产文件 `production_files()`＝**271**；「顶层非 `test_` 的 .py」＝**274**（多出 `smoke_test.py`／`run_selftests.py`／`selftest_sandbox.py` 三个开发工具，门禁不计入生产）。
- 层级登记 `_layers.py` 注册 **276** 个名字：L0 27／L1 32／L2 70／L3 57／L4 88／L5 2。其中有实体文件的 **267**，另 4 个属 `TOOLS`（`blender_previs_template`、`codex_paste`、`codex_tasks`、`console_submit`）。
- 注册表内**无实体文件**的名字 **9 个**（见 M 节）。
- 未登记模块：**0**（我的扫描与门禁 `test_every_top_level_runtime_module_is_registered_or_an_explicit_tool` 同结论）。
- 架构门禁 356 项全绿（本轮实测）；`tests/architecture/` 之外另有全量用例（最近凭据 R1624 共 5407 条，非本轮实测）。

## C 分层依赖扫描

- 门禁 `test_higher_layers_may_depend_only_on_same_or_lower_layers` 绿 → **未登记越层 0 处**。
- 已登记越层豁免＝`架构统一基数.json.层级.items` **37 行**，`baseline_exempt`＝**37**（**已顶到基数上限**），全部 `disposition=exempt`、`reason=既存越层，待专项收口`；门禁另断言「台账必须仍可定位」「不得高于基数」。
- 我的独立扫描得 **42 组** (importer→imported) 越层对（按对去重）；与台账 37 行的差额属口径差异（台账按 `file/importer/imported` 三元组登记，我按对去重），**需在收口轮复核**；结论以门禁为准。
- 越层最多的 importer：`asset_batch_service`(6)、`asset_batch_execution`(3)、`engine`(2)、`native_apps`(2)、`previs_automation`(2)、`stage_models`(2)、`workflow_engines`(2)、`workflow_tasks`(2)。

## D 循环依赖扫描

- 门禁 `test_no_circular_import` 绿；我的独立 **Tarjan**（271 节点、313 个不同 import 目标）**SCC 大小 >1 的分量＝0** → 无模块环。
- 口径局限：只扫顶层 `程序/*.py` 模块图，`agent/**` 作为单个 `agent` 节点参与，包内环不在该口径内。

## E 路径与删除权威扫描

- 删除：生产 `os.remove/unlink/rmtree/rmdir` 命中集中在权威或既有豁免面——`storage_maintenance.py`（回收权威）、`agent/core.py`（原子写临时文件）、`file_cache.py:200,234`（缓存）、`log_maintenance.py:50`（自有日志）、`run_selftests.py`／`smoke_test.py`（开发工具）。门禁 `test_remove_authority` 绿 → **未发现绕过 `recycle_paths()` 的用户可见删除**。
- 路径：门禁 `test_path_authority` 绿 → 未发现绕过 `stage_path_service`／`storyboard_paths` 的正式路径拼接。
- 局限：只读扫描不能证明「运行期不存在」，以门禁＋台账为准。

## F 动态导入与事件边界

- 事件：生产 `Bus.emit(` 命中 **1 处**＝`pet_bus.py:114`（`emit_safe()` 自身的实现 `return bus.emit(kind, **payload)`）；`emit_safe(` 14 处。→ **无直调 `Bus.emit()` 的越界转发**。
- 动态导入：`importlib.import_module(` 生产命中 **4 处且全在开发工具**（`run_selftests.py:886,1018`、`smoke_test.py:141,169`）；生产插件／阶段加载走 `ui_plugin_registry.module()`。`覆盖率审计24`（动态导入）当前 `count=0`，items 全 exempt 且逐条带理由。

## G 阶段命令与完成核验

- `stage_handler_registry.start(` 生产命中 4 处（注册表自身＋既有调用方）；门禁清单内无「绕过注册表」项。
- 阶段完成核验权威为 `stage_completion_service`（L3），在册；`stage_parallel.GATES` 的 7 条门禁由 `维护记录/基准脚本/探针_阶段门禁端到端.py` 驱动（R1630 已扩到全部 7 条；本轮未重跑探针，属只读诊断口径）。

## H L2 服务契约与项目上下文

- `service_contract` 被 **28 个文件**引用；L2 实体模块 **64** 个中 **27** 个引用它，其余为只读／纯计算模块——其边界由 `架构统一基数.json` 的 `readonly_scope_audit` 逐条登记，门禁 `test_service_return_contract.test_every_registered_l2_module_has_a_scope_record` 与 `test_audited_readonly_scope_has_reasons_and_fixed_entrypoints` 断言覆盖。
- `ProjectContext` 被 **30 个文件**引用；门禁 `test_project_context_boundary` 绿。
- 统一棘轮：`test_unification_ratchet` 的第三项（L2 直写正式路径）与第四项（裸 `json.load`）当前 `count=0`，`baseline_pending` 66／35，且断言扫得集合是台账的**不增子集**。

## I 正式 JSON 读写与启动路径

- 裸 `json.dump(`：生产 2 处＝`publication.py:31`（事务日志写前记录，权威）、`run_selftests.py:248`（工具）。
- 裸 `json.load(`：生产 11 处＝`agent` 适配器解析 HTTP 响应（`local_video.py:42`、`volcengine.py:74`、`wan.py:51`）、`qwen_setup.py:157`（HTTP）、`optimizer_mcp_bridge.py:48`（stdin）、`run_selftests.py`×5（工具）、**`pet_ui_voice.py:901`（L4 直读 `程序/projects.json`）**——最后一项越出既有 JSON-IO 门禁范围（P1-1）。
- 启动路径：`performance_contract.STARTUP_RECURSIVE_SCAN_COUNT = 0` 且有 `test_startup_budget` 守护；生产 `rglob/os.walk` 共 16 处，分布在 `storage_maintenance`(6)、`projects.py:158`、`artifact_lineage.py:180`、`line_endings.py:133`、`script_contract.py:159,535`、`shot_numbering.py:138,158`、`skill_import_service.py:51`、`stage_completion_service.py:452`、`stage_execution_service.py:117`、`stage_write_preparation_service.py:55`、`storyboard_catalog_service.py:40`、`usage_overview.py:26`、`workflow_context.py:41`、`workspace_maintenance.py:65,87,109`、`writing_tools.py:57` —— **无一在 `app.py`／`desktop.py` 的启动序列内**；`projects.py:158` 由页面动作 `desktop_project_pages.py:31` 触发的迁移校验路径。

## J 整改路线（优先级／最小闭环／完成判据）

### P0（阻断级）

**本轮未发现 P0。** 依据：循环依赖 0 环（D）、未登记越层 0 处（C）、未登记模块 0 个（B）、直调 `Bus.emit()` 0 处（F）、生产 `except: pass` 0 处（L）、裸控件全部落在 `ui_widgets.py`（L）、启动递归扫描契约＝0（I）、架构门禁 356/356（A）。「未发现」不等于「不存在」，但本轮可查面均已查。

### P1

**P1-1 L4 直读正式 JSON，绕过登记索引的读取边界**
- 位置：`程序/pet_ui_voice.py:899-901`（`path = PROGRAM / 'projects.json'` → `json.load(handle)`）。
- 影响：`projects.json` 是项目登记索引；该处是 UI 层自行打开文件的兜底读，且 `except Exception` 只把错误 append 到 `self.errors` 后返回 `{}`（调用方静默拿到空）。`test_unification_ratchet._bare_json_loads()` 只扫 L2（`_l2_source_files()`），`test_json_io_boundary` 只覆盖 previs 进度 → **该处不在任何 JSON-IO 门禁范围内**。
- 最小闭环：删除文件兜底，改用已注入的 `self.desktop.projects.info`（同函数前半段已是该路径）；失败走既有错误上报。
- 完成判据：该处无 `json.load`／`open`；把 `_bare_json_loads()` 范围扩到 L4 正式路径读取后，该项不出现（或作为登记豁免且带理由）；定向 1 条用例断言读不到时不再自行开文件。

**P1-2 越层豁免已顶到基数上限，且无收口路径**
- 位置：`程序/维护记录/架构统一基数.json`（`层级.baseline_exempt`＝37 ＝ `items` 37 行）。
- 影响：门禁只保证「不再增加」，37 条既存越层（其中 `asset_batch_service` 6 条）没有任何到期或收敛机制；一旦需要新增一处越层，就必须先动台账（弱化门禁的信号）。
- 最小闭环：按 importer 分组择一并开工（先 `asset_batch_service`），每收口一组同步下调 `baseline_exempt`。
- 完成判据：`层级.items` 行数下降且 `baseline_exempt` 同步下调，门禁 `test_layer_exemptions_are_a_locatable_nonincreasing_baseline` 绿；台账 `reason` 仍可定位。

**P1-3 覆盖率审计 19–23 未入账，安全面只有部分契约有门禁**
- 位置：`程序/维护记录/覆盖率审计判据_20261001.md:3`（只有 20／21／24／25／26／27 是冻结契约段落，其余为 R742 只读提案）。
- 影响：「密钥流入日志／任务 JSON／prompt」目前只有 27 一项有台账依据（`架构统一基数.json.覆盖率审计27`＝`count 0`、`items []`）；其余契约无独立门禁，历史快照数字不得当债务认定（判据文档自述）。
- 最小闭环：按判据文档既有三步——先把金丝雀＋扫描器实现为独立于台账的门禁，再逐条复核真候选，最后写入基数。
- 完成判据：19–23 每条都有 `disposition`＋理由，且由棘轮测试断言（当前 20/21/24/26 已 `count=0`、25/27 `items` 为空可作范式）。

### P2

**P2-1 分层登记里的僵尸／未审计历史名称 3 个**
- 位置：`程序/tests/architecture/_layers.py:26`（`project_storage`）、`:29`（`asset_detail_ui`）、同段（`workflow`）。
- 影响：全仓检索中 `project_storage`／`asset_detail_ui` **仅有 `_layers.py` 自身引用**（僵尸登记）；`historical_name_audit`（R1028）只覆盖 6 个名字（`asset_gating`／`keyframe`／`keyframe_api`／`previs`／`writing_files`／`writing_workflow`），这 3 个不在其中；`workflow` 与普通词冲突，文本检索无法判定引用面。
- 最小闭环：先只读确认三者是否仍有采用方（`workflow` 用 AST 判定 `import workflow`／`workflow.` 形式），确认后或并入 `historical_name_audit`，或从登记表移除。
- 完成判据：登记表中每个名字满足「有实体文件 ∨ 在 `TOOLS` ∨ 在 `historical_name_audit`」并由门禁断言（见 K-2）。

**P2-2 `skills/` 内无效转义仍在，静态卫生门禁有意不覆盖**
- 位置：`程序/skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239`（`and "[\[【]?" in _bbl_txt`）。
- 影响：本轮跑架构门禁时实测仍打印 `SyntaxWarning: "\[" is an invalid escape sequence`；`test_static_hygiene` 的 `_EXCLUDED_PARTS` 含 `skills`（外部独立技能包），故门禁绿 ≠ 全仓无此问题。随附解释器为 3.15.0a2，未来版本会变硬错误。R1610 记录的另一处 `tests/test_dev_entry.py:23` 已在 R1611 修为 raw 字符串。
- 最小闭环：把该行改为 raw 字符串或 `\\[`；同一批在 `test_static_hygiene` 内把「`skills/` 有意排除」写成断言（防误读为全仓覆盖）。
- 完成判据：门禁运行输出不再出现该 SyntaxWarning；静态卫生测试显式声明排除范围。

**P2-3 关窗竞态：轮询重排未捕获 `tk.TclError`**
- 位置：`程序/desktop_script_pages.py:136`（`self.win.after(2000, poll)`）；对照同文件 `:439-451` 的 `await_preview` 已用 `try/except tk.TclError` 包裹。
- 影响：窗口销毁瞬间重排定时器会抛 `TclError` 进入 Tk 回调（有 `app_logging` 兜底记录，不会静默，但属可避免的噪声与竞态窗口）。
- 最小闭环：与 `await_preview` 同构加 `try/except tk.TclError`；顺带确认该轮询在销毁时停止（`winfo_exists` 判据）。
- 完成判据：定向用例覆盖「销毁后重排不抛」，或静态扫描断言该文件 `after(` 调用点均受 `TclError` 保护。

**P2-4 性能基准停更且与现行契约口径不一致**
- 位置：`程序/维护记录/基准历史.json`（15 条，最新 `round 1373`，2026-10-12）。
- 影响：无法从基准判断近期回归；旧指标（如 `asset_page_300_warm_ms`）与 `tests/performance_contract.py` 现行契约（`LONG_LIST_SCROLL_MEDIAN_MS=150`、`STARTUP_FIRST_FRAME_MS=1500` 等 11 条）不可直接比较。本轮未触发全量（欠账 2/8、后台 False），因此也没有新的性能凭据。
- 最小闭环：把基准记录入口与现行契约指标对齐后重跑一次基准，或在文档中明示「基准历史仅历史参考，不作当前判据」。
- 完成判据：`基准历史.json` 出现与 `performance_contract` 同名指标的记录，或文档写明口径差异且被测试引用。

**P2-5 无整仓覆盖率口径，「未覆盖模块」当前无可信数字**
- 位置：`程序/维护记录/覆盖率基线.json`（`modules_total=281`、`modules_covered=49`、`percent=0` 的模块 232 个、均值 7%、`tests_ok=true`、`targets` 8 个）。
- 影响：这是**定向测量**（8 组定向用例对模块的行覆盖），不能读成总覆盖率 7%，也不能据此列出「未覆盖模块」清单。
- 最小闭环：在覆盖率文档与状态页写明口径；若确实要「未覆盖清单」，另立一次全量 `sys.settrace` 测量（成本高，需用户同意）。
- 完成判据：文档口径与 `覆盖率基线.json` 字段一致，且门禁 `test_coverage_baseline` 断言仍绿。

**P2-6 正式产物版本字段仍有 6 类「待核查」**
- 位置：`程序/说明/持久化产物版本清单.md`「待核查」段（`assets.json`、`skill_config.json`、`natural_script_selection.json`、批次／三元组台账、`产物来源关系.json`、各 manifest）。
- 影响：格式漂移检出覆盖不全；`artifact_schema.migrate` 只加键，旧数据可读性有保障，但「能不能发现漂移」尚无全量入口。
- 最小闭环与完成判据：见阶段5 清单 U11（本项与其同一工作项，不重复立项）。

**P2-7 迁移校验是全量 rglob＋逐文件 sha256，代价随素材库线性增长**
- 位置：`程序/projects.py:158`（`for p in (self.app/name).rglob('*')` ＋ `file_hash` 双向比较），由 `desktop_project_pages.py:31` 的页面动作触发。
- 影响：大素材库上迁移是一次 O(全量) 读盘＋哈希；不在启动路径（未违反启动扫描契约），但用户点「迁移」会长时间无反馈风险。
- 最小闭环：迁移前给可取消的后台任务＋进度（复用既有后台任务生命周期）；哈希比较改用 `file_cache` 既有缓存。
- 完成判据：迁移走后台任务且失败可恢复；`file_hash` 调用经缓存层。

**P2-8 越层对计数与台账不一致，口径需复核**
- 位置：我的独立扫描 42 组 vs `架构统一基数.json.层级.items` 37 行（门禁断言两者一致且绿）。
- 影响：若差额来自扫描口径（导入写法／文件集合／去重方式），台账的「完全相等」断言在换实现后可能失准；若来自我漏判层级，则需修正我的结论。
- 最小闭环：复核轮用与门禁同一 `_scan.import_rows()`＋`production_files()` 复算，逐条对齐 42 与 37 的差集并写明原因。
- 完成判据：差集为空，或差集每条都有书面归属（例如「同一对在 2 个文件各出现 1 次」）。

## K 测试迁移计划

- **是否移动**：不移动、不重命名任何测试文件（本轮无搬目录权限，且无必要）。
- **新增（3 条，均落在 `tests/architecture/`，定向运行，不新增全量频率）**
  1. **L4 正式 JSON 读取边界**：把 `_bare_json_loads()` 的扫描范围由 `_l2_source_files()` 扩到「L2＋L4 正式路径读取」并加金丝雀（当前唯一命中＝`pet_ui_voice.py`）；断言集合是台账的不增子集。
  2. **历史名称收口门禁**：断言 `LAYERS` 每个名字满足「有实体文件 ∨ 在 `TOOLS` ∨ 在 `historical_name_audit`」；当前会红出 `project_storage`、`asset_detail_ui`、`workflow`（先只读确认再决定登记或移除）。
  3. **静态卫生范围声明**：在 `test_static_hygiene` 内把「`skills/` 排除」写成显式断言，并登记 `check_package.py:2239` 为已知豁免（带 owner／理由），避免把「门禁绿」读成「全仓无无效转义」。
- **覆盖范围**：三条都只覆盖结构不变量（AST 静态）；不改任何产品行为，故不新增 `run_selftests --all --safe` 触发条件，也不动 `baseline_exempt`／`baseline_pending` 数值（除非收口轮同步下调）。
- **不改测试迁就实现**：P1-1 若整改，断言的是「不再自行开文件」这一行为契约，而非放宽既有扫描。

## L UI 统一入口与静默失败

- 裸控件（生产，本轮实测计数）：`tk.Button(` **0** 处（文本扫描命中的 7 处全是 `ttk.Button(`）；`tk.Entry(`／`filedialog.` **0** 处；`ttk.Treeview(` **4** 处（`desktop_project_pages.py:228,320`、`desktop.py:150`、`ui_widgets.py:175`＝统一表组件本体）；`messagebox.` **2** 处均为 `ui_widgets.py` 内的说明文字；`tk.Toplevel(` **2** 处均在 `ui_widgets.py`（:844、:1153）。→ 生产页面未见裸控件绕过统一入口。
- 静默失败：生产 `except:`＋`pass`／`except Exception:`＋`pass` **0** 处；`test_silent_exception_ratchet` 绿（历史登记位只减不增）；`app_logging` 已接管主线程／后台线程／Tk 回调／C 层崩溃。
- Tk 生命周期：`after(` 57 处／`after_cancel(` 73 处；仅 `desktop_script_pages.py`（4 处）与 `pet_ui.py`（1 处，`schedule` 回调注入 `pet_chat_coordinator`，由所有者管理）无 `after_cancel` → 见 P2-3。

## M 性能、安全、兼容、历史名称

- **性能**：本轮未触发全量（`--status`：上次 R1624、源码轮 2/8、后台触发 False）；`performance_contract.py` 11 条阈值在册（含 `STARTUP_RECURSIVE_SCAN_COUNT=0`）；架构门禁 177.9 秒属正常区间；**基准历史停更于 R1373**（见 P2-4）。
- **安全**：`覆盖率审计27`（密钥 sink）`count=0`、`items=[]`；`覆盖率审计26`（出站 HTTP）`count=0`、`baseline_pending=2`；`test_secret_sink_audit` 绿。**局限**：只覆盖 20／21／24／25／26／27，其余为只读提案（见 P1-3），零命中不得解释为全路径安全。
- **兼容 facade**：`legacy_compat.FACADE_MANIFEST` 逐条带 `owner`／`callers`／`retire_after`，门禁 `test_facade_is_not_past_its_retirement_date` 绿 → **无过期未退役项**；到期前须处理（现有机制会红）。
- **历史名称**：注册表 9 个名字无实体文件——`asset_gating`／`keyframe`／`keyframe_api`／`previs`／`writing_files`／`writing_workflow` 已在 `historical_name_audit`（R1028）登记现行职责入口；`project_storage`／`asset_detail_ui` 仅被 `_layers.py` 自身引用；`workflow` 需 AST 判定（见 P2-1）。
- **数据迁移**：`artifact_schema.migrate` 只加键、读取侧容忍缺版本；白模旧目录迁移可重复／不覆盖／失败回滚；缺口是产物版本字段的「待核查」6 类（见 P2-6）与迁移成本（P2-7）。
- **测试卫生**：`skip台账.json` 229 条全部带「何时应恢复执行」的理由（环境类 203＝无可用 tkinter、16＝无 Tk display、4＝无目录链接、2＝发行包缺 bundled skill、2＝缺 FFmpeg、1＝无 node、1＝无工作集接口），**空／失效 skip 0 条**；`test_skip_hygiene` 绿。

## 附：本轮未做的事（如实登记）

- 未跑 `探针_阶段门禁端到端.py`、未跑全量、未实机、未联网；「未检索到」不等于「不存在」。
- 未复核我的独立扫描与门禁在越层计数上的 5 组差额（列为 P2-8）。
- 按本轮边界，未更新 `.agent-handoff/` 接力文件与状态页正文；如需刷新接力，另立轮次。