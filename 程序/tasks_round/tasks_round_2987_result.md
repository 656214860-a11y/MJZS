# R2987 结果：合并轮准备——codex/wip-R2980 合入 master 前消解冲突（功能分支侧）

## 三问

1. **轮次类型**：合并轮准备（修复轮性质：在功能分支内 `git merge master` 消解冲突，使后续 master 合入无冲突）。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k test_shared_input_ui test_shared_input_stages test_stage_reasoning test_skills test_skill_command test_idea_attachments` 合并树实测 **238 条全绿**（GUI 令牌排队约 6 分钟）；覆盖率基线按原 9 组 targets 重测，97 条目标用例全过，`维护记录/覆盖率基线.json` 重写为 547 模块／71 覆盖。冒烟与架构门禁未单独跑（合并提交由 master 侧 `dev.py merge` 的 `local_ci exit` 出口档把关）。
3. **欠账少了吗**：消除合并阻断欠账——master 已合入 R2964 模型选择器浮层版（`stage_model_picker` 全量重写）与 R2962 项目文件面板，与本分支 R2971/R2980 的输入框改造正面冲突 7 处文件；本轮全部消解，master 合入将为干净合并。

## 冲突消解明细（7 个 UU 文件）

| 文件 | 消解方式 |
|---|---|
| `stage_model_picker.py` | 全取 master R2964 新版（无外框钮＋`ui_popup.Flyout`），在其上重删「+ 添加模型…」尾项：`_popup_spec` 去 add 行与尾部分隔、`_fill_popup` 去 add 分支、删 `_choose_add_model` 与 `choose_model`/`ADD_MODEL_LABEL` 死分支、`open_model_manager` 保留为「＋」下拉入口 |
| `docs/stages/S01_剧本准备.md` | REQ-S01-82／DES-S01-82 取 master 浮层版描述、尾项从句改为「已于 R2971 移入「＋」下拉」；REQ-S01-71 取 master 离线语音版；**REQ/DES 编号撞号消解**：master 的 REQ-S01-90 已被 R2962 项目文件面板占用，本分支两条顺延为 REQ-S01-91（✦／＋面板）与 REQ-S01-92（`/`/`@`候选浮层），DES 同步 91/92，追溯表与代码/测试注释同步改号 |
| `runbook.md` | 覆盖率口径段取 master 侧并按重测结果更新为 547 模块 |
| `PROJECT_MAP.md` | 并集：master 的 `desktop_files_panel` 入「三虎与自动化」行、本分支的 `desktop_shared_menus` 入「阶段配置」行 |
| `tests/test_skills.py` | 保留本分支 `test_add_menu_model_entry_opens_the_manager_and_reverts`（测「＋」下拉开模型管理），picker 断言由已删的 `_fill_menu`/`_menu` 旧 API 改为 `_popup_spec()` 无 add 行 |
| `tests/test_stage_reasoning.py` | 取 master `_popup_spec` 断言组（reasoning 行四档），尾项断言由「spec[-1] 为 add」改为「无 add 行」，REQ 注释改 91 |
| `维护记录/覆盖率基线.json` | 冲突双方均为旧树测量值，均不可信；按原 9 组 targets 在合并树重测重写 |

## 验证记录

- `run_selftests.py -k test_shared_input_ui test_shared_input_stages test_stage_reasoning test_skills test_skill_command test_idea_attachments`：238 条 0 红（合并树）。
- `scripts/coverage_report.py <原 9 targets> --json`：97 条全过，基线 547 模块／71 覆盖。
- AST/import 检查：`stage_model_picker`、`desktop_shared_input`、`desktop_shared_menus`、`skill_command`、`desktop_writing_page` 全过。
- 全库 grep 确认无 `ADD_MODEL_LABEL`／`_fill_menu`／`_level_menu` 残留引用（`test_pet_ui` 一处仅为无关注释子串）。

## 范围外记录

- master 侧 `project_status.md` 与 `_master_verify.txt` 未动（前者仅 master 提交）。
- 合并提交后由 master 侧 `dev.py merge codex/wip-R2980` 完成正式合入与合并轮号。
