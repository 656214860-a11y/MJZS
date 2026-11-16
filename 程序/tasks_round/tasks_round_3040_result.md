# R3040 结果（修复轮：共享输入框技能面板勾选死锁＋＋菜单「添加技能…」下钻被误收）
<!-- round-evidence: {"commit_base": "177dab9d", "credential_hits": 0, "evidence_sha256": "7256eb2d946a1619", "exit": 0, "failed": 0, "passed": 185, "round": 3040, "tests": "run_selftests.py -k shared_input test_skills"} -->

## 三问
1. 轮次类型：修复轮（runbook §15.2 / AGENTS §3.2）——两个用户实报交互缺陷，先红后绿。
2. 测试：新增 2 条回归先红后绿（改动前 `test_add_menu_drilldown_keeps_panel_open` 断言 `is_open()` 红、`test_skill_panel_checks_reflect_stage_config` 断言跨阶段行无勾选框红）；`run_selftests.py -k shared_input` 3 文件 58 条全绿；`-k test_skills` 127 条全绿；`smoke_test.py` 8/8。架构门禁沿用本会话实测：本轮文件零新增违规，`cell_hover.py`/`pet_ui_view.py`/`ui_tooltip.py` 棘轮红为 master 既有欠账（与本 diff 无关，未动）。
3. 债务：未新增欠账；状态页无对应欠账条目（两缺陷为用户实报 bug，非登记欠账）。顺带修复本工作树环境欠账：3 个未检出的 gitlink（`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`编剧技能集`，均按 pin 提交从主检出干净副本补齐）＋`reference/HoLLMwood`，注册表计数 71→73 与测试基线一致。`project_status.md` 仅 master 可提交，本轮不改。

## 根因

- **勾选框无法选中（两因叠加）**：① 面板列「本阶段在前＋其余所有技能」，旧代码给每行都画勾选框；跨阶段/判不出阶段的技能经 `stage_config.clean_skills` 必然被滤掉，勾选写不进配置——死控件。② R2980 把打开预填改成「一律未勾选」，但 `_toggle_skill_default` 对配置真值取反：默认里本有的技能第一次点击是移除，视觉无勾看似无反应。
- **「添加技能…」无响应**：`AddMenuPanel._drill_in → refresh() → clear()` 销毁被点 label；顶层 `<Button-1>` 绑定 `_panel_outside_click` 派发时 `event.widget` 回退为路径**字符串**（Tkinter `_nametowidget` 失败分支），旧 `_widget_within` 走 `.master` 链对字符串恒 False → 误判外部点击 → `panel.hide()`。下钻成功瞬间被自己收掉，「‹ 返回」同病。

## 改动

- `desktop_shared_input.py`：新增 `_widget_path()`（Widget 取 `_w`、字符串原样）并把 `_widget_within()` 改为 Tk 路径比较（`==` 或 `ancestor + '.'` 前缀，ancestor 为根 `.` 恒真）；新增 `_skill_stage()`（显式 `stage` 字段优先、缺失按名回查注册表、`stage_id` 归一）与 `_skill_defaultable()`（项目已开 且 归属阶段==当前阶段）。
- `desktop_shared_menus.py`：`SkillPickPanel.refresh()` 捕获 `_defaults = host._default_skills()`；`_skill_row()` 仅 `host._skill_defaultable(item)` 时渲染勾选框且 `selected=name in self._defaults`（恢复所见即真）；`sync_check` 注释更正。
- `tests/test_shared_input_ui.py`：`test_add_menu_drilldown_keeps_panel_open`（下钻/返回后 `is_open()` 保持、菜单文本正确）、`test_skill_panel_checks_reflect_stage_config`（预填已选、点击取反写回 `skill_config.json`、面板不关、跨阶段行无勾选框但名称可点插入 `/mine-skill`）。

## 验证

- 红→绿证据：两新测试改动前实跑失败（面板 `open=False`；`mine-skill` 出现在 `_check_rows`），改动后全绿。
- `run_selftests.py -k shared_input`：test_shared_input_stages/ui/voice 共 58 条 0 红（GUI 隐藏桌面，跨树令牌排队实跑）。
- `run_selftests.py -k test_skills`：127 条 0 红（环境补齐 gitlink 后；补齐前 2 条红为 `reg.count()` 71!=73，系工作树缺技能包内容，主检出同测 127/127 绿可证非代码回归）。
- `smoke_test.py`：8/8。
- repro 脚本（`repro_bugs.py`/`repro_outside.py`）用后已删；真实 Tk 复测确认：勾选行仅本阶段 4 行、点击即时翻转写回、＋菜单下钻后 `open=1` 显示「‹ 返回／从仓库导入／本地安装」。

## 边界与遗留

- 未动 `stage_config`/`skill_registry`/`skill_import_service` 契约；「本地安装」在 repro 中的 `IndexError` 为 mock 路径过浅所致，真实路径深度足够，非本轮范围。
- `cell_hover.py`（1028>1016）、`pet_ui_view.py::PetViewMixin`（746>732）、`ui_tooltip.py::__init__`（9>7）棘轮红为 master 既有欠账，建议后续结构治理轮处理（右键菜单逻辑拆分方案此前已提出未实施）。
- 工作树 gitlink 补齐内容不入 git（160000 仅记提交指针），`git status` 无污染。
