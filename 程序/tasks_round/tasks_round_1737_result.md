# R1737：结构治理轮——skill_panel.py 拆出预设 mixin（1500→1355 行）（SPSPLIT）

- 任务书：`SPSPLIT_taskbook.md`
- 车道工作目录：`D:\漫剧制作助手\.wt\lane_spsplit\程序`（只改本树，未执行任何 git 写命令，未领号、未提交、未改 `project_status.md` / `AGENTS.md`，未读 `private\`、未打开用户项目）
- 基线：`HEAD = 1acddc52`（R1732）
- 解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`

## 0. 每轮三问（§7）

1. **轮次类型**：§3.3 结构治理轮（执行子场景）——把 `Panel` 的预设区方法原样拆到同层新模块，行为不变，不加功能。
2. **测试跑了吗 / 三个基线**：
   - 默认冒烟 `smoke_test.py`：**通过 8 项、失败 0 项**（8/8）。
   - 架构门禁 `smoke_test.py --architecture`：**Ran 368 tests，OK（exit 0）**；改前（未登记新模块时）为 **FAILED (failures=3)**，详见 §4。
   - 全量回归与欠账：**未跑全量**（任务书只要求三条命令）。common-dir `full-safe-receipts.json` 最新真实凭据为 `{round: 1734, tree: 97f433771bc63b967eede4bc14118ee3d6d05362, seconds: 784.055, at: 2026-10-19T16:28:13}`，与本轮内容树不同，不能复用；是否在合并前补跑 `--all --safe` 见 §6。
3. **欠账是否减少**：本拆分为纯结构改动，未新增欠账；`project_status.md` 由提交方维护，本车道未改。

## 1. 拆分前后行数

| 文件 | 改前 | 改后 |
| --- | --- | --- |
| `程序/skill_panel.py` | 1500 行（= 门禁 `LIMIT`，再加一行即红） | **1355 行**（-145，余量 145 行，满足 ≤1380） |
| `程序/skill_panel_presets.py` | 不存在 | **166 行**（可执行语句 120 行） |

`skill_panel.py` 的 `Panel` 现在继承 `FormScrollMixin, PresetMixin, ttk.Frame`，参照既有 `FormScrollMixin` 写法（`skill_panel.py:166`）。

## 2. 搬移清单（方法 → 新文件:行）

新模块 `程序\skill_panel_presets.py`，`class PresetMixin`（新文件 line 20）。旧文件对应块为 `skill_panel.py` 改前 1224–1369 行（diff hunk `@@ -1221,151 +1221,6 @@`，连同上方一条注释与空行一并搬走）。

| 方法 | 旧行（HEAD） | 新位置 | 备注 |
| --- | --- | --- | --- |
| `run_preset_action` | 1224 | `skill_panel_presets.py:23` | |
| `share_preset_copy` | 1243 | `skill_panel_presets.py:42` | 跨页面复制，含 `BaseDialog` |
| `preset_names` | 1277 | `skill_panel_presets.py:86` | |
| `show_presets` | 1282 | `skill_panel_presets.py:92` | |
| `save_preset` | 1295 | `skill_panel_presets.py:103` | 用 `simpledialog` |
| `drop_preset` | 1312 | `skill_panel_presets.py:120` | |
| `rename_preset` | 1326 | `skill_panel_presets.py:134` | 用 `simpledialog` |
| `apply_preset` | 1349 | `skill_panel_presets.py:157` | |
| `PRESET_PLACEHOLDER` 常量 | 120 | `skill_panel_presets.py:17` | `skill_panel` 仍 `import` 该名，`skill_panel.PRESET_PLACEHOLDER` 继续可用（`skill_panel.py:2,191,273`） |

**行为一字不变**：用脚本把 HEAD 中 `run_preset_action … apply_preset` 整块（含注释、空行、docstring）与新模块 `PresetMixin` 类体逐字节比较，结果 `identical: True`；只调整了 import。

新模块依赖（全部为同层或下层，无反向、无循环）：
`tkinter`、`stage_config`(L3)、`pet_bus`(L0)、`skill_panel_support`(L4)、`ui_tokens`(L1)、`ui_widgets`(L4)；**不 import `skill_panel`、不 import `desktop`/`app`**。

`skill_panel.py` 顶部新增一行导入并保留旧名转发：

