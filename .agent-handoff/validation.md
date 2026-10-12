## 2026-10-13 R1399 UI 路线图 §一 第 2 项（设计 token）第 2 批单页迁移（功能轮 §3.1）

- 类型：功能轮（§3.1），4 个生产页内联常量等值改用 token＋各页 1 处 import；不改业务/阶段/路径/分层、不改字体，颜色仅等值提换。
- 内容：21 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）→ `SPACING['xs'/'sm'/'md']`；`asset_detail.py` 1 处 `bg='#ffffff'`→`COLORS['background_card']`。行号平移同步 2 个基线（TODO注释快照／架构统一基数 第四项）。
- 定向 `test_asset_detail`＋`test_asset_detail_service`＋`test_token_boundary`：**50/50**；`test_api`＋`test_copy_text`＋`test_seedream_direct`：**70/70**。默认冒烟 **8/8**。架构 **341/341**（首次 2 红＝行号平移，定向修绿后复验第 2 次全绿）。
- **全量（§5 五轮必需，1399−1394=5）**：干净 master `o07-fullsafe-master`（reset→`4ed81e9`）`run_selftests.py --all --safe` **4983 条、609.6 秒、0 文件有红、ALL TESTS PASSED**；凭据 tree=`250b6384…`＝`4ed81e9:程序`，`last_full_safe_all_round` 1394→1396。
- 提交：内容 `4ed81e9`；报告／状态／接力本轮收尾提交。注：本轮原领 1397，被并行轮占用，改领 1399。

## 2026-10-13 R1396 UI 路线图 §一 第 2 项（设计 token）单页迁移（功能轮 §3.1）

- 类型：功能轮（§3.1），只改 1 个生产模块的内联间距字面量＋1 处 import；不改业务/阶段/路径/分层，不改颜色/字体。
- 内容：`asset_reference_images.py` 13 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token；新增 `from ui_tokens import SPACING`（纯数据、无环、不新增启动图节点）。零视觉变更（取值相等且间距与调色板无关）。
- 定向 `tests.test_reference_images`＋`tests.architecture.test_token_boundary`：**26/26**。默认冒烟 **8/8**。架构 **341/341**（数量不变）。`test_token_boundary` 该文件数字 `padx/pady` 计数 18→5。
- 不跑全量：`1396−1394=2<5` 且未命中 §5 升级条件。最近绿全量 R1395 `tree=886cfd07…`（4983/4983）。
- 提交：内容 `ac01f9f`；报告／状态／接力本轮收尾提交。

## 2026-10-13 接力收尾 — 更新项目阻塞项与待办任务清单（R1395 已收口）

- 类型：接力收尾（纯文档），不改生产代码／测试／台账／路线图。
- 内容：`程序/project_status.md`「已知阻塞与待办」将 R1393「【待裁定·R1393 → 拟 R1394】agent 包进程／网络真候选」收口为「【已收口·R1394／R1395】agent 包进程原语与出站 HTTP 真候选」（进程 2 处→`platform_tools.run_process`、出站 2 处→`platform_tools.open_https`；覆盖率审计21／26 清零、判据第 21／26 项真候选 0）；状态表覆盖率审计棘轮行补 R1394／R1395 收口结论。`.agent-handoff/backlog.md`／`snapshot.md` 已由前两轮接力收尾更新至 R1395，无需再改。
- 校验：`tests.architecture.test_round_baselines`（被断言文件，含 `project_status.md` 轮次头＝最新结果轮次+1）＋默认冒烟 `smoke_test.py`；纯文档无行为变更，不跑全量／架构全表。最近绿全量 R1395 `tree=886cfd07…`（4983/4983）。

## 2026-10-13 R1395 出站 HTTP 收口到 platform_tools.open_https（修复轮 §3.2）

- 类型：修复轮（§3.2），新增 platform_tools 出站 HTTP 入口 + 改 2 处 agent/core 调用 + 台账／判据同步。
- 实现：`platform_tools.open_https(url,*,timeout=60,data=None,headers=None)`（惰性 import urllib.request）；`agent/core.py` `request()`／`download()` 出站调用改经它，行为/错误分类/发布语义不变。
- 台账／判据：`覆盖率审计26` pending→migrated（2 条）、count 2→0；判据第 26 项真候选 2→0。
- 定向 `tests.architecture.test_coverage_audit_ratchet`＋`test_unification_ratchet`：**7/7**。默认冒烟：**8/8**。架构：**341/341**（数量不变）。运行期本地 HTTP 服务下 `request` 返回预期 JSON。
- **全量（§5 五轮必需，1395−1390=5）**：干净 master `o07-fullsafe-master`（reset→`d93993e`）`run_selftests.py --all --safe` **4983 条、602.9 秒、0 文件有红、ALL TESTS PASSED**；凭据 tree=`886cfd07…`，`last_full_safe_all_round` 1390→1394。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无阈值抖动。
- 提交：内容 `d93993e`；报告／状态／接力本轮收尾提交。

## 2026-10-13 R1394 agent 进程原语收口到 platform_tools（修复轮 §3.2）

- 类型：修复轮（§3.2），改 2 处生产模块进程调用 + 台账／判据同步。
- 实现：`agent/core.py` `command()` → `platform_tools.run_process`（惰性 import，移除 `import subprocess`）；`agent/prompt_optimizer.py` MCP 桥 → `platform_tools.run_process`（模块级 import，保留 `subprocess` 异常类型）。行为与异常类型不变。
- 台账／判据：`覆盖率审计21` pending→migrated（2 条）、count 2→0；`第四项` `json.loads` 行号 13→12、174→175；判据第 21 项真候选 2→0。
- 定向 `tests.architecture.test_coverage_audit_ratchet`＋`test_unification_ratchet`：**7/7**。默认冒烟 `smoke_test.py`：**8/8**。架构 `smoke_test.py --architecture`：**341/341**（数量不变）。运行期：`agent.core.command(['python','-c','print(12345)'])` → `'12345\n'`；缺程序 → `RuntimeError`。
- 不跑全量：`1394−1390=4<5` 且未命中 §5 升级条件。最近绿全量 R1391 `tree=a8cfd2f0…`。
- 提交：内容 `a966c41`；报告／状态／接力本轮收尾提交。

## 2026-10-13 接力收尾 — 更新项目阻塞项与待办任务清单（R1393 已收口）

- 类型：接力收尾（纯文档），不改生产代码／测试／台账／路线图。
- 内容：`程序/project_status.md`「已知阻塞与待办」补登 R1393（覆盖率审计棘轮递归化已收口＋4 条 agent 进程／网络真候选 pending 待裁定，拟定 R1394 经 `platform_tools.run_process` 收口 2 处 subprocess）；校正「§三 覆盖率审计 7 项全部收口（R1390＋R1391）」；状态表新增一行。`.agent-handoff/backlog.md` 表头由 R1391 补到 R1393（`8f1a1fc` 已提交）。
- 提交：`14409cd`。收尾后安全复验（纯文档，但属被断言文件）：`tests.architecture.test_round_baselines` **5/5**、默认冒烟 `smoke_test.py` **8/8**；无行为变更，不跑全量／架构全表。最近绿全量 R1391 `tree=a8cfd2f0…`（4983/4983）。

## 2026-10-12 R1393 覆盖率审计棘轮口径递归化（修复轮 §3.2）

- 类型：修复轮（§3.2），只改架构扫描辅助／覆盖率审计棘轮与台账／判据文档，不改生产代码。
- 实现：`_scan.production_runtime_files()`（递归再排除 skills／scripts／reference／outputs／附加工具，239 模块）；`scan()` 默认范围改它、台账键改相对 `程序/` 的 posix 路径 `_key()`；台账覆盖率审计21／26 各 +2 pending（count 21→2、26→2、26 baseline_pending 1→2）；判据文档第 21／26 行真候选 0→2。
- 新暴露真候选（pending）：`agent/core.py:173`、`agent/prompt_optimizer.py:172`（subprocess）；`agent/core.py:189`／`208`（urllib）。
- 定向 `tests.architecture.test_coverage_audit_ratchet`＋`test_unification_ratchet`：**7/7**。默认冒烟 `smoke_test.py`：**8/8**。架构 `smoke_test.py --architecture`：**341/341**（数量不变）。
- 不跑全量：`1393−1390=3<5` 且未命中 §5 升级条件（无启动路径／Tk 生命周期／删除语义／层级表改动）。最近绿全量 R1391 `tree=a8cfd2f0…`。

## 2026-10-12 R1391 项目进入路径覆盖门禁（修复轮 §3.2）

