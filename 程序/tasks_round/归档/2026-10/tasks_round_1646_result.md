# R1646 修复轮：P1-1 收口（L4 直读正式 JSON）＋新增第 5 项棘轮

- **本轮类型**：§3.2 修复轮（源码＋门禁；不改契约、不分层、不搬目录、不重命名）。
- **测试与三个基线**：默认冒烟 **8/8**；行尾＋轮次基线 **21/21**；架构门禁 **357/357（190.1 秒，本轮实测，含本轮新增 1 条）**；受影响模块 `tests/test_pet_ui` **599/599（77.2 秒）**、`tests/architecture/test_unification_ratchet` **4/4**。**未跑全量**（改源码轮，全量欠账未到门禁线 8，后台触发 False）。
- **欠账**：本轮改源码，全量欠账 **2/8 → 3/8**。改前实测（本轮 `scripts/auto_full_safe.py --status`）：`上次全量 R1624；最新 R1645；其间改过源码的轮次 2（门禁线 8）`。
- **清单依据**：`tasks_round/tasks_round_1645_result.md` J 节 P1-1（该节 P0 为空）。
- **指令冲突记录**：本会话顶部重新下发的提示把本轮描述为「结构治理轮（只读诊断）」，但该诊断已由 R1645 交付（A–M 清单即其产物），且当前 active 目标为「按顺序自动完成 `tasks_round_1645_result.md` 清单」。故本轮执行清单首项（修复轮）。两处边界差异如实登记：① 本轮**修改了 .py**（若用户要的是重跑诊断，A 节改动可整体 revert）；② 本轮**新增了测试与门禁条目**。除清单项外未扩大写入范围。

## A 改动

1. `程序/pet_ui_voice.py:890-896`（`PetVoiceMixin.projects_registry`）：删除「宿主给不出就自己开 `PROGRAM/'projects.json'`」的文件兜底（原 `:895-905`：`import json`／`path.open`／`json.load`／`except Exception` 记错后返回 `{}`），改为只认宿主注入的 `self.desktop.projects.info`；拿不到就 `self.errors.append(('projects.read', '宿主未提供项目登记表'))` 并返回 `{}`。同步清理 `from pet_ui_support import ...` 中已无用的 `PROGRAM`（全仓唯一使用处即此处，已核）。
   - 依据：`desktop.py` 恒有 `self.projects = Projects(...)`（L2，含 `.info`），真实需求走第一分支，故文件兜底在生产是死路径；调用方只有 `pet_ui_voice.py:917`（`projects_snapshot`）。
2. `程序/tests/test_pet_ui.py:6575-6580` 新增 `test_a_missing_host_registry_is_reported_not_read_from_disk`：宿主无 `projects` 时返回 `{}`、记 `projects.read`、不再自行开文件。
3. `程序/tests/architecture/test_unification_ratchet.py` 新增 `_formal_path_json_reads()`（第 5 项：L2 之外的生产模块直接读 `config.json`／`settings.json`／`projects.json`）与用例 `test_formal_path_reads_outside_l2_are_a_nonincreasing_subset`。
4. `程序/维护记录/架构统一基数.json` 新增 `第五项`：`count 0`、`baseline_pending 0`，1 条 `exempt`（`scripts/migrate_workflow_presets.py:registered_projects`）。

## B 扫描实测（改前 → 改后）

- 生产集合 `_json_source_files()` 共 317 文件；「三个正式文件名字面量＋`json.load/loads` 或 `open`」命中：**改前 2 处 → 改后 1 处**。
  - 消除：`pet_ui_voice.py:901`（P1-1 目标）。
  - 保留：`scripts/migrate_workflow_presets.py:17`（程序外的独立迁移脚本，无宿主上下文，只能自读登记表）→ 登记 `exempt`＋理由，门禁 `actual - exempt == pending == ∅` 成立。
- 门禁新条目首跑即绿（未出现未登记新增债务），说明扫描集合内不存在其他同类残留。
- 顺带实测确认 **P2-2 仍成立**：扫描该文件时解释器实测打印 `SyntaxWarning: "\[" is an invalid escape sequence`，位置 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239`；本轮不改，留作 P2-2 的当前树依据。

## C 完成判据对照（P1-1 原文三条）

| 判据 | 结果 |
| --- | --- |
| 该处无 `json.load`／`open` | ✅ `pet_ui_voice.py` 全文 `json` 与 `PROGRAM` 出现次数均为 0 |
| 把扫描范围扩到 L4 正式路径读取后该项不出现（或登记豁免且带理由） | ✅ 第 5 项 `count=0`；唯一残留已 `exempt`＋理由 |
| 定向 1 条用例断言读不到时不再自行开文件 | ✅ `tests/test_pet_ui.py:6575` |

## D 验证命令与结果（本轮实测）

- `python -B -m unittest tests.test_pet_ui` → `Ran 599 tests in 77.156s` `OK`。
- `python -B -m unittest tests.architecture.test_unification_ratchet` → `Ran 4 tests` `OK`。
- `python -B smoke_test.py` → `通过：8 项 / 失败：0 项`。
- `python -B -m unittest tests.test_line_endings tests.architecture.test_round_baselines` → `Ran 21 tests` `OK`。
- `python -B smoke_test.py --architecture` → `Ran 357 tests in 190.138s` `OK`（改前 R1645 为 356，本轮 +1）。

## E 未做与局限

- 未跑全量 `run_selftests.py --all --safe`（欠账 3/8，未到门禁线 8）；未实机、未联网。
- 本轮未动 P1-2／P1-3／P2-1…P2-8 任何一项；未改契约与分层；未更新接力文件与状态页正文（仅同步轮次头，另立轮次整理）。
- `第五项` 只覆盖三个正式登记／配置文件名与 `json.load/loads`＋`open` 形态；其他正式路径（阶段状态文件、各 manifest 等）仍依赖既有 `test_json_io_boundary` 与各 `*_json_boundary` 门禁，不因本轮而获全量保证。
- 提交：按 §2.6 一次性 `git add`＋`git commit`，提交信息以 `R1646: ` 开头；hash 见 `git log`（本文写入时尚未提交，故不预填）。