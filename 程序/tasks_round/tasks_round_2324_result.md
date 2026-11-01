# R2324 右键「重写XX」改为「取消已确认」结果

## 三个必答问题（AGENTS.md §7.3）

1. **本轮类型**：功能轮（UI + L2/L3），§3.1。
2. **测试跑了吗、三个基线过了吗**：
   - 默认冒烟 `smoke_test.py`：8/8 通过。
   - 架构门禁 `run_selftests.py -k ratchet requirement_traceability layers`：56 条全绿（含分层、模块大小棘轮、需求锚定）。
   - 定向回归 `run_selftests.py -k writing preparation idea_chat ui_edges`：468 条全绿；新测试 `-k writing_unconfirm` 9 条全绿。
   - 全量 `--all --safe`：未由本轮运行（本工作树为分支，全量由调度方在 master 提交点执行，本任务未触发）。
3. **project_status.md 的欠账少了吗**：未涉及；本任务不新增欠账。

## 改动文件

- `程序/writing_unconfirm.py`（新增，L3）：`preparation_confirmed_stages`、`unconfirm_preparation_document`。
- `程序/stage_execution_service.py`：新增 `unconfirm_writing_preparation`（净 0 行，仍 1442 行 = 上限）。
- `程序/desktop_writing_page.py`：删除模块级 `_restart_preparation` 与页面方法 `restart_preparation`；新增 `unconfirm_preparation`；`script_menu` 的「重写<阶段>」「放弃重写，恢复原稿」改为「取消已确认」（仅已确认阶段显示）。
- `程序/tests/architecture/_layers.py`：登记 `writing_unconfirm` 为 L3。
- `程序/tests/test_writing_unconfirm.py`（新增）：9 条测试。
- `程序/tests/test_writing_restart.py`：删除 3 条旧菜单/预填测试（见「断言处理声明」）。
- `程序/docs/stages/S01_剧本准备.md`：新增 REQ-S01-78、DES-S01-78；更新 REQ-S01-52；测试锚定表同步。

## 旧「重写」菜单与「放弃重写」的去留结论

- **「重写<阶段>」菜单**：移除，改为「取消已确认」（本任务核心需求）。桌面模型预填「重新生成<阶段>」随之移除；聊天口令「重新生成<阶段>」仍由 `workflow_tasks.writing_restart_requested` 识别，行为不变。
- **「放弃重写，恢复原稿」菜单**：移除。已查清其独立用途：`restart_preparation(None)` 分支在产物代码中只被该菜单项调用（另有 `test_writing_edited_restart.py` 直接测 L2 函数本身）；`_preparation_rollback`、`preparation_restart_intent`、`_preparation_restart_target`、`restart_preparation(stage)` 被聊天回退路径使用。因此**保留底层函数** `writing_api.restart_preparation`（含 `None` 分支）与 `_preparation_rollback` 等，仅移除菜单项；聊天口令回退路径行为不变。

## 实现要点

- 取消确认是 `confirm_preparation_document` 的对称操作：把采用 `documents` 截断为 `documents[:index] + [该阶段(confirmed=False)]`，下游已确认阶段一并失效，阶段指针回到该阶段；清除 `revision`／`pending_restart`。只改 `preparation_state.json`，不删改任何 `.md` 文件。
- 写台账复用 `writing_api._save_preparation_state`、读复用 `file_cache.read_json`，不另立第二入口；桌面经 `stage_execution_service.unconfirm_writing_preparation` 注入 `publish_stage_text`，不直接写台账。
- 因 `writing_api.py` 已到模块大小上限（1372=上限），按模块大小棘轮要求把新函数放入新模块 `writing_unconfirm.py`（60 行 ≤ 1000），`writing_api.py` 保持不动（与「只新增不改既有函数、减少合并冲突」一致）。
- 菜单可用性：`script_menu` 只在 `stage in preparation_confirmed_stages(project)` 时加「取消已确认」项；未确认不显示。取消前弹 `writing_page_services.confirm` 说明连带取消的下游阶段与不删文件。

## 测试命令与实际结果

| 命令 | 结果 |
| --- | --- |
| `& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B smoke_test.py` | 8/8 通过 |
| `& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B run_selftests.py -k writing_unconfirm` | 9 条全绿 |
| `& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B run_selftests.py -k ratchet requirement_traceability layers` | 56 条全绿 |
| `& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B run_selftests.py -k writing preparation idea_chat ui_edges` | 468 条全绿 |

测试覆盖任务书 6 项验证：

1. 取消中间阶段（大纲）→ 设定仍确认、大纲与角色卡取消：`test_unconfirm_middle_stage_keeps_setting_and_cancels_outline_and_character`。
2. 取消首阶段（设定）→ 三阶段全取消：`test_unconfirm_first_stage_cancels_all_three`。
3. 未确认阶段取消无效且不报错：`test_unconfirm_unconfirmed_or_missing_stage_is_noop`。
4. 文件不被删改：`test_unconfirm_keeps_files_on_disk`；重写台账清理：`test_unconfirm_clears_pending_rewrite`。
5. 菜单项文案与可用性（真 Tk）：`test_menu_offers_cancel_confirmation_only_when_stage_confirmed`。
6. 聊天口令回退路径行为不变：`test_chat_restart_path_unchanged`；REQ-S01-52 锚定 `test_req_s01_52_unconfirm_does_not_require_api_model`。

## 断言处理声明

契约有意变更：右键菜单「重写<阶段>」→「取消已确认」，「放弃重写，恢复原稿」移除（任务书明确要求）。

- 因契约变更而改的旧测试：删除 `test_writing_restart.py` 中 3 条针对旧行为的测试（`test_desktop_stage_menu_routes_explicit_restart_and_cancel`、`test_req_s01_52_desktop_model_prefills_explicit_restart_command`、`test_req_s01_52_api_model_and_cancel_keep_revision_path`），它们断言的是被移除的旧菜单与桌面预填行为；REQ-S01-52 锚定从 `test_writing_restart` 改到 `test_writing_unconfirm`（`test_req_s01_52_unconfirm_does_not_require_api_model`，仍断言「桌面/命令行模型不报请选择 API 模型」）。
- **断言未弱化**：新测试对任务书 6 项验证逐项断言；`test_chat_restart_path_unchanged` 保留「聊天口令回退路径（含 `restart_preparation(None)` 恢复原稿）行为不变」的断言；未删除任何仍有行为意义的断言，未跳过测试制造通过。

## 未验证项

- 全量回归 `run_selftests.py --all --safe`：未运行（分支轮不累计全量欠账，由调度方在 master 提交点执行）。
- 未提交：按任务书「不提交（调度方提交）」。
- 说明：本工作树缺少 git 子模块内容（`程序/skills/00全流程SKILL/AIGC创作全流程` 等 4 个 gitlink 为空），导致任何经 `writing_api.reply → freeze_skills` 的测试缺 SKILL 引用。验证前已从主树按同一 gitlink commit 复制子模块内容到本工作树（与 `git ls-tree HEAD` 的 gitlink SHA 一致，未使 `git status` 变脏），使 `-k writing` 回归可运行。该子模块内容不在本轮改动范围内。
