# R1313：结构治理轮（执行）——路径/命名策略拆成 idea_document_paths

类型：结构治理轮（执行子场景，拆职责、不加功能）。中央轮次 1313。来源为用户直接指定的执行条目"拆分 2：路径/命名策略"。用户未给出只读诊断报告路径与 J/K 条目编号，本轮按用户逐条列出的执行口径实施（此为本轮信息缺口，照实记录，不补造来源报告）。
轮次说明：本工作树原按中央轮次 1311 起草，但领取后中央计数器被并行车道推进到 1312（master 上 R1312-FAIL，非本分支祖先），按规则 27 与 commit-msg 门禁（提交号须等于中央 last_claimed、且不得复用非祖先分支已用轮次），领取时重新取号，本轮实际中央轮次为 1313。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.3 结构治理轮，执行子场景。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 `--affected idea_chat idea_document_paths workflow_tasks writing_api desktop`：9 项通过、0 个文件有红（561 秒，含 `test_idea_chat`、`test_writing_api`、`test_desktop_startup_perf` 等）；默认冒烟 8/8 加门禁 1 项＝通过 9、失败 0；架构门禁 312/312 OK。全量未跑（纯 L2 搬迁，无五轮差、无升级项）。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 实现
- 新增 L2 `程序/idea_document_paths.py`：搬入 `storage_identity()`、`reply_path_parts()`、`reply_document_path()`、`project_script_filename()`、`project_document_directory()`、`PROJECT_DOCUMENT_DIRS`，函数签名、返回结构与命名规则原值不变。
- 随迁其必需的私有命名辅助：`ChatModel`、`_storage_name()`、`_file_day()`、`_file_part()`、`_project_file_type()`、`_OVERWRITE_FILE_TYPES`。这些辅助被"移走"与"留在 `idea_chat`"的代码共用，若留原地会形成 `idea_chat` ↔ 新模块的静态互引，被 `test_no_circular_import.py` 禁止，故随职责一并迁入新模块，`idea_chat` 反向 import 使用。
- `_context()` 未随迁：`test_project_context_boundary.py` 硬性要求 `idea_chat.py` 仍含 `def _context(value)` 与 `writing(_context(context).root)`；按本项目各 L2 模块各自持有 `_context` 的既有惯例（如 `previs_routing`），新模块内保留语义一致的独立一份，`idea_chat` 继续持有自身校验。异常文案按原文保留。
- `程序/idea_chat.py` 删除上述定义，改为 `from idea_document_paths import (…)`；因内部 `model_history_path()`／`save_reply()`／`save_manual_creative()`／`creative_documents()` 仍要用 `storage_identity`／`_storage_name`／`_file_day`／`_project_file_type`／`reply_document_path` / `project_document_directory` / `project_script_filename` / `PROJECT_DOCUMENT_DIRS`，故保留必要 re-export；`reply_path_parts` 内部已无消费者，仅因 `tests/test_script_agent_delivery_paths.py` 直接以 `idea_chat.reply_path_parts` 调用而保留 re-export（非死引用，符号可解析）。
- 调用方改指新模块：`程序/workflow_tasks.py`（第 11、20 行 import）、`程序/writing_api.py`（`from idea_chat import ChatModel` → 新模块；`project_document_directory` import；`_preparation_step`／`_save_formal_script` 内 `import idea_chat` → `import idea_document_paths` 并改 `storage_identity`／`reply_document_path` 取值来源）。调用方式（参数、返回值用法）未动。
- 新增 L2 模块登记：`tests/architecture/_layers.py`；`architecture.md` 的 L2 模块表与"维护边界"新增 R1313 条目。