```python
# 预设区（占位项常量与八个预设方法）在 skill_panel_presets；按原名转发，旧补丁点有效。
from skill_panel_presets import PRESET_PLACEHOLDER, PresetMixin
```

`skill_panel.py` 的 `from tkinter import messagebox, simpledialog, ttk` 未动。搬移后 `simpledialog` 在本文件已无使用者（与搬移前就已经无人使用的 `messagebox` 同状），保留该行以最小化 diff；若门禁要求清死导入，见 §6 第 5 条。

## 3. 改了哪些 patch 路径（断言未动）

`tests/test_skills.py` 中只有 monkeypatch 目标从旧模块改到新模块，**断言、用例名、docstring、fixture 一律未动**：

| 文件:行（改后） | 改前 | 改后 |
| --- | --- | --- |
| `tests/test_skills.py:43` | （无） | 新增 `import skill_panel_presets`（引用新 patch 目标所需） |
| `tests/test_skills.py:1318` | `real = skill_panel.simpledialog` | `real = skill_panel_presets.simpledialog` |
| `tests/test_skills.py:1319` | `skill_panel.simpledialog = Typed` | `skill_panel_presets.simpledialog = Typed` |
| `tests/test_skills.py:1320` | `self.addCleanup(setattr, skill_panel, 'simpledialog', real)` | `self.addCleanup(setattr, skill_panel_presets, 'simpledialog', real)` |
| `tests/test_skills.py:1373` | `real = skill_panel.simpledialog` | `real = skill_panel_presets.simpledialog` |
| `tests/test_skills.py:1374` | `skill_panel.simpledialog = Typed('  新 名字  ')` | `skill_panel_presets.simpledialog = Typed('  新 名字  ')` |
| `tests/test_skills.py:1375` | `self.addCleanup(setattr, skill_panel, 'simpledialog', real)` | `self.addCleanup(setattr, skill_panel_presets, 'simpledialog', real)` |

原因：`save_preset`/`rename_preset` 的 `simpledialog` 解析发生在 `skill_panel_presets` 的模块全局，旧 patch 点（`skill_panel.simpledialog`）改的是另一个模块的全局，不再生效；不迁移会让这两条用例弹真对话框并永久等待（实测：迁移前这两条用例挂死，迁移后 <0.4s 通过）。

**未迁移的 patch 点（核验后仍有效，故不动）**：
- `tests/test_skills.py:1847` `mock.patch.object(skill_panel.tk, 'Toplevel')`：`skill_panel.tk` 与 `skill_panel_presets.tk` 是同一个 `tkinter` 模块对象，且该用例命中的是无预设早返回分支，不建对话框。
- `tests/test_skills.py:1204` / `tests/test_opencode_engine.py:240` 的 `skill_panel.stage_config`：`stage_config` 是同一模块对象，`patch.object` 打其属性对两个模块都生效。
- `tests/test_core.py:144`、`tests/test_skill_notes.py:66` 的 `skill_panel.program_of` / `skill_panel.sync_models`：命中的是仍留在 `skill_panel` 的方法与 `desktop` 路径，不经预设方法。

## 4. 登记（架构门禁要求的位置）

| 登记位置 | 改动 |
| --- | --- |
| `程序/tests/architecture/_layers.py:34` | L4 列表加入 `"skill_panel_presets"`（`test_layers.test_every_top_level_runtime_module_is_registered_or_an_explicit_tool`） |
| `程序/architecture.md` §3 L4 行 | L4 模块列举加入 `skill_panel_presets`（目录树用 `skill_*.py` 通配，已覆盖，未改） |
| `程序/维护记录/覆盖率基线.json` | 用 `scripts/coverage_report.py` 以原 8 组定向用例重跑刷新：`modules_total` 285→**286**，新增 `skill_panel_presets.py` 行（covered 0 / total 120），`skill_panel.py` total 1095→988；`tests_ok=true` |
| `程序/runbook.md` §11 | 同步基线口径数字：285→286、235→236（`test_coverage_baseline.test_runbook_states_the_directed_measurement_caliber`） |

架构门禁改前失败集（登记前）：
- `test_coverage_baseline.test_baseline_modules_exist_and_keep_production_scope`（baseline 缺 `skill_panel_presets.py`）
- `test_coverage_baseline.test_coverage_tool_runs_on_bundled_interpreter`（286 != 285）
- `test_layers.test_every_top_level_runtime_module_is_registered_or_an_explicit_tool`（`['skill_panel_presets']`）

