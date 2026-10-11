# R1317：结构治理轮（执行）——简报表单解析/校验拆成 idea_brief_form

类型：结构治理轮（执行子场景，拆职责、不加功能）。中央轮次 1317。来源为用户直接指定的执行条目"拆分 3：brief 表单解析"。用户未给出只读诊断报告路径与 J/K 条目编号，本轮按用户逐条列出的执行口径实施（此为本轮信息缺口，照实记录，不补造来源报告）。
轮次说明：本工作树先按中央轮次 1315 起草，但领取后中央计数器被并行车道推进到 1316（非本分支祖先），按规则 27 与 commit-msg 门禁（提交号须等于中央 last_claimed、且不得复用非祖先分支已用轮次），提交前重新取号，本轮实际中央轮次为 1317。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.3 结构治理轮，执行子场景。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 `--affected idea_chat idea_brief_form idea_document_paths desktop writing_api stage_execution_service`：9 项通过、0 个文件有红（95 秒，含 `test_idea_chat`、`test_idea_inline_brief`、`test_idea_local_brief`、`test_idea_semantic_brief`、`test_idea_attachment_brief`、`test_stage_prompt_governance`、`test_writing_api`、`test_desktop_startup_perf` 等）；默认冒烟 8/8；架构门禁 312/312 OK。全量未跑（纯 L2 搬迁，无五轮差）。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 实现
- 新增 L2 `程序/idea_brief_form.py`：搬入 `extract_brief_creation()`、`merge_brief_creation()`、`inline_required_missing()`、`brief_creation_values()`、`format_brief_creation()`，以及其解析辅助 `_brief_plain_text()`、`strip_inline_required_markers()`、`inline_template_labels()` 与字段契约 `BRIEF_CREATION_FIELDS`。函数签名、返回结构与必填/锁门禁判定门槛原值不变。
- 依赖处理（本拆分唯一硬约束点）：`brief_creation_values()` 要读简报文件，需 `brief_raw_path()`／`legacy_brief_raw_path()`。这两者当时仍在 `idea_chat`（R1313 拆分 2 未提取它们；用户口径假设它们在拆分 2 模块内，实为事实差异）。若 `idea_brief_form` 反向 import `idea_chat`，会与 `idea_chat`→`idea_brief_form` 形成静态互引，被 `test_no_circular_import.py`（`ast.walk` 连函数内 import 一并计入）判红；重复定义又违反本轮"不要重复定义路径权威"的口径。故按用户"改为 import 拆分 2 的新模块"的意图，把简报文件路径族 `brief_raw_path()`／`legacy_brief_raw_path()`／`brief_complete_path()` 及其文件名常量（`BRIEF_CREATION_NAME`／`LEGACY_BRIEF_RAW_NAME`／`BRIEF_RAW_NAME`／`BRIEF_COMPLETE_NAME`）随迁到既有 L2 路径权威 `idea_document_paths`（纯路径计算，签名与原命名不变），`idea_brief_form` 与 `idea_chat` 均从该权威 import。
- `程序/idea_chat.py` 删除上述函数/常量与 `brief_*_path` 定义，改为 `from idea_brief_form import (…)` 与 `from idea_document_paths import (…brief_complete_path, brief_raw_path, legacy_brief_raw_path…)`；因内部 `_brief_value()`／`_brief_fields()`／`_append_raw_brief()`／`save_brief_creation()`／`receive_brief()` 仍要用解析辅助与简报路径，故保留必要 re-export（`extract_brief_creation`／`merge_brief_creation`／`inline_required_missing`／`brief_creation_values`／`format_brief_creation`／`strip_inline_required_markers`／`inline_template_labels`／`BRIEF_CREATION_FIELDS`／`brief_raw_path`／`legacy_brief_raw_path`／`brief_complete_path`）。这些符号均有活消费者（测试经 `idea_chat.X` 取用、`desktop` 经模块属性调用），非死引用。
- 调用方改指新模块：`stage_execution_service.py` 两处（第 402、1427 行附近）`from idea_chat import extract_brief_creation` → `from idea_brief_form import extract_brief_creation`；`writing_api.py` `preparation_continuation()` 内 `import idea_chat`＋`idea_chat.extract_brief_creation` → `from idea_brief_form import extract_brief_creation`；`desktop.py` 第 727 行 from-import 改指新模块。调用方式（参数、返回值用法）未动。

