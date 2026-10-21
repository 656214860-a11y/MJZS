# R1788：结构治理轮——清除全仓零引用的死代码（第一批，高把握）

1. 本轮类型：§3 结构治理轮（只删无调用方的代码，不改行为）。起因：用户反馈“项目有历史垃圾和无用功能”，先出清单（只读调查），再按风险从低到高清理。

2. 测试跑了吗、三个基线过了吗：
   - 架构门禁 `smoke_test.py --architecture` 375 条：本轮删除没有触发任何登记/行号/基数类门禁变红。剩 3 条均与本轮无关：
     - `test_agents_md.test_performance_history_is_declared_as_historical_only`、`test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：工作树缺 gitignore／gitlink 文件（R1775 结果文件已记录同样两条）；
     - `test_round_baselines.test_round_number_continuous`：状态页轮次头只能在 master 更新（pre-commit 钩子规定），工作树分支上恒为旧值，合入 master 时同步为本轮号加一。
   - 受影响冒烟 `smoke_test.py --affected`（10 个被删模块）首跑 8/9：`test_app_metadata` 因 `ui_widgets.py` 的 `APP_NAME` 唯一用法就是 Splash，删后它不再是显示名生产者——契约有意变更，把它移出 `tests/test_app_metadata.py::DISPLAY_SOURCES` 并去掉无用 import，**断言未动**；复跑绿。
   - 另有 22 个测试文件红（`test_idea_chat`、`test_writing_*`、`test_script_contract` 等），报错均为“已勾选的 SKILL 或其引用未加载”：本工作树里 `skills/01 剧本准备SKILL/剧本锻造`、`编剧技能集` 是空的 gitlink 目录（主检出有内容），与 R1775 记录的两条环境红同根，不是本轮引入；同一批用例在带完整 gitlink 的干净检出里的复核结果见下节。
   - 完整安全全量：**本轮未跑**，历史凭据仍是 R1734；合入 master 后由后台通道补跑（红后冷却见 R1781）。

3. project_status.md 欠账少了吗：本轮改源码 +1。

## 删了什么（每项都先全仓 `git grep` 复核，只出现定义处）

| 位置 | 删除内容 | 行数 |
|---|---|---|
| `ui_widgets.py` | `Splash` 启动画面类、`SPLASH_STAGES`，以及只为它而 import 的 `time as _time`、`ui_tokens as T` | −147 |
| `ui_tokens.py` | 仅供 Splash 使用的 13 个 `SPLASH_*` 设计令牌 | −15 |
| `agent/video.py` | 自注“虚构协议，非真实厂商”的 `ContractExampleAdapter` 与无调用方的 `adapter()` 工厂，及随之无用的 4 个 import；保留被 `volcengine.py` 继承的 `VideoAdapter` | −36 |
| `continuity_ledger.py` | `write_anchors`、`write_triplets` | −12 |
| `project_settings.py` | `set_auto_submit` | −3 |
| `stage_execution_service.py` | `asset_deletion_references`（底层 `asset_plan.deletion_references` 有需求锚点测试，保留） | −6 |
| `white_model.py` | `workspace_settings_path` | −3 |
| `asset_thumbs.py` | `worker_bad` | −5 |
| `script_contract.py` | `rhythm_template_reference`（常量 `RHYTHM_TEMPLATE_PATH` 仍被引用，保留） | −5 |
| `stage_layout.py` | `duty_rows` | −8 |
| `stage_parallel.py` | `unit_name` | −4 |

合计 −244 行。

## 调查误报（已核对并保留，不要再当死代码）

- `platform_tools.window_outer_rect`／`outer_rect_for_client`：被根目录 `启动漫剧制作助手.pyw` 调用（调查只扫了 `程序\`）。
- `stage_config.apply_workflow_empty_stages`：被 `scripts/migrate_workflow_presets.py` 与 `test_workflow_migration` 使用。
- `storyboard_catalog.py`：有意保留的兼容门面，退役期 2027-03-31（`legacy_compat` 同一口径）。
- `storyboard_files.synced_assets`：非死代码（其余引用的是 `has_synced_assets`），本轮未动，待下一批单独核对。

## 清理背景（未提交的本机清理，不进 Git）

- `.wt\` 约 1.24 GB → 132 MB：回收 39 个 detached 工作树（HEAD 均为 master 祖先）。其中 21 个与 master 有差异的，差异补丁与未跟踪文件先打包到 `D:\repo-meta\wt-archive-20261021.zip`（含 `MANIFEST.json`）再回收。保留 `ci`（锁定，后台全量在用）、`lane_triage`（只含诊断结果草稿）、`lane_uimod`（约 2 小时内仍有修改，疑似活跃）。
- `工作流任务\` 删除 211 个超过 24 小时的旧 `.log`（91 MB）与全仓唯一的 `.bak_*`（`dispatch.sh.bak_20261020`）；根目录 `outputs\`（144 个文件）、`启动错误.log`、孤立的根 `维护记录\基准历史.json` 一并清掉。均为被 gitignore 的文件。

## 后续批次（仅记录，未处理）

- 约 83 个“仅测试引用”的符号（集中在 `token_saver.py`、`stage_parallel.py`、`stage_layout.py`），需逐个判断测试是否在守护真实行为。
- 缺模块线索：`skills\` 下 4 个 gitlink 目录无 `.gitmodules`；`_layers.py` 登记了 6 个不存在的模块名；阶段 04 的 `总控.json` 缺 `stage_skills`；文档里残留“12 阶段”说法。

## 提交

- 已提交，commit hash 见 git log `R1788:`。