- 类型：修复轮（§3.2），只新增架构门禁测试与 `AGENTS.md` §5 清单登记，不改生产代码。
- 实现：新增 `tests/architecture/test_project_entry_boundary.py`（5 条）：冻结 `desktop.py` 直接 `self.load(...)` 的进入入口集合（进入 open_project_or_cleanup／_choose_project_impl／new／import_json／enter；关闭 gone／completed）；每条进入路径必须经当天选择记忆；`DesktopStartupController` 单次装配并绑定 `choose_project`／`before_project_choice`；当天选择委托 `publish_desktop_preferences`；控制器模块不 import tkinter。
- 反向验证（mutation）：向 `switch()` 注入未登记 `self.load(path)` → `entering` 多出 `switch`，门禁失败。
- 定向 `tests.architecture.test_project_entry_boundary`：**5/5**。默认冒烟 `smoke_test.py`：**8/8**。架构 `smoke_test.py --architecture`：**341/341**（336→341，+5）。
- 全量（§5 五轮规则 1391−1386=5 触发）：干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` **4983 条、546.4 秒、0 文件有红**；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无抖动。凭据 `{round:1390, tree:a8cfd2f0…, at:2026-10-12T23:44:43}`＝`37ed5bc:程序`；`last_full_safe_all_round` 刷新为 1390。
- 提交：内容 `37ed5bc`；报告／状态／接力见后续补记。§三 7 项全部收口。

## 2026-10-12 R1390 §三 覆盖率门禁口径对齐递归（修复轮 §3.2）

- 类型：修复轮（§3.2），只改架构门禁测试文件与新 `_scan` 辅助，不改生产代码。
- 实现：`_scan.production_files_recursive()`（递归口径，排除 tests／tasks_round／维护记录／.git／__pycache__ 与 smoke_test／run_selftests／selftest_sandbox 及 test* 前缀）；`test_deletion_gateway`／`test_remove_authority`（程序 scripts/ 开发脚本显式豁免 `_DEV_SCRIPT_PARTS`）／`test_completion_gate`（2 处）／`test_event_bus_boundary`（3 处）改递归扫描。
- §三 7 项裁定：6 项已收口（第 2 事件总线／第 5 删除／第 6 阶段完成＝本轮升递归；第 1 配置读写／第 3 缓存失效／第 7 SKILL 说明标签＝已有门禁）；1 缺口＝第 4 项项目进入路径（`DesktopStartupController`）缺架构覆盖门禁（登记待办）。
- 验证：定向 `tests.architecture`（4 文件）**8/8**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **336/336**（数量不变，改既有门禁）。
- 不跑全量：`1390−1386=4<5` 且未命中 §5 升级条件（无启动路径／Tk 生命周期／删除语义／层级表改动）。最近绿全量 R1387 `tree=000477da…`。
- 提交：内容＋报告＋接力 `fdb1daf`（含 `.agent-handoff/backlog.md`／`snapshot.md`）；报告与状态页补记 `c7e40e8`；本轮刷新阻塞项／待办清单（`.agent-handoff/risks.md`／`backlog.md`）。

## 2026-10-12 R1389 设计 token 内联常量棘轮门禁（修复轮 §3.2）

- 类型：修复轮（§3.2）。新增 `tests/architecture/test_token_boundary.py`（5 条）：内联 hex 与数字 padx/pady 按文件棘轮「只减不增」（新增文件即违规）；权威 ui_tokens/ui_theme/ui_widgets/ui_icons 与 skills 脚本豁免；基线＝R1388 审计值（hex 111/8、padx/pady 213/19）。`AGENTS.md` §5 清单补该文件。不改生产代码。
- 未纳入棘轮：数字 font/wraplength/width/height 候选 189/32（width/height 部分属布局），只审计。
- 定向 `tests.architecture.test_token_boundary`：**5/5**。默认冒烟 `smoke_test.py`：**8/8**。架构 `smoke_test.py --architecture`：**336/336**（331→336）。
- 不跑全量：`1389−1386=3<5` 且未命中 §5 升级条件（无启动路径／Tk 生命周期／删除语义／层级表改动）。最近绿全量 R1387 `tree=000477da…`。

## 2026-10-12 R1388 设计 token 内联视觉常量审计（只读诊断 §3.5）

- 类型：只读诊断轮（§3.5）。只读扫描 269 个生产 `.py`；不改生产代码/测试/台账/路线图。
- 发现：业务页内联 hex **111 处/8 文件**；数字 padx/pady **213 处/19 文件**；数字 font/wraplength/width/height 候选 **189 处/32 文件**；ui_tokens（14 hex）与 ui_theme（53 hex）双调色板并存且 ui_theme 未 import ui_tokens；无 token 专用门禁。
- 测试：§5 只读诊断默认不跑测试；附加默认冒烟 `smoke_test.py` 8/8（不计验收）。**不跑全量**（距最近绿全量 R1387 `tree=000477da…`、`last_full_safe_all_round=1386` 仅 2 轮，无生产改动）。
- 登记 backlog：先统一调色板、逐页迁 hex、加 `test_token_boundary.py` 棘轮门禁（只减不增）；padx/pady 与字号按单页粒度另批。

## 2026-10-12 R1387 按钮门禁递归零容忍（修复轮 §3.2）

- 类型：修复轮（§3.2），只改架构门禁测试文件，不改生产代码。`test_button_boundary` 由「固定页清单」升为「递归零容忍」：`BUTTON_OWNERS={'ui_widgets.py'}`＋`EXCLUDED_PARTS`；`test_production_modules_use_semantic_buttons`（`ROOT.rglob('*.py')`、裸 `tk/ttk.Button` 零容忍）＋`test_recursive_scan_covers_subdirectories` canary。
- 站点实测：269 个生产 `.py` 除 `ui_widgets.py` 外 0 命中。
- 定向 `tests.architecture.test_button_boundary`：**25/25**（原 23）。默认冒烟 `smoke_test.py`：**8/8**。架构 `smoke_test.py --architecture`：**331/331**（329→331）。
- 全量（§5 五轮规则 1387−1382=5 触发）：干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` **4973 条、572.5 秒、0 文件有红**（凭据 round=1386、tree=`000477da…`＝`d5f597f:程序`；`last_full_safe_all_round` 刷新为 1386）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无抖动。
- 提交：内容 `d5f597f`；报告／状态／接力另一次提交。

## 2026-10-12 R1386 阶段显示收口（修复轮 §3.2）

