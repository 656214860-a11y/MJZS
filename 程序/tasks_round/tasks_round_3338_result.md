# R3338 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 6D（D7 结构治理轮第四组：阶段别名收敛）
<!-- round-evidence: {"commit_base": "df324d65", "credential_hits": 0, "evidence_sha256": "6065ea0604e8ff19", "exit": 0, "failed": 0, "passed": 28, "round": 3338, "tests": "run_selftests.py -k stage_layout stage_path project_stages"} -->

## 三问

1. **本轮类型**：§3.3 结构治理轮——L0 契约层防崩溃与协议补齐任务书「轮 6D·D7（第四组）」：阶段别名收敛为一份（R3230 §2.3）；`structure`／`frames`／`editing` 三个多出别名先查消费者再定去留。契约模块边界＝2 个（`contract/stage_layout.py`＋`contract/stage_path_service.py`），符合「每次最多 3 个模块」。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k stage_layout stage_path project_stages` 28 条 0 红；`smoke_test.py --affected stage_layout stage_path_service` 10/10 通过（门禁段 31 个测试模块、624 秒隐藏桌面全过）；默认冒烟 9/9；`smoke_test.py --architecture` 532 条、唯一红 `test_round_number_continuous`（3234 != 3331）——工作树 `project_status.md` 只许 master 更新的既有治理现场，改前改后同一失败集合；全量回归未跑（分支轮不累计，`full-safe-receipts.json` 为唯一权威）。
3. **欠账少了吗**：少了——阶段键→规范阶段 id 的解析原先在 `stage_path_service._STAGES` 硬编码 16 条（13 个规范 id 逐字重抄 `stage_layout.STAGES` 第 2 列＋3 个别名），现改为 `stage_layout.canonical_stage_id()` 单点派生：规范 id 只认 `STAGES` 第 2 列、历史拼写只认 `STAGE_ALIASES` 一张表，阶段别名事实全部收进 L0 契约权威模块一处维护。新增欠账：无。

## 前置核对与别名消费者证据

- 领号：`round_claim.py next` → **R3338**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`；round-claims.json 已核对归属本树）。
- 决策来源：`tasks_round_3230_result.md` §2.3「阶段别名｜`stage_layout.py:67-80`／`stage_path_service.py:10-15`｜后者多出 `structure`/`frames`/`editing` 三个别名，`pet_bus.STAGES` 里没有」；任务书轮 6D 行「先查消费者再定去留」。
- 历史背景：R3093 删掉了 `project_stages.STAGES` 字典（键拼写 `structure`/`frames`/`editing` 与 `pet_bus.STAGES` 不一致），但 `structure()`／`editing()` 便捷函数与 `stage(dst,'frames')` 调用点保留了旧拼写，`_STAGES` 里的三个别名正是为它们兜底。

### 三个多出别名的消费者（全仓 grep，含测试）

| 别名 | 规范 id | 生产消费者 | 测试消费者 |
| --- | --- | --- | --- |
| `structure` | `script_structure` | `contract/script_contract.py:494,573`（`write_dir(project,'structure')`）；`domain/script_workspace_service.py:245`；`contract/project_stages.py:29` `structure()` → `domain/storyboard_catalog_service.py:453`、`orchestrator/storyboard_recycle_service.py:22,82` | `tests/test_critical_chains.py:321`、`tests/test_script_structure_dedup.py:90`、`tests/test_stage_path_service.py:13` |
| `frames` | `keyframe` | `domain/projects.py:389,397`（`project_stages.stage(dst,'frames')`） | —（间接经 `test_stage_path_service` 等路径口径用例） |
| `editing` | `edit` | `contract/project_stages.py:50` `editing()` → `domain/edit_service.py:40`、`domain/stage_workspace_service.py:24`、`orchestrator/engine.py:885,912` | `tests/test_editing_scope.py:66,89`、`tests/test_stage_workspace_service.py:50,58`、`tests/test_project_stages.py:16,20` |

**去留决策：三个别名全部保留**——均有真实生产消费者，删除会破坏剧本结构稿发现/回收、首帧导入目录解析与剪辑清单发布。任务书「别名行为对外不变（同一输入同一解析结果）」约束下，保留是唯一不改行为的选择；消费者证据如上表。

### 边界核对（防止误删/误并）

- `_STAGES`／`_LEGACY` 为私有名，全仓无外部 import；`LEGACY_NUMBERED`（公开）键是规范 id，本轮未动其内容与键域。
- `stage_dir()`／`paths()` 的入参域是**目录名**（`01剧本准备`…`13质检交付` 或 `LEGACY_STAGE_ALIASES` 旧目录名），与阶段键域不相交；`write_dir()` 系列入参域是**阶段键**（规范 id＋三个历史拼写）。两域不合并：若把 `LEGACY_STAGE_ALIASES` 与 `STAGE_ALIASES` 压成一张「别名→id」表，`write_dir(project,'00_script')` 会从 `ValueError` 变成合法解析——违反「同一输入同一解析结果」。故两表在 `stage_layout` 内按域并存，别名事实仍只有一个模块维护。
- 流程名↔阶段 id 的另一套映射（`script_contract.lock_stage:1004`、`orchestrator/workflow_engines.py:27`、`orchestrator/qwen_adapter.py:27`、`desktop_shared_send.FLOW_FOR_STAGE`、`workflow_settings.STAGE_CONFIG_STAGES`、`ui/desktop_page_registry.NAV_STAGE_ICONS`）属「工作流流程名」命名空间（writing/frames/video_prompt…），不是阶段路径别名，超出本轮两文件边界，记录不改。

