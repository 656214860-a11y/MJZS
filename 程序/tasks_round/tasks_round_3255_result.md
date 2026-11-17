# R3255 结果：框架复用评估并入任务书与诊断报告（文档轮）
<!-- round-evidence: {"commit_base": "6d7fc243", "credential_hits": 0, "evidence_sha256": "b764f85efbc7cb0b", "exit": 0, "failed": 0, "passed": 0, "round": 3255, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 文档轮（`CLAUDE.md`「文档轮、状态页同步轮不跑 smoke／selftest」的例外口径）＋ 只读调研。本轮**不新增、不修改任何产品 `.py`**，只做两件事：① 把「框架复用／不重复造轮子」评估写进 `tasks_round_3230_result.md`（§10）；② 确认任务书 §3b／§3c 已有该内容。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟：`smoke_test.py` → **9/9 通过**。
   - 架构门禁：`smoke_test.py --architecture` → 488 条，failures=4／errors=3。
   - **失败集合与本轮改动无关**，已用 stash 对照验证（见 §3）。
   - 定向：`run_selftests.py -k media_signature layers episode_contract` → 22 条全绿。
3. **欠账少了吗？** 没有减少。本轮是调研并入文档，不闭环欠账；但新增了「调研完整性」这条验收（任务书 §8）。

---

## 1. 本轮交付物

| 文件 | 改动 | 性质 |
| --- | --- | --- |
| `程序/tasks_round/tasks_round_3230_result.md` | 追加 §10「框架复用与不重复造轮子评估」（406→490 行，纯新增，未改 1–406 行任何内容） | 用户明确要求 |
| `程序/tasks_round/L0契约层防崩溃与协议补齐任务书.md` | §3c 同域应用对标（前序 R3246 后已并入）＋ §8「调研完整性」验收条 | 前轮已写，本轮确认 |

**未改动**：任何 `.py`、任何测试、任何基线 JSON。

---

## 2. §10 的内容要点

### 2.1 结论：没有可直接复用的「L0 契约层框架」

「L0 契约层」是 Clean/Hexagonal 架构里各家自行约定的概念，**不存在对应发行包**。可复用的只有局部方案与设计思想。

### 2.2 六项强烈建议复用（全部零新增依赖）

| # | 来源 | 复用内容 | 落点 |
| --- | --- | --- | --- |
| 1 | **ComfyUI** `main.py` | 失败分级三段式：固定 `kind` 闭集 + `what` + `fix` + 每条附逃生开关 | `Diagnostic` 增 `escape_hint` |
| 2 | **InvokeAI** `config_default.py` | 版本阶梯 + `.bak` 备份 + 失败回滚 + 落盘后 `assert` 版本 | `artifact_schema.migrate()` |
| 3 | **Spring Boot** `diagnostics` | `FailureAnalyzer` 派发链，诊断器异常不掩盖原错 | `error_codes.analyze()` |
| 4 | **Chromium** `gpu_process_host.cc` | 崩溃预算：5 分钟赦免窗 + 阈值 3 + 正常退出清零 | 安全模式判定 |
| 5 | **A1111** `modules/scripts.py` | 扩展隔离：每个挂载点各自 try | 13 阶段失败边界 |
| 6 | **A1111** `modules/cmd_args.py` | 开关按族命名（`skip-*` / `disable-*`） | 安全模式 GUI |

### 2.3 十三项明确不复用

`blinker`（实测无法替代 `pet_bus`：无队列、无背压、无终态保护、无异常落审计）、`pydantic-settings`（6 传递依赖 + 二进制 core）、`dependency-injector`（C 扩展 + 4920 stars 卡门槛）、`lagom`/`punq`、`import-linter`、`tach`、`pytest-archon`、`returns`/`result`、`alembic`、`dynaconf`/`hydra-core`、`healthcheck`/`py-healthcheck`、`structlog`/`loguru`、`jsonschema`。

### 2.4 两项无行业对标，如实标注须自研

| 检查项 | ComfyUI | InvokeAI | A1111 |
| --- | --- | --- | --- |
| 磁盘空间前置检查 | 零命中 | 零命中 | 零命中 |
| L0 契约层自检 | 无 | 无 | 无 |

**不得声称有对标实现。** 可借 ComfyUI 的信息格式外壳，检查逻辑原创。

### 2.5 四处明确不能照搬

1. ComfyUI 模型池为空静默返回空列表（Web 假设，Tkinter 流水线跑到第 7 阶段才失败）
2. ComfyUI 的 `sys.exit(1)` + 启动器匹配日志行（本项目 `.pyw` 直启，无中间启动器）
3. A1111 用 `str(e)` 子串匹配已崩形态（升级即失效）
4. InvokeAI 的 `scan_models_on_startup` 默认关且只登记孤儿模型（服务于测试场景）

### 2.6 工具风险如实记录

评估期间 `web_search` 持续 HTTP 401（凭据无效）。全部证据改用 `web_fetch` 直连 `raw.githubusercontent.com`；两条最关键结论（InvokeAI 的 `migrate_*`+`.bak`+`assert`、ComfyUI 的 `stop_startup`+`failure`/`fix`）另用 PowerShell 逐字复核。

---

## 3. 架构门禁失败归因（7 项，全部既有）

带轮 2 改动时的失败集合：

```
FAIL: test_whitelist_versions                      requests 2.34.2 ≠ 预期 2.32.3
FAIL: test_round_number_continuous                 状态页 3234 ≠ 最新结果 3246+1
FAIL: test_module_set_matches_l01_registry         contract/media_signature.py 未刷新基线
FAIL: test_runbook_states_the_directed_measurement_caliber
ERROR: test_performance_history_is_declared_as_historical_only
ERROR: test_branch_coverage_tool_runs_on_bundled_interpreter
ERROR: test_coverage_tool_runs_on_bundled_interpreter
```

**对照验证**：`git stash push --include-untracked` 回到 R3246 基线后重跑 → **failures=6／errors=9**，比带改动时**更多**（多出 `test_registered_names_resolve_to_a_file_tool_or_historical_entry` 等 6 项）。

**结论**：这 7 项全部是既有欠账／环境差异，**与轮 2 改动无关**；轮 2 改动反而使 `architecture.test_layers` 由红转绿（基线态该测试有失败，带改动时 6/6 通过）。

**⚠️ 操作失误如实记录**：对照验证用了 `git stash`，而本工作树当时有另一会话未提交的轮 2 改动（11 个文件）。stash 期间对方工作树短暂回到基线态。已立即 `git stash pop` 恢复，实测 16 个修改 + 2 个新增全部回来、无冲突标记，并 `git stash drop` 清理。**后续不再用 stash 做对照验证**，改用 `git worktree` 或临时副本。

---

## 4. 未运行项

- **全量 `--all --safe`**：未运行。本轮无 `.py` 改动，不触发全量条件（AGENTS §5：仅启动路径／Tk 生命周期／删除语义／层级登记表改动触发）。
- **覆盖率工具刷新**：未运行。原因见 §6 欠账 N1。

---

## 6. 移交欠账（按 Q1＝(b) 留给轮 2 执行会话）

| 编号 | 内容 | 移交理由 | 目标轮次 |
| --- | --- | --- | --- |
| **N1** | `test_module_set_matches_l01_registry` 红：`contract/media_signature.py` 未入覆盖率基线（`维护记录/覆盖率基线.json`）。实测报错 `基线模块集合与生产运行时口径不一致；新增／删除生产模块后须重跑工具刷新基线` | 基线刷新必须与「模块集合确定」绑同一轮；R3246 结果 §8 已记录「口径变更须重跑覆盖率工具」的历史教训。R3255 插手会造出「同一事实两处不同轮次」 | 轮 2 收尾（该轮执行者） |
| **N2** | `test_round_number_continuous` 红：状态页轮次 3234 ≠ 最新结果 3246+1。状态页由 master 侧同步轮维护，分支不写 | 仅 master 可提交 `project_status.md`（AGENTS §2.6） | master 同步轮 |
| **N3** | `test_whitelist_versions` 红：实测 `requests 2.34.2 ≠ 预期 2.32.3` | 属环境差异（随包解释器已装的版本高于白名单记录），非本轮代码问题；需在 whitelist 合入轮统一核对 | whitelist 合入轮 |

**未计入欠账的观察**：轮 2 的 `_layers.py` 只用了 5 条 `_register` 覆盖 10 个 `agent` 子模块，且 `prompt_optimizer` 登记为 **L4**（任务书 §2.5 建议表写的是 L2）。该轮注释给出的理由是其消费 `ui_widgets`——**属该轮执行者的层级判断，R3255 不评价、不修改**，仅在此记录供任务书后续核验。

---

## 7. 本轮结论

1. 框架复用／不重复造轮子的评估（§10）已并入 `tasks_round_3230_result.md`，纯新增 83 行，未改动前 406 行任何内容。
2. 任务书 §3b／§3c 的对应内容已在前轮写入，本轮仅确认在位。
3. 架构门禁的失败经 stash 对照验证（带改动 failures=4／errors=3，共 7 项红；基线 failures=6／errors=9，共 15 项红）确认为既有欠账；轮 2 改动反而使 `architecture.test_layers` 由红转绿、并让红项总数从 15 降到 7。
4. 操作失误（对并发会话的在途改动执行 `git stash`）已如实记录于 §3，已完整恢复并调整后续做法。
5. 三项门禁红按 Q1＝(b) 移交，本轮不越界处理。

---

## 5. 与其他会话的边界

| 项 | 归属 |
| --- | --- |
| 轮 2（`media_signature` 下沉 + `agent` 登记） | 另一会话在途（11 个文件已改、`_layers.py` 已登记、`architecture.md` 已同步） |
| 轮 2 的基线刷新与门禁转绿 | 同上，本轮不接手 |
| §10 框架复用内容 | 本轮（R3255） |
| 任务书 §3b／§3c | R3246 后已写，本轮确认 |

**未触碰**：`_d2_sim.py`（对方探针脚本）、`程序/nul`（Windows 重定向事故残留）。