- 类型：修复轮（§3.2）。新增权威入口 `pet_bus.stage_label(stage)`＝`'%02d %s' % (STAGES.index+1, STAGE_NAMES[stage])`，6 个用户可见展示位点（keyframe_batch 4／stage_parallel GATES SG-01..05／pet_ui gaps／desktop 视频页标题×2＋镜头编号提示／skill_tools 导出 note）改由它现算；生产注释／docstring 过期编号按权威序纠正；不改业务逻辑／阶段／路径／分层。
- 门禁：`tests/architecture/test_stage_display_boundary.py` 新增 3 条（生产「NN 阶段名」编号==STAGES 步号，豁免 stage_path_service；6 展示位点冻结；stage_label 对齐导航序）；架构 326→**329**。
- 定向 `run_selftests.py -k ...`：**1275 条、0 文件红、305.5 秒**。默认冒烟 `smoke_test.py`：**8/8**。
- 全量（路线图条目收口触发 §5）：干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` **4971/4971、0 红、534.1 秒**（凭据 round=1382、tree=`d9aee73c…`＝内容提交 `4cb02d3:程序`；同一内容树不重跑第二次）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无抖动。
- 提交：内容 `4cb02d3`（26 files）；报告／状态／接力另一次提交。审计口径更正 97→96。

## 2026-10-12 R1382 状态接续轮（只读审计 + 状态/接力更新）

- 类型：状态接续轮（§3.11）。不改生产代码，只更新 project_status.md「已知阻塞与待办」、接力文件与结果报告；未触生产文件，故 §5 无升级触发。
- 默认冒烟 smoke_test.py：8/8、0 失败（含「13 个制作阶段路由仍完整」，确认权威序与显示名）。
- 只读审计：生产文案「NN 阶段名」过期编号；扫描口径＝对 pet_bus.STAGE_NAMES 每个显示名匹配 (\d{1,2})\s*名称，序号≠STAGES 序即命中，排除 stage_path_service.LEGACY_NUMBERED。结果＝生产 14 文件 97 处＋tests/ 19 文件 56 处（登记为待办，未实现）。
- 未跑全量（无生产改动、未命中 §5；最近绿全量 R1380、tree=f62cd088、last_full_safe_all_round=1380，且 1382−1380=2<5）。

## 2026-10-12 R1381 弹窗门禁递归化

- 类型：修复轮（§3.2）。`tests/architecture/test_dialog_boundary.py`：扫描 `ROOT.glob` → `ROOT.rglob`，排除 `{tests,tasks_round,维护记录,.git,__pycache__}`，保留 `TOPLEVEL_OWNERS`；谓词加名字式识别；+1 canary。
- 结果：该文件 6/6；定向 `-k "dialog prompt_window qwen tts_settings cloud_assets"` 24/24、0 文件红；默认冒烟 8/8；架构 `--architecture` 326/326（原 325），0 红。
- 全生产模块（含子目录）裸 `Toplevel` = 0（仅 `ui_widgets.py` 除外）；未跑全量（1<5 且未命中 §5），无欠账。

## 2026-10-12 UI 统一入口覆盖轮完成（R1376—R1380）

- R1376 忙碌态／R1377 文案与复制／R1378-R1379 卡片容器／R1380 文字层级；各轮定向＋默认冒烟 8/8、0 红；架构 315→320→321→323→325。
- R1380 命中 §5 五轮规则（1380−1375=5≥5）：干净 master `o07-fullsafe-master` `run_selftests.py --all --safe` **4967/4967、0 红、631.2 秒**（首次即绿）；凭据 round=1380、tree=f62cd088…（＝该轮内容提交 `e25c70d:程序`，**不**等于最终 `HEAD:程序`＝3c0d7ead…；其后记账提交只改报告与状态页）、last_full_safe_all_round=1380；同树架构 325/325；性能阈值类用例无抖动。五轮门禁 `latest−last_full=0<5` 提前返回仍绿（已实跑 test_round_baselines 5/5 OK）。提交 e25c70d（内容）＋633eb4e（补记）。
- R1376-R1379 因欠账 <5 且未命中 §5 升级条件（启动路径/Tk 生命周期/删除语义/层级登记表均未改），按用户「不因收尾跑全量兜底」不跑全量。

## 2026-10-12 O48 完成

- 2026-10-12 O48（R1375）：`pet_bus.stage_step(stage)` 成为阶段步号唯一权威（按 `STAGES` 顺序两位步号，与阶段目录／导航页同源）；13 个生产模块的用户可见文案改由它现算，纠正旧步号（分镜 02→03、资产 03→05、定稿 04→07、首帧 05→08、白模 06→09、视频 07→10，共 24 处）。`architecture.md` §4／§5／§8 三表补齐为 13 行并与 `pet_bus.STAGES`／`stage_parallel.CONFIG` 同源，`README.md` 历史目录树加「历史记录」提示（不动历史正文）。
- 测试：架构 `smoke_test.py --architecture` **315/315**（原 312，+3 新用例：阶段表逐行同源／并行表逐行同源／生产文案「第N步」只许来自 `pet_bus.stage_step`）；定向 `-k "video white_model project_open row_targets asset workflow ui_edges pet_ui engine storyboard local_video batch_frames critical_chains shot_assets"` **1456 条／386.7 秒**，仅 1 红为既有环境相关（`test_workflow` 桌面模型标签：主树未跟踪模型池把 `claude-desktop` 标成「Claude Desktop」，出厂池为「Claude Code」；干净工作树单跑为绿）；交互验收 `tests.test_asset_detail tests.test_ui_theme tests.test_ui_widgets_inputs tests.test_idea_chat tests.test_video_ui` **244/244**（`tk scaling` 1.0／1.5／2.0、`<Return>` 发送、takefocus／焦点回归、禁用控件说明）；默认冒烟 **8/8**。
- 登记平移：`架构统一基数.json` 第四项 `batch_frames.py` point 13→14／77→78；`TODO注释快照_20261003.json` `asset_detail.py` 350→351；`skip台账.json` 用例更名 `..._points_to_step04`→`..._points_to_step07`。
- 全量：1375−1374=1<5，但 O48 为 R1267 路线图收口项（§5）→ 收口在干净 master 工作树 `o07-fullsafe-master` 跑 `--all --safe`：**4957/4957、0 红、715.1 秒**（首次即绿）；凭据 round=1375、tree=c3df6a57…（＝`afcc0a4:程序`＝`HEAD:程序`）、at=2026-10-12T19:33:12、last_full_safe_all_round=1375；4957−4954=3＝本轮新增架构用例；性能阈值类用例绿、无抖动。提交：内容 d5de4df、报告与接力 afcc0a4、收尾补记见 R1375 报告。
## 2026-10-12 O47 完成

- 2026-10-12 O47：新增 `程序/tests/test_critical_chains.py` 17 条（链路 A 回收站 O38/O39、链路 B 模型请求链、链路 C 导入→完成证据 O02/O03、链路 D 剧本→结构→分镜、O04 返工门禁、O05/O06 首帧门禁）；无生产代码改动。测试：`-k critical_chains` 17/17；定向 `-k critical_chains recycle audio_import stage_completion delivery_import script_contract stage_flow` 187/187；架构 312/312；默认冒烟 8/8，0 红。未命中 §5（只新增测试文件）。全量：1374−1373=1<5，收口在干净 master 跑一次 `--all --safe`（4954/4954、0 红、665.09 秒；凭据 round=1374、tree=4778c99e…＝`HEAD:程序`、last_full_safe_all_round=1374；4954−4937=17＝本轮新增用例）。
## 2026-10-12 O46 完成

- 2026-10-12 O46：新增无 Tk 热点探针 `程序/维护记录/基准脚本/基准_热点路径.py`（换项目／刷新目录／长对话／媒体导入；合成负载 24 项目／1500 文件／800 条消息／400 文件），结果 `基准结果_热点路径.json`；Tk 侧复用 `基准_启动与页面.py full`（改前留档 `基准结果_启动与页面_full_改前.json`）。两段保持入口的迁移：`platform_tools.py`（L0）新增 `open_directory`／`find_editor_shortcut`，`idea_chat_controller.py`（L3）新增 `bubble_timestamp`／`collapse_preview`／`speaker_name`，`desktop.py` 的 5 个入口变 1 行委托（7510→7491 行）。测试：新增 `tests/test_idea_chat_presentation.py` 10/10、`tests/test_platform_tools.py` 20/20（+3）；定向 `-k platform_tools idea_chat_presentation` 30/30；Tk 消费者 `-k ui_edges idea_chat unification_ratchet` 259/259；架构 312/312；默认冒烟 8/8，0 红。未命中 §5（无启动路径、无 Tk 控件生命周期、无删除语义、未改 `_layers.py`）。全量：1373−1372=1<5，收口在干净 master 跑一次 `--all --safe`（4937/4937、0 红、710.39 秒；凭据 round=1373、tree=efdd7f8a…＝`HEAD:程序`、last_full_safe_all_round=1373；4937−4924=13＝本轮新增用例）。

## 2026-10-12 O45 完成

- 2026-10-12 O45：新增 `程序/scripts/distribution_build.py`（`parse_manifest`／`pattern_regex`／`plan`／`build`／`verify`／CLI `--plan|--build|--verify`），精化 `程序/distribution_manifest.md`（补保留／排除行＋「可复验构建器」一节）。实测 `--plan`：keep 1170／excluded 4684／undecided 36。测试：新增 `tests/test_distribution_build.py` 12/12；定向 `-k distribution_build` 12/12；架构 312/312；默认冒烟 8/8。未命中 §5（只新增 scripts/ 工具与文档）。全量：1372−1371=1<5，收口在干净 master 跑一次 `--all --safe`（4924/4924、0 红、688.63 秒；凭据 round=1372、tree=71554aa7…＝`HEAD:程序`、last_full_safe_all_round=1372）。

## 2026-10-12 O44 完成

- 2026-10-12 O44：`model_secrets.py`（L1）新增 `_BLOB_HEADER`／五状态常量／`looks_like_blob`／`diagnose`／`verdict`；`diagnostic_capture.py`（L1）新增 `redact`／`retention_note`／`preview_detail`（含 keep_days／expires_at／expired）与 URL 查询参数脱敏分支；`model_diagnostics.py`（L1）新增 `_scrub`（context／response_meta 落盘前脱敏）。测试：新增 `tests/test_secret_status_diagnostics.py` 13/13；定向 `-k secret_status_diagnostics diagnostic_capture model_diagnostics model_pool pet_llm writing_api hollmwood_roles pet_settings` 269 条、仅 test_model_pool 1 条既知主树环境红（路径限定 git stash 复现：与本改动无关）、`-k test_api test_recycle` 全绿；架构 312/312；默认冒烟 8/8。全量：1371−1370=1<5、未命中 §5，收口在干净 master 跑一次 `--all --safe`（4912/4912、0 红、752.38 秒，凭据 round=1371、tree=de0084a9…）。

## 2026-10-12 O43 完成

- 2026-10-12 O43：`skill_orchestrator.py`（L3）新增 `CHECKPOINT_VERSION`／`checkpoint_digest()`；`before_step(..., skills=None)` 写 `version`／`at`／`project`／`skills`／`digest` 且「写成功才认内存状态」；新增只读 `resume_preview()`（`continue`／`skip`／`verify` 逐步判定＋工具调用完成/阶段成果完成分开＋`paid` 列表＋`text`）。测试：新增 `tests/test_resume_preview.py` 12/12；定向 `-k resume_preview skill_registry skill_budget skill_templates skills workflow_settings workflow_tasks pet_agent pet_state stage_flow` 318/318；`-k test_pet_ui skill_panel` 586/586；架构 312/312；默认冒烟 8/8；`test_workflow` 主树 1 条红为既知主树环境项。全量：1370−1369=1<5、未命中 §5，收口在干净 master 跑一次 `--all --safe`（4899/4899、0 红、963.97 秒，凭据 round=1370、tree=4a7be90a…）。

## 2026-10-12 O42 完成

- 2026-10-12 O42：`pet_bus.py`（L0）新增 `PENDING_LIMIT`／`ERROR_LIMIT`／`ERROR_PERSIST_LIMIT`／`SHEDDABLE_EVENTS`／`is_sheddable`；`Bus.publish` 入队前合并重复上报（记 `dropped`）、待处理数到 `pending_limit` 时只让 `SHEDDABLE_EVENTS`（`stage.executing`／`notify.aggregate`）让路（记 `shed`），终态与 `stage.paused` 永不丢弃；`errors` 有界环形＋`errors_total`＋`bus.subscriber.error` 持久诊断；新增 `pending`／`water`／`stats()`／`unsubscribe`／`release`。测试：新增 `tests/test_pet_bus_backpressure.py` 15/15；定向 `-k pet_bus pet_agent pet_state stage_flow skill_orchestrator` 186/186；`-k test_pet_ui test_pet_cloud` 606/606；架构 `--layer architecture --all` 312/312；默认冒烟 8/8；0 红。合成测量：重复上报 200000 条 `qsize()==1`、异常 20000 次 `len(errors)==64`。全量：1369−1368=1<5、未命中 §5，收口在干净 master 谱系工作树 `o42-fullsafe-master` 跑一次 `--all --safe`：4887/4887、0 红、547.7 秒，凭据 `round=1369`、`tree=0ed4726b…`、`last_full_safe_all_round=1369`。

## 2026-10-12 O41 完成

- 2026-10-12 O41：`desktop_automation_service.py`（L3）`BackgroundTaskLifecycle` 新增 `submit(ticket, *, remote_task_id=None, costly=False)`、`cancel(ticket=None, *, costly=False, remote_task_id=None, remote_cancel_requested=False, remote_cancel_confirmed=False)`、`cancellation_status(ticket=None)`（`remote` ∈ confirmed／pending／not-requested／unknown；`text` 给界面直接用的三态说明＋可查询编号＋「远端确认前不能当作未计费」；普通任务返回 None）与有界 `late_results()`（`finish` 对被拒迟到结果登记、不改 `snapshot()`）；新增常量 `LATE_RESULT_LIMIT=8`。`stage_execution_service.py`（L3）新增 `publish_response_archive(project, text)`（经 `publish_stage_text` 原子归档到 `01剧本准备/responses/`，只归档不采用）并在 `reply_to_writing` 注入 `archive=`。`writing_api.py`（L3）`reply(..., archive=None)`＋`_archive_returned_response`／`_archive_note`／`_archive_then_require_active`：在取消检查前先给已返回可见正文留档、路径写进取消错误；覆盖 messages 与普通对话两条出口，默认 None 时既有行为逐字不变。`desktop.py`（L4）`interrupt_script_agent` 按是否在调 API 标 `costly` 并合并三态说明／编号／归档提示（无 API 时不提计费）、`_tick_async_result` 先判归属再判代次（迟到只登记不交付）、`close()` 确认框补远端计费提示。 新增 `tests/test_cancellation_status.py` 13/13；定向 131/131、关联 253/253、架构 312/312、默认冒烟 8/8，0 红。契约变化：`snapshot()` 不变、普通任务 `cancellation_status()` 为 None、`finish` 增加迟到登记副作用、`reply` 新增仅关键字 `archive`。未新增顶层模块／裸 json.loads／L2 直写／skipTest；把新函数置于 `stage_execution_service.py` 末尾、桌面改动压成等行数单行以避免行号位移，故未改 `架构统一基数.json` 与 `TODO注释快照`。1368−1367=1<5 且未命中 §5；收口在干净 master 工作树跑一次 `--all --safe`：第 1 次 4872/4872、0 红、524.6 秒但因工作树为 detached HEAD 未写凭据（`is_master_checkout()` 为假，凭据只记主干提交序列），把该工作树 HEAD 指向 `refs/heads/master`（仍停在 `467843e`、树干净）后第 2 次 4872/4872、0 红、537.3 秒并写凭据：`round=1368`、`tree=dd48d82b…`（＝内容提交 `467843e:程序`）、`last_full_safe_all_round=1368`；`test_desktop_startup_perf`／`test_perf_baseline` 两轮均绿，无阈值抖动。。

## 2026-10-12 O40 完成

- 2026-10-12 O40：`projects.py`（L2）新增 `_drop_registration_entry(path, *, message=None)`（先改 `deepcopy`、发布成功才提交 `self.info`；`OSError` 时把内存回退到磁盘事实并带 `ui_message` 重抛），`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它；`_project_write_result` 的 `OSError` 分支优先用 `exc.ui_message`，删除路径给出「内容已移入回收站、可『重新查找项目』或『重建项目索引』、仍可从回收站恢复」的定向指引。新增模块级 `_discover_candidates(base)`（把 `reconcile_missing` 的一级目录扫描抽出复用、返回与匹配规则不变）与 `Projects.rebuild_registry()`（保留 `path` 仍在的登记、移除失效登记、补登 `_discover_candidates` 新目录；`active` 失效落到首个有效项目或 `None`；无变化返回 `changed=False` 不写盘）；`desktop.py`（L4）新增 `Desktop.rebuild_project_index()` 与主页「重建项目索引」按钮，主页状态栏与删除确认框把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述。新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149、架构 `--layer architecture --all` 312/312、默认冒烟 `smoke_test.py` 8/8，0 红。契约：删除／清除路径登记写失败时内存与磁盘登记都停在删除前状态（不再内存先清、磁盘后留）；新增 L2 `rebuild_registry`；「永久清除」只做界面单独明示、未新增永久删除入口（`projects.py` 只回收，无 `rmtree`／`unlink()`）；「从备份恢复」按项目库回收站（删除前可恢复副本）实现与验证，未新建独立备份子系统。未新增顶层模块（`_layers.py` 未动）、未新增裸 `json.loads`／L2 直写／`skipTest`／动态导入；未改启动路径与 Tk 控件生命周期（只新增普通按钮与状态栏文案）。命中 §5 删除语义，收口在干净 master 工作树 `o40-fullsafe-master` 跑 `--all --safe`：第 1 次为新工作树环境未就绪（缺 4 个嵌套仓库与 3 个忽略运行文件）假红，补齐后定向修绿，第 2 次 4859/4859、0 红、527.6 秒，凭据 round=1367、tree=1d7630f1（＝`HEAD:程序`），`last_full_safe_all_round=1367`。
## 2026-10-12 O39 完成

