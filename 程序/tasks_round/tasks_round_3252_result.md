# R3252 结果 · U5 Box 框体组件与聊天框迁移
<!-- round-evidence: {"commit_base": "e109879a", "credential_hits": 0, "evidence_sha256": "dee19b4cac1b1e2f", "exit": 0, "failed": 0, "passed": 46, "round": 3252, "tests": "run_selftests.py -k ui_theme writing_page script_page ui_batch5 empty_box ui_writing_recon box_boundary"} -->

- 轮次类型：功能轮（UI 统一组件标准任务书 U5，D10/D14 契约）。
- 三问：测试跑了；定向集 46/46 全绿、冒烟 9/9；架构门禁 507 条实测 504 绿、3 项红均为环境/历史欠账（`基准历史.json` 为 gitignore 的本地运行时产物、工作树缺失已从主工作区同文件补齐；`requests` 版本钉在测试内 2.32.3 而共享运行环境已被 whitelist-framework 车道升到 2.34.2，master 侧 R3250/R3254 已改白名单口径，待同步主干后复测；`test_round_number_continuous` 因本分支 `project_status.md` 停在 3214（仅 master 可提交），合并主干后自解）。`project_status.md` 欠账无变化。

## 改动

- `ui/ui_theme.py`：新增 `box_frame(master, padding=(SPACING['xs'], SPACING['none']), **kwargs)`——`Box` 框体唯一创建入口，内部即 `ttk.Frame(style='Box.TFrame', ...)`；样式本体（直角、1px `color.border.strong`、`background=BG`）仍在 `apply()` 第 75 行定义，本轮未动样式取值，外观零变化。文件 405→416 行，`test_function_size_ratchet`／`test_complexity_ratchet`／`test_module_size_ratchet` 实测仍绿，未触发 D7 停批情形。
- `ui/desktop_writing_page.py:243`：剧本页聊天框 `ttk.Frame(style='Box.TFrame', ...)` 改走 `box_frame(...)`，padding 实参不变；新增 `from ui.ui_theme import box_frame`。
- `ui_components.md`「框体」节、`design_tokens.md`「框体（Box）」节：入口名落为 `ui_theme.box_frame()`（U0 文档先行已写分工与取值，本轮补函数名）。
- `architecture.md` 门禁清单「体验与布局」补登 `test_box_boundary.py`。
- 新门禁 `tests/architecture/test_box_boundary.py`（AST 口径，`production_files_recursive`）：
  - `literal_debt`：`'Box.TFrame'` 字符串字面量，`ui/ui_theme.py`（样式定义本体）豁免，其余生产文件零容忍——迁移后全仓为 0；
  - `border_debt`：`tk`/`ttk` 的 `Frame`/`Label`（含裸名）构造上 `relief∈{solid,ridge,sunken,raised,groove}` 且 `borderwidth` 为 1–3 整数字面量的「自拼 1px 边框」，按文件冻结只减不增（存量：`cell_hover.py`×1 放大镜描边、`ui/skill_panel.py`×2 ttk 忽略的死选项 relief/borderwidth）；
  - 正向锚点：`desktop_writing_page.py` 必须含 `box_frame` 调用；坏样本 canary ×2 组。

## 验证

- `python -B -m unittest tests.architecture.test_box_boundary` → 5/5 绿（含 canary）。
- `python -B -m unittest tests.architecture.test_function_size_ratchet tests.architecture.test_complexity_ratchet tests.architecture.test_module_size_ratchet` → 8/8 绿（ui_theme 体量棘轮无回归）。
- 像素级外观证据（隐藏桌面真 Tk，PrintWindow）：
  - `tasks_round/evidence/R3252_script_page.png`：真 Desktop＋最小项目剧本页整窗，聊天框实测 858×705，style=`Box.TFrame` 经 `box_frame` 创建；
  - `tasks_round/evidence/R3252_box_ab.png`：同一无边框窗内 `box_frame()` 与裸 `ttk.Frame(style='Box.TFrame', 同 padding)` 左右并排各 200×160，裁剪区逐像素 `mean_abs=0.0000`（96000 字节全等）——创建入口与旧写法渲染逐像素一致。
- `run_selftests.py -k ui_theme writing_page script_page ui_batch5 empty_box ui_writing_recon box_boundary` → **46 条用例全绿，0 红**（716.0 秒；含 `test_ui_theme` 18、`test_ui_batch5_stage_panel_and_script_page` 4、`test_script_structure_empty_box_edit` 2、`test_ui_writing_recon` 2、`test_writing_page_controller` 3、`test_writing_page_services` 6、`test_script_page_services` 3、`architecture.test_box_boundary` 5、`architecture.test_combobox_boundary` 3）。GUI 令牌排队约 11 分钟（跨树串行，非并发误报）。
- `smoke_test.py` → 9/9 绿。
- `smoke_test.py --architecture` → 507 条中 504 绿；3 项红均非本轮代码：①`test_performance_history_is_declared_as_historical_only` ERROR——`维护记录/基准历史.json` 系 `.gitignore:63` 本地运行时产物，功能工作树不随检出，已从主工作区复制同文件后该项转绿待复测；②`test_whitelist_versions` FAIL——共享运行环境 `requests 2.34.2` vs 本分支测试内钉版 `2.32.3`，master 侧 whitelist-framework 车道 R3250/R3254 已将版本口径改为生产锁，待同步主干复测；③`test_round_number_continuous` FAIL——本分支 `project_status.md` 停在 3214（§2.6 仅 master 可提交），合并主干（状态 3257）后自解。

## 基线与欠账

- `Box.TFrame` 字面量欠账：**清零**（全仓除 `ui_theme.py` 样式定义/入口本体外零出现，门禁冻结为 0）。
- 自拼 1px 边框冻结欠账 3 处（`cell_hover.py`×1、`ui/skill_panel.py`×2），均非聊天/内容/列表框语义，按 D6 不批量迁移、只减不增。
- `ui_widgets.py` 未触碰（体积棘轮 1125 约束不变）；`Box` 按 D10 落在 `ui_theme.py`。

## 提交

见 git log（`codex/wip-R3241`）。
