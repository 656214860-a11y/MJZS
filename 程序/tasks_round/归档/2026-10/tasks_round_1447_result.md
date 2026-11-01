# R1447 修复轮（性能）：03 初步分镜切页阻塞及其他页面排查

> 说明：本轮在车道分支 `codex/wip-R1445` 开发，号源已被并行任务占用，合并时正式记为 R1447。

## 验收补修：坏 JSON 重复保存提示

- 仅修这一处回归。原因是事件顺序：07 异步落表/预览后，`<FocusOut>` 可以先于排队的 `<<Modified>>` 到达。`ask_save` 只取消已有计时器，没有消费当前 Modified 标志；坏 JSON 保存失败后文字仍为已编辑状态，迟到的 Modified 事件又挂一次提醒，因而确认和错误各出现两次。不是目录线程重复弹错。
- `storyboard_files.py`：在 `ask_save` 确认有未保存编辑后调用 `viewer.edit_modified(False)`，让当前编辑的排队通知不再重挂提醒。未改变控制器的未保存内容判断；后续真实修改仍会重新设置标志。异步目录、渐进列表及预览加载逻辑未改。
- `tests/test_final_viewer.py`：新增 `test_pending_modified_event_does_not_repeat_a_failed_save`，仅在该用例把提醒延时设为 0，以确定性推进排队通知，不靠机器运行速度碰运气；检查确认一次、错误一次、磁盘未改。修复前该新增用例实际失败 `2 != 1`，修复后通过。原 `test_broken_json_is_reported_and_not_written` 的函数体及全部断言保持不变。
- 原先该测试文件的“5 行改动”为 1 行导入、2 处 `show(...)` 替换（diff 为 +3/-2）：用 `show_catalog_page_ready` 在测试建立和重绘页面时完成异步目录任务，避免把 idle 当成后台完成。它没有过滤确认/错误、清空计数或改断言。本次保留该夹具时新增用例仍能先报红，确认没有掩盖本问题。
- 本次只运行 `test_final_viewer` 和 `test_final_page_loading`：修复前普通两模块 19 条曾通过，说明原问题受时序影响；新增确定性用例后单独 `test_final_viewer` 为 14 条、1 红；修复后 `run_selftests.py --serial -k 'test_final_viewer test_final_page_loading'` 为 **20 条（14+6）、19.8 秒、0 红、退出 0**。实际仍经 `.r1445_tmp/validation_entry.py selftests` 隔离 runner 台账，未写主树；未运行其他模块或整卷。仍有既有 Tk speak 清理警告。
- 按此次要求仅再尝试一次 PowerShell `Remove-Item -Recurse -Force` 清理 `.r1445_tmp/`，自动审批审查再次拒绝，原因仅 `blocked by policy`；按用户指示保留，不再重试。本次只改以上源码、测试和本结果文件。

以下为首次交付记录，测试数量及临时文件数量对应当时状态。

1. **本轮类型＝修复轮（性能）**。
2. **测试跑了；页面相关回归通过，全局基线不能报绿，全量未运行、未刷新。** 改动相关 89 条通过；页面构造/启动 256 条通过。默认 smoke gate 的增量子进程执行 1717 条、1 红，失败是异步加载后的旧测试等待夹具；保留断言修复夹具后，定向 smoke 9/9、`test_row_targets` 15 条通过，没有重滚整卷。额外分层与 SG 检查 53 条、1 红，定向复查后仅剩基线已有的 `scripts/auto_full_safe.py:87` 架构清单不匹配；SG 相关 18 条通过。
3. **欠账有明确边界，交付尚未完全收尾：** 本轮关闭 03 目录重复读取及同步扫描阻塞，并处理 07 同类扫描；05/06 的扫描与发布事务耦合、公共布局耗时保留为后续项。架构 AST 对比确认没有新增裸 JSON 读取债务，范围外脚本的既有清单红灯保留。既有全量验证欠账未清偿，不写全量绿凭据。按任务书不更新共享状态/接力文件，轮次元数据由主树验收同步。临时文件清理遭自动审批审查拒绝，详见交付自检，不能标记满足全部完成判据。

## 范围与测量口径