- 2026-10-12 O39：`storage_maintenance.py`（L1）新增 `EXPORT_MANIFEST_NAMES`／`SETTLED_STATES`／`RETAIN_UNSETTLED`／`RETAIN_LOCKED`／`RETAIN_EDIT_SOURCE`／`RETAIN_APPROVED`／`RETAIN_LATEST`／`RETAIN_FRESH`／`RETAIN_REASONS`／`VERSION_CLEAN_REASON`，新增 `edit_source_versions(root)`（只读 `13质检交付/导出成片` 下的成片清单 `edit_bundle.json`／`edit_manifest.json`，取被引用的 `(镜头,版本)` 与 `(镜头,sha256)`）与 `version_retention(version, shot, newest, referenced, digests, now)`（保留口径：未结算含未知状态／用户锁定／已进成片来源／`review==pass`／最新版／不足 7 天；缺 `created` 按未到期保守留住）；`clean_project` 先取引用图、台账扫描排除回收区（回收站里的旧台账不再当生产目录），逐版先问 `version_retention`，只有定局且无引用的过期旧版才回收并写 `cleaned_reason`。新增 `tests/test_video_retention.py` 12/12；定向 `-k storage exit_maintenance force_quit integration core video edit retention adaptation cleanup recycle pet_report` 536/536、架构 `--layer architecture --all` 312/312、默认冒烟 `smoke_test.py` 8/8，0 红。契约：版本清理新增 4 类保护（成片来源引用／已验收通过／用户锁定／非定局状态），`AGE_SECONDS` 与「最新版必留」不变；只读成片清单、未改 engine 采用口径、未新增跨层导入（只用 L0 `project_stages` 与 L1 `file_cache`）。未新增顶层模块／裸 json.loads／L2 直写／skipTest。1364−1363=1<5 无五轮欠账，但命中 §5 删除语义，收口在干净 master 工作树 `o07-fullsafe-master`（HEAD=597f787）跑 `run_selftests.py --all --safe`：第 1 次 4844/4844、0 红、483.2 秒，凭据 `round=1364`、`tree=0db16c0f…`（＝`HEAD:程序`）、`last_full_safe_all_round=1364`；`test_desktop_startup_perf`／`test_perf_baseline` 本轮均绿。

## 2026-10-12 O38 完成

- 2026-10-12 O38：`storage_maintenance.py`（L1）新增 `MANIFEST_NAME`／`BATCH_PREFIX`／批次态 `BATCH_PLANNED`／`BATCH_COMMITTED`／`BATCH_ROLLED_BACK`／逐项态 `ITEM_PLANNED`／`ITEM_MOVED`／`ITEM_FAILED`／`ITEM_UNDONE`，新增 `batch_name`（秒级时间＋UUID8）、`_write_batch_manifest`、`plan_recycle`、`move_planned`、`_undo_moves`、`rollback_recycle_batch`；`recycle_paths` 改为「写前计划先落盘 → 逐项移动并随时落盘 → 全成功写 committed；任一项 OSError 记 failed 与原因、撤回已搬项、落 rolled_back、原样重抛」；`restore_recycle_batch` 跳过回收站里确无该文件的 planned／failed 记录（不挡同批其余项），`restore_latest_recycled_path`／`restore_latest_recycled_child` 跳过 rolled_back 批次，`read_recycle_batch` 纯追加 `state`，`clean_project` 走同一写前计划。新增 `tests/test_recycle_write_ahead.py` 9/9；更新 `tests/test_pet_report.py` 71/71；定向 `-k recycle storage retention deletion_gateway remove_authority exit_maintenance force_quit pet_report video_ui` 213/213、`-k asset keyframe storyboard projects skill_panel stage_execution codex_skill reference_images` 441/441、架构 `--layer architecture --all` 312/312、默认冒烟 `smoke_test.py` 8/8，0 红。契约变化：每次 `recycle_paths` 调用独立 UUID 批次（旧同秒合并行为移除）、多路径调用整批原子（单路径语义不变）；需迁移的既有断言只有 `tests/test_pet_report.py` 的「同清单 2 条」。未新增顶层模块／裸 json.loads／L2 直写／skipTest；`架构统一基数.json` 无需改（本轮无新增扫描命中）。1363−1361=2<5 无五轮欠账，但命中 §5 删除语义，收口在干净 master 工作树 `o07-fullsafe-master`（HEAD=bcc2dff）跑 `run_selftests.py --all --safe`：第 1 次 4832/4832、0 红、425.6 秒，凭据 `round=1363`、`tree=f19816aa…`（＝`HEAD:程序`）、`last_full_safe_all_round=1363`；`test_desktop_startup_perf`／`test_perf_baseline` 本轮均绿，无阈值抖动。

## 2026-10-12 O37 完成

- 2026-10-12 O37：`model_pool.py`（L1）新增分层常量 `PROBE_DIMENSIONS`（connectivity／protocol／model_id／capabilities／full_task）、`PROBE_DIMENSION_LABELS`、`PROBE_FULL_TASK_STATE`／`PROBE_FULL_TASK_NOTE`、`PROBE_WIRE_FIELDS`、`VERIFY_TOKENS`／`SAMPLE_PROMPT`、`TASK_TRUNCATED`、`HEALTH_KEY`；新增纯函数 `config_version`／`request_spec`／`body_signals`／`_full_task_check`／`classify`／`probe_summary` 与 `health`／`health_of`／`record_health`；`probe` 改经共享 `request_spec`，返回体追加 `config_version`／`signals`／`checks`／`summary`／`full_task`（原键与「连接成功，延迟」不变）；新增 `verify_sample`（真实短请求判完整任务）。`pet_models_ui.py`（L4）新增 `probe_breakdown`／`verify_line`，`probe_line` 追加分层说明，模型配置页加「小样本验证」按钮（只在默认模型这一条上发一次）与 `probe_sample` seam。`tests/test_model_probe_layers.py`（新）16 条。定向 `-k model_pool pet_models model_router model_diagnostics pet_ui token_saver request_ledger model_probe_layers` 771 条 1 红（主树未跟踪用户配置的桌面模型标签环境项；干净工作树该用例绿）；`-k pet_settings copy_rules line_endings skip_hygiene model_probe_layers model_pool` 中 copy_rules／pet_settings／skip_hygiene／model_probe_layers 全绿，2 红同为环境项（桌面模型标签＋主树 `desktop.py` 行尾 LF）；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8。同步 `架构统一基数.json` 第四项 `model_pool.py:576→808`、`:613→845`。未新增 skipTest／裸 json.loads／顶层模块，`_layers.py` 未动。1362−1361=1<5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O36 完成

- 2026-10-12 O36：`workflow_context_budget.py`（L0）新增 `estimate_tokens`／`text_fingerprint`／`budget_sections`／`default_safety_margin`／`dominant_sections`／`budget_split_options`／`context_budget_report`／`budget_advice`／`context_budget_error`；`prepare_request_context`／`ensure_request_context` 新增可选 `sections`／`context_limit`／`output_reserved`／`safety_margin`／`report`，超限抛错不截断。`writing_api.py`（L3）`DIRECT_REQUEST_CONTEXT_MAX_CHARS = REQUEST_CONTEXT_MAX_CHARS`；新 `_messages_text`；`_context_budget_error` 追加 `budget_advice`；`WritingRequestAdapter._call` 用 `context_budget_report` 重建 `context_budget`（新增 `sections`／`dominant`／`projected_tokens`／`fingerprint`，保留旧键）。`hollmwood_roles.py`（L2）`_ensure_context_budget(..., context_limit, output_reserved)`；`_ask` 取 `adapter.record` 的 `context_length` 并按最坏情况预留输出，越限在调用前拒绝。`desktop.py`（L4）三处 `prepare_request_context(..., report=True)`。`tests/test_context_budget_model.py`（新）14 条。定向 `-k writing_api hollmwood_roles codex_tasks qwen_adapter workflow_engines idea_chat script_agent_delivery` 221/221；新增 14/14；关联 `-k workflow skill_reference workflow_settings claude_writing_session idea_semantic_brief script_agent_delivery context_budget_model` 174 条 1 红（主树未跟踪用户配置，干净树绿）；架构 `--layer architecture --all` 312/312；默认冒烟 8/8。同步 `架构统一基数.json` 第四项 `writing_api.py:490→512`（行号位移）。未新增 skipTest／裸 json.loads／顶层模块。本轮 1361−1356=5 命中五轮欠账，干净 master 工作树 --all --safe 第 1 次 0 红（4763 条、404.452 秒，凭据 round=1361、tree 3e20f7c4）。

## 2026-10-12 O35 完成