## 范围与调用方核验（含与用户口径的事实差异）
- `rg` 复核五个符号的调用方：`desktop.py`（`idea_chat.extract_brief_creation`／`merge_brief_creation`／`inline_required_missing` 模块属性调用，及第 727 行 `from idea_chat import strip_inline_required_markers`）、`writing_api.py`（第 498 行）、`stage_execution_service.py`（第 402、1427 行）。`workflow_tasks.py` 不使用本批符号（其 diff=0）。
- 事实更正：用户口径称 `brief_complete_path` 由"拆分 2 的新模块"产出；实际 R1313 只提取了 `storage_identity`／`reply_path_parts` 等 6 个符号，`brief_raw_path`／`legacy_brief_raw_path`／`brief_complete_path` 仍留在 `idea_chat`。本轮为满足"import 拆分 2 的新模块、不重复定义"并规避静态互引，随迁这三个简报路径函数到 `idea_document_paths`。
- `desktop.py` 保留 `idea_chat.extract_brief_creation`／`merge_brief_creation`／`inline_required_missing` 模块属性调用不改：`tests/test_idea_inline_brief.py:378` 以 `patch('idea_chat.inline_required_missing', wraps=idea_chat.inline_required_missing)` 断言桌面发送确实经该入口（`missing.call_args.args[0] is None`）；若改为直接 import 新模块将破坏该断言，违反"断言未动"。故仅改其唯一对搬家符号的 from-import（第 727 行），其余经 re-export 仍为活引用。
- 测试侧改动：无。相关测试经 `idea_chat.X` 或注入代理调用，re-export 已保证符号可解析；patch 目标保持 `idea_chat.*`。断言与判定门槛未动。
- 生产模块改动 6 个（`idea_chat`、新增 `idea_brief_form`、`idea_document_paths`、`desktop`、`writing_api`、`stage_execution_service`），**超出** §3.3"每次最多改 3 个模块"。超支因用户明确要求 3 个调用方逐一改 import，且为规避静态互引必须随迁简报路径族；与 R1309／R1313 同型，如实记录。

## 门禁台账同步（架构门禁要求，非功能改动）
- `tests/architecture/_layers.py`：新增 L2 模块 `idea_brief_form` 入表。
- `维护记录/架构统一基数.json` 第一项：`idea_brief_form` 加入 `exempt_items`（纯文本解析、零数据读写），`exempt_count` 37→38。`idea_document_paths` 仍为既有豁免项，其新增简报路径函数未引入新的越层依赖（沿用 `project_stages.writing`）。
- `architecture.md`：L2 模块表加入 `idea_brief_form`；"维护边界"新增 R1317 条目。
- 未改 `legacy_compat.FACADE_MANIFEST`：`idea_brief_form`／`idea_document_paths` 均不 import `legacy_compat`（`optional_model_identity` 仍只由 `idea_document_paths.storage_identity` 使用，调用方登记不变）。

## 验证
- 定向：`smoke_test.py --affected idea_chat idea_brief_form idea_document_paths desktop writing_api stage_execution_service` → 9 项通过、0 个文件有红（95 秒，增量台账已刷新）。
- 默认冒烟：`smoke_test.py` → 8/8 通过。
- 架构门禁：`smoke_test.py --architecture` → 312/312 OK（含 `test_no_circular_import`、`test_layers`、`test_project_context_boundary`、`test_service_return_contract`、`test_unification_ratchet`、`test_todo_comment_snapshot`）。
- 未跑全量：改动属 L2 纯搬迁，无"轮次号 − last_full_safe_all_round ≥ 5"；`_layers.py` 更新按 §5 属"合并到 master 前全量升级"条件，本工作树按 §5 只跑架构门禁，是否触发全量升级交由 master 合入判定。按 §5 本轮不跑全量。

## 自审（§4.2）
1. 验收：新模块落地、命名体现"简报表单解析"职责、位于 L2 同层、`idea_chat` 删除定义并保留必要 re-export（无死引用）、`stage_execution_service`／`writing_api`／`desktop` 改 import、定向与门禁按 §5 全绿——均达成。
2. 范围：未改其他函数、未改用户数据、未动 `.agent-handoff/`；`workflow_tasks.py` diff=0。生产模块 6 个，超 §3.3 上限，已如实记录；`idea_document_paths` 的改动为简报路径族随迁（规避静态互引的必需项）。
3. 验证：定向、默认冒烟与架构门禁为本轮实测绿；全量未跑并已注明，未冒用历史凭据。
4. 新问题：无环（`idea_brief_form`→`idea_document_paths`、`idea_chat`→`idea_brief_form`／`idea_document_paths` 均为同层单向）。`idea_brief_form` 只 import L0 `script_contract` 与同层 `idea_document_paths`，无越层。

## 收尾提交
- 已提交；轮次类型：结构治理轮。提交首行：`R1317: 轮次类型：结构治理轮——简报表单解析拆成 idea_brief_form`。
- 工作树因预提交门禁（只有 master 可提交 `project_status.md`）不把状态页并入本提交。
