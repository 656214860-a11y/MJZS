# R2758 结果：剧本结构页阅读体验优化（行号栏／查找替换／大纲跳转／字号缩放）
<!-- round-evidence: {"commit_base": "fd56ad67", "credential_hits": 0, "evidence_sha256": "a3dc4a6ab85f0fcc", "exit": 0, "failed": 0, "passed": 20, "round": 2758, "tests": "run_selftests.py -k script_line_numbers script_find_bar script_outline script_zoom"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1），执行 `程序/tasks_round/剧本阅读体验优化任务书.md`。
   自然语言剧本与结构化剧本两种阅读器同时获得四项能力：常驻逻辑行号栏、
   查找／替换条、集／场大纲跳转、字号缩放（键盘＋Ctrl+滚轮）；不引入
   代码折叠、多光标、小地图、HTML 渲染或第三方编辑器，零第三方依赖不变。
   文档先行：S02 阶段文档新增 REQ-S02-36／DES-S02-36 后实现。
   轮次号说明：本轮工作最初以 R2641 领号实施；提交时中央计数器已被
   其他车道推进，`round_claim.py next` 重新领取 **R2758**（分支
   `codex/wip-R2758`，由 `codex/wip-R2641` 脏树带出）。R2641 成空号
   （无提交、无结果文件）；本轮全部改动与证据以 R2758 为准。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - 新增 4 个测试文件共 **20 条用例全绿**
     （`test_script_line_numbers` 4、`test_script_find_bar` 8、
     `test_script_outline` 6、`test_script_zoom` 2）。
   - 相关回归（script_structure 系列＋script_view_style 等 8 个文件）：
     **72 条用例 0 红**；与新测试合并跑 **92 条用例**，仅
     `test_script_zoom` 一条因 `script_reading` 拆分后方法归属
     `box.aids` 的断言路径过期而红，已修正后复跑 2/2 绿。
   - `smoke_test.py --architecture`：**466 条用例全部通过（0 红 0 错）**。
     过程中修复三处与本轮相关的门禁问题：
     `desktop_script_pages.py` 超 1000 行模块上限（拆出
     `script_reading.py` 后约 919 行）；覆盖率基线随新增 4 个生产模块
     由 367→371，已用 `scripts/coverage_report.py` 显式重测刷新
     `覆盖率基线.json` 并同步 runbook §11 数字（371/59/312/8）；
     `runbook §10` 基准历史声明缺失导致的 ERROR 已补。
   - 分支环境修复（不入提交）：本工作树 `程序/skills/00全流程SKILL/
     AIGC创作全流程` 子模块工作副本与父仓登记的 gitlink `1a43ae5`
     不一致（多出 `short-drama-director/scripts/` 等新版文件，含 5 处
     未登记 `json.loads` 触发统一棘轮）。已用主工作区干净的 `1a43ae5`
     检出做镜像对齐（robocopy /MIR，剔除 `.git`），该目录不受父仓
     版本控制，属工作树环境修复。
   - `test_round_number_continuous`：写结果文件后本分支会出现
     「状态页轮次 != 最新结果+1」的固有口径红——`project_status.md`
     仅 master 可提交，合入轮同步状态页后转绿（同 R2612 先例；
     本分支结果轮次 2758 与状态页差距较大，因中间轮次由其他车道产生）。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账；合入 master 前
     按 §5 触发条件另计）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；`优化待办队列.md` 新增一条登记项：「阅读框跨页重复」
   ——自然剧本正文在剧本准备页与剧本结构页各有一套阅读/编辑实现，
   待后续结构治理轮统一，本轮不实现仅登记（规则 30a 如实记录）。

## 改动清单

- `程序/script_line_numbers.py`（新增）：`LineNumberGutter(tk.Canvas)`，
  经 `text.index('@0,0'/'@0,<h>')` 与 `dlineinfo` 对齐可视逻辑行；
  软换行折行不单独编号；随 yscrollcommand／Configure／内容替换／
  `set_font` 刷新；宽度随最大行号自适应。
- `程序/script_find_bar.py`（新增）：`_search_positions`（转义正则、
  非重叠字符偏移）、`FindBar`（大小写切换默认不敏感、上一条/下一条
  循环、计数显示、替换一个/全部、Esc 关闭、只读拒绝替换并提示先点
  「编辑」；替换自尾向前保偏移，经 `<<Modified>>` 走既有修改/撤销/保存链）。
- `程序/script_outline.py`（新增）：`outline_entries` 复用
  `script_view_style.spans()` 识别自然稿「第…集／场景…：」与结构稿
  标题 tag，清洗 Markdown 标记并截 40 字；`OutlinePanel` 点击 `see()`
  跳行并临时高亮 `script_outline_hit`，无标题显示空态。
- `程序/script_reading.py`（新增）：自 `desktop_script_pages.py` 拆出的
  阅读编排——`_SCRIPT_FONT_TAGS`、`_font_at_size`、预览构建、缩放与
  gutter/outline/查找条同步（`_reading_sync` 在 `load_preview` 前挂接，
  大文档分块加载完成后统一收尾）。
- `程序/desktop_script_pages.py`：`_ContentBox.build()` 接入
  gutter/find/outline 与阅读快捷键；`preview._ctrl_wheel_zoom`
  挂接缩放入口；阅读辅助方法块移交 `script_reading`（文件回到
  模块上限内）。
- `程序/desktop_layout.py`：`scroll_page()` 识别
  `_ctrl_wheel_zoom`——Ctrl+滚轮委托内容框缩放，普通滚轮维持原滚动。
- `程序/ui_tokens.py`：`SCRIPT_VIEW_FONT`、`SCRIPT_VIEW_FONT_MIN=8`、
  `SCRIPT_VIEW_FONT_MAX=32`、`SCRIPT_GUTTER_WIDTH`。
- `程序/tests/architecture/_layers.py`、`程序/architecture.md`：
  四个新模块登记 L4。
- `程序/docs/stages/S02_剧本结构.md`：REQ-S02-36／DES-S02-36。
- `程序/PROJECT_MAP.md`：剧本结构页双阅读器能力与新模块登记。
- `程序/runbook.md` §10/§11、`程序/维护记录/覆盖率基线.json`：
  基准历史声明补齐、覆盖率基线刷新（367→371）。
- `程序/tests/test_script_{line_numbers,find_bar,outline,zoom}.py`：
  新增 20 条用例。

## 验证

- 语法/导入：全部改动文件 AST 与 import 检查通过。
- 功能测试：4 个新文件 20/20 绿；script 相关回归 72/72 绿；
  合并跑 92 条仅 zoom 一处断言路径过期（已修）。
- 冒烟：8/8。架构门禁：466/466 绿（修复模块上限、基线口径、
  子模块环境漂移后三项归零）。
- 关键行为：行号按逻辑行对齐可视区且随滚动/缩放/换行同步；查找
  计数与循环正确、替换走 `<<Modified>>` 撤销链、只读拒绝；大纲点击
  `see()`＋临时高亮、空态正确；Ctrl+=/- 与 Ctrl+滚轮缩放双阅读器
  生效且夹取 8–32pt，普通滚轮仍滚动；大文档分块加载收尾后
  gutter/outline/缩放状态一致。

## 未运行项与说明

- 全量 `--all --safe` 未跑：功能分支不累计欠账。
- `test_round_number_continuous` 分支固有口径见上，合入轮转绿。
- 子模块工作副本对齐为环境修复，不产生父仓 diff；若后续需要
  `AIGC创作全流程` 子模块新版内容，应走子模块自身提交与
  gitlink 更新流程，不在本轮范围。
- 领号沿革：R2641 领号后中央计数器被其他车道推进至 R2704+，
  提交被 commit-msg 钩子拦截后重新 `next` 领得 R2758；
  R2641 无提交无结果文件，成空号。
- 队列：`round_claim.py` 领号 R2758，无匹配队列任务 ID。
