# R1327：结构治理轮（执行）——聊天记录持久化拆成 L2 idea_transcript

类型：结构治理轮（执行子场景，拆职责、不加功能）。中央轮次 1327。来源为用户直接指定的执行条目"拆分 4：聊天记录持久化"。用户未给出只读诊断报告路径与 J/K 条目编号，本轮按用户逐条列出的执行口径实施（此为信息缺口，照实记录，不补造来源报告）。
轮次说明：本工作树开工时中央最后领取号为 1318（已由并行 O08 车道提交，非本分支祖先）；因并行车道持续领取，按规则 27 与 commit-msg 门禁（提交号须等于中央 last_claimed），提交前多次重新取号，本轮实际中央轮次 1327。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.3 结构治理轮，执行子场景。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 `--affected idea_chat idea_transcript desktop writing_api stage_execution_service`：234 条用例、0 个文件有红（107.6 秒）；默认冒烟 8/8；架构门禁 312/312 OK。全量未跑（纯 L2 搬迁，无五轮差）。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 实现
- 新增 L2 `程序/idea_transcript.py`：搬入 8 个目标函数 `load()`、`append()`、`replace()`、`remove()`、`remove_all()`、`restore_latest_removed()`、`compact_context()`、`repair_internal_replies()`，以及它们必需的私有读写辅助 `_all_rows()`、`_read_rows()`、`save_rows()`、`_row_indexes()`、`_stamp()`、`_visible_claude_text()`、模型会话路径 `folder()`、`history_path()`、`chat_model()`、`model_history_path()`、`deleted_history_path()`、缓存常量 `FOLDER`、`CHAT_NAME`、`_HISTORY_CACHE_LIMIT`、`_history_cache`，以及 `_context()`、`_require_gateway()`。函数签名、返回结构与缓存上限原值不变（超时／轮询／体积常量属语义简报职责，已在 R1309 拆到 `idea_semantic_brief_service`，不在本组）。
- 依赖处理（本拆分唯一硬约束点）：`_all_rows()`／`chat_model()`／`model_history_path()` 需要 `ChatModel`、`_storage_name`、`storage_identity`，从同层 `idea_document_paths`（R1313 产出的路径权威）import；`_context` 沿用本项目各 L2 模块各自持有 ProjectContext 校验的惯例，在新模块内保留独立一份。若把辅助留在 `idea_chat` 而新模块反向 import，会与 `idea_chat`→`idea_transcript` 形成静态互引，被 `test_no_circular_import.py`（`ast.walk` 连函数内 import 一并计入）判红，故辅助随迁。
- `程序/idea_chat.py` 删除被迁移的函数/常量，改为 `from idea_transcript import (...)` 静态重导出；保留自身 `_context()`／`_require_gateway()`／`folder()`，因 `test_project_context_boundary.py` 以源码文本 `def _context(value)` 与 `writing(_context(context).root)` 断言 L2 消费上下文，不能删。被搬符号在 `idea_chat` 仍为活引用（测试经 `idea_chat.X`、desktop 经模块属性调用），非死引用。
- 调用方：`writing_api.py` 的 `load` 改从新模块导入（`import idea_transcript` + `idea_transcript.load(`）；`desktop.py` diff=0——其 `idea_chat.load`／`append`／`repair_internal_replies` 等 15 处为模块属性调用，且 `tests/test_writing_quality.py:173/199/202` 以 `patch('idea_chat.append')`、`tests/test_idea_chat.py:1362` 以 `patch('idea_chat.repair_internal_replies')` 拦截桌面调用，`tests/architecture/test_project_context_boundary.py:150` 断言 desktop 源码含 `idea_chat.load(self.idea_chat_context(`；改指新模块会破坏这些断言，故调用方式与断言未动，沿用 R1313 对 desktop 的同类处置。

