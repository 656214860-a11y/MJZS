# R3246 结果：L0 契约层任务书轮 1 — D0＋D1 修复轮（writing.py 路径＋message_parts 登记）
<!-- round-evidence: {"commit_base": "fe13482e", "credential_hits": 0, "evidence_sha256": "0d43876f21e64220", "exit": 0, "failed": 0, "passed": 25, "round": 3246, "tests": "run_selftests.py -k storyboard_contract layers"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（任务书轮 1：D0＋D1），只改根因所在模块。
2. **测试跑了吗、三个基线过了吗？**
   - 定向自检：`run_selftests.py -k storyboard_contract layers` → 25 条全绿（新增 `test_storyboard_contract` 3/3 先红后绿、`architecture.test_layers` 6/6、`test_model_probe_layers` 16/16）；补跑 `service_return_contract`／`project_context_boundary` 共 54 条全绿。
   - 默认冒烟：`smoke_test.py` → 通过 9 项／失败 0（当轮实际为 9 项，任务书口径「8/8」已过时，如实记录）。
   - 架构门禁：`smoke_test.py --architecture` → 488 条，failures=2／errors=3；失败集合与改前（stash 回 R3239 基线逐文件复测）完全一致，均为环境性既有欠账，本改动零新增违规（对比见 §4）。
   - 全量凭据：未运行。修复轮未触发全量条件；层级登记表改动按任务书约定「合入 master 前触发当次全量」，留待合入轮执行。
3. **欠账少了吗？** 少了 2 条：D1（契约文本指向不存在的 `contract/writing.py`）与 D0（`domain/message_parts` 未登记）闭环。D2–D8、§9.2 增补项（D9–D11、D7 增补）仍在后续轮次。

---

## 1. 改动清单

| 文件 | 改动 |
| --- | --- |
| `程序/contract/storyboard_contract.py` | `rules()` 的 `validator` 由 `with_name('writing.py')`（解析到不存在的 `程序/contract/writing.py`）改为 `parents[1]/'writing.py'`（`程序/writing.py` 顶层门面，实测存在）；校验指令段抽为 `validation` 变量，仅当 `validator.is_file()` 时拼接，路径缺失时 `rules()` 不再输出「使用 JSON 序列化器…validate_episode…」指令；import 行 `from storyboard_paths import media_root` 改为 `from contract.storyboard_paths import media_root`（见 §3 小决策）。 |
| `程序/tests/architecture/_layers.py` | 新增 `_register(2, "message_parts")`（扁平登记名，对应实体 `domain/message_parts.py`；登记前已核实其只 import 标准库，消费者 `idea_transcript`(L2)／`idea_chat_controller`(L3)／`ui_*`(L4) 均不低于 L2，无新增越层）。 |
| `程序/维护记录/架构统一基数.json` | 「第一项」台账同步：`message_parts` 入 `exempt_items`（纯数据契约、不走 ServiceResult，与 `idea_*` 纯模块同口径），`exempt_count` 48→49；同时入 `historical_name_audit_pending`（该门禁按「无顶层 `name.py` 即旧逻辑名」机械口径，domain 包实体无门面者一律挂此名单，25→26）。 |
| `程序/tests/test_storyboard_contract.py` | 新建，3 条用例（先红后绿，见 §2）。 |

## 2. 验证输出摘要

**先红**：`run_selftests.py -k storyboard_contract`（改动前）→ 3 条全红：

- `test_rules_point_at_a_directory_that_really_has_writing_py`：提示词给出的目录为 `…\程序\contract`，其下无 `writing.py`；
- `test_validation_imports_resolve_from_the_emitted_directory`：子进程（cwd 刻意离开 `程序/`，只按提示词给的目录导入）报 `ModuleNotFoundError: No module named 'writing'`——即诊断预言的「模型照做会 import 失败」；
- `test_validation_block_is_omitted_when_writing_py_is_missing`：`Path.is_file` 对 `writing.py` 返 False 时校验指令段仍输出。

**后绿**：同命令加 `layers` → 25 条全绿；`smoke_test.py` → 9/9；`smoke_test.py --architecture` → 488 条中 failures=2／errors=3（全部既有，见 §4）。

新测试断言行为而非源码：解析 `rules()` 文本中「将 <目录> 加入 Python 模块搜索路径」的目录并断言其下 `writing.py` 存在、且等于 `程序/` 根；子进程真实执行提示词给出的 import 语句；`is_file` 返 False 分支断言校验指令段整体缺席。

## 3. 小决策（任务书未覆盖处，按最简方案处理）

- **import 行同步修正**：D1-b 只点名「sys.path 目录」，但同段 `from storyboard_paths import media_root` 在 `程序/` 上 sys.path 下同样不可导入（T10 后 `storyboard_paths` 实体在 `contract/` 包内、顶层无门面；已用子进程实测 `ModuleNotFoundError`）。改为 `from contract.storyboard_paths import media_root`，与全仓 20+ 处生产 import 口径一致；`from writing import validate_episode` 保留（`程序/writing.py` 门面 → `domain.writing` 再导出 `contract.episode_contract.validate_episode`，子进程实测可导入）。
- **覆盖率基线无需更新**：`domain/message_parts.py` 本就在 `维护记录/覆盖率基线.json`（filesystem 口径扫描，0/141），登记层级不改变该集合；分支覆盖率基线只管 L0/L1，L2 不适用；`类型检查基线.json` 为只减棘轮，不强制收新模块。
- **台账分组选择**：`message_parts` 入 `exempt_items` 而非 `scope_audit_pending`——它是无任何服务函数／零 IO 的纯数据契约，与 R1310/R1313/R1317/R2893 轮 `idea_*` 纯模块入豁免的先例同口径；`adopters` 组被 `test_only_approved_l2_adopters` 钉死为「实际 import service_contract 的 L2 集合」，本模块不导入，不能入。

## 4. 架构门禁失败集合（改前后对比）

`smoke_test.py --architecture`：488 条，failures=2／errors=3。失败集合改前（stash 本轮 3 个跟踪文件改动后逐文件复测）与改后**完全相同**，均与本改动无关：

| 用例 | 结果 | 归因（改前已复现） |
| --- | --- | --- |
| `test_agents_md…test_performance_history_is_declared_as_historical_only` | ERROR | `维护记录/基准历史.json` 被 gitignore、本工作树不存在（环境欠账） |
| `test_branch_coverage_floor…test_branch_coverage_tool_runs_on_bundled_interpreter` | ERROR | 测试自身 `subprocess.run(text=True)` 无 encoding，子进程 GBK 输出触发 UnicodeDecodeError（环境欠账） |
| `test_coverage_baseline…test_coverage_tool_runs_on_bundled_interpreter` | ERROR | 同上 |
| `test_round_baselines…test_round_number_continuous` | FAIL | `project_status.md` 当前轮次 3234 vs 最新结果 3239+1；状态页只在 master 更新，工作树分支固有滞后 |
| `test_skill_reference_injection…test_script_stages_name_only_their_approved_00_references` | FAIL | `skills/00全流程SKILL/…/screenplay-gate-engine.md` 在本工作树缺失（内容不在版本控制内） |

本改动引入的 `test_every_registered_l2_module_has_a_scope_record` 红项已通过台账登记修复（§1），复跑 9/9 绿。登记 `message_parts` 后 `test_layers`（越层扫描）、`test_migrated_ui_boundaries`（L0–L3 tkinter 扫描）、`test_coverage_audit_ratchet`（L2 config 写入扫描）均无新增违规。

## 5. 遗留欠账

- 任务书 D2–D8、§9.2 增补 D9–D11 与 D7 增补：按轮次表后续执行（轮 2 起）。
- §4 五项环境性架构门禁失败为既有欠账，建议主区择机处理（补 `基准历史.json` 实体、测试 subprocess 加 encoding、状态页同步轮、skills 内容补齐），不在本轮范围。
- 提示词中「通过校验并采用后…」一句在 `writing.py` 缺失分支仍保留（任务书只要求 :39-43 段条件输出）；若未来出现 writing.py 缺失的发布形态，可再议是否连带条件化。

## 6. 提交

- 领号：`round_claim.py next` → **R3246**（脏树自动切 `codex/wip-R3246`，改动原样带入）。
- commit：`R3246: …`（hash 见 git log；提交时 `round_evidence` 自动盖 `tasks_round/evidence/R3246.json` 并回填本文件机器头）。