改后：**Ran 368 tests，OK（0 红，exit 0）**。任务书允许的 `test_full_safe_all_is_required_after_eight_source_rounds` 在本树两次架构运行里都是绿的。

## 5. 实际计数

| 命令 | 实际输出 |
| --- | --- |
| `python -B smoke_test.py --affected skill_panel` | ✅ 门禁 `run_selftests.py`（定向：skill_panel）：**624 秒 → 0 个文件有红**；通过：**9 项**，失败：**0 项**；ALL TESTS PASSED（含 `test_manual_plan`、`test_pet_ui`、`test_idea_chat`、`test_skill_notes`、`test_skill_panel_*`、`test_skills`、`test_ui_edges` 等消费者） |
| `python -B run_selftests.py -k preset skill_panel test_skills` | **共 171 条用例，38.8 秒；0 个文件有红**；ALL TESTS PASSED |
| `python -B smoke_test.py --architecture` | **Ran 368 tests in 130.9s — OK**（仅允许红的 `test_full_safe_all_…` 实为绿，无红） |
| `python -B smoke_test.py`（默认快速） | 通过 **8 项**，失败 **0 项** |

补充证据（非任务书命令，仅定位用）：行为一致性比对脚本输出 `identical: True`；迁移前 `test_skills.PanelTests.test_presets_round_trip_through_the_panel` 等 3 条预设用例挂死（>300s，等真对话框），迁移后 4 条预设相关用例合计 <1.5 秒全绿。

## 6. 需裁决事项

1. **覆盖率基线整表刷新**：为过 `test_coverage_baseline` 必须让基线集合等于生产模块集合（新增模块），按 `runbook.md`/工具 docstring 的规定「刷新基线必须显式重跑工具」，我用原 8 组用例重跑了 `scripts/coverage_report.py` 并整表覆盖写入。这次重跑同时改动 24 行与本次拆分无关的历史口径（例如 `desktop.py` total 1474→1529、`client_profiles.py` covered 52→54、`agent/publication.py` covered 133→131、percent 91.1→89.7）——说明已提交的基线早于其它已落地代码。请裁决：整表刷新保留，还是只补 `skill_panel_presets.py` 一行、其余数字不动（后者 diff 更小，但基线会继续与工具实测不一致）。
2. **`runbook.md` §11 的改动**是否算任务书允许的「架构门禁要求登记新模块的登记文件」；不改它 `test_coverage_baseline` 会红。
3. **`tests/architecture/_layers.py` 的改动**：它是架构门禁的分层登记文件（不是产品代码），任务书允许「门禁要求登记新模块的那几个登记文件」，已列入本表；若审查口径要求此文件不随执行轮改动，请退回并要求改由提交方登记。
4. **全量回归**：最新真凭据 `R1734 / tree 97f4337…` 不覆盖本轮内容树，本轮未跑 `--all --safe`。若合并到 master 前需要全量，请指定后补跑。
5. **`skill_panel.py` 中已无人使用的 `simpledialog` 导入**：保留是为最小化 diff（该文件本就带一个没人用的 `messagebox` 导入）。若死导入被 lint 视为新增问题，可去掉 `simpledialog` 一个词（测试已不再引用 `skill_panel.simpledialog`）。

## 7. 改动文件清单

- `程序/skill_panel.py`（改）
- `程序/skill_panel_presets.py`（新增）
- `程序/tests/test_skills.py`（只改 patch 路径 + 一行 import）
- `程序/tests/architecture/_layers.py`（登记 L4）
- `程序/architecture.md`（L4 登记）
- `程序/runbook.md`（§11 覆盖率口径数字）
- `程序/维护记录/覆盖率基线.json`（工具重跑刷新）
- 本结果文件

未提交（派发执行方不执行 git 写命令）。

## 独立验收（Claude，主工作区）

- 车道 diff 应用到 R1736；AST 逐方法对比 8/8 与 HEAD 相同。
- `run_selftests.py -k test_skills test_skill_panel preset test_production_lock test_idea_inline_brief`：209 条 0 红；`smoke_test.py --architecture`：374 条 0 红。
- 裁决：①覆盖率基线整表刷新保留（工具实测为准，门禁只校结构与下限）；②③runbook §11、_layers.py 属新模块登记，接受；⑤`skill_panel` 里不再使用的 `simpledialog` 导入保留，不扩大 diff。