- 2026-10-12 O35：`skill_registry.py`（L3）新增 `REFERENCE_SUFFIXES`／`_LINK_RE`／`reference_targets(text)`（kind：markdown／other／remote／anchor；区分 fragment，剥离标题与尖括号，反斜杠转正斜杠）、`classify_dependencies(skill, known)`、`dependency_report(skill, known)`（skill／external／tools），`external_references` 委托同一分类。`workflow_settings.py`（L4）新增 `_reference_row`／`_nested_references`／`_skill_blocks`／`_inline_skill_report`，`_inline_skill` 变薄壳；闭包状态 inlined／duplicate／outside／missing／resource／remote／anchor／absolute 与 depth2 nested／cycle／outside／missing；缺失直接 md 引用抛 ValueError 阻止发送；`freeze_skills` 汇总 `skill_injection` 的 references 键（每个技能带 `skill` 归属）。本轮刻意不改 `idea_chat.py`（主树带他人已暂存的无关改动，避免把他人 WIP 带进提交）；闭包落在请求快照 `skill_injection`。`tests/test_skill_reference_closure.py`（新）11 条；既有测试未改动、未弱化。定向 `-k skill_ skills workflow_writing stage_prompt_governance request_freeze stage_config codex_skill_sync` 241/241、`-k test_skill_reference_closure` 11/11、`-k writing_api` 全绿、架构门禁 312/312（最终树复跑）、默认冒烟 8/8，全 0 红。未新增 skipTest／裸 json.dump／动态导入／顶层模块；`workflow_settings` 顶部新增 `import skill_registry`（L3→L4 向下）。未实发模型请求、未重启、未真实点击界面。1360 − 1356 = 4 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1356（tree 006d0295、4749/4749、425.3 秒），下一欠账点 1361。
# 验证证据

## 2026-10-12 O34 完成

- 2026-10-12 O34：`handoff_service.py`（L2）新增 `BUNDLE_MANIFEST_NAME`／`MEDIA_PACKAGE_KIND`／`MEDIA_PACKAGE_LABEL`／`MEDIA_PACKAGE_NOTE`；`publish_bundle` 生成 `summary`（kind/label/note/shots{included,expected,missing}/subtitle/sources）并传给发布器；新增 `build_bundle_manifest(summary, files)`（entries: name/size/sha256，清单不自列）与 `verify_manifest(manifest, probe)`（`probe(name)->(size,sha256)`；缺失／大小／摘要不符、声明齐全却漏镜、声明含字幕无 `对白.srt` 记为 problems）。`stage_execution_service.py`（L3）`publish_handoff_bundle(project, name, artifacts, *, auto=False, summary=None)` 把 `交接包清单.json` 并入同一 `publish_stage_bundle(payload)`；新增 `verify_handoff_bundle(folder)`（`file_cache.read_json` 读清单、`file_cache.file_digest` 核对，条目解析后必须落在包目录内）。`desktop.py`（L4）新增 `Desktop.verify_handoff`（`FileDialog.directory` 选目录→后台校验→状态栏报通过/缺陷）与「校验交接包」按钮，页面说明补「素材交接包…不是剪映草稿」。`tests/test_handoff_bundle.py`（新）9 条：清单记录文件与覆盖与来源版本／清单不自列／完整包校验通过并报声明缺镜／缺失·同长度被改·被截断三种失败／`../` 越界条目被拒／缺清单·坏清单报错／声明齐全却漏镜失败／声明缺镜不算失败／声明含字幕无字幕失败；`tests/test_ui_edges.py` 三处自动交接包目录断言补 `交接包清单.json`。定向 `-k test_handoff_bundle test_handoff_service` 16/16、`-k test_copy_rules` 14/14＋`architecture.test_handoff_publication_boundary` 4/4、`-k test_ui_edges` 115/115、`-k stage_execution stage_completion final_viewer handoff delivery skill_tools engine_probe` 107/107、架构门禁 312/312、默认冒烟 8/8，全 0 红。`stage_execution_service` 3 处裸 `json.loads` 行号 1040→1044／1071→1075／1087→1091 已同步 `架构统一基数.json` 第四项；未新增豁免／`skipTest`／顶层模块，`desktop.py` 唯一 TODO 仍在 2753。1359 − 1356 = 3 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1356（tree 006d0295），下一欠账点 1361。

## 2026-10-12 O33 完成

- 2026-10-12 O33：`engine.py`（L3）新增 `ADOPT_*`／`ADOPT_REASON_TEXT`／`adopted_edit_version(versions, root=None)`（返回 `(version, reason)`）／`adoption_summary(root, versions)`／`QC_NAME`／`EDIT_MANIFEST_NAME`／`EDIT_BUNDLE_NAME`／`read_edit_bundle(out)`；`auto_edit_ready` 与 `assemble` 改用 `adopted_edit_version`（错误／跳过文案原样，补「视频无法读取」分支），`assemble` 记 `coverage` 并透传 `_encode(chosen, out, coverage=None)`；`publish_edit_bundle` 先写 `edit_bundle.json`（成片名＋`master_sha256`＋`output_spec`＋qc＋来源清单＋coverage＋`published_at`）再写 `qc.json`／`edit_manifest.json`。`editing_page_controller.py`（L3）新增 `duration_text`，`assembled_message` 报覆盖率；`desktop.py`（L4）交付视图逐镜改用 `adoption_summary`。`tests/test_edit_adoption.py`（新）7 条：最新失败版不顶替采用版／缺失·被替换不判采用／仅未验收报 unapproved／bundle 绑定成片与索引／删 `qc.json` 后从 bundle 恢复／老索引兼容／空目录无 bundle。`tests/test_editing_page_controller.py` +2、`tests/test_integration.py` 部分粗剪加断言、`tests/test_ui_edges.py` 更新 `ApprovedVersionSourceGuardTests`（engine 两处改走 `adopted_edit_version`、desktop 导入 `adoption_summary`）。定向 `-k test_edit_adoption test_editing_page_controller` 11/11、关联 `-k test_ui_edges` 115/115、`-k test_integration` 27/27、`-k test_edit_service test_delivery_import_service test_animatic_timeline` 14/14、`-k stage_execution stage_completion final_viewer handoff delivery skill_tools engine_probe` 98/98、架构门禁 312/312、`-k test_copy_rules` 14/14、默认冒烟 8/8，全 0 红。未新增裸 `json.loads`／L2 直写／动态导入／顶层模块／`skipTest`，`desktop.py` 唯一 TODO 仍在 2753。1358 − 1356 = 2 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1356（tree 006d0295），下一欠账点 1361。主树 `desktop.py` 为 LF 与 `.gitattributes` 钉的 CRLF 不符，主树 `test_line_endings` victims 用例红属环境项（干净工作树 CRLF、16/16 绿），与本轮改动无关。

## 2026-10-12 O32 完成

- 2026-10-12 O32：`script_contract.py`（L0）新增 `resolve_output_spec(locks)`（画幅→分辨率按 1080 短边推算、宽高取偶；`resolution`／`fps` 显式覆盖、非法/越界回退）、`preview_spec`（720 短边／24fps，画幅跟项目）、`output_filter`（scale decrease＋pad 居中留边，无 crop）、`loudness_filter`、`overlay_metrics`（字号与安全边距随高度等比）、`describe_output_spec`；`PRODUCTION_LOCK_DEFINITIONS` 增加 `resolution`／`fps`。`engine.py`（L3）`_encode` 改用项目制作锁规格并新增 `output_spec`／`output_spec_text`；`edit_service.assemble_image_timeline(..., spec=)`＋`animatic_service.build_bundle(..., spec=)`＋`stage_execution_service.animatic_preview_spec` 让预演低清但画幅跟项目；`desktop` 后期页导出前显示实际规格。`tests/test_output_spec.py`（新）15 条。定向 `-k output_spec` 15/15、关联 136/136、架构与端到端 66/66＋153/153＋120/120、默认冒烟全绿，0 红；真实 ffmpeg 端到端 9:16→1080x1920@30、16:9→1920x1080@30（源 640x360 等比留边未裁切），`qc.json` 记 `output_spec`。`stage_execution_service.py` 4 处裸 `json.loads` 行号 +1 已同步 `架构统一基数.json`；未新增豁免／`skipTest`／顶层模块，`desktop.py` 唯一 TODO 仍在 2753。1357 − 1356 = 1 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O31 完成

- 2026-10-12 O31：`tts_api.py`（L1）新增 `AUDIO_KINDS`／`AUDIO_KIND_LABELS`／`audio_kind`／`marked_audio_name`／`voice_for`／`missing_voices`／`silent_lines`／`voice_snapshot`，`save_key` 音色变化自增 `voice_version`，`batch_signature(lines, episode=None)`／`resume_folder(root, lines, episode=None)`／`run_lines(..., episode=None)` 增至集标识；`audio_import_service.import_audio(..., kind='dialogue')` 给非对白加前缀；`stage_completion_service.prepare_media_completion` 对 audio 要求对白音轨；`stage_execution_service.run_tts_lines(..., episode=None)`／`desktop.generate_tts_per_line` 带集 token。`tests/test_audio_role_binding.py`（新）18 条：ID 优先／名字兜底／改名不丢映射／缺配角色／静音台词／音色版本只在变化时自增／用途前缀往返／对白原名／未知默认对白／`batch_signature` 默认与旧公式逐字节相同＋带 episode 区分／两集不互命中／BGM 加前缀＋非法用途报错／完成核验 BGM-only 拒绝、对白音轨接受。定向 `-k audio_role_binding` 18/18、关联 `-k tts audio stage_completion media_import ui_edges skill stage_execution` 427/427、架构门禁 312/312、默认冒烟 8/8，全 0 红；未新增裸 `json.loads`／L2 直写／动态导入／顶层模块／`skipTest`，`desktop.py` 唯一 TODO 仍在 2753。1356 − 1351 = 5 命中五轮欠账，收口在干净 master 工作树跑 `--all --safe`：第 1 次 4749/4749 中 1 红（`video_progress.py:94` 文案规则，R1353 遗留），第 2 次 4749/4749、425.3 秒、0 红，凭据 round=1356、tree=006d0295。

## 2026-10-12 O30 完成

- 2026-10-12 O30：`subtitle_timing.py`（L1）新增 `calibrate_entries(episode, audio=None)`（镜内按 `line_weight` 句长或真实音频秒数／对齐区间重排；超镜头整镜压缩记 `overflow`；输出 `mode`／`calibrated`／`audio`／`uncalibrated`／`source`）、`validate_entries(entries, total=None)`（非有限／负数／反向／重叠／越界抛 ValueError）、`rows_from_entries`、`line_weight`；`srt_rows(episode, audio=None)` 改用校准轴并先校验（仍返回 `(rows, estimated)`）；`timed_entries` 等分估算行为不变。`subtitle_export_service.py`（L2）`export_srt`／`export_dialogue_script` 改用校准轴并返回 `(target, report)`，`export_srt` 另写 `字幕校准.json`，新增 `pending_calibration`／`export_calibration`；`desktop.py` `subtitles`／`dialogue_script` 按 report 提示。`tests/test_subtitle_calibration.py`（新）23 条；`tests/test_subtitle_export_service.py` 契约更新为 `(target, report)`。定向 `-k subtitle ui_edges skill handoff stage tts` 690/690、架构门禁 312/312（含 `test_subtitle_export_publication_boundary`）、默认冒烟 8/8，全 0 红；未新增裸 `json.loads`／L2 直写／动态导入／顶层模块／`skipTest`，`desktop.py` 唯一 TODO 仍在 2753。1355 − 1351 = 4 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 2026-10-12 O29 完成