## 范围与调用方核验
- `rg -n "idea_chat\.(append|load|replace|remove|remove_all|restore_latest_removed|compact_context|repair_internal_replies)"` 复核：剩余调用面全部为 desktop 模块属性调用与测试经 `idea_chat.X`／注入代理调用，均由 re-export 指回 `idea_transcript`，无死引用。
- `workflow_tasks.py`、`stage_execution_service.py`、`desktop.py` 不使用本组符号：三者 diff=0。
- 测试侧改动仅 1 处：`smoke_test.py` 第 415 行默认冒烟关键字检查（msg："切换模型保留各自独立聊天记录且经 L3 网关读取"）的 `path` 由 `程序\idea_chat.py` 随迁为 `程序\idea_transcript.py`，`keyword`（`def load(root, model=None, *, gateway=None):`）与 `msg` 原样不变。`load` 必须随迁（`compact_context` 内部调用它，留在 `idea_chat` 会与新模块静态互引），故按 R1313／R1317 更新引用点的同类口径随迁检查位置，未改判定内容。
- 生产模块改动 3 个（`idea_chat`、新增 `idea_transcript`、`writing_api`），符合 §3.3"每次最多改 3 个模块"；另同步架构门禁台账与 `smoke_test.py` 检查位置（非功能改动）。

## 门禁台账同步（架构门禁要求，非功能改动）
- `tests/architecture/_layers.py`：L2 登记新增 `idea_transcript`。
- `维护记录/架构统一基数.json`：第一项 `exempt_items` 增 `idea_transcript`、`exempt_count` 38→39；第三项中随迁函数 `remove`／`save_rows`／`restore_latest_removed` 的台账项 `file` 由 `idea_chat.py` 改指 `idea_transcript.py`；第四项 `idea_chat.py:135/330/345` 三项随迁为 `idea_transcript.py:_read_rows`／`remove`／`restore_latest_removed`（其登记的 `json.loads` 债对应的读取点物理搬移）。层级台账未变（未新增越层依赖，仍 37 项）；`第二项` 未变（该路线图为固定 37 项范围，新模块不在其中）。
- `architecture.md`：第 3 节 L2 模块表加入 `idea_transcript`；`## 维护边界` 增 R1327 条目。
- 未改 `legacy_compat.FACADE_MANIFEST`：`idea_transcript` 不 import `legacy_compat`。

## 验证
- 定向：`smoke_test.py --affected idea_chat idea_transcript desktop writing_api stage_execution_service` → 234 条、0 个文件有红（107.6 秒）。
- 默认冒烟：`smoke_test.py` → 8/8。
- 架构门禁：`smoke_test.py --architecture` → 312/312 OK（含 `test_layers`、`test_no_circular_import`、`test_project_context_boundary`、`test_service_return_contract`、`test_unification_ratchet`、`test_todo_comment_snapshot`）。
- 未跑全量：纯 L2 搬迁，无"轮次号 − last_full_safe_all_round ≥ 5"；`tests/architecture/_layers.py` 改动按 §5 属"合并到 master 前全量升级"条件，本工作树只跑架构门禁，是否触发全量升级交由 master 合入判定。

## 自审（§4.2）
1. 验收：新模块落地、命名体现"语义 brief 之外"的聊天记录持久化职责、位于 L2 同层、`idea_chat` 删除定义并保留必要 re-export（无死引用）、`writing_api` 改 import 且 `desktop` 调用方式与断言未动、定向与门禁按 §5 全绿——均达成。
2. 范围：未改范围外文件（`workflow_tasks.py`／`stage_execution_service.py`／`desktop.py` diff=0），未改用户数据，未动 `.agent-handoff/`；生产模块 3 个，符合 §3.3 上限。
3. 验证：定向、默认冒烟与架构门禁为本轮实测绿；全量未跑并已注明，未冒用历史凭据。首次默认冒烟因 `smoke_test.py` 关键字检查仍指向 `idea_chat.py` 而 1 红，随迁该检查位置后复跑 8/8（属引用点随迁，非断言弱化）。
4. 新问题：无环（`idea_transcript`→`idea_document_paths`、`idea_chat`→`idea_transcript`／`idea_document_paths` 均为同层单向）；`idea_transcript` 只 import L0 `project_context` 与同层 `idea_document_paths`，无越层。

## 收尾提交
- 已提交；轮次类型：结构治理轮。提交首行：`R1327: 轮次类型：结构治理轮——聊天记录持久化拆成 idea_transcript`。
- 工作树因预提交门禁（只有 master 可提交 `project_status.md`）不把状态页并入本提交。