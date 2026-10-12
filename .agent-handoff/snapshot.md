# 当前快照

## 2026-10-13：UI 路线图 §一 第 2 项（设计 token）末页迁移 agent/prompt_optimizer.py（R1402，功能轮 §3.1）
- 范围＝零视觉变更子集最后一处：`agent/prompt_optimizer.py` 10 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token；新增 `from ui_tokens import SPACING`。
- 行号平移同步：架构统一基数 第四项 `agent/prompt_optimizer.py` 175→176；覆盖率审计21 位点 173→174。
- 验证：定向 8/8、默认冒烟 8/8、架构 341/341；1402−1400=2<5 且未命中 §5 → 不跑全量。提交内容 `8274dee`。
- **设计 token 决策-free 子集至此全部迁完**（五轮累计 81 处：R1396 13＋R1399 21＋R1400 24＋R1401 13＋R1402 10）。再推进**必须先有调色板决议**：hex（含 `desktop.py` 31 处）、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级全部依赖它。

## 2026-10-13：UI 路线图 §一 第 2 项（设计 token）desktop.py 内联间距（R1401，功能轮 §3.1）
- 范围＝零视觉变更子集的一页：`desktop.py` 13 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（4×2／8×2／12×3／16×6）；该模块已 `from ui_tokens import COLORS, FONTS, SPACING, …`，**无新增 import、行数 7498 不变、无行号平移**。
- 未动 hex（31 处内联色属旧调色板决策；`#ffffff` 大小写等值会与 `test_idea_chat` 字面量断言冲突）。
- 验证：默认冒烟 8/8、架构 341/341；**命中 §5**（启动路径＋五轮）→ 干净 master 全量 **4983/4983、558.1 秒、0 红**（凭据 tree=`60d4e23d…`＝`a8a0803:程序`，last_full 1396→1400）。提交内容 `a8a0803`。
- **决策-free 子集基本耗尽**：仅余 `agent/prompt_optimizer.py`（10，agent 层须另评）；其余 hex／103 处旧色／非 token 间距／文字层级全部待调色板三选一。

## 2026-10-13：UI 路线图 §一 第 2 项（设计 token）第 3 批单页迁移（R1400，功能轮 §3.1）
- 范围＝零视觉变更子集第 3 批：`keyframe_comfy.py`／`workflow_settings.py`／`white_model.py`／`native_assets.py`／`background_characters.py` 24 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token；`keyframe_comfy.py` 1 处等值 `#ffffff→COLORS['background_card']`。
- 验证：定向 168/168、默认冒烟 8/8、架构 341/341；1400−1396=4<5 且未命中 §5 → 不跑全量（最近绿全量 R1399）。提交内容 `e81df9c`。
- 同轮缺陷：首版脚本误判 import 存在性（扫全文而非 import 行）→ 5 页缺 import、5 条 NameError，已同轮修绿；教训记入报告。
- **决策-free 子集接近耗尽**：仅余 `agent/prompt_optimizer.py`（10）与 `desktop.py`（13，启动路径须另评 §5）；其余为 0 值间距。
- 未做（需用户决策）：hex 其余 6 处、103 处旧调色板值、非 token 间距值、旧页面文字层级 —— 待设计 token 调色板三选一。

## 2026-10-13：UI 路线图 §一 第 2 项（设计 token）第 2 批单页迁移（R1399，功能轮 §3.1）
- 范围＝零视觉变更子集第 2 批：`asset_detail.py`／`prompt_window.py`／`qwen_setup.py`／`seedream_settings.py` 21 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token；`asset_detail.py` 1 处等值 `#ffffff→COLORS['background_card']`。
- 行号平移同步：TODO注释快照 `asset_detail.py` 353→354；架构统一基数 第四项 `qwen_setup.py` 48→49、170→171。
- 验证：定向 50/50＋70/70、默认冒烟 8/8、架构 341/341（首次 2 红＝行号平移，同步后复验全绿）；**命中 §5 五轮** → 干净 master `o07-fullsafe-master` 全量 **4983/4983、609.6 秒、0 红**（凭据 tree=`250b6384…`＝`4ed81e9:程序`，last_full 1394→1396）。提交内容 `4ed81e9`。
- 说明：本轮原领 1397，提交前中央号被并行轮推进到 1398，改领 1399；1397／1398 未由本会话产生提交。
- 未做（需用户决策）：hex（全站仅 8 处等于现有 token）、103 处旧调色板值、非 token 间距值、旧页面文字层级。下一轮候选：`workflow_settings.py`／`native_assets.py`／`background_characters.py` 等剩余决策-free 页。

## 2026-10-13：UI 路线图 §一 第 2 项（设计 token）单页迁移（R1396，功能轮 §3.1）
- 范围＝设计 token 迁移中**可证明零视觉变更**的子集、单页粒度：`asset_reference_images.py` 13 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改从 token 取值（`SPACING['md']`×11、`SPACING['xs']`×2），新增 `from ui_tokens import SPACING`。
- 依据：取值完全相等 → 渲染不变；间距与调色板无关 → 与「调色板三选一」决议互不冲突。未触碰任何颜色（此文件无内联 hex）。
- 验证：定向 `test_reference_images`＋`test_token_boundary` 26/26、默认冒烟 8/8、架构 341/341；`test_token_boundary` 该文件数字间距 18→5。1396−1394=2<5 且未命中 §5 → 不跑全量（最近绿全量 R1395 `tree=886cfd07…`）。提交内容 `ac01f9f`。
- 未做（需用户决策）：hex 颜色（仅 8 处等于现有 token）、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级 —— 均需先对设计 token 调色板三选一。
- 下一轮候选：同法继续 100% 可判定的单页（如 `prompt_window.py` 3/3、`native_assets.py` 3/9）。

