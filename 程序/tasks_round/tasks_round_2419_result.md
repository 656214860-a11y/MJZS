# R2419 结果：拆分 script_contract 的简报子系统到 script_brief（L0）

## 三个必答（§7）

- **轮次类型**：结构治理轮·执行（§3.3）——按「代码重构可优化清单」优先级一 A 项，把 `script_contract.py` 里的「剧本准备输入简报」子系统（字段分级、收敛、workflow 投影、节奏模板引用）原样迁到新 L0 模块 `script_brief.py`，`script_contract` 按原名转发，行为零变化。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k script_contract`：**58 条 0 红**（含 `test_script_contract` 与 `test_script_contract_production_locks`）。
  - 架构 `smoke_test.py --architecture`：**416 条，仅 1 红** = R2417 欠完整安全全量（后台 post-commit 自动补跑，非本轮范围）。模块/函数/复杂度尺寸棘轮、覆盖率口径、分层门禁全绿。
  - 全量：未跑（不命中 §5 强制全量条件；沙箱无法派生工作进程）。
- **project_status.md 的欠账少了吗**：无新增欠账；R2417 全量欠账由后台补跑；R2398 页签化 2 条列表测试迁移欠账仍遗留。

## 本轮内容

### 拆分：`script_contract.py` → `script_brief.py`（L0）

把 `script_contract.py` 中「剧本准备输入简报」这一内聚子系统原样迁出，形成新 L0 模块 `script_brief.py`：

- **迁出的名字**（`script_contract` 按原名转发，调用方无感）：
  - 常量：`RHYTHM_TEMPLATE_FIELD`／`RHYTHM_TEMPLATE_PATH`、`BRIEF_REQUIRED_FIELDS`、`BRIEF_RECOMMENDED_FIELDS`、`BRIEF_PRODUCTION_LOCKS_FIELD`、`BRIEF_OPTIONAL_FIELDS`、`BRIEF_REQUIREMENT_LEVELS`、`BRIEF_FIELDS`、`BRIEF_LABELS`、`WORKFLOW_PROJECTION_KEY`、`WORKFLOW_LOCK_SCHEMA`。
  - 函数：`normalize_brief`／`missing_brief_fields`／`normalize_workflow_projection`／`brief_document`。
- **留在 `script_contract` 的**：`INLINE_REQUIRED_LABELS`、`STAGE_LOCK_REQUIREMENTS`、`PRODUCTION_LOCK_DEFINITIONS`、`BRIEF_EXTRACTION_LABELS` 与全部制作锁函数（制作锁与简报是两个独立关注点，不混迁）。
- **验证**：`script_contract.brief_document is script_brief.brief_document`（转发同一函数对象）；`from script_contract import brief_document / BRIEF_REQUIRED_FIELDS` 等全部调用方不受影响。

### 同步治理台账

- `tests/architecture/_layers.py`：`script_brief` 登记为 L0。
- `tests/architecture/test_module_size_ratchet.py`：`script_contract.py` 上限 1293 → **1209**（拆分固化下降）。
- `维护记录/覆盖率基线.json`：新增顶层模块后 `modules_total` 359 → **360**（重跑 `scripts/coverage_report.py` 刷新，目标用例全通过）。
- `runbook.md` §11：覆盖率口径数字 359/301 → 360/302 同步。

## 改动文件

- `script_brief.py`（新增，L0，107 行）
- `script_contract.py`（移除简报子系统，1293 → 1209 行）
- `tests/architecture/_layers.py`、`tests/architecture/test_module_size_ratchet.py`
- `维护记录/覆盖率基线.json`、`runbook.md`

## 遗留欠账

- R2417 欠一次完整安全全量，由 post-commit 钩子后台自动补跑（见 `程序/logs/auto_full_safe.log`）。
- R2398 页签化 2 条列表测试迁移欠账（`KeyError: 'ChatGPT Desktop · Codex'`）仍遗留。
- 工作树另有一批用户并发进行中的气泡改版迭代（`desktop_idea_bubbles.py` 等 5 文件 + `bubble_bug.png`），不属于本轮，未纳入提交。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2419: 拆分 script_contract 简报子系统到 script_brief（L0）`。
