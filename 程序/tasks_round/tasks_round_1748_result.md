# R1748：UI 统一入口轮——18 处 simpledialog.askstring 迁到 ui_widgets.ask_string（SDMIG）

- 轮次类型：**修复轮（合并解冲突）**（按任务书标注）。执行方：DeepSeek Harness。
- 测试跑了吗：跑了。任务书指定的两项验证全绿（见「命令实际计数」）。
- 三个基线：默认冒烟 **未运行**（任务书明确不跑 `--affected`，只要求 `-k` 定向与 `--architecture`）；架构门禁 **通过**（`smoke_test.py --architecture` 375 条 0 红，exit 0）；全量安全回归 **未运行**（任务书未要求）。
- `project_status.md` 欠账：**未改状态页**（执行方不领号、不提交、不改状态页）；本轮为合并解冲突，不涉及欠账增减。

## 一、合并与冲突

工作树：`.wt/lane_sdmig2`，detached HEAD `a1bbeef3`（R1744 UIFIX），`git apply -3` 以三路合并应用 `sdmig.patch`。

- 干净应用：`app.py`、`architecture.md`、`desktop.py`、`desktop_asset_pages.py`、`desktop_writing_page.py`、`pet_ui_stages.py`、`skill_panel.py`、`skill_panel_presets.py`、`ui_widgets.py`、6 个测试文件、两个基线 JSON。
- 冲突 2 处（`git apply -3` 报 `with conflicts`，`git reset -q` 后手解）：

| 文件 | 冲突位置 | 解法（两边都保留） |
| --- | --- | --- |
| `asset_detail.py` | 第 30–34 行 `from ui_widgets import ...` | UIFIX 的 `HintLabel` + SDMIG 的 `ask_string` 同时保留：`... DescriptionBlock, HintLabel, PrimaryButton, SecondaryButton, TextArea, ask_confirmation, ask_string, notify` |
| `desktop_media_pages.py` | 第 25–29 行 `from ui_widgets import ...` | UIFIX 的 `DescriptionBlock` + SDMIG 的 `ask_string` 同时保留：`Card, DataTable, DescriptionBlock, PrimaryButton, SecondaryButton, ask_string` |

- `HintLabel` 在 `asset_detail.py` 有 3 处使用（356/359/626 行），`DescriptionBlock` 在两文件均有使用；保留后 import 未引新增死导入。清除全部 `<<<<<<<`／`=======`／`>>>>>>>` 标记。

## 二、基线 JSON（任务书第 3 步）

- `维护记录/skip台账.json`：补丁干净应用，仅 +9 行——新增 `tests/test_ask_string.py` 的 `AskStringTests.setUp` → `PLATFORM_TK_DISPLAY` 一条（Tk display 跳过项）。
- `维护记录/测试分层基线.json`：补丁原为**整文件覆盖**（旧车道把 architecture 计 312→375、`full_safe_verified_trees` 整表换成 1453–1734、`last_full_safe_all_round` 1322→1734）。按任务书「以 master 版为底，只加入 SDMIG 新增内容」，**回退到 master 版**，仅把 `architecture.test_count` 312→313、`architecture.unit_count` 104→105（SDMIG 新增 1 个架构门禁测试 `test_simpledialog_boundary.py`，1 用例 1 模块）；`full_safe_verified_trees`（30 条）与 `last_full_safe_all_round`（1322）保持 master 原值，**未**带入旧车道的 1734 数据。
  - 说明：master 的 `测试分层基线.json` 是本文件快照，`architecture.test_count` 停在 312（round 1322 时点）。本机 `smoke_test.py --architecture` 实测 375 条（master 实际累计 + SDMIG 新增 1 条）；分层基线由 `run_selftests.py --layer architecture --all` 自动重写，本次任务书未要求跑该命令，故不手填 375，仅按「master 底 + 新增计数」记 313，避免伪造快照。

## 三、命令实际计数