## 2026-10-13：出站 HTTP 收口到 platform_tools.open_https（R1395，修复轮 §3.2）
- 范围＝R1393 登记的 4 条 agent 真候选中「网络传输」2 条（覆盖率审计26）。
- 裁定：两处调用点均为应用自身资产 I/O（参考图／云端视频下载）非模型路由；`download()` 依赖 `agent.core` 原子发布权威不能外移 → 只把出站调用收口到宿主适配层（同 R1394／R832）。
- 实现：`platform_tools` 新增 `open_https(url,*,timeout=60,data=None,headers=None)`（惰性 import urllib.request）；`agent/core.py` `request()`／`download()` 改经它（错误分类、HTTPS 强制、`geturl()` 重定向校验、1GB 上限、原子发布不变）。
- 台账／判据：`覆盖率审计26` 两条 pending→migrated、count 2→0；判据第 26 项真候选 2→0。
- 验证：定向 7/7、默认冒烟 8/8、架构 341/341；命中 §5 五轮 → 干净 master 全量 **4983/4983、602.9 秒、0 红**（凭据 tree=886cfd07…＝`d93993e:程序`，last_full 1390→1394）。提交 `d93993e`。4 条 agent 真候选全部裁定完毕。
- 下一轮候选：① secret sink（第 27 项）是否同批递归化；② 设计 token 迁移（卡在调色板决策，需用户确认）；③ 旧页面文字层级 backlog；④ `probe_http_endpoint` 是否并入 `open_https`。

## 2026-10-13：agent 进程原语收口到 platform_tools（R1394，修复轮 §3.2）
- 范围＝R1393 登记的 4 条 agent 真候选中「进程原语」2 条（覆盖率审计21）。
- 实现（生产代码，最小改动，行为不变）：`agent/core.py` `command()`：`subprocess.run` → `platform_tools.run_process`（惰性 import、移除模块级 `import subprocess`）；`agent/prompt_optimizer.py` MCP 桥子进程同改（模块级 import，保留 `subprocess` 供 `TimeoutExpired`／`SubprocessError`）。
- 台账／判据：`覆盖率审计21` 两条 pending→migrated、count 2→0；修正 `第四项` `json.loads` 行号平移（core 13→12、prompt_optimizer 174→175）；判据第 21 项真候选 2→0。
- 验证：定向 7/7、默认冒烟 8/8、架构 341/341；运行期 `command` 复验通过；1394−1390=4<5 且未命中 §5 升级条件 → 不跑全量。提交 `a966c41`。
- 保留待裁定：`agent/core.py:189/208`（HTTPS 传输，覆盖率审计26）。
- 下一轮候选：① 覆盖率审计26 两条 HTTPS 传输裁定／收口；② secret sink（第 27 项）是否同批递归化；③ 设计 token 迁移（卡在调色板决策，需用户确认）；④ 旧页面文字层级 backlog。

## 2026-10-12：覆盖率审计棘轮口径递归化（R1393，修复轮 §3.2）
- 范围＝R1390 登记待办「其余根目录口径门禁（coverage ratchet 20/21/22/24/25/26）是否同批递归化」的逐段评估与执行。**不改生产代码。**
- 评估：全递归实测新增 kind 21＝9／22＝2／26＝2，其中 skills／scripts／reference／outputs 属非产品目录；剔除非产品后新命中仅 agent 包 4 条。
- 实现：`_scan.py` 新增 `NON_PRODUCT_PARTS`＋`production_runtime_files()`（239 个运行时模块）；`test_coverage_audit_ratchet.scan()` 默认范围改它、台账键改相对路径 `_key()`；`架构统一基数.json` 覆盖率审计21／26 各 +2 pending（count 21→2、26→2）；判据文档第 21／26 行真候选 0→2。
- 新暴露真候选（pending 待裁定）：`agent/core.py:173`、`agent/prompt_optimizer.py:172`（subprocess）；`agent/core.py:189`／`208`（urllib）。
- 验证：定向 **7/7**、默认冒烟 **8/8**、架构 **341/341**（数量不变）；`1393−1390=3<5` 且未命中 §5 升级条件 → **不跑全量**。
- 下一轮候选：① 4 条 agent 真候选裁定／收口；② secret sink（第 27 项）是否同批递归化；③ 设计 token 迁移（**卡在调色板决策，需用户确认**）；④ 旧页面文字层级 backlog。