- 工作树 `D:\漫剧制作助手\.wt\R1447`，分支 `codex/wip-R1447`，基于 `a8fd664`。未领取新轮次，未提交、合并、推送或切分支；未改主树、`project_status.md`、共享接力文件、用户项目数据或凭据。
- 当前 `pet_bus.STAGES` 实际有 **13 页**，比任务书所称 12 页多了 Animatic。本轮全部测量，没有漏掉第 13 页。
- 同机 Windows 11（10.0.26100）、Intel64 Family 6 Model 151 Stepping 2、项目解释器 Python 3.15.0a2（MSC 1944 AMD64）、Tk 8.6。真实 Desktop/Tk，1360×900，使用 `test_ui_edges.make_populated_project` 的临时夹具，不读取真实用户项目。桌宠不自动启动、Desktop 启动控制器及自动化计时器取消，白模工作区重定向到本工作树临时目录；没有调用模型 API。仍有桌宠延迟开机招呼计时器，08 的独立 profile 捕获其执行，属于该页测量的时序干扰，不能将涨幅全部归于业务退化。
- 每个版本独立进程，按 01→13 首次进入，再按同序再次进入，各一次。`S`＝`Desktop.go_page()` 返回的同步耗时；`P`＝从调用开始到首轮 `win.update()` 完成；`R`＝03/07 加载提示消失、所有渐进表格完成的耗时。其他页的 P 不保证其所有异步媒体任务结束。单位均为毫秒。
- 下表是本轮修改前/最终修改后的实测，**不含 profiler 和调用栈采集开销**。操作系统磁盘缓存未清空，单次样本不代表 P95，也不据此宣称所有页面更快。筛选慢页采用更保守的 P：首次 >300 或再次 >150。
- 单独用 `sys.setprofile` 采集 Python 调用累计/自身耗时，并记录 UI 线程 `os.walk` 栈；项目便携解释器缺少 `cProfile`。profile 数字只用于定位，不与无探针基准直接比较；父子累计时间不能相加。

## 13 页修改前后对比

每格为 **S / P**。

| 页面 | 修改前首次 | 修改后首次 | 修改前再次 | 修改后再次 |
|---|---:|---:|---:|---:|
| 01 script | 254.56 / 665.05 | 251.62 / 647.96 | 105.49 / 499.28 | 84.19 / 427.87 |
| 02 script_structure | 88.80 / 260.75 | 92.84 / 320.78 | 114.07 / 272.11 | 111.14 / 294.21 |
| 03 storyboard | 189.04 / 574.82 | 153.81 / 600.18 | 56.93 / 145.33 | 51.84 / 158.56 |
| 04 animatic | 34.10 / 160.99 | 31.98 / 150.24 | 33.67 / 97.23 | 30.11 / 93.65 |
| 05 assets | 204.41 / 539.38 | 162.44 / 448.39 | 105.89 / 331.79 | 93.14 / 293.18 |
| 06 continuity | 156.09 / 347.52 | 170.34 / 332.49 | 107.55 / 239.33 | 136.23 / 299.42 |
| 07 final | 121.62 / 346.96 | 116.54 / 341.73 | 103.67 / 306.10 | 78.50 / 368.73 |
| 08 keyframe | 176.74 / 413.55 | 350.05 / 550.52 | 95.25 / 277.92 | 104.03 / 304.02 |
| 09 previs | 181.30 / 404.50 | 171.90 / 377.54 | 102.88 / 278.18 | 99.47 / 272.32 |
| 10 video | 91.70 / 231.00 | 98.41 / 214.90 | 74.18 / 179.63 | 76.69 / 170.94 |
| 11 audio | 112.48 / 253.93 | 92.25 / 199.31 | 72.80 / 172.02 | 67.00 / 173.48 |
| 12 edit | 81.88 / 417.06 | 87.30 / 417.53 | 54.42 / 279.07 | 58.81 / 278.60 |
| 13 delivery | 65.69 / 244.88 | 43.88 / 198.07 | 42.94 / 149.04 | 47.32 / 141.24 |

03 最终 R：首次 **602.17**、再次 **160.49**；07 最终 R：首次 **343.61**、再次 **370.60**。修改前两页同步完成目录填充，R 与 P 相同。基础夹具中 03 并非所有页面里最慢；卡顿对文件数量敏感，不能把“小项目首轮绘制没有下降”隐去。

在相同基础夹具上额外加入 **120 份剧本及对应 120 份初稿 JSON**，只按 02→03→04 测首次和再次，所得 03 压力结果如下。两版测量均无 profile/栈采集。

| 03 压力样例 | 修改前 S / P / R | 修改后 S / P / R |
|---|---:|---:|
| 首次 | 689.81 / 1230.17 / 1230.17 | 141.57 / 734.13 / 736.27 |
| 再次 | 42.90 / 164.18 / 164.18 | 40.58 / 160.77 / 163.02 |

首次同步处理减少 **79.5%**，列表完整显示减少 **40.1%**；缓存再次进入本来就快。基础、压力及独立归因探针的 Tk 回调异常捕获列表均为空。

## 03 根因与修复证据

修改前压力 profile 的主要调用链：

`Desktop.show → _show_cached_page → storyboard_creation → storyboard_files.show → refresh → refresh_catalogs / apply_catalogs → catalog / produced_scripts / insert_entries`。

| 修改前 profile 位置 | 累计耗时 / 次数 | 解释 |
|---|---:|---|
| `desktop.show` | 1631.32 ms / 1 | 这是带 profiler 的同步调用，不能拿来与上表 141.57 ms 直接比较 |
| `storyboard_files.show → refresh` | 1563.95 → 1518.44 ms | 首次建页把目录、来源匹配、填表串在 UI 线程 |
| `StoryboardPageController.refresh_catalogs` | 963.27 ms / 1 | 分别取两栏，剧本已制作状态又查询分镜 |
| `storyboard_catalog_service.catalog` | 1329.68 ms / 3 | 一个刷新重复构造目录；嵌套于前述调用 |
| `produced_scripts` | 579.04 ms / 2 | 取目录和应用目录时重复推导已制作集合 |
| `board_source_script` | 413.97 ms / 488 | 重复取 JSON 来源并解析路径 |
| `file_cache.read_json` | 124.43 ms / 874 | 是缓存读取调用数，**不是 874 次磁盘解析** |
| `discover_files` | 230.60 ms / 369 次生成器进入/恢复 | 不是 369 次完整目录扫描 |
| `insert_entries` | 403.33 ms / 2 | 同步全量填两张表，重复取摘要/测列宽 |
| `fit_file_columns` | 190.25 ms / 9 | Tk 字体测量与列宽计算仍有成本 |

基础夹具同一链条的 `refresh` 为 59.83 ms、3 次 `catalog` 为 42.90 ms，说明问题随目录规模放大。另有 `pet_at_stage → broadcast → pet_cloud._render → update_idletasks`：基础 profile 的 `_render` 累计 363.70 ms，其中 `update_idletasks` 累计 359.71 ms。它会执行待处理的布局、控件销毁等回调；不能解释成“云朵自己重建了全部控件”。

修复点：

| 文件 / 函数 | 改动及原因 |
|---|---|
| `storyboard_catalog_service.py:430 catalog_snapshot`、`:440 _catalog` | 在 L2 一次建立剧本/分镜目录、已制作路径集合和摘要；每种目录只发现一次，分镜 JSON 在快照中复用；最终目录根只计算一次。沿用 `file_cache`、排序、来源与采用过滤规则；异常 episode_id 的摘要回退保持原行为。 |
| `stage_execution_service.py:1667 storyboard_catalog_snapshot` | 由既有 L3 服务入口提供快照，保持单向依赖，不新增动态导入、Tk 状态或持久缓存。新增函数放在文件末尾，避免改变按行号登记的既有架构清单位置。 |
| `storyboard_page_controller.py:55 refresh_catalogs / apply_catalogs` | 应用完整快照时不重扫、不重读已制作集合、不重复 resolve 快照路径；集合匹配替代二次遍历。保留旧两栏调用方兼容路径。 |
| `storyboard_files.py:590 show` | 初次/文件监听刷新在后台生成快照；UI 只接收结果、应用选择与更新控件。revision 拒绝过期结果，busy/pending 合并扫描期间的事件，规范化改名后重扫；销毁/切项目丢弃迟到结果。失败有本页提示，手动刷新可恢复。 |
| `storyboard_files.py:190 show_final` | 07 同类首次/监听目录扫描后台执行，并保留编辑区未保存文本、预览选择、旧结果失效及失败恢复。修改前一次 catalog 会遍历四个根，不能把四次 walk 误称四次 catalog。 |
| `storyboard_table_ui.py:78 insert_entries` | 每批最多 40 行，后续 `after` 填充；复用已有行标识与高亮，完成后统一移除旧行/排列顺序，销毁或新填充取消旧批次；填充中抑制重复自适应列宽。摘要优先使用快照，07 不再读取不展示的摘要列。 |

