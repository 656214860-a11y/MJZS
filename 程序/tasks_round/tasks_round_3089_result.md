# R3089 结果：SKILL 生命周期 T7——设置页「SKILL 管理」统一管理页
<!-- round-evidence: {"commit_base": "39ea00fc", "credential_hits": 0, "evidence_sha256": "8f7f79dfe3cf4c10", "exit": 0, "failed": 0, "passed": 692, "round": 3089, "tests": "run_selftests.py -k pet_skills_manage pet_settings pet_ui skill_panel pet_settings_contract"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T7；基于 R3084 `39ea00fc`，同栈功能工作树 `codex/wip-R3089`）。
**测试**：`smoke_test.py --affected pet_skills_manage pet_settings_ui pet_ui_settings pet_ui_support pet_ui_view skill_panel pet_settings_contract` → 冒烟 8/8；定向门禁 58 文件全量跑通，唯一红 `test_pet_ui.ForegroundTests.test_a_line_said_while_away_goes_into_the_record_only`（云泡可见性时序），单跑 3/3 与整类 27/27 复绿，判定并行负载下偶发、与本改动无关（设置页不触云泡路径）；`smoke_test.py --architecture` 470 条，12 红全部修复后 8 个相关测试文件 48 条复跑全 OK，余 `test_round_number_continuous`（堆叠分支状态页滞后，同前轮口径）。
**基线**：冒烟 8/8；架构门禁当轮 470 条、改后实跑红 1（轮次连续性，堆叠分支已知）；全量回归凭据未新增（功能轮分支不累计欠账）。
**欠账**：无新增；`project_status.md` 仅 master 可提交，堆叠分支轮次号差按先例记录。

## 变更摘要

- `contract/pet_settings_contract.py`：`TABS` 增 `('skills', 'SKILL 管理')`，排在预算与开发信息之间；`pet_ui_support._settings_entries()` 兜底表同步，右键「设置」子菜单与齿轮分页继续共用同一份表（第 59 期第 10 条口径不变）。
- 新增 `pet_skills_manage.py`（L4）：设置页「SKILL 管理」格——
  - 平铺列表（`DataTable`，非裸 Treeview）：name／displayName／阶段／层（项目版·用户版·内置版）／体检状态五列，打开时后台加载（规则 33），不加启动递归扫描；
  - 行操作：查看说明（复用 `skill_panel_support.note_text`）、体检详情（复用 `skill_panel.show_skill_health_report`，范围措辞参数化 lead）、删除（仅用户层／项目层，`uninstall_skill` 回收站口径，内置层只读拒绝并提示同名覆盖）、导入（T2/T3 既有五入口：文件／文件夹／ZIP／仓库／链接，默认阶段＋「导入到：项目／全局」选择）；
  - 线程封送：worker 只写 `queue.Queue`，Tk 侧 `after(50)` 轮询回填（`after` 不能在后台线程登记，直调抛 `main thread is not in main loop`——首版踩坑后改为 `desktop_async_tasks` 同口径）；`load_gen` 防连续刷新回填过期结果；
  - 安装根取 `pet.program`（自检临时目录跟着走），退回模块所在目录。
- `skill_panel.py`：`show_skill_health` 的报告窗抽出为 `show_skill_health_report(parent, report, lead, refresh)`，阶段面板与设置页共用；`lead` 参数化范围措辞（本阶段／全部）。
- `pet_settings_ui.py`／`pet_ui_settings.py`／`pet_ui_view.py`／`pet_ui_support.py`：页数口径四格→七格注释同步，SKILL 管理落地说明替换「这一轮不做」旧注。
- 测试：新增 `tests/test_pet_skills_manage.py`（8 条，隐藏桌面）：三层列表渲染＋体检状态列、项目隔离、说明/体检弹窗、内置删除拒绝、用户层删除进回收站、导入对话框五入口、文件导入落用户层阶段目录；`test_pet_settings.py` 页签契约断言更新（§2.4 有意变更：SKILL 管理格落地）；`test_pet_ui.py` 右键设置子菜单断言同步。
- `tests/architecture/_layers.py`：`pet_skills_manage` 登记 L4（UI 层，含 tkinter/ui_widgets）。
- `维护记录/skip台账.json`：登记新测试文件 `SkillsManageCase.setUp` 的 PLATFORM_TKINTER skip（295 条，与源码双向相等）。
- `维护记录/覆盖率基线.json`：`scripts/coverage_report.py` 以既有 9 组定向用例显式重跑刷新（97 条全过），模块 551→552；`runbook.md` §11 口径同步 552/72。

## 验证

- `python smoke_test.py` → 8/8 通过。
- `python tests/test_pet_skills_manage.py` → 8 条全绿（2.5s）。
- `smoke_test.py --architecture` → 470 条；首轮 12 红全部修复后复验：层级登记（L3→L4）、循环依赖（去掉对 pet_settings_ui 的反向引用，`page_title`/`token_project` 本地同口径副本）、DataTable 边界（裸 Treeview→DataTable）、函数尺寸（`import_dialog` 163 行→`_ImportFlow` 类拆分）、token 数字布局（SelectBox 宽度改自适应、表格 height 用 `TEXT_ROWS`）、覆盖率基线、skip 台账——8 个架构测试文件 48 条复跑全 OK；余 `test_runbook_states_the_directed_measurement_caliber`（runbook 551→552 已同步）与 `test_round_number_continuous`（2989 vs 最新结果+1，堆叠分支状态页滞后，同 R3054/R3084 口径如实记录，master 集成时消解）。
- `smoke_test.py --affected pet_skills_manage pet_settings_ui pet_ui_settings pet_ui_support pet_ui_view skill_panel pet_settings_contract` → 冒烟 8/8 通过；定向自检门禁退出码 1，唯一红为 `test_pet_ui` 云泡时序用例（见上，复绿证据充分）。
- `run_selftests.py -k pet_settings pet_ui skill_panel pet_skills`（692 条批次）→ 1 红：`test_pet_ui` 右键设置子菜单旧断言 `assertNotIn('SKILL 管理')`，已按 §2.4 契约变更更新并单测复绿；其余全绿。
- 未运行：`--all --safe` 全量（功能轮分支不累计欠账；合入 master 前按 §5 触发）。

## 边界与说明

- 管理页只做安装级增删查；阶段勾选/配置仍归各阶段面板（规则 28，不双入口）。
- 不做启用/禁用、重命名/编辑/version——属 T8；不做不可信提示/完整性校验——属 T9。
- `.agents/skills` 仍是 agent_skill_sync 导出目标，不是应用注册表层（T5/T6 口径不变）。
- Tk 生命周期噪音：`invalid command name "...poll"/"..._focus_first_interactive"` 为既有 after 回调在控件销毁后触发的 stderr 提示，与本页 poll 同类，未新增处理（窗口销毁后 poll 自查 `winfo_exists` 即停）。