## 2026-10-12：UI 路线图 §三 第 4 项 — 项目进入路径覆盖门禁（R1391，修复轮 §3.2）
- 范围＝路线图 v1 §三「已存在权威，仅需审计覆盖率」第 4 项「项目选择／切换」（权威＝`DesktopStartupController`／`desktop_settings_service`）——承接 R1390 登记的缺口「缺『所有项目进入路径必经控制器』的架构覆盖门禁」。**不改生产代码。**
- 实现：新增 `tests/architecture/test_project_entry_boundary.py`（5 条）：① 静态冻结 `desktop.py` 直接 `self.load(...)` 的入口集合（进入＝open_project_or_cleanup／_choose_project_impl／new／import_json／enter；关闭＝gone／completed），新增未登记进入路径即失败；② 每条进入路径必须经当天选择记忆；③ `DesktopStartupController` 单次装配并绑定 `choose_project=self.choose_project`／`before_project_choice=self._after_first_paint`；④ 当天选择委托 `publish_desktop_preferences`（不直接写 settings_file）；⑤ 控制器模块不 import tkinter。`AGENTS.md` §5 清单补该文件。
- 反向验证（mutation）：向 `switch()` 注入未登记 `self.load(path)` → 门禁识别 `entering` 多出 `switch` 并失败。
- 验证：定向 **5/5**、默认冒烟 **8/8**、架构 **336→341**；**命中 §5 五轮规则（1391−1386=5）**，干净 master 工作树 `o07-fullsafe-master` `--all --safe` **4983 条、546.4 秒、0 红**（凭据 round=1390、tree=a8cfd2f0…＝内容提交 `37ed5bc:程序`；`last_full_safe_all_round` 刷新为 1390）。提交内容 `37ed5bc`。
- §三 7 项全部收口。下一轮候选（backlog）：① 设计 token 迁移（先统一调色板，可能改视觉须先确认）；② 其余走根目录口径的门禁（coverage ratchet 20/21/22/24/25/26、json_io/table 等）是否同批递归化（需逐段评估子目录候选）；③ 优化队列条件项（J20／J22—J26、R1068 真实清理等）。

## 2026-10-12：UI 路线图 §三 覆盖率审计 — 门禁口径对齐递归（R1390，修复轮 §3.2）
- 范围＝路线图 v1 §三「已存在权威，仅需审计覆盖率（7 项）」。
- 实现（**不改生产代码**）：`_scan.py` 新增 `production_files_recursive()`（递归口径，与 `production_files()` 同语义：排除 tests／tasks_round／维护记录／.git／__pycache__ 与 smoke_test／run_selftests／selftest_sandbox 及 test* 前缀）；`test_deletion_gateway`／`test_remove_authority`（对程序 scripts/ 开发脚本显式豁免 `_DEV_SCRIPT_PARTS`）／`test_completion_gate`（2 处）／`test_event_bus_boundary`（3 处）改递归扫描。
- **§三 7 项裁定**：6 项已收口（第 2 事件总线／第 5 删除／第 6 阶段完成本轮由根目录门禁升为递归门禁；第 1 配置读写／第 3 缓存失效／第 7 SKILL 说明标签已有门禁）；**1 项缺口**＝第 4 项「项目进入路径」（`DesktopStartupController`）缺架构覆盖门禁 → 登记待办。
- 子目录实测影响：删除仅 `scripts/clean_dev.py`（已豁免）、`stage.completed` 0、直调 `bus.emit` 0、`_emit` 包装器仍仅 pet_agent／pet_ui。
- 验证：定向 4 文件 **8/8**、默认冒烟 **8/8**、架构 **336/336**；`1390−1386=4<5` 且未命中 §5 升级条件 → **不跑全量**。提交 `fdb1daf`（报告／状态页补记 `c7e40e8`）。详见 [R1390](../程序/tasks_round/tasks_round_1390_result.md)。
- 下一轮候选：① 第 4 项项目进入路径覆盖门禁；② 其余走根目录口径的门禁（coverage ratchet 20/21/22/24/25/26、json_io/table 等）是否同批递归化（需逐段评估子目录候选）；③ 设计 token 迁移（须先确认调色板）。

## 2026-10-12：UI 统一入口覆盖轮 — 设计 token 内联常量棘轮门禁（R1389，修复轮 §3.2）
- 承接 R1388 只读审计（路线图 §一 第 2 项「设计 token」）：新增 `tests/architecture/test_token_boundary.py`（5 条）——`hex_color_count`／`numeric_padding_count` 两谓词，业务页内联 hex 与数字 `padx/pady` 按文件**棘轮「只减不增」**（新增文件即违规）；权威 `ui_tokens/ui_theme/ui_widgets/ui_icons` 与 `skills` 独立脚本豁免；基线＝R1388 审计值（hex 111 处/8 文件、padx/pady 213 处/19 文件）。`AGENTS.md` §5 清单补该文件。**不改生产代码。**
- 未纳入棘轮：数字 `font/wraplength/width/height` 候选 189 处/32 文件（`width/height` 部分属布局），只审计。
- 验证：定向 **5/5**、默认冒烟 **8/8**、架构 **331→336**；`1389−1386=3<5` 且未命中 §5 升级条件 → **不跑全量**（最近绿全量 R1387 `tree=000477da…`）。
- 下一轮候选（backlog）：① 先确认再统一调色板（`ui_theme.py` 复用 `ui_tokens`，**可能改视觉**）；② 逐页迁 hex（8 文件 111 处）；③ padx/pady（19 文件 213 处）与字号按单页粒度另批；④ §三 覆盖率审计 7 项。