最终归因探针中，03/07 首次与再次的 **UI 线程 `os.walk` 均为 0**；新测试还直接断言 catalog 发现入口不在 UI 线程。手动“刷新列表”保留立即扫描的既有语义，未把用户主动操作扩大成新异步契约。压力 profile 修改后 `storyboard_files.show` 为 45.47 ms，`Desktop.show` 为 106.68 ms；后台工作不在当前线程 profiler 内，不能把“从 UI 栈消失”解释成后台耗时为零。

## 其他页面与剩余问题

以下 I/E 为独立 profile 的累计/自身耗时（ms），与上表无 profiler 的 S/P 不混算。覆盖所有达到 P 阈值的页面；04 未达阈值，未见 UI 目录扫描，保留作对照。

| 页 | 具体归因与本轮处理 |
|---|---|
| 01 | `desktop.py:4593 writing` 611.55/2.24 → `:1066 refresh_uploaded_idea_attachments` 400.43/0.14 → `stage_execution_service.py:350 idea_attachment_local_mode` 370.46/0.05；其中 `writing_api.py:24 selected_model` 252.39/0.10，首次导入明显。回访 writing 93.60/2.48，但 P 仍 427.87；首次依赖导入与公共布局留后续。 |
| 02 | `desktop.py:5155 script_structure` 96.93/0.36，`skill_panel.py:371 stage_button` 38.07/0.06，Tk `update_idletasks` 187.92/126.10；页面构造外仍有共享事件/布局成本，未见 UI 目录扫描。 |
| 03 | `storyboard_files.py:590 show` 65.20/1.13，首次模块加载 60.31/0.14；`:702 apply_background_catalog` 51.56/0.09 → `:646 apply_catalogs` 50.69/0.18 → `storyboard_table_ui.py:78 insert_entries` 34.68/0.09，落表的 `:45 fit_file_columns` 29.57/2.11。本轮消除 UI 扫描并分批落表；整窗首绘未同比改善。 |
| 05 | `desktop.py:6035 asset_page` 245.30/0.85 → `:6226 assets` 103.95/0.68；`:6196 asset_requirements` 72.32/0.08，`stage_button` 66.31/0.04。保留一次 UI 扫描，发布事务的原因及后续拆法见下文。 |
| 06 | `desktop.py:5792 continuity_page` 153.72/0.46 → `:5773 continuity_ledger_data` 67.10/0.06；`asset_requirements` 43.34/0.09。保留一次 UI 扫描，与 05 同一发布链，留后续。 |
| 07 | `storyboard_files.py:190 show_final` 84.28/1.07，`stage_button` 39.15/0.04，Tk idle 168.53/121.32。本轮 UI 扫描归零，剩余为构建及共享事件；回访 S 78.50、P 368.73，不能宣称全面提速。 |
| 08 | `desktop.py:6736 storyboard` 307.51/2.18，`pet_ui.py:3286 greet` 255.10/0.07，`stage_button` 93.44/0.05，Tk idle 228.88/169.65。同次阶段 `speak` 只有 20.31/0.01，大项为开机招呼。`greet` 由 `pet_ui.py:3264 schedule_greet` / `:3268 after` 调度，不是首帧业务直接调用。回访 builder 82.37/0.96、无 profiler S 104.03。独立 profile 支持时序干扰解释，但不能用 255.10 抵扣基准涨幅；稳定退化尚未证实。 |
| 09 | `desktop.py:7180 previs` 223.70/0.08 → `local_previs.py:82 show` 193.51/1.21 → `:104 refresh_environment` 43.62/0.05 → `white_model_service.py:406 environment_summary` 41.79/0.11 → `shutil.py:1575 which` 35.95/10.15；环境探测、首次导入与 Tk idle 199.39/132.58 共存，留后续拆开环境探测。 |
| 10 | `desktop.py:7204 video_home` 36.78/0.68，Tk idle 128.13/79.38，`desktop.py:613 resize` 9.28/1.96；主要是公共切页成本，未见 UI 目录扫描。 |
| 11 | `desktop.py:7386 audio` 98.02/0.35，`stage_button` 61.87/0.05，Tk idle 117.61/78.06；阶段配置占构建显著部分，留公共优化。 |
| 12 | `desktop.py:7485 editing` 69.30/0.39，Tk idle 369.48/314.87，`:598 _fit_content_now` 32.61/0.53（3 次）；主要是 Tk/native idle 及共享布局，不能归于编辑业务计算。 |
| 13 | `desktop.py:7609 delivery` 85.57/0.27，`stage_button` 70.82/0.04，Tk idle 194.30/155.50；公共布局对照页，未见 UI 目录扫描。 |