- 2026-10-12 O29：`pet_llm.py`（L1）新增 `RequestLedger`（`reserve`／`link`／`settle`／`mark_unknown`／`cancel`／`report`／`price`／`save`／`load`）＋ `REQUEST_LEDGER_PATH`／`REQUEST_KINDS`／`REQUEST_STATES`／`REQUEST_MODES`；`model_pool.py` `probe(..., ledger=None)` 增 `PROBE_USAGE_NOTE` 与返回体 `usage_note`，有 ledger 时对探测记未知；`pet_models_ui.py` `probe_line` 附探测提示。`tests/test_request_ledger.py`（新）11 条：幂等预留／重试不重复结算／usage 汇总与缺量未知／缺量不显免费／同远端任务唯一账单／取消不伪造退款／取消已预留转未知／分列 kinds／可选带日期价格表与缺费率／save-load 往返／探测标注。定向 `-k request_ledger pet_llm model_router pet_models_ui` 73/73、架构门禁 312/312、默认冒烟 8/8，全 0 红；未新增裸 `json.loads`（`model_pool.py` 两处响应体解析行号 568→576、605→613 已在 `维护记录/架构统一基数.json` 第四项同步登记，仍 exempt）／L2 直写／动态导入／顶层模块，棘轮均绿。1354 − 1351 = 3 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 2026-10-12 O28 完成

- 2026-10-12 O28：`video_progress.py` 新增 `task_status`／`status_label`／`status_next`／`status_detail`／`error_kind`／`ERROR_LABELS`／`ERROR_NEXT`（八态＋失败/拒绝/缺文件；七类错误；本机磁盘标记先判、其余复用 `pet_agent.classify`）；`engine.py` `poll` 取回失败分支记 `download_error` 且保留 `succeeded`；`app.py` 视频页状态行与 `desktop.py` 交付页逐镜行改用统一状态与下一步。`tests/test_video_task_status.py`（新）13 条；`tests/test_integration.py` 新增 `DownloadResumeTests`（取回失败只保留一版、状态 succeeded、再 poll 续取成功且仍一版）。定向 `-k video_task_status integration video ui_edges` 332/332、架构门禁 312/312、默认冒烟 8/8，全 0 红；未新增 `json.loads`／L2 直写／动态导入／顶层模块，棘轮均绿。1353 − 1351 = 2 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 2026-10-12 O27 完成

- 2026-10-12 O27：`engine.py` 新增 `review_source`／`content_reviewed`／`review_label` 与状态常量、`AUTO_REVIEW_MARK`／`AUTO_REVIEW_NOTE`；无人值守自动放行（`engine.py` download 分支与 `local_video.py` 取回分支）写 `review_by='auto'`＋自动 note，`Studio.review` 写 `review_by='user'`，老记录无 `review_by` 时按 `review_note` 前缀回推（认不出当真人）。`app.py`／`desktop.py` 验收列改用 `review_label`，交付页加「采用」列。`tests/test_integration.py` 新增 3 条（自动放行≠内容审核、用户通过=内容审核、老记录回推），`tests/test_ui_edges.py` 交付页断言「采用 v1」。定向 `-k integration ui_edges video` 318/318、架构门禁 312/312、默认冒烟 8/8，全 0 红；未新增 `json.loads`／L2 直写／动态导入／顶层模块，棘轮均绿。1352 − 1351 = 1 < 5 且未命中 §5，本轮不跑全量；上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 2026-10-12 O26 完成

- 2026-10-12 O26：新增 `tests/test_white_model_workspace.py` 21 条（默认成果目录在用户数据目录且不等于 Blender 安装目录旁／环境变量与设置文件都能改成果目录与 blender 路径／`workspace()` 随目标变更失效／中文＋空格目录可写且探针不留痕／权限不足与缺盘符给可执行提示／轻量检查不建目录／版本读取与缓存、失败返回空串、无 exe 不执行／配置路径优先、旧盘符仍在候选表、PATH 只扫一次／旧成果目录只读发现且不误报当前目录／诊断给出缺 Blender、不可写、旧目录提示与版本，`diagnose_text` 成文）。`file_cache.py` 两处 `json.loads` 行号平移（54→55、140→141）同步 `维护记录/架构统一基数.json` 第四项。定向 `-k white_model previs native_apps` 160/160、`-k white_model_workspace file_cache` 47/47、`-k ui_edges core paths stage_flow stage_parallel notification` 360/360、`-k stage_execution stdlib_closure import_error` 20/20、注释快照／统一棘轮／覆盖率棘轮／跳过卫生全绿、架构 312/312、默认冒烟 8/8，全 0 红。1351 − 1346 = 5 ≥ 5，收口在干净 master 工作树跑全量：第 1 次 4680/4680 中 1 红（`continuity_ledger.py:596` 文案规则，R1347 遗留，定向用例当时未覆盖），把该短语改为 `人工关闭` 后第 2 次全量 4680/4680、416.2 秒、0 红（`test_desktop_startup_perf` 13.8 秒、`test_perf_baseline` 20.5 秒均过）；凭据刷新 round=1351、tree=c97c1336，`last_full_safe_all_round`=1351。

## 2026-10-12 O25 完成

- 2026-10-12 O25：新增 `tests/test_keyframe_batch_plan.py` 15 条（`missing` 只取从没提交过的缺帧镜头／提交过的跳过不重付费／`deleted`·`empty`·`unset`·`outside` 跳过并给原因；`retry` 只取有记录仍缺帧；`replace` 只对点名且已有可用首帧；切集换 source 不跨集；`plan_summary` 文案；`pending_shots` 口径；Tk `DialogPlanTests` 显示「批次意图」下拉与目标集预览）。新增一条 Tk 平台限制，同步 `维护记录/skip台账.json`（+1，手写插入不整份重写）。定向 `-k batch_plan keyframe` 93/93、`-k keyframe previs stage_execution` 全绿、`-k batch_frames todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 27/27、`tests.architecture.test_skip_hygiene` 3/3、架构 312/312、默认冒烟 8/8，全 0 红。1350 − 1346 = 4 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O24 完成

- 2026-10-12 O24：新增 `tests/test_stage_gate_modes.py` 14 条（默认浏览放行且各 `*_ready` 口径不变；正式生产把「上游未开始」当作缺前置并点明缺哪一步、怎么豁免；上游标 `skipped`＝主动豁免；两种口径只差「上游未开始」这一种；真问题两口径都拦；台账格式异常不静默放行；结论标签；页面/审计文案；`Agent` 默认浏览口径与档位无关＋显式 `PRODUCTION` 拦截＋`skipped` 豁免；`Pet.gate_reason` 链在推要 `PRODUCTION`、浏览要 `BROWSE`、分镜历史豁免仍优先）。`tests/test_stage_parallel.py` 两处桩函数放宽为接受可选 `mode` 关键字（断言不变）。定向 `-k stage_parallel stage_flow pet_agent stage_completion` 192/192、`-k stage_gate` 18/18、`-k todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 9/9（pet_ui 快照行号 2792→2801）、架构 312/312、默认冒烟 8/8，全 0 红。1348 − 1346 = 2 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O23 完成

- 2026-10-12 O23：新增 `tests/test_continuity_issues.py` 20 条（稳定编号＋证据＋严重度／同一台账编号稳定／不同批次不串号／干净台账无问题；不重复新增／修好解除／解除后再现重开／忽略后证据变了重开且清空决定；忽略必须理由／决定记理由与作用版本／未知编号与非法决定拒收／重新打开清忽略；只读预览不写盘／注入发布器才落盘／无登记表读成空／门禁只拦待处理／修好清空／`stage_parallel.ledger_ready` 忽略后放行）。定向 `-k continuity stage_parallel confirm_gates` 124/124、`-k ui_edges todo_comment unification_ratchet desktop` 160/160、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1347 − 1346 = 1 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O22 完成

- 2026-10-12 O22：新增 `tests/test_asset_impact.py` 10 条（`referencing_shots` 命中字段命名/`location`+`props` 可命中/未知资产不命中；受引用资产带镜头与首帧文件且 `protected`、孤立资产 `orphan` 可回收、`canon`/`variants` 只读回显、非法编号 `ValueError`、删除引用清单列出镜头并警示、孤立资产删除清单为空；写状态变体不覆盖正典键）。定向 `-k asset_impact asset_context asset_plan asset_detail asset_reference` 64/64、`test_todo_comment_snapshot`＋`test_unification_ratchet` 5/5、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1346 − 1341 = 5 ≥ 5；收口安全全量第 1 次 4610/4610、410.3 秒、0 红（凭据 round=1346、tree=3488e392，last_full_safe_all_round=1346）。

## 2026-10-12 O21 完成

- 2026-10-12 O21：`tests/test_reference_search.py` 新增 5 组（分项结构/总分=分项和/`score` 与分项一致；缺地址/缺来源/缺许可/低分/不可商用/可入库六态＋note；许可依据与采集日期随条目、同图不同源记进 `alts`、许可冲突标 `source_conflict`、同许可不算冲突；低分与同图落后分逐条解释、已上墙不重复列；credit 记 license_url/collected_at 且 `rank`/`suppressed` 对已入库资产只读）。`tests/test_reference_wall.py` 新增 3 条（图墙显示许可依据与采集日期列；同图冲突只展示一条且状态提示「不一致」、同图来源为 1；右键剔除候选后 assets.json 字节不变）。定向 `-k reference` 118/118、锚定 `-k asset_detail asset_plan asset_reference workflow_context skill_tools` 全绿、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1345 − 1341 = 4 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O20 完成

- 2026-10-12 O20：新增 `tests/test_file_cache.py::FileDigestTests` 2 条（`file_digest` 与 `hashlib.sha256` 整份结果一致且第二次命中不再打开文件；内容变化后刷新、`invalidate()` 后重算）＋ `tests/test_animatic_service.py` 1 条（确认后对 `.mp4/.wav/.png` 的 `Path.read_bytes` 打补丁抛错、清缓存后 `evidence` 仍 True，证明成果校验不再整份读媒体）。定向 `-k animatic file_cache` 41/41、锚定 `-k animatic_timeline stage_completion previs` 117/117、架构 312/312、默认冒烟 8/8，全 0 红。台账第四项 `file_cache.py` 两处 json.loads 行号平移（53→54、112→140）已同步，`-k unification_ratchet` 3/3。实测 64 MiB 文件：旧法峰值 64.1 MiB／114ms，新法冷算 2.1 MiB／118.7ms、命中 0.002 MiB／0.211ms。1344 − 1341 = 3 < 5 且未命中 §5，本轮不跑全量。