## 2026-10-12：只读诊断 — 设计 token 内联视觉常量审计（R1388，§3.5）
- 范围＝路线图 v1 §一 第 2 项「设计 token」（审计点原文「页面是否仍内联视觉常量待审计」）。扫描 269 个生产 `.py`（排除 tests／tasks_round／维护记录）：**业务页内联 hex 111 处/8 文件**（pet_ui 45／desktop 31／asset_detail 21／cell_hover 6／keyframe_comfy 3／app 2／storyboard_table_ui 2／previs_monitor 1）、**数字 padx/pady 213 处/19 文件**、**数字字号尺寸候选 189 处/32 文件**。
- **双调色板风险**：`ui_tokens.py`（14 hex）与 `ui_theme.py`（53 hex）各自硬编码，`ui_theme.py` **未** import `ui_tokens`；全生产仅 `desktop.py` import `ui_theme`，`ui_tokens` 被 14 个模块 import。同一 hex 多点重复 → 改色易漂移。现状 `tests/architecture` 无 token 专用门禁（仅 scrollbar theme）。
- **未收口**，登记 backlog：先统一调色板（ui_theme 复用 ui_tokens）、再逐页迁 8 个文件的 111 处 hex；新增 `test_token_boundary.py` 棘轮门禁（按文件冻结、只减不增、权威与 skills 脚本白名单）；padx/pady 与字号按单页粒度另批。
- 本轮只读：不改生产代码/测试/台账/路线图；默认冒烟 8/8（§5 只读诊断默认不跑测试）；**不跑全量**（距最近绿全量 R1387 仅 2 轮）。报告见 [R1388](../程序/tasks_round/tasks_round_1388_result.md)。
- 下一轮候选：R1389 修复轮＝先统一调色板 + 逐页迁 hex + 加 token 棘轮门禁（第一批）。

## 2026-10-12：UI 统一入口覆盖轮 — 按钮门禁递归零容忍（R1387，修复轮 §3.2）
- 承接 R1381 复核校正 backlog：`test_button_boundary` 仍是「固定页清单」。本轮按路线图 v1 §一 第 1 项「按钮」（审计点原文「全页面覆盖率待审计」）把门禁收紧为「递归零容忍」，与 R1381 弹窗门禁同法。
- `tests/architecture/test_button_boundary.py`：新增 `BUTTON_OWNERS={'ui_widgets.py'}`（统一基类自身允许）与 `EXCLUDED_PARTS`（与 test_dialog_boundary 一致）；新增 `test_production_modules_use_semantic_buttons`（`ROOT.rglob('*.py')` 递归扫全部生产模块，裸 `tk/ttk.Button` 零容忍）与 `test_recursive_scan_covers_subdirectories`（镜像 canary）；保留既有逐页语义组件断言。**不改生产代码。**
- 站点实测：递归 269 个生产 `.py`，除 `ui_widgets.py`（7 处基类自身）外 **0 命中**（站点早已清零，缺的只是门禁口径）。
- 验证：定向 **25/25**（原 23）、默认冒烟 **8/8**、架构 **329→331**；**命中 §5 五轮规则（1387−1382=5）**，收口在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4973 条、572.5 秒、0 文件有红**（凭据 `round=1386`、`tree=000477da…`＝内容提交 `d5f597f:程序`；`last_full_safe_all_round` 刷新为 1386）。提交内容 **`d5f597f`**。
- 下一轮候选（backlog）：设计 token 内联视觉常量；§三 覆盖率审计 7 项。测试按 §5。

## 2026-10-12：UI 统一入口覆盖轮 — 阶段显示收口（R1386，修复轮 §3.2）
- 承接 R1382 只读审计登记的待办「生产文案阶段编号漂移」，对应 `维护记录/UI统一入口路线图_v1.md` §二 第 15 项「阶段显示」（完成判据原文「任何阶段名称展示均从权威表取值」）。
- 新增唯一权威入口 `pet_bus.stage_label(stage)`＝`'%02d %s' % (STAGES.index+1, STAGE_NAMES[stage])`（未知阶段退回 `stage_name`；步号与 `desktop.PAGES` 同源）。keyframe_batch（4）／stage_parallel（GATES SG-01..05）／pet_ui（gaps 气泡）／desktop（视频页标题×2、镜头编号提示）／skill_tools（导出 note）改由它现算；`skill_panel.stage_label` 退化为薄封装。生产注释／docstring 过期编号按权威序纠正（资产 03→05／连贯性 04→06／定稿 05→07／首帧 06→08／白模 07→09／视频 08→10／配音 09→11／剪辑 10→12／质检 11→13）；`skill_tools.PAGES` 去掉已死旧编号前缀（行为不变）。**不改** `stage_path_service.LEGACY_NUMBERED`／`desktop.PAGES`／`stage_layout.STAGES`。
- 门禁 `tests/architecture/test_stage_display_boundary.py` +3：生产「NN 阶段名」编号必须==`pet_bus.STAGES` 步号（豁免 `stage_path_service.py`）；6 个已迁移展示位点冻结不得退回写死；`stage_label` 对齐导航序。架构 326→**329**。
- 验证：定向 **1275/1275、0 文件红、305.5 秒**；默认冒烟 **8/8**；路线图条目收口触发全量，在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4971/4971、0 红、534.1 秒**（凭据 `round=1382`、`tree=d9aee73c…`＝内容提交 `4cb02d3:程序`；同一内容树**不重跑第二次**）。提交内容 **`4cb02d3`**（26 files）。
- 审计口径修正：R1382 报的生产 14 文件 97 处含 1 处误报（`animatic_service.py:1`「L2 分镜预演」的 L2 是层级前缀）；加词边界后准确＝生产 **13 文件 96 处**、`tests/` 19 文件 56 处。
- 编号：开工领 1383，提交时中央计数被并发车道推到 1385，重领得 **1386**；1383／1384／1385 无结果文件。全量凭据 `round=1382`（跑时本轮结果未落盘，执行器取最新已完成结果号）。轮次头写 **1387**。
- 下一轮候选（backlog）：`test_button_boundary` 由固定页清单收紧为递归零容忍（站点已 0 裸 `tk/ttk.Button`）；设计 token 内联视觉常量；§三 覆盖率审计 7 项。测试按 §5，纯服务层改动不强制全量。

