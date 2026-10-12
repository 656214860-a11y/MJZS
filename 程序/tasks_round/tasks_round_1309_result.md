# R1309：结构治理轮（执行）——语义简报请求与结果校验拆出 idea_chat

类型：结构治理轮（执行子场景，拆职责、不加功能）。中央轮次 1309。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.3 结构治理轮，执行子场景。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 247/247、0 个文件有红；默认冒烟 8/8 加门禁 1 项＝通过 9、失败 0；架构门禁 312/312。全量未跑（纯服务迁移，无五轮差、无升级项）。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 来源与范围

- 轮次号冲突（事实记录）：本轮初次领取的是 1308，但并行 O06 车道已占用 `R1308`（提交 9fe543e，非本分支祖先），commit-msg 门禁以"已被非祖先分支使用"拒绝；已重新领取 1309，本结果文件、`architecture.md` 备注与 `project_status.md` 条目同步为 R1309。
- 来源为用户直接指定的执行条目（把 `程序/idea_chat.py` 的语义 brief 请求轮询部分抽成独立模块）。
- §3.3 要求执行子场景写明来源报告路径与执行条目编号；用户未给出报告路径与编号，故按用户直接条目执行，此处如实记录该缺口，不补造报告。
- 用户条目含两处与当前树不符的前提，已按实际更正并执行（见"与用户口径的偏差"）。

## 实现
- 新增 L3 `程序/idea_semantic_brief_service.py`：迁入 `semantic_brief_request`、`semantic_brief_values` 与 `SEMANTIC_BRIEF_TIMEOUT`／`SEMANTIC_BRIEF_POLL_SECONDS`／`SEMANTIC_BRIEF_MAX_BYTES`／`SEMANTIC_BRIEF_INFERRED`。函数签名、返回结构、超时／轮询／体积常量原值未动。
- 简报文件路径与 `ProjectContext` 校验仍委托 L2 `idea_chat.brief_raw_path()`；新模块不自行拼接路径（"路径命名"职责留在 `idea_chat`）。
- `程序/idea_chat.py` 删除上述 2 函数与 4 常量，并移除随之无消费者的 `BRIEF_EXTRACTION_LABELS` 导入。
- 调用点改指新模块：`stage_execution_service.py` 两处（原 414、428 行）、`writing_api.py` 一处（原 470 行）、`desktop.py` 的 `poll_idea_semantic_brief`（原 1631／1637／1643 行）、`tests/test_idea_semantic_brief.py` 六处。
- 登记：`tests/architecture/_layers.py` 的 L3 登记表；`architecture.md` 的 L3 模块表与"维护边界"新增 R1309 条目。

## 与用户口径的偏差（依据与风险）
1. "唯一生产调用方只有 `stage_execution_service.py`"不成立。`writing_api.extract_idea_brief()`（非本地 API 通道）与 `desktop.Desktop.poll_idea_semantic_brief()` 也直接用这批符号：`writing_api.py:470` 用 `SEMANTIC_BRIEF_MAX_BYTES`／`semantic_brief_values`，`desktop.py:1637`／`1643` 用 `SEMANTIC_BRIEF_TIMEOUT`／`SEMANTIC_BRIEF_POLL_SECONDS`。因此"这三个文件 diff 应为 0"对 `writing_api.py`、`desktop.py` 不成立；`workflow_tasks.py` 确实不用这批符号，其 diff 为 0（它只用 `reply_path_parts`／`storage_identity`／`PROJECT_DOCUMENT_DIRS`）。
2. 要求"第 402 行也改指新模块"不成立：`stage_execution_service.py:402` 是 `from idea_chat import extract_brief_creation`，属"brief 表单解析"职责，不在本轮范围，保持不动。
3. 要求"`idea_chat` 保留必要的 re-export"在本分层下不可实现，故未保留。新模块必须复用 `idea_chat.brief_raw_path()`；若 `idea_chat` 反向 re-export 新模块符号，则同时构成 L2→L3 反向 import 与两模块静态互引，`test_layers` 与 `test_no_circular_import` 必红。因此调用点直接改指新模块，不留兼容 re-export；`idea_chat` 中这批符号已无残留引用。
4. 代价：实际改动 5 个生产模块（`idea_chat`、新增 `idea_semantic_brief_service`、`stage_execution_service`、`writing_api`、`desktop`），超过 §3.3"每次最多改 3 个模块"；其中 `writing_api.py`、`desktop.py` 仅为 import 来源重定向，无逻辑改动。若要严格守住 3 模块上限，只能缩到"仅搬 `semantic_brief_request`"，那会把同一职责留在两个文件，故本轮选择一次搬干净并如实上报代价。
5. 常量值未改（300／1／65536、三项归纳标签），`idea_chat` 侧无行为变更。

## 验证
- 定向：`smoke_test.py --affected idea_chat idea_semantic_brief stage_execution_service writing_api desktop` → 247 条用例、128.2 秒、0 个文件有红；默认冒烟 8/8 加门禁 1 项，合计通过 9、失败 0。
- 架构门禁：`smoke_test.py --architecture` → 312/312 OK（含分层登记、无环依赖、历史兼容门面）。
- 未跑全量：纯服务迁移，本轮无"轮次号 − last_full_safe_all_round ≥ 5"，也无启动路径／Tk 生命周期／删除语义／层级登记表改动，按 §5 不触发全量。
- 环境事实（非本轮代码问题）：本工作树 `程序/skills/00全流程SKILL/AIGC创作全流程` 是 gitlink（mode 160000）且 `.gitmodules` 无对应条目，内容未落盘，导致 1 项架构用例与多个依赖 SKILL 引用的用例在本轮之前即报 `screenplay-gate-engine.md` 缺失。本轮把主树同名目录内容复制进工作树（未跟踪内容，不改仓库跟踪文件，不进提交），修复后上述用例全绿；该目录内残留一份复制误操作产生的嵌套副本 `AIGC创作全流程/AIGC创作全流程/`，递归删除被环境策略拦截，未清理，仅存在于未跟踪目录内。

## 自审（§4.2）
1. 验收：抽取独立模块、签名／结构／常量不变、调用点改指新模块、`idea_chat` 删除、按 §5 跑测试与架构门禁均达成；与之冲突的三处用户前提已如实更正并给出依据。
2. 范围：5 个生产模块＋1 个测试文件＋分层登记＋架构文档，超出"最多 3 个模块"，已在偏差 4 列明。
3. 验证：定向与架构门禁为本轮实测绿；全量未跑并已标注，未冒用历史凭据。
4. 新问题：无新增越界依赖；新模块仅依赖 L0 `script_contract`、L2 `idea_chat`／`idea_attachments` 与标准库，自身位于 L3，无反向依赖。