| 命令 | 结果 |
| --- | --- |
| `git apply -3 D:/漫剧制作助手/工作流任务/sdmig.patch`（仓库根 `.wt/lane_sdmig2`） | 干净应用 21 个文件；`asset_detail.py`、`desktop_media_pages.py` 2 个 `with conflicts`；exit 1（三路合并有冲突，预期） |
| `git reset -q` | exit 0 |
| grep 生产代码 `simpledialog`／`askstring`（`程序` 根及子目录 `.py`，排除 `tests\`） | **0 命中**（迁完生产代码零遗留） |
| `run_selftests.py -k ask_string asset_detail startup_perf recon_service script_workspace_results test_skills ui_batch6 ui_widgets pet_ui` | 13 个测试文件 / 76+1 路工作单元，**899 条，0 红**（153.9 秒），`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | **375 条，0 红**（187.3 秒），exit 0，`✅ 架构治理测试：tests/architecture` |
| `tests/architecture/test_simpledialog_boundary.py` 单测 | ran=1, failures=0, errors=0 |

- 过程说明：`-k` 定向含 `test_ask_string`（新入口 6 条）、`test_asset_detail`、`test_desktop_startup_perf`、`test_recon_service`、`test_script_workspace_results`、`test_skills`、`test_ui_batch6`、`test_ui_widgets`、`test_pet_ui` 全绿。stderr 中的 `unknown encoding "cp1252"`／`invalid command name ...speak` 为 Tk 在非 ASCII 临时路径下的既有噪音，不产生失败。旧车道同命令 898 条，本树 899 条——多出的 1 条来自 master R1744（UIFIX）自身新增用例，非本次引入。
- **断言未动**：6 个测试文件的改动均为 mock 落点搬家（`xxx.simpledialog` → `xxx.ask_string`、`dialog.askstring` → `dialog.ask_string`、`skill_panel_presets.simpledialog` → `skill_panel_presets.ask_string`），未改任何断言语义、未弱化、未新增 skip（`test_ask_string.py` 的 `PLATFORM_TK_DISPLAY` skip 是新增测试的正常 Tk 守卫，已登记 `skip台账.json`）。

## 四、需裁决事项

1. **补丁自带旧结果文件**：`git apply` 顺带引入了旧车道的 `程序/tasks_round/tasks_round_pending_SDMIG_result.md`（其内容为旧车道 898 条等，已被本 SDMIG2 结果取代）。任务书只要求写 `SDMIG2_result.md`，未要求删除旧文件；是否在提交时丢弃该旧文件，请提交方裁决。
2. **基线 `architecture` 计数口径**：本文件按任务书「master 版为底 + 新增计数」记 313（312+1），非实测 375；`smoke_test.py --architecture` 实测 375 条已记录。若需以实测回填，跑 `run_selftests.py --layer architecture --all` 即自动重写，请提交方定夺。
3. **`parent` 第一位置参**：SDMIG 的 18 处调用点均把 `parent` 重排为第一位置参（`ask_string(parent, title, prompt, …)` 签名所致，与 `ask_confirmation` 同构），本次合并未改动该语义，与旧车道一致。
4. 无阻塞事项；`tasks_round_pending_` 前缀按任务书命名（执行方不领号，轮次号由提交方补记）。

## 独立验收（Claude，主工作区）

- 执行链：改动由执行方（DeepSeek Harness v4-pro）先在 a1bbeef3 底座上完成并解决 asset_detail／desktop_media_pages 与 UIFIX 的冲突；之后 master 前进到 R1747，调度方把该车道的全量 diff 导成补丁，`git apply --check` 对 R1747 的 master 零冲突后应用到主工作区。本提交没有手工解冲突。
- 范围：恰为补丁的 21 个文件（9 个生产模块、2 个新测试、6 个既有测试搬 mock、architecture.md、skip台账、测试分层基线），未夹带用户的 AGENTS.md 与 程序/Tencent/。
- 复跑：生产代码 `grep simpledialog|askstring` 无残留；`run_selftests -k ask_string asset_detail startup_perf recon_service script_workspace_results test_skills ui_batch6 ui_widgets pet_ui` ALL PASSED；`smoke_test --affected ui_widgets` 0 个文件有红（391 秒，9 项冒烟通过）；`smoke_test` 通过；`smoke_test --architecture` 375 条中 1 条红，即已知的「R1747 欠一次完整安全全量」，由 post-commit 钩子后台补跑。
- 口径说明：测试分层基线 JSON 以 master 为底只加了 architecture 与 unit 的新增计数（312→313、104→105），不是实测的 375；该快照由 `run_selftests --layer architecture --all` 重写，本轮未要求跑，故未手填。
- 断言未动：6 个既有测试只改 mock 落点（xxx.simpledialog → xxx.ask_string），未弱化断言、未新增 skip；test_ask_string 的 Tk display 守卫已登记 skip 台账。