## 2026-10-12：状态接续轮 — 更新阻塞与待办（R1382，§3.11）
- 按用户要求更新 project_status.md 的「已知阻塞与待办」与接力状态；**本轮不改生产代码、无功能改动、未跑全量**（未触生产文件、未命中 §5）。默认冒烟 smoke_test.py 8/8。
- **只读审计（登记为待办，未实现）**：生产文案散落的「NN 阶段名」仍是旧编号（R1375 只收了 24 处「第N步」）。排除 stage_path_service.LEGACY_NUMBERED（旧目录只读兼容）后命中生产 **14 文件 97 处**（skill_tools.py 56／desktop.py 15／stage_parallel.py 5／keyframe_batch.py 4／pet_ui.py 4／app.py 3／其余 6 文件各 1–2）＋tests/ **19 文件 56 处**。权威＝pet_bus.STAGES 顺序（01 剧本准备…13 质检与交付）／STAGE_NAMES；导航标签＝desktop.PAGES 的 f'{index:02d}  {stage_name(stage)}'。
- 用户可见字符串：keyframe_batch.py:51/52/141/236（04→08）、desktop.py:2484（02→03）、desktop.py:7015/7058（08→10）、pet_ui.py:2956/2959、stage_parallel.py:477–489、skill_tools.py PAGES 说明列；勿误改 stage_path_service.py:26–28（LEGACY）与 desktop.py:5180/5212（01/02 正确）。
- 现有门禁 tests/architecture/test_stage_display_boundary.py 只校验 desktop.PAGES 生成源，未覆盖散落字符串；修复轮须加门禁并同轮改 tests/ 的 56 处断言。对应路线图 §二 第 15 项「阶段显示」。
- 下一轮候选：按 §3.2 修复轮纠正上述编号＋新增架构门禁；其后把仍是「固定页清单」的 test_button_boundary 按 R1381 同法收紧为递归零容忍，及设计 token 内联视觉常量／§三 覆盖率审计 7 项。