## 实现

- `contract/stage_layout.py`：新增 `STAGE_ALIASES`（`structure→script_structure`、`frames→keyframe`、`editing→edit`，注释注明与 `LEGACY_STAGE_ALIASES` 的分域）与 `canonical_stage_id(stage)`——阶段键（含历史拼写）→ 规范阶段 id，认不出返回 `None`；规范 id 成员判定直接遍历 `STAGES` 第 2 列，不另抄清单。
- `contract/stage_path_service.py`：删除 `_STAGES` 硬编码 16 条表；`write_dir()`／`legacy_read_dirs()`／`read_dirs()` 改经 `stage_layout.canonical_stage_id()` 解析；`_LEGACY` 按规范 id 重键（去掉 `'structure'` 重复键，`'script_structure'` 键保留同一目录元组）；`LEGACY_NUMBERED`、`LEGACY_READ_UNTIL`、`existing_dir()`、`read_file()`、共享参考图函数均未动。
- `tests/test_stage_path_service.py`：新增 `test_stage_aliases_resolve_like_canonical_ids`——`STAGE_ALIASES` 值必须 ∈ `STAGES` 第 2 列；三个别名经 `write_dir`/`read_dirs`/`legacy_read_dirs` 与规范 id 结果全等；`canonical_stage_id` 对别名/规范 id/未知值/目录名（`00_script` 不进入阶段键口径）的判定。

## 行为等价证据

- 临时核验脚本（未入库）：旧 `_STAGES` 字面量 vs 新 `canonical_stage_id`，对 38 个输入（全部 16 个旧键、13 个规范 id、旧目录名 `00_script`/`01剧本准备`/`02剧本结构`/`13质检交付`、`writing`/`episode`/`unknown`/空串/`None`/`0`/带空格 `' script '`）逐一比对解析结果——**全部一致**；`_LEGACY` 与 `LEGACY_NUMBERED` 查表路径按输入逐一枚举等价（`structure`→`script_structure` 命中同一 `('writing/结构剧本',)`，`frames`/`editing` 的旧英文目录本就为空）。
- 决策点数不变：`stage_layout.py` 34、`stage_path_service.py` 9（`scripts/branch_coverage_report._decision_points` AST 实测），`分支覆盖率基线.json` 无需重测重写。

## 验证证据

- **定向**：`run_selftests.py -k stage_layout stage_path project_stages` → 28 条用例 0 红（test_stage_layout 20、test_stage_path_service 4、architecture.test_stage_paths 3、test_project_stages 1）。
- **受影响冒烟**：`smoke_test.py --affected stage_layout stage_path_service` → 10/10 通过；门禁段自动圈定 31 个测试模块（全部直接 import 两契约的测试＋模块名匹配），624 秒隐藏桌面 0 红。
- **默认冒烟**：9/9 通过。
- **架构门禁**：532 条、failures=1（`test_round_number_continuous`，`project_status.md` 停在 3234、状态页仅 master 可提交的既有欠账）；改前基线同为 532 条同一失败集合——**零新增红**，覆盖率下限（stage_layout≥70%、stage_path_service≥66%）与决策点基线（34/9）均通过。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（本工作树 HEAD `df324d65`，未含本轮 diff） | 532 条，failures=1：`test_round_number_continuous` |
| 改后 | 532 条，failures=1：同一用例（期望值随最新结果文件递增，本文件落盘领号 R3338 后口径同前）——**失败集合不变，零新增红** |

## 备注

- **范围**：本轮提交只含 2 个契约模块＋1 个测试文件＋本结果文件（证据 JSON 由提交门禁生成）。`project_status.md` 未动（仅 master 可提交）；未跟踪的 `tasks_round/地基加固_跨车道交接单档.md` 未 add。
- **保留的防御分支**：`write_dir()` 的 `folder is None → '阶段目录契约缺少'` 分支在新口径下理论不可达（`canonical_stage_id` 已以 `STAGES` 第 2 列为成员判据），按最小改动保留原错误契约未删。
- **范围外观察（记录不改）**：`script_manifest_schema.py:20-26` 的 `STAGE`/`STRUCTURE_STAGE`/`STORYBOARD_STAGE` 目录名字面量、`stage_path_service._LEGACY`/`LEGACY_NUMBERED` 旧目录表，属 R3230 §2.3 另两行「阶段中文名／manifest→阶段归属」重复，任务书未排入 6D，留待后续轮次评估。
- **欠账**：无新增。历史欠账（工作树状态页抬头滞后、后台全量自检凭据）维持原状记录。
- **未运行**：`--all --safe` 全量（分支轮不累计；合入轮出口 CI 另行核验）。