## 2026-10-12 O19 完成

- 2026-10-12 O19：新增 `tests/test_adoption_impact.py` 7 条（同文件重排只报 reordered 且文件字节不变；删镜 → 首帧+已生成视频入失效清单；仅改对白 → fields=[dialogue] 且无媒体失效；换资产/改时长 → 首帧失效；无基线 → 全部 added + `+2 镜`；预览对 ui_settings.json 与候选文件只读）。`-k adoption_impact storyboard file_cache row_targets workflow_context` 78/78、`test_ui_edges.BatchContinuationTests.test_adopt_skips_adopted_without_confirm` 1/1（Tk）、架构 312/312、默认冒烟 8/8，全 0 红。未增删 `json.loads`（台账未平移）。1343 − 1341 = 2 < 5，本轮不跑全量。

## 2026-10-12 O18 完成

- 2026-10-12 O18：新增 `tests/test_artifact_lineage.py` 10 条（同路径内容变更标 stale 但仍 available、恢复回 current；改无关文件不失效；删源标 missing 且 unavailable；无账本 UNKNOWN 且 available None；旧单来源账本可读；多来源逐角色状态；重记覆盖旧来源；`affected` 只列非 current 且按 source 过滤；`adopt` 后 current；结构/分镜/首帧/白模/音频/剪辑六类都能登记并检出过期）；`tests/test_file_cache.py` 增 1 条（定稿来源变更后仍在目录且标题含「来源已变更」）。定向 `-k artifact_lineage file_cache storyboard script_structure script_contract` 136/136、架构门禁 312/312、默认冒烟 8/8，全 0 红。未动 `script_contract.py`／`storyboard_final.py` 登记调用点，未增删 `json.loads`（台账未平移）。1342 − 1341 = 1 < 5，本轮不跑全量。

## 2026-10-12 O17 收口全量

- 2026-10-12 O17 收口：干净 master 工作树（`o07-fullsafe-master`，HEAD=00d3a80）`run_selftests.py --all --safe` 第 1 次即绿：4561 条用例／420.2 秒／0 文件红；`test_desktop_startup_perf` 13.6 秒、`test_perf_baseline` 22.4 秒均通过，未出现已知阈值抖动。内容树全量凭据刷新 round=1341、tree=06c23252d59254ca25619e76b7de8c650cd23749。收口文档提交在绿凭据之后，文档树与凭据树不同树。

## 2026-10-12 O17 完成

- 2026-10-12 O17：新增 `tests/test_script_structure.py::ExtractionProvenanceTests` 6 条（结构稿标本地规则提取且阶段 detail 不再写 Writer 已提取；无对白标签与未知道具尺寸保留待确认/出处；别名与跨集 ID 保留出处且跨集稳定；回忆场景标时间线待确认；同名特征矛盾给同名提醒；规则校验要求出处但仍接受待确认字段）。`test_ui_edges` 结构页说明断言同步为「本地规则提取」。定向 `-k script_structure script_contract stage_templates` 71/71、`-k ui_edges` 全绿、`-k skills` 全绿、`-k agents_md todo_comment line_endings structured_script_write_boundary json_io_boundary unification_ratchet` 35/35、`-k copy_rules` 14/14、默认冒烟 8/8，全 0 红。`desktop.py` 只改 1 行文案，行数不变（TODO 注释快照 2753 未平移）。本轮 1341 − 1336 = 5 ≥ 5，收口须补一次干净 master 全量。

## 2026-10-12 O16 完成

- 2026-10-12 O16：新增 `tests/test_hollmwood_roles.py::ReviewTraceabilityTests` 5 条（同一冻结输入 `review_basis` 四键一致且为 64 位摘要；记录区分规则合格/创意满意并保留退回原文与通过条件；返工 prompt 只含明确问题、节奏正文只在 system 出现一次、prompt 不含节奏；最终判退异常带 basis 与 records；断点恢复前缀记为「上一轮已审核通过」）；`tests/test_hollmwood_performance.py` 2 条（成功结果透出 `hollmwood_review_audit`；失败结果带 basis/scope/records）；`tests/test_hollmwood_ui_queue.py` 1 条（完成文案区分规则合格与创意满意、仍用「您」）。定向 `-k hollmwood` 51/51、关联 `-k writing` 139/139、`-k idea_chat` 全绿、`-k stage_prompt_governance` 15/15、`-k copy_rules` 14/14、`-k todo_comment` 2/2、默认冒烟 8/8，全 0 红。`writing_api.py` 加行后第 4 项 `json.loads` 台账 486→490（已同步），`-k unification_ratchet` 3/3 复验通过；`desktop.py` 只改 1 行文案，行数不变（TODO 注释快照 2753 未平移）。本轮 1340 − 1336 = 4 < 5，且未命中 §5 升级条件，不跑全量。

## 2026-10-12 O15 完成

- 2026-10-12 O15：新增 `tests/test_request_freeze_entries.py` 3 条（`capture_request` 冻结后改技能文件与阶段配置只影响新任务、同一次捕获的 `frozen_skill_prompt` 与 sha256 摘要不变；直连 API 与桌面 Agent 两入口对同一技能 `selected`／`loaded.sha256` 一致；静态核对 desktop 直连走 `capture_request`、writing 投递走 `validate_selected_skills`＋`freeze_skills`、`open_flow_agent` 的 `current(...)` 先于 `def build()`、桌面 `launch_interactive(` 仅一处）。定向 `-k request_freeze_entries` 3/3、关联 `-k workflow_settings request_freeze_entries writing` 全绿、默认冒烟 8/8，全 0 红。未改生产代码，台账不变。本轮 1339 − 1336 = 3 < 5，不跑全量。

## 2026-10-12 O14 完成

- 2026-10-12 O14：新增 `tests/test_idea_chat.py::SessionOverviewTests` 1 条（`gpt-4o`＝API 直连、`claude-code`＝桌面 Agent（claude），已确认阶段文件 1 份，摘要含模型名与「不隐藏也不复制项目成果」）；新增 Tk 用例 `ComposerLayoutTests::test_session_label_explains_dimensions_and_follows_model_switch`（首帧含「当前会话：」「按模型隔离」，切「另一模型」后标签更新）。定向 `-k idea_chat` 131/131、关联 `-k ui_edges idea_inline_brief writing` 全绿、架构相关全绿、`-k desktop_startup_perf` 14/14（13.3 秒）、默认冒烟 8/8，全 0 红。`desktop.py` 增 Tk 标签 → TODO 注释快照行号 2749→2753。本轮 1338 − 1336 = 2 < 5，不跑全量。

## 2026-10-12 O13 收口全量

- 2026-10-12 O13 收口：干净 master 工作树（`o07-fullsafe-master`，HEAD=baf816c）`run_selftests.py --all --safe` 第 1 次 4542 条用例／385.8 秒／0 文件红；`test_desktop_startup_perf` 13.0 秒、`test_perf_baseline` 20.4 秒均通过，未出现已知阈值抖动。内容树全量凭据刷新 round=1336、tree=d934dd219a8ff155f7330220e12081af3f4efabc。收口文档提交在绿凭据之后，文档树与凭据树不同树。

## 2026-10-12 O13 完成

- 2026-10-12 O13：新增 `tests/test_writing_response_preservation.py::PreparationReplyStateTests` 3 条（状态判据区分四态／无状态消息为空串；确认成功后为「阶段稿待确认」且消息含路径与确认；取消后迟到错误含「原始响应已保存」「不等于正式采用」与归档路径且台账未变）；扩展既有 2 条（格式不合格与截断带 `原始响应已保存`＋原因标签且消息点明归档不等于正式采用；版本变化经 `reply_to_writing` 带 `因版本变化未采用`）。定向 `-k writing` 139/139、关联 `-k idea_inline_brief writing_response_preservation` 46/46、桌面 `-k ui_edges` 115/115、架构相关 22/22、默认冒烟 8/8，全 0 红。`desktop.py` 增 1 行 → TODO 注释快照 desktop.py 行号 2748→2749。本轮 1336 − 1330 = 6 ≥ 5，收口补一次干净 master 全量。

## 2026-10-12 O12 完成

- 2026-10-12 O12：新增 `tests/test_tts.py::TtsBatchIdentityTests` 6 条（清单记身份／中途改设置不混用／换模型与换端点失效旧缓存／截断与空文件不续用／旧清单无摘要时文件非空即沿用／密钥不入指纹清单批次记录）；定向 `-k tts` 49/49、`-k tts audio animatic subtitle` 全绿、关联 `-k ui_edges` 115/115、架构相关 `-k unification_ratchet json_io_boundary layers tts_publication_boundary todo_comment_snapshot` 12/12、默认冒烟 8/8，全 0 红。夹具 `fake_synthesize` 跟随新签名补 `**_kwargs`（`tests/test_ui_edges.py` 两处，只改夹具）。本轮 1334−1330=4<5，不跑全量。

## 2026-10-12 O11 完成

- 2026-10-12 O11：新增 `tests/test_confirm_gates.py::ConfirmationBindingTests` 5 条（换候选只失效那一个角色且门禁重问／改冲突优先级重问／跨集同批次 ID 内容不同即复核／无关字段不扰动／旧记录无摘要仍算已确认）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 101/101、接缝 `-k ui_edges stage_execution stage_parallel` 172/172、架构相关 `-k unification_ratchet confirm_gates_json_boundary todo_comment_snapshot layers no_circular_import stage_paths` 15/15、默认冒烟 8/8，全 0 红。台账无变化（`stage_execution_service.py` json.loads 仍 108/1039/1070/1086）。本轮 1333−1330=3<5，不跑全量。

## 2026-10-12 O10 完成

- 2026-10-12 O10：新增 `tests/test_confirm_gates.py::AdoptTransactionTests` 6 条（落盘失败留 failed 且门禁不通过／应用前中断留 pending／成功记 applied 不再问／重复点击幂等／旧记录无 state 按 applied／未知 key 空相位），改 `tests/test_asset_detail.py` 两条（第二步失败事件 `['record','apply','record']` 且不刷新不报成功；第一步失败不落盘）；定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 96/96、架构棘轮 `-k unification_ratchet confirm_gates_json_boundary` 5/5、默认冒烟 8/8，全 0 红。台账 `架构统一基数.json` 第四项三处行号随 adopt 加长平移（1025/1056/1072→1039/1070/1086，exempt 不变），`TODO注释快照_20261003.json` 的 asset_detail.py 注释行号 346→350。
- 2026-10-12 O10 收口全量（干净 master 工作树 `--all --safe`）：第 1 次 4528 条／445.5 秒／1 文件红（`architecture.test_todo_comment_snapshot` 行号平移，定向 2/2 修绿）→ 第 2 次 4528 条／449.2 秒／0 红，绿凭据 round=1330、tree=3281c7c7，`last_full_safe_all_round`=1330。文档收尾在绿凭据之后，非同树全量。

## 2026-10-12 O09 完成

- 2026-10-12 O09：新增 `tests/test_previs.py::PrevisEvidenceTests` 2 条（改调度失效／改回复用／换文件失效且不删成果／旧记录无来源时退回旧口径）；定向 `-k previs white_model` 138/138、关联 `-k stage_execution_service stage_parallel` 57/57 与 `-k ui_edges` 115/115、默认冒烟 8/8，全 0 红。架构（干净 master 工作树 `--layer architecture --all`）312/312、0 红。台账 `架构统一基数.json` 第四项三处行号随插入平移（exempt 不变）。

## 2026-10-12 O08 完成

- 2026-10-12 O08：新增 `tests/test_previs.py::RoutingGateConsistencyTests` 4 条（自动→复杂、复杂→简单、跨集同镜头 ID、删除覆盖）；定向 `previs stage_parallel` 143/143、0 红；接缝 `previs stage_parallel stage_execution local_previs stage_completion white_model stage_models manual_gate row_targets ui_edges desktop` 398/398、119.2 秒、0 红；架构 `smoke_test.py --architecture` 312/312 OK；默认冒烟 8/8。回归修复仅颜色：`test_previs_monitor.py`、`test_ui_edges.py` 的 `ready` 打桩补 `source=None`。本轮号 1316 − 上次绿全量 1312 = 4 < 5，未跑全量。

## 2026-10-12 O07 完成

- 收口全量：干净 master 工作树（`HEAD=b0c6716`、`HEAD:程序`=12ad4759）`run_selftests.py --all --safe`——第 1 次 4500 条／528.7 秒／21 文件红（缺嵌套子模块致写作与技能组假红；补子模块后同树定向 489/489、0 红），第 2 次 4516 条／388.1 秒／0 红，凭据 round=1312、tree=12ad4759。

- 定向：新增 `tests/test_white_model_identity.py` 12 条＋ `white_model_identity previs` 相关 136/136、5.0 秒、0 红。
- 接缝：`white_model previs project stage_execution local_previs desktop stage_parallel stage_completion storyboard keyframe asset` 669/669、48.9 秒、0 红（`test_desktop_startup_perf` 本轮通过）。
- 门禁：默认冒烟 8/8；`smoke_test.py --architecture` 312/312（首次 311/312，因本轮在 `stage_execution_service.py` 插入 7 行使 `架构统一基数.json` 第四项三处豁免行号漂移，同步行号后全绿）。
- 全量：见 [R1312](../程序/tasks_round/tasks_round_1312_result.md) 文末；按用户 2026-10-12 指令只在收口跑一次，先查 7 天内同内容树绿凭据（无），本轮未命中 AGENTS §5 升级条件。

## 2026-10-12 O06 完成

定向 591/591（含接缝）、修复后相关 128/128、默认冒烟 8/8。第 1 次全量（树 e0df829a）4 文件红，均为夹具/环境；第 2 次全量（树 0e2a2f06）4504/4504、536.7 秒通过，但检出为 detached 工作树，执行器未写绿凭据；第 3 次全量为取凭据在 master 临时工作树重跑，行至性能用例被并发活动中断退出 1，未取得凭据，不再重跑。O05 历史全量不覆盖本轮树。详见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。

## R1265

- 最终受影响 14 文件 458/458、156.7 秒；冒烟 9/9，日志 程序/outputs/r1265-affected-final.log。
- 本轮架构 307/311；四处失败修复后相关 3 文件 10/10，日志 程序/outputs/r1265-architecture-fix.log。未改门禁断言。
- R1264 历史真实全量 tree=9ea232b7027c6e77b4ef9516c146a8e9c5ae2b95、413.396 秒；不覆盖本次树。中央 validate 0 errors/0 warnings，未实发 API 或重启。见 [报告](../程序/tasks_round/tasks_round_1265_result.md)。

## R1208

- 正式 master fe4a923 安全全量 4291/4291、397.379 秒、含架构 311/311，执行器凭据 round=1208、tree=3831b1e0fe2e20cf1ea6c7b0b8afb9c881c3bff9；日志 TEMP/r1208-full-final.log。
- 首次全量 2 条旧取消 fixture 失败，补齐前置后定向 73/73，再完整复验通过。默认冒烟 8/8、受影响冒烟 9/9。全量后的缓存隔离补丁先红后绿、定向 68/68，日志 TEMP/r1208-cache-green.log；最终树未同树全量。见 [R1208](../程序/tasks_round/tasks_round_1208_result.md)。

## R1200

- 定向 129/129、默认冒烟 8/8、受影响冒烟 9/9。首次全量仅架构登记行号漂移，修正后定向 71/71。
- 干净 e1f2d26 安全全量 4283/4283、539.0 秒、exit=0（含架构 311/311）。后续仅文档收尾；不声称最终文档树或用户主目录同树全量。
- 后续干净 master 808a972 正式全量 4283/4283、511.725 秒，R1202 凭据已写入；未实发 API、未重启。原始日志 TEMP/R1200-full-recheck.log、TEMP/R1202-master-full.log；见 [报告](../程序/tasks_round/tasks_round_1200_result.md)。

## R1162

- 定向 137/137、受影响冒烟 9/9（含默认 8/8）、相关边界 5/5；主目录两项回归 2/2。先红后绿与命令目录错误记录见 [报告](../程序/tasks_round/tasks_round_1162_result.md)。
- 实现 db0e878，主目录同步回执 6523465；既有 6 项已跟踪改动保持原样。未重启应用、未真实桌面粘贴或模型发送。本次交接补记仅文档与只读代码核验，不重复运行测试，以上均为 R1162 已有凭据。

## R1139

- 技能/Codex 定向 197 条通过，默认冒烟 8/8；补充定向 27 条和 ratchet/coverage 7 条通过。
- 干净 master 191ef05 全量安全回归 exit=1，旧 UI 按钮样式及剧本输出契约断言失败；没有本轮绿色全量凭据。详情与未运行项见 [报告](../程序/tasks_round/tasks_round_1139_result.md)。
- 实际 67 技能安装，重复 67 unchanged；只读 Codex skills/list 确认 pipeline-script-preparation enabled，不冒称已验证模型加载执行。

## R1074

- 旧实现内存对照 17/17，迁移后定向 58/58，默认冒烟 8/8，受影响 9/9；原断言未改，新增 11 条。
- 干净 master 813b662 正式安全全量 4026/4026，含架构 309/309，exit=0。tree=c924740a7a042954a6e4e086736a15fe5c31437c、round=1074、seconds=295.657、at=2026-10-06T00:23:14；执行器真实凭据，不手改。
- 初次 runner 无写锁权限中止；获授权后通过。旧实现对照首次 cwd 导入错误，修正绝对导入路径后通过；详见本轮报告。全量后仅文档回填，不冒称最终文档树受测。
- 收尾文档／轮次门禁 15/15、0.8 秒；中央任务 completed，validate 0 errors、1 条既有租约警告。

## R1073

- 迁移前 test_pet_ui 574/574（含新增 G3 7 条）；迁移后定向 588/588，默认 smoke 8/8。冻结 100 个 ID 的摘要与 R1059 一致，前后方法 AST 不变。
- 干净 master d6bfe1e 正式全量 4015/4015，含架构 309/309，exit=0。新增 G3 7 条及内存协调 10 条，未删原测试。
- 执行器凭据：tree=68211bcc962eff5e40fe0722c0735a920044e7ec，round=1073，seconds=359.982，at=2026-10-05T17:51:24。临时日志 R1073-full.log。
- 后续仅文档回填，最终文档树未重跑全量；不声称实机视觉体验已验收。
- a517dd1 后文档／轮次 15/15；中央 R1073-CHAT-COORDINATION completed，validate 0 errors、1 条既有租约警告。

## R1072

- 定向 70/70；默认 smoke 8/8；失败集合修复后 200/200。首轮 5 文件／6 失败均已关闭，位置快照仅同步行号，不增加豁免。
- 正式安全全量：干净 master 6cf0911e6f7b9f86e27433f72031201a734fe6e5，3998/3998，含架构 309/309，exit=0。
- 执行器真实凭据：tree=ba1498584b9be6c5e89736ebc21fef649ae8a594，round=1072，seconds=357.954，at=2026-10-05T17:35:42。后续仅文档收尾，不冒称最终文档树已全量。
- 日志：系统临时目录 R1072-master-full.log；长期事实摘要见 R1072 结果文件。

## R1070

- 周期安全全量：干净 master bc6358e719fea403a0e74a09f06786a0a7ab7bf7 执行 run_selftests.py --all --safe，exit=0，ALL TESTS PASSED，313.560 秒。
- 执行器真实凭据：tree=69a5dd97bc85aebed4f89780683ae3ecce1ee34c，round=1069，at=2026-10-05T08:44:11。round 取执行时最新报告，不手工改为 1070。
- 输出仅保留尾部，未保留本次总用例计数，不沿用历史 3994 冒充本次计数。全量后仅文档收尾，不声称最终文档树同树全量通过。
- 中央 validate：0 errors、1 既有租约 warning，详见 risks。文档链接与 diff --check 通过，凭据形态扫描 0 命中；默认 smoke_test.py：8/8、0 失败。未独立重跑架构门禁。

## R1069

静态检查：11 份入口/接力文档链接有效、标记唯一、无模板占位符；diff --check 通过。
在 程序/ 执行 ../运行环境/Python/python.exe -B -m unittest tests.architecture.test_agents_md tests.test_round_claim：23/23，10.982 秒。
同一解释器执行 -B smoke_test.py：8/8，0 失败；默认模式未启动独立架构门禁。
仅文档改动；全量凭据轮次 1067 至本轮 1069 差 2，按既有周期不重复全量。
最终结果见 [R1069](../程序/tasks_round/tasks_round_1069_result.md)。

## 历史基线（不是当前树验收）

- R1068 主树全量：干净提交 1b36059d5e7c8036b50cbf8118d41b3d0aa2ed84，3994 条通过。
- 凭据 tree=8466f0109fe30c54a31d1ea8890e5b05843553d6，round=1067，at=2026-10-05T08:20:53。
- R1068 收尾：冒烟 8/8，test_agents_md + test_round_claim 23/23。
- R1068 隔离副本：批量删除定向 90/90、冒烟 8/8、架构 309/309；不是生产删除或逐候选独立证明。