## 2026-10-12：UI 统一入口覆盖轮 — 弹窗门禁递归化收口（R1381，修复轮 §3.2）
- `tests/architecture/test_dialog_boundary.py` 全局门禁由 `ROOT.glob('*.py')` 改 `ROOT.rglob('*.py')`（覆盖 `batch_frames_tool/`／`agent/`／`scripts/` 等子目录，对齐 R922「递归审计」口径）；裸窗谓词由「属性式」扩为「属性式 ∪ `from tkinter import Toplevel` 名字式」，并加镜像 canary。全生产模块裸构造 `Toplevel` = 0（仅 `ui_widgets.py` 统一基类自身除外）。
- 验证：`test_dialog_boundary` 6/6、定向 24/24、默认冒烟 8/8、架构 326/326（+1），0 红；1381−1380=1<5 且未命中 §5 升级条件，不跑全量。见 [R1381](../程序/tasks_round/tasks_round_1381_result.md)。
- **重要校正（R1381 复核）**：路线图其余待审计项多数**早已递归零容忍收口**（表格／输入／下拉／提示／右键菜单／文件选择／快捷键／Tooltip／图标／滚动条／文案与复制／忙碌态 均为 `violations==[]`）。此前 backlog 列「~22 项未收口」为**高估**，已更正。
- 下一轮候选：把仍是「固定页清单」的门禁（`test_button_boundary`；站点实测裸 `tk/ttk.Button`＝0）按 R1381 同法收紧为递归零容忍；其后处理 阶段显示（仅查 `desktop` 生成源）／设计 token 内联视觉常量／§三 覆盖率审计 7 项。
## 2026-10-12：会话收尾（R1376—R1380 已收口，无待办）
- 本次仅做收尾复核并记录：确认 R1376—R1380（UI 统一入口覆盖轮：忙碌态／文案与复制／卡片容器／文字层级）已全部提交并收口，本次会话未新增功能改动、未改任何生产代码或测试。
- 状态一致：`程序/project_status.md` 当前轮次＝1381；中央 `.git/round-counter.json` `last_claimed=1380`；R1267 清单 O01—O48 全完成。
- 全量凭据口径（**修正**）：R1380 全量 4967/4967、0 红、631.2 秒的 tree=f62cd088…＝该轮**内容提交 `e25c70d:程序`**，**不**等于当前 `HEAD:程序`（＝3c0d7ead…）。其后 R1380 的 3 个记账提交（`633eb4e` 报告与状态页、`452fb73` 与本次收尾提交 接力）只改 `程序/tasks_round/` 与 `程序/project_status.md`，未改生产代码。因 `latest(1380)−last_full(1380)=0<5`，`test_round_baselines.test_full_safe_all_is_required_every_five_rounds` 走 `full_safe_required=False` 提前返回、**仍绿**（已实跑该文件 5/5 OK）；若后续某轮再次要求全量，须在干净 master 工作树对新树重跑，**勿复用此凭据**（树不同）。
- 工作区：master 仅余他人**已暂存** WIP（`程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）与未跟踪产物（`outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`），不读／不改／不暂存／不覆盖；无属于本轮的未提交改动或阻塞。
- 下一步：无待办；开工即读 `程序/AGENTS.md` §0，测试按 §5 触发表（每轮 `smoke_test.py`，结构治理轮 `--architecture`，触及 `程序/` 生产文件后命中 §5 升级条件或 ≥5 欠账才全量）；文字层级旧页面 backlog（见 R1380 审计表）按单页粒度滚动迁移，非阻塞。等用户新指令。

## 2026-10-12：UI 统一入口覆盖轮完成（R1376—R1380，路线图 4 项全收口）
- 范围＝`程序/维护记录/UI统一入口路线图_v1.md` 尚未收口的 4 项：卡片容器、文字层级、忙碌态（提交/取消/成功/失败/迟到结果全链路）、文案与复制。用户 5 条硬要求：先读 `程序/AGENTS.md` §0/§2/§5 定轮型；单页粒度分批迁移（不整仓机械替换）；验收以各项「完成判据」原文为准、收口写「完成全量覆盖审计」；测试按 §5 触发表、不因收尾跑全量兜底；完成/暂停都更新接力。
- R1376 忙碌态：`app.py`／`native_assets.py` 的进度条 `start/stop` 收口到 `BusyState.set_busy`；`tests/architecture/test_busy_state_boundary.py` 7 条（含「生产代码 `ttk.Progressbar` 的 `.start/.stop` 只许出现在 `ui_widgets.py`」零容忍门禁）。架构 315→320。
- R1377 文案与复制：4 处复制失败术语统一为「复制失败：…」，禁止「复制成功／成功复制」；修正 `asset_detail.py` 锚点复制失败被成功文案覆盖的缺陷；`test_copy_entry_boundary.py` 增递归生产扫描。架构 320→321。
- R1378＋R1379 卡片容器：页面级信息/操作单元承载区 `ttk.LabelFrame`→`ui_widgets.Card`（标题改卡内标签）。R1378 迁 asset_detail(7)/native_assets/asset_batch；R1379 迁 keyframe_comfy(2 窗)/desktop(6 区：参考网站分类导航、连续性表格框、待办与裁决、开工前先确认、本地生成、线上生成)。架构 321→323→325。全站点审计：21 页已用 Card，其余（white_model/workflow_settings/cloud_video 的卡内小节、skill_panel 锁定几何阅读区、batch_frames_tool 独立脚本）豁免。**卡片容器完成全量覆盖审计**。
- R1380 文字层级：asset_batch/keyframe_comfy 的功能说明→`DescriptionBlock`、状态行→`ProgressLabel`、标题→`style='Tokens.Title.TLabel'`；`test_text_component_boundary.py` 的 `TEXT_PAGE_COMPONENTS` 增这两页（7 页门禁固化）。全站点审计：组件内部/主题/自绘、缩略图窄格豁免；标题层级无语义组件（登记改用 `Tokens.Title.TLabel`）；其余说明文字按单页粒度续跟（backlog）。**文字层级完成全量覆盖审计**。
- 验证：各轮定向＋默认冒烟 `smoke_test.py` 8/8，0 红。**R1380 命中 §5 五轮规则（1380−1375=5≥5）**，收口在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4967/4967、0 红、631.2 秒**（首次即绿）；凭据 round=1380、tree=f62cd088…＝`HEAD:程序`、last_full_safe_all_round=1380；同树架构门禁 325/325；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无阈值抖动。
- 提交：R1376 a44ad5c、R1377 ef25cde、R1378 dd87f02、R1379 6bdbc0f、R1380 e25c70d（内容）＋633eb4e（补记全量结果）。`project_status.md` 当前轮次＝1381。
- 下一步：路线图 4 项已全收口、无待办；R1267 清单 O01—O48 亦已全完成。文字层级旧页面 backlog（见 R1380 审计表）按单页粒度滚动迁移，非阻塞。等用户新指令。

## 2026-10-12：O48 完成 — R1267 清单 O01—O48 全部收口
- 按 R1267 清单 O01→O48 顺序逐个完成。**O48 已完成（R1375），R1267 清单全部完成**。
- O48（13 阶段、文档与界面标签使用一致权威源）= R1375：`pet_bus.py`（L0）新增 `stage_step(stage)`（按 `STAGES` 顺序给两位步号，与阶段目录、导航页 `PAGES` 同源，未知阶段空串）；13 个生产模块（`app`／`asset_context`／`asset_detail`／`batch_frames_tool/batch_frames`／`desktop`／`engine`／`local_video`／`storyboard_files`／`storyboard_selection`／`video_navigation`／`white_model`／`white_model_ref`／`agent/shot_assets`）的用户可见文案改由它现算，纠正 R1124 前旧步号（分镜 02→03、资产 03→05、定稿 04→07、首帧 05→08、白模 06→09、视频 07→10，共 24 处）；`architecture.md` §4 阶段表 12 行错位→13 行（序号 01—13／ID／中文名逐行＝`pet_bus.STAGES`／`stage_name`）、§5 并行表与 §8 输入输出表各补 `animatic` 成 13 行；`README.md` 第 61 期历史目录树加一行「历史记录」指回 PROJECT_MAP 与 `pet_bus.STAGES`（不动历史正文）。**不改业务逻辑、门禁、路径、分层；不重排页面**。见 [R1375](../程序/tasks_round/tasks_round_1375_result.md)。
- O48 验证证据：架构 315/315（原 312，+3 新用例）＋定向 1456 条 386.7 秒（仅 1 红为既有环境相关）＋交互验收 244/244（`tk scaling` 1.0／1.5／2.0、`<Return>` 发送、takefocus／焦点回归、禁用控件说明）＋默认冒烟 8/8，0 红。唯一红 `test_workflow.DesktopModelPoolTests.test_stage_model_selects_the_matching_desktop_agent`：主树未跟踪 `程序/配置/宠物/配置.json` 把 `claude-desktop` 标签改成「Claude Desktop」，出厂池为「Claude Code」；干净全量工作树单跑为绿（既有、用户配置相关，非本轮回退）。资产子步骤编号（固定角色＝1／场景道具＝2／图片＝3）属另一套口径，未改并列入新门禁白名单。
- 登记平移：`维护记录/架构统一基数.json` 第四项 `batch_frames_tool/batch_frames.py` point 13→14／77→78；`维护记录/TODO注释快照_20261003.json` `asset_detail.py` 350→351；`维护记录/skip台账.json` 用例更名 `..._points_to_step04`→`..._points_to_step07`。
- O48 全量：1375−1374=1<5，但 O48 为路线图收口项（§5「路线图条目收口」）→ 收口在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4957/4957、0 红、715.1 秒**（首次即绿，无二次全量）；凭据 round=1375、tree=c3df6a57…＝`HEAD:程序`、last_full_safe_all_round=1375；4957−4954=3＝本轮新增架构用例。提交：内容 d5de4df、报告与接力 afcc0a4。
## 2026-10-12：O47 完成（历史）
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O46 已完成，**O47 已完成（R1374）**，下一项 O48（13 阶段、文档与界面标签使用一致权威源，P2／事实·建议，S/M）。
- O47（关键真实链路集成测试）= R1374：**无生产代码改动**，只新增 `tests/test_critical_chains.py` 17 条（合成数据＋注入传输／发布器，不调用真实付费 API、不依赖 Tk）。链路 A 回收站（O38/O39）：`recycle_paths` 提交／失败注入整批 `rolled_back`→`restore_recycle_batch` 复原字节、`version_retention` 六类保留原因、`edit_source_versions` 读 `13质检交付/导出成片` 的 `edit_bundle.json`、`clean_project` 只处理下载根下带 `config.json` 的项目且回收不永久删除；链路 B 模型请求链：URL／请求头／payload 冻结、密钥不入 payload、`response_meta` 白名单、`usage_of` 映射 `cached_tokens`、`model_diagnostics.record` 落盘不含任何正文、超时 `error_class=timeout` 不抛；链路 C 导入→完成证据（O02/O03）：`import_audio` 落 `11配音与字幕/音频` 且源文件保留、导入≠完成、非对白不能顶替对白、`prepare→confirm` 后才完成、`import_delivery_master` 落交付阶段；链路 D 剧本→结构→分镜：`write_structured_script` 由本地规则生成结构稿、`verified_stage_output(script_structure)` 真、`completion_evidence(storyboard)` 要有采用且含镜头；O04 `video_task_state.submission_block_reason` 区分需修改返工／未决禁投；O05/O06 `stage_parallel.frames_ready` 逐项报未配置／已删除／越界／缺失／空文件／损坏 PNG。见 [R1374](../程序/tasks_round/tasks_round_1374_result.md)。
- O47 验证证据：新增 17/17；定向 `-k critical_chains recycle audio_import stage_completion delivery_import script_contract stage_flow` 187/187、架构 312/312、默认冒烟 8/8，0 红。实测契约事实：`completion_evidence` 对 script/script_structure/storyboard 的返回 detail 是固定「未找到」文案，判定只看 ok；`stage_parallel.frames_ready` 在无可用帧且 keyframe 未跑过时按「上游还没做先不拦」放行，故用例需含真实非空帧文件。
- O47 全量：1374−1373=1<5 且未命中 §5（只新增测试），收口在干净 master 工作树跑一次 `--all --safe`：全量 4954/4954、0 红、665.09 秒（干净 master 工作树 `o07-fullsafe-master`，凭据 round=1374、tree=4778c99e…＝`HEAD:程序`、at=2026-10-12T18:47:48、last_full_safe_all_round=1374；4954−4937=17＝本轮新增用例；无阈值抖动）。

## 2026-10-12：O46 完成（历史）
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O45 已完成，**O46 已完成（R1373）**，下一项 O47（测试从"数量多"补到关键真实链路，P2／验证·建议，M/L）。
- O46（模块治理与热点性能按段推进）= R1373：先测七条热点路径——Tk 侧复用 基准_启动与页面.py full（启动 ready 735.1→714.8ms、首帧 297.7→289.0ms、缩略图冷 2.8ms、300 资产页 1837.9→1515.5ms、滚动 20 步 0.2ms），缺的换项目／刷新目录／长对话／媒体导入新增无 Tk 探针 `基准_热点路径.py`（≤16ms）；纯服务层无瓶颈 → 不做全项目异步化。再做两段保持入口的迁移：`platform_tools`（L0）新增 `open_directory`／`find_editor_shortcut`，`desktop` 的 `find_editor_shortcut`／`open_folder` 变 1 行入口；`idea_chat_controller`（L3）接管 `bubble_timestamp`／`collapse_preview`／`speaker_name`，`desktop` 的 `bubble_time`／`bubble_preview`／`model_name` 变 1 行入口（desktop 7510→7491 行）。见 [R1373](../程序/tasks_round/tasks_round_1373_result.md)。
- O46 同步项：`tests/architecture/test_migrated_ui_boundaries.py` 适配入口集合登记 `find_editor_shortcut`／`open_directory`；`维护记录/TODO注释快照_20261003.json` 的 desktop.py 行号 2753→2741 平移（注释集合不变，沿 R1330 做法）。
- O46 验证证据：新增 `tests/test_idea_chat_presentation.py` 10/10、`tests/test_platform_tools.py` +3（20/20）；定向 30/30、Tk 消费者 `ui_edges idea_chat unification_ratchet` 259/259、架构 312/312、默认冒烟 8/8，0 红。
- O46 全量：1373−1372=1<5 无五轮欠账且未命中 §5，收口在干净 master 工作树跑一次 `--all --safe`：全量 4937/4937、0 红、710.39 秒（干净 master 工作树 `o46-fullsafe-master`，凭据 round=1373、tree=efdd7f8a…＝`HEAD:程序`、at=2026-10-12T18:24:25、last_full_safe_all_round=1373；4937−4924=13＝本轮新增用例；无阈值抖动）。

## 2026-10-12：O45 完成（历史）
- O45 = R1372（把分发声明变为可复验的干净安装流程：新增 `程序/scripts/distribution_build.py` 的 `parse_manifest`／`plan`／`build`／`verify`＋CLI，精化 `distribution_manifest.md`，新增 `tests/test_distribution_build.py` 12 条）；全量 4924/4924、0 红、688.63 秒（凭据 round=1372、tree=71554aa7…）。详情见 [R1372](../程序/tasks_round/tasks_round_1372_result.md)。
## 2026-10-12：O44 完成（历史）
- O44 = R1371（密钥四态可诊断＋诊断预览与回显脱敏）；全量 4912/4912、0 红、752.38 秒（凭据 round=1371、tree=de0084a9…）。详情见 [R1371](../程序/tasks_round/tasks_round_1371_result.md)。

## 2026-10-12：R1335 并入 master（阶段④分集增量上下文）
- 分支 `codex/episode-incremental-context` 已合入 master。`script_contract.split_script_episodes`＋分集账本 `write_dir(project,'script')/剧本分集增量账本.json`（每集 sha256＋based_on 其余集快照）；`writing_api.reply()` 前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 后更新账本；`workflow_tasks._episode_change_notice()` 只给本地 Agent 报集号；首次／无账本退化为全量。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。
## 2026-10-12：O43 完成（历史）
- O43 = R1370（检查点版本化＋只读恢复预览）；全量 4899/4899、0 红、963.97 秒（凭据 round=1370、tree=4a7be90a…）。详情见 [R1370](../程序/tasks_round/tasks_round_1370_result.md)。

## 2026-10-12：O40 完成（历史）

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O40 已完成（见上一节）。
- O40（项目管理、备份与清理统一空间和恢复说明）：`projects.py`（L2）新增 `_drop_registration_entry`（登记移出索引一律先改 deepcopy、发布成功才提交 `self.info`；`OSError` 时内存回退到磁盘事实并带 `ui_message` 重抛），`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它，删除路径在登记写失败时给出「内容已移入回收站、点『重新查找项目』或『重建项目索引』、仍可从回收站恢复」的定向指引；新增模块级 `_discover_candidates`（把 `reconcile_missing` 的一级目录扫描抽出复用、行为不变）与 `Projects.rebuild_registry`（按磁盘事实保留仍在的登记、移除失效登记、补登新目录；无变化不写盘；只读写一级目录与登记文件，不移动也不删除任何项目内容，回收站永不回流）。`desktop.py`（L4）新增 `Desktop.rebuild_project_index` 与主页「重建项目索引」按钮，主页状态栏与删除确认框把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述（移入回收站＝可恢复、不是永久清除、同盘回收不等于释放空间）。见 [R1367](../程序/tasks_round/tasks_round_1367_result.md)。
- 契约变化：删除／清除路径的登记写失败不再让内存先显示成「已删除」（内存与磁盘登记都停在删除前状态）；新增 L2 公开方法 `rebuild_registry`（返回 `{kept,dropped,added,changed}`）；「永久清除」只做界面单独明示，**未新增任何永久删除入口**（`projects.py` 只回收，无 `rmtree`／`unlink()`）；「从备份恢复」本轮按「项目库回收站即删除前可恢复副本」实现与验证，未新建独立备份子系统。
- 验证证据：新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1367−1364=3<5 无五轮欠账，但改动命中 §5（项目删除语义），收口在干净 master 工作树 `o40-fullsafe-master` 跑 `--all --safe`：第 1 次为新工作树环境未就绪（缺 4 个嵌套仓库与 3 个忽略运行文件）假红，补齐后定向修绿，第 2 次 4859/4859、0 红、527.6 秒，凭据 round=1367、tree=1d7630f1（＝`HEAD:程序`），`last_full_safe_all_round=1367`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：O40 为 R1367、O41 为 R1368；`project_status.md` 的 `当前轮次` 已改为 1369（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