公共阶段配置链为 `skill_panel.stage_button:371` → `stage_button_label:332` → `stage_config.get:304` → `default_entry:67` → `skill_registry.getByStage:743`。旧页销毁入口在 `desktop.py:4416–4418`，缓存失效销毁另在 `:4354`；Tk `destroy` 首次自身耗时 02=32.49、03=27.35、06=30.60、07=21.41、08=22.65、09=17.81、10=26.40、11=20.87 ms，递归累计时间有重叠，不能当作独立墙钟预算。profile 的自身耗时也包含未拆分的 Tcl/native 时间及探针开销。

05/06 的已确认扫描链为 `desktop.asset_requirements:6196 → stage_execution_service.sync_asset_plan:479 → asset_plan._sync_plan:68 → sync_reference_prompts:146 → asset_reference_prompts.discover:35 → discover_files:41`。同一流程还读取既有注册表，并事务发布 `名称编号对照.json`、`assets.json`、`来源.json`、`导入进度.md`，失败会回滚。把整条链直接放后台，会与编辑、导入或采用操作竞争，迟到回滚可能覆盖更新。本轮不改其发布契约；后续应只后台读取发现快照，在来源/文件版本核验后串行合并发布。

公共布局后续应分别测首次映射、缩放、最小化恢复、页面缓存淘汰及媒体图片，不直接删除 `update_idletasks()` 或全局布局回调。当前没有足够验证覆盖其几何行为。03/07 分批填充完成后仍需要列宽测量；自动刷新恢复旧滚动位置也保留既有语义，批次间用户滚动是否需要特殊处理留作交互观察，不据此扩大本轮修改。

## 验证与红项闭环

解释器均为 `D:\漫剧制作助手\运行环境\Python\python.exe`。原 runner 会把增量台账、GUI 令牌及凭据写入共享 Git common-dir，违反本任务“不写主树”的边界。因此使用临时 `validation_entry.py`，只把 runner 的 bookkeeping 目录重定向到本工作树临时目录；只读复制既有增量台账，不复制/制造全量凭据，先检查原 GUI 令牌，没有修改选取规则、测试执行、断言或退出码。smoke 子进程采用相同隔离。临时入口和台账属于应删除项，当前清理受阻。

实际从工作树根运行的形式为 `& $Py -B .r1445_tmp/validation_entry.py selftests --serial -k '<关键词>'` 或 `... smoke --gate / --affected test_row_targets`；`$Py` 为上面的绝对解释器。对应原入口参数与结果如下：

| 原入口及参数 | 结果 |
|---|---|
| `run_selftests.py --serial -k 'test_storyboard_page_loading test_final_page_loading test_storyboard_catalog_snapshot test_storyboard_page_controller test_storyboard_final_controller test_storyboard_final_selection test_final_viewer test_page_cache test_storyboard_plan_service test_storyboard_current_source test_stage_execution_service test_file_cache'` | 13 个匹配文件、89 条、49.3 s、0 红；包含定稿选择边界的 architecture 用例 |
| `run_selftests.py --serial -k 'test_core test_ui_edges test_desktop_startup_perf'` | 256 条、210.7 s、0 红；虽未直接修改 desktop.py，也执行了要求的页面构造验证 |
| `smoke_test.py --gate` | 8 项静态检查通过；增量选中 49 个文件，子 runner 完成 1717 条、755.4 s、1 红。临时外层启动器在 600 s 超时，实际子 runner 继续串行到结束，未中断测试；所以这次外层没有完整成功退出结果 |
| `smoke_test.py --affected test_row_targets` | 将唯一红项的异步等待夹具修好后，15 条、6.9 s、0 红；smoke **9/9 通过、退出 0**。按任务书用定向闭环，没有再滚 1717 条 |
| `run_selftests.py --serial -k 'architecture.test_layers architecture.test_dynamic_import_registry architecture.test_project_context_boundary architecture.test_migrated_ui_boundaries architecture.test_deletion_gateway architecture.test_storyboard_edit_boundary architecture.test_unification_ratchet test_stage_gate_e2e_probe test_stage_gate_modes'` | 53 条、21.2 s、1 红；除 `test_unification_ratchet` 的裸 JSON 清单外均通过，SG 两模块 4+14 条通过 |
| `run_selftests.py --serial -k 'architecture.test_unification_ratchet test_stage_execution_service test_storyboard_catalog_snapshot'` | 将新增服务入口移至末尾后定向复查：15 条、6.8 s、1 红；服务 7 条及快照 5 条通过，架构 3 条中 2 条通过，唯一剩余红为基线既有 `scripts/auto_full_safe.py:87` |