## 范围与调用方核验（含与用户口径的事实差异）
- `rg` 复核六个符号在生产侧的调用方：`workflow_tasks.py`（reply_path_parts、storage_identity、PROJECT_DOCUMENT_DIRS）、`writing_api.py`（storage_identity、reply_document_path、project_document_directory）、`desktop.py`（仅 storage_identity）。`stage_execution_service.py` 不使用这六个符号（该文件只承接任务 1 的语义简报，与本拆分无关）。
- 用户口径更正 1：`writing_api.py` 实际用的是 `storage_identity`／`reply_document_path`／`project_document_directory`，并非用户列举的 `brief_complete_path`；`brief_complete_path` 不在本轮六个提取符号内（它是消费方，`idea_chat` 定义、`writing_api` 268 行与 `stage_execution_service` 1393 行调用），本轮不动。
- 用户口径更正 2：`desktop.py` 对本轮符号只有一处调用 `idea_chat.storage_identity(selected_model)`（第 2114 行，函数内 `import idea_chat` 后按模块属性取值），并非"调用面最广"。用户同时要求"不改调用方式"，且 `tests/test_idea_chat.py:168` 断言 `idea_chat.storage_identity` 被实际调用；若改为直接 import 新模块将破坏该断言或必须改测试 patch 目标。综合"不改调用方式 + 断言未动"，`desktop.py` 保持 0 改动：其 `idea_chat.storage_identity` 经 `idea_chat` 的必要 re-export 解析到新模块定义，来源已指向新模块。`git diff --numstat -- desktop.py` 为空。
- 测试侧改动：仅 `程序/tests/test_script_agent_delivery_paths.py` 两处 patch 目标改指新模块（`'idea_chat.storage_identity'`→`'idea_document_paths.storage_identity'`、`'idea_chat.reply_path_parts'`→`'idea_document_paths.reply_path_parts'`）。这是接口搬家后同步调用路径（§用户要求"不要留死引用"的性质），断言内容与判定门槛未动。其余经 `idea_chat.X` 的测试引用（`test_idea_chat.py` 364/407、`test_writing_api.py` 647、`test_workflow_writing_stages.py` 41、`test_script_agent_delivery_paths.py` 50）因保留 re-export 仍为活引用，未改。
- 生产模块改动 5 个（`idea_chat`、新增 `idea_document_paths`、`workflow_tasks`、`writing_api`、`legacy_compat`），**超出** §3.3"每次最多改 3 个模块"。超支仅因用户明确要求 3 个调用方逐一改 import；`legacy_compat` 仅改一行门面台账（见下）。此为已知代价，与 R1309 同型。

## 门禁台账同步（架构门禁要求，非功能改动）
- `维护记录/架构统一基数.json` 第一项：新增 L2 模块必须登记范围记录，`idea_document_paths` 加入 `exempt_items`（与 `idea_chat` 同组，纯路径计算、零数据读写），`exempt_count` 36→37。
- 同文件"层级"台账：`legacy_compat` 的既存越层豁免项由 `(idea_chat.py, idea_chat, legacy_compat)` 原位改为 `(idea_document_paths.py, idea_document_paths, legacy_compat)`（`storage_identity` 是 `idea_chat` 唯一 import `legacy_compat` 的位置，已随迁）。项数 37→37、`baseline_exempt` 不变。
- `程序/legacy_compat.py`：`FACADE_MANIFEST['optional_model_identity']['callers']` 由 `('idea_chat',)` 改为 `('idea_document_paths',)`，`test_legacy_facade_manifest.py` 要求登记调用方与实际调用方一致。仅改调用方名字，facade 行为、owner、retire_after 未动。

## 验证
- 定向：`smoke_test.py --affected idea_chat idea_document_paths workflow_tasks writing_api desktop` → 9 项通过、0 个文件有红（561 秒）；默认冒烟 8/8 加门禁 1 项，合计通过 9、失败 0。
- 架构门禁：首次 `smoke_test.py --architecture` 312 项中红 1 项（`test_legacy_facade_manifest` 门面调用方未同步）；同步 `legacy_compat.FACADE_MANIFEST` 后复跑 312/312 OK。该红为本轮符号搬家的必然联动，非放宽断言。
- 未跑全量：改动属 L2 纯搬迁，无"轮次号 − last_full_safe_all_round ≥ 5"，也未改启动路径、Tk 控件生命周期、删除语义；`_layers.py` 虽更新，但 §5 的"合并到 master 前全量升级"针对"层级登记表改动"，本工作树按 §5 只跑架构门禁，是否触发全量升级交由 master 合入判定。按 §5 本轮不跑全量。

## 自审（§4.2）
1. 验收：新模块落地、命名体现"路径/命名策略"职责、位于 L2 同层、`idea_chat` 删除定义并保留必要 re-export、`workflow_tasks`／`writing_api` 改指新模块、`desktop` 调用方式与断言未动、定向与门禁按 §5 全绿——均达成（`desktop` 保持 0 改动及其理由见上，属与用户措辞的有据偏差）。
2. 范围：未改其他函数、未改用户数据、未动 `.agent-handoff/`；`workflow_tasks` 之外的用户点名的三文件 diff 见 `git diff --numstat`（`desktop.py`=0）。生产模块 5 个，超 §3.3 上限，已如实记录。
3. 验证：定向与架构门禁为本轮实测绿；全量未跑并已注明，未冒用历史凭据。
4. 新问题：新模块不 import 更高层之外的越层仅 `legacy_compat` 一项（既存豁免随迁登记）；无环（新模块不 import `idea_chat`，`idea_chat` 对新模块为单向依赖）。`_context` 为按项目惯例的每模块独立实现，非隐藏复制，已在架构文档说明。`idea_chat.reply_path_parts` 为迁移期兼容 re-export，已在架构文档记录。

## 收尾提交
- 已提交；轮次类型：结构治理轮。提交首行：`R1313: 轮次类型：结构治理轮——路径命名策略拆成 idea_document_paths`。
- 提交后 HEAD 的 commit hash 记录在 `project_status.md` 的 R1313 条目；工作树因预提交门禁（只有 master 可提交 `project_status.md`）不把状态页并入本提交。