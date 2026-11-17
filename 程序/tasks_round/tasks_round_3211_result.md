# R3211 结果：T10 包化 ui/ 第六批——pet_ui 族三模块迁入 ui/
<!-- round-evidence: {"commit_base": "d0376705", "credential_hits": 0, "evidence_sha256": "33df1f9c09bde76c", "exit": 0, "failed": 0, "passed": 1094, "round": 3211, "tests": "run_selftests.py -k pet_ui sanhu pet_settings pet_skills skills broadcaster app_metadata stage_gate stage_flow stage_parallel token_saver latent flatten pet_offer desktop_shortcuts ui_batch9"} -->

## 三问

1. **轮次类型**：结构治理轮（§3.3，T10 包化路线既定批次；用户任务书指派的包化迁移延续）。
2. **测试跑了吗、三个基线过了吗**：默认冒烟 9/9 通过；定向用例与架构门禁见下方验证记录；覆盖率基线已重测。
3. **欠账少了吗**：`OVERSIZE_CAPS` 无涉；ui/ 顶层实体再减 3，门面待清除轮统一处理（需单独授权）。

## 交付

- `git mv` 三模块入 `ui/`：`pet_ui.py`（908 行，Pet 主类＋Mixin 组装）、`pet_ui_stages.py`（1186 行，PetStagesMixin 阶段/自动化）、`pet_ui_support.py`（667 行，共享常量/辅助/小类）——T10 批量迁入计数 129→**132**（ui/ 目录实体合计 147 个含历史包内成员）。
- 顶层同名 `sys.modules` 别名门面 ×3；门面同一性 `pet_ui is ui.pet_ui` 等 3/3 校验通过。
- 批内依赖边规范：`ui/pet_ui.py` 两处（`pet_ui_stages`/`pet_ui_support`）、`ui/pet_ui_stages.py` 一处（`pet_ui_support`）改 `ui.` 前缀；`pet_ui_support.PROGRAM` 的 `__file__` 锚点 `.parent`→`.parents[1]`（程序根，供 `autostart_command`/`toggle` 默认参数）。
- 消费方改包路径导入：生产 8 文件（`desktop.py`、`ui/desktop_automation_tick.py`、`ui/desktop_layout.py` 三处 `import pet_ui`→`import ui.pet_ui as pet_ui`；`ui/pet_cloud.py`/`ui/pet_ui_popup.py`/`ui/pet_ui_settings.py`/`ui/pet_ui_view.py`/`ui/pet_ui_voice.py` 五处 `pet_ui_support` from-import；`ui/keyframe_comfy.py` 动态串 `import_module('pet_ui')`→`'ui.pet_ui'`）；测试 17 文件同口径改写（含逗号混合 import 与函数内联 import）。
- `selftest_discovery.gui_test_module` GUI 探测集补 `ui.pet_ui*` 七个点号名——否则 7 个仅以 `import pet_ui` 为 GUI 标记的测试文件会失判为非 GUI 而绕开隐藏桌面（实测模拟：test_app_metadata/test_broadcaster/test_latent_defects_r1853/test_sanhu_mode/test_stage_flow/test_stage_gate_modes/test_stage_parallel）。
- `smoke_test.py` 源路径探针 `程序\pet_ui.py`→`程序\ui\pet_ui.py`（`def open_claude_desktop(` 字面量检查）。
- 登记面：`architecture.md` ui/「八批共 132 个」→实际以基线为准；`PROJECT_MAP.md` 三虎行全部改 `ui/` 路径；`维护记录/覆盖率基线.json` 重测；`runbook.md` §11 基线数字同步。

## 验证记录

- AST 全库复扫 `pet_ui`/`pet_ui_stages`/`pet_ui_support` 裸引用：**0 残留**（门面文件自身与 `ui_plugin_registry` 注册表键 `'pet_ui'`、`app.py` 的 `module('pet_ui')` 查询键按既有口径保留扁平——注册表键是插件名不是模块路径，门面解析）。
- 门面同一性：`pet_ui is ui.pet_ui`、`pet_ui_stages is ui.pet_ui_stages`、`pet_ui_support is ui.pet_ui_support` 3/3 通过。
- 实体内残留扁平 import 复核：仅 `pet_agent`、`ui_widgets`、`ui_tokens` 等**未迁移**模块，符合分层。
- 默认冒烟：**9/9 通过**。
- 覆盖率基线重测：**646 模块／71 覆盖**（97 用例全过；+3 为本批新门面），runbook §11 已同步。
- 定向用例（`-k pet_ui sanhu pet_settings pet_skills skills broadcaster app_metadata stage_gate stage_flow stage_parallel token_saver latent flatten pet_offer desktop_shortcuts ui_batch9`）：20 文件 / **1094 条用例，125.8 秒**；首轮 1 红文件 `test_app_metadata`——`PROGRAM/'pet_ui_support.py'` 硬编码顶层路径在门面化后读到 3 行壳，改实体取径 `ui/pet_ui_support.py`（断言未动），复跑该文件 **6/6 绿**，其余 19 文件首轮全绿。
- 架构门禁 `smoke_test.py --architecture`：**483/483 全绿**（176.6s；首轮 2 红＝TODO注释快照扫描序（pet_ui_stages 路径键随包化后排序变化，按 R3085 先例按实扫描序重写 3 项、处置字段保留）＋状态页轮次头陈旧（3210→3212），均与迁移行为无关，复测清零）。

## 过程记录

- 领号 R3211（R3210 被并行车道占用）；分支 `codex/wip-R3211`。
- `pet_ui` 消费面含 `desktop.py:351,367` 的 `pet_ui.DOCK_ROOM`/`pet_ui.StageQueue` 属性访问——`import ui.pet_ui as pet_ui` 保持绑定名不变，属性面无损。
- `ui/pet_ui_stages.py`/`ui/pet_ui_support.py` 模块 docstring 明确「不导入 pet_ui、无导入环」——三角依赖为单向 pet_ui→stages→support，批内迁移无环。