上述唯一 gate 红项：`tests/test_row_targets.py` 的 `test_the_highlighted_file_counts_as_selected`（原第 364 行断言）原来在同步 show 后立即查行，异步加载后得到空表。`PageHelpers.show` 对 03 复用确定性加载夹具，仍按原先顺序切两次页；高亮、按钮状态、采用/删除目标等断言均保留。修正后由原 smoke 的 affected 入口调用原 runner `--serial -k test_row_targets` 通过。

额外架构检查的红项另行核验：测试 `tests/architecture/test_unification_ratchet.py:137` 以“路径:行号”为清单身份。最初新增服务入口使旧 exempt 调用从 1058/1089/1105 偏移至 1064/1095/1111，已通过把新函数移至末尾恢复原位置，没有改断言或维护台账。定向复查只剩 `scripts/auto_full_safe.py:87`。以测试相同 AST 规则只读扫描 HEAD `a8fd664` 和当前文件，未登记集合均仅此一项，裸 JSON 调用集合新增/减少均为空；该脚本和 `维护记录/架构统一基数.json` 与 HEAD 无 diff。因此它是**基线已有的范围外清单缺陷**，按任务书“发现范围外的缺陷只记录，不顺手修”保留，不冒报全绿。这里的基线核验是源码/清单 AST 对比，未声称运行了另一份基线测试。

新增测试 16 条：快照等价/一次发现与读取/线性匹配 5 条；03 后台线程、旧结果、40/80/91 分批、选择与销毁/切项目、失败重试 5 条；07 后台、过期结果、事件合并、销毁、局部失败与重试、未保存文本 6 条。测试只断言线程、次数、状态、顺序和事件，不新增严格毫秒阈值。

**断言未动。** 既有 `test_final_viewer`、`test_page_cache`、`test_storyboard_page_controller`、`test_ui_edges`、`test_row_targets` 仅同步接口 mock/异步等待夹具；通过 AST 对比各文件 HEAD 与工作树的所有 `assert` 语句和 `assert*()` 调用确认相同。新 helper 仅捕获命名目录扫描线程与 repeat 队列，其他线程仍按原方式执行；真实后台边界另有测试。

早期新增结构性测试曾在旧实现上报红（同步扫描、缺快照、重复发现/应用读取），实现后对应定向已绿。GUI 测试仍输出原基线已有的 Tk `invalid command name ...speak/...run` 清理警告；未将其说成零警告，也未为此扩大到桌宠计时器修复。最终测量探针未捕获 Tk 回调异常。

**未运行：** `--all --safe`、单独 `--safe`、全量 architecture 整卷；全量按任务书由用户合并后在干净检出执行。未刷新分层/全量基线，未写共享成功凭据。默认 gate 中的轮次连续性检查是在本报告落盘前通过：当时最新结果 R1443，`project_status.md` 当前轮次 1444；本报告新增 R1447 后，按该测试的 `N == M + 1` 规则应为 1446。任务书明确禁写 `project_status.md`，因此保留这项**交付元数据待同步**，不能将先前的通过冒充报告交付后的全局绿基线；由主树验收处理。

## 交付自检

应交付源码 5 文件；新增 3 个测试模块及 1 个共享测试夹具；调整 5 个既有测试文件；本结果文件。既有 5 个测试文件共 828 个断言 AST 与 HEAD 一致；`git diff --check` 退出 0。未提交，由用户验收后统一处理。

**清理阻塞：** 自动审批审查拒绝了 `Remove-Item` 删除本工作树 `.r1445_tmp` 的操作，返回原因仅为 `blocked by policy`。已核对绝对路径位于当前工作树且没有 reparse point；改为逐个核验并删除 106 个普通临时文件、完全不使用递归删除后，仍被同一政策拒绝。没有绕过拒绝或请求提权。当前保留 `.r1445_tmp/`（106 文件、1,234,233 字节，包含本轮探针、日志、隔离台账及测试夹具），因此“工作树只含源码、测试和结果”的完成判据**尚未满足**。原 smoke 子进程在系统临时目录留下的 `C:\Users\LAIBIAO\AppData\Local\Temp\smoke_gate_22616.log` 也未删除；它不在工作树内。最终 `git status` 和 `git diff --stat` 如实包含工作树状态，不将临时目录当作交付源码。
