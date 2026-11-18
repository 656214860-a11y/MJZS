# R3304 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 5B（D6＋D8 功能轮：失败契约接线）
<!-- round-evidence: {"commit_base": "85e32355", "credential_hits": 0, "evidence_sha256": "df768f033d9d9cf8", "exit": 0, "failed": 0, "passed": 144, "round": 3304, "tests": "run_selftests.py -k error_codes pet_agent pet_retry_anim_edges state_transition"} -->

## 三问

1. **本轮类型**：功能轮（§3.1／任务书轮 5B）——`pet_agent.retry_plan` 的「是否重试」接 L0 `error_codes.retryable` 唯一权威，`ui.pet_agent_rules` 删 `PATTERNS`、`VERDICTS` 瘦身为 `(action, hint)`；`self.errors` 接可见出口（状态栏角标＋一次性 `【警告】`）。未动 `docs/stages/` 任何 REQ/DES——宠物重试分类与内部错误出口是跨阶段的 agent／UI 接缝，不属于已建阶段文档面（同 R3002 等宠物轮先例）。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k error_codes pet_agent` 107 条全绿；`smoke_test.py --affected pet_agent pet_agent_rules` 10/10 绿（内含 16 个定向测试模块全过）；默认 `smoke_test.py` 9/9 绿；`smoke_test.py --architecture` 502 条 failures=1（`test_round_number_continuous`，`project_status.md` 陈旧的既有欠账，改前改后同一失败集合，见 §架构门禁对比基线）。
3. **欠账少了吗**：少了。重试判定不再有第二份布尔（`PATTERNS` 删除、`VERDICTS` 去 retry 位、`pet_agent._mark_hit` 随旧分类器一并移除）；`self.errors`／`Agent.errors` 两份 ErrorLog 从此有用户可见出口，不再只进内存；对照表 8 行每行一条断言钉死。

## 前置核对

- 领号：`round_claim.py next` → **R3304**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`，commit_base `85e32355`＝R3300）。
- 任务书 D6-d／D6-e／D6-f／D8-a 四条全部执行；§9「明确不做」未触碰：重试次数与退避配置一字未动（`MAX_ATTEMPTS`／`pet_llm.RETRY_DELAYS`／`stage_parallel.retry_attempts` 原样），编排器 `self.errors` 绑定范围未扩大（只扫宠物与父 Agent 两份 ErrorLog）。
- 「先红后绿」：新测试 `tests/test_pet_agent_error_wiring.py` 先落盘首跑 **10 条全红**（`AttributeError: 'Pet' object has no attribute 'sync_errors'`＋`VERDICTS` 三元组解包失败），实现后转绿；既有测试同步更新处逐条注明契约变化（见 §测试契约变更）。

## 实现

### D6-d／D6-e：重试判定唯一权威

- **`pet_agent.py`**：`classify(error, status)` 改为 `error_codes.classify(error, status)` 取码，再按 `_CODE_TO_CATEGORY`（`TEXT_RULES` 码→原 PATTERNS 类目反查表＋`E-UNKNOWN→unknown`）翻回 VERDICTS 类目；`verdict()` 加 `retryable` 形参，`plan['retry']` 一律取码的 `retryable`，VERDICTS 只出 `(action, hint)`。`retry_plan` 逻辑零改动——`allow`／`next_attempt`／`delay`／`max_attempts`／`fix_params` 分支原样，`params` 归一动作保留为「动作驱动的预留路径」（当前码表下没有「可重试＋fix_params」组合，生产唯一调用方 `pet_ui_stages.py:55` 也不传 `params`）。删 `PATTERNS` 导入与 `_mark_hit`（口径已在 L0 `error_codes._mark_hit`）。
- **`ui/pet_agent_rules.py`**：`PATTERNS` 整表删除（关键词唯一权威在 L0 `TEXT_RULES`）；`VERDICTS` 每项由 `(retry, action, hint)` 瘦身为 `(action, hint)`，**动作名与提示文案逐字保留**（含 params 行「先归一尺寸/时长/模型名，再立即重试一次」——按 D6-e 原样保留，语义上已是给用户的手动建议，见 §欠账 2）。

### D8-a：`self.errors` 可见出口

- **`ui/pet_ui.py`** 新增 `Pet.sync_errors(at=None)`，由 `pump()` 每拍心跳调用（`announce_failures()` 之后）：
  - 扫描宠物 `self.errors` 与父 Agent `agent.errors` 两份 `ErrorLog`（emit_safe 失败、界面动作异常、journal/gate/parallel 写失败原先只进内存）；
  - **角标**：状态栏左区常驻段 `pet_errors` 显示「异常 N」（`desktop.set_status_segment`，tooltip 注明明细去向）；清零时 `status_bar.clear_segment` 摘除；文案没变不重写 Tk；
  - **一次性警告**：每条新错误经 `status_bus.publish(Message.make('warning', '【警告】三虎内部错误：<名>：<文>…', source='pet'))` 播报一次，前缀 `【警告】` 合法；同一 `(名字, 归一化原文)` 判重键只播第一次，`_errors_seen` FIFO 封顶 512；
  - 宿主缺状态栏三件套（假宿主／自检／单测）时静默降级——记账照旧、只是不显示；角标写失败走 `app_logging.swallowed()` 留痕（架构棘轮要求），不新增静默 except。

## 对照表逐行断言（D6-f）

`tests/test_pet_agent_error_wiring.py::RetryAuthorityTests` 的 `ROWS` 即 R3300 §D6-0 对照表 8 行，每行一条断言链：`error_codes.classify` 期望码＋`retryable` → `pet_agent.classify` 期望类目＋`retry` → `retry_plan(0,…)['allow']`：

| 类目 | 码 | retryable | 断言位置 |
| --- | --- | --- | --- |
| auth | E-AUTH-REJECTED | False | `test_each_comparison_row_agrees_with_error_codes` subTest |
| quota | E-QUOTA-EXCEEDED | False | 同上 |
| content | E-CONTENT-POLICY | False | 同上 |
| params | E-NET-CLIENT | **False（唯一行为变化）** | 同上＋`test_retryable_rows_back_off_and_non_retryable_rows_stop` |
| rate_limit | E-NET-RATE-LIMIT | True | 同上 |
| timeout | E-NET-TIMEOUT | True | 同上 |
| server | E-NET-SERVER | True | 同上 |
| unknown | E-UNKNOWN | False（D6-b 现行行为保留） | 同上 |

另有 `test_verdicts_carry_only_action_and_hint`（VERDICTS 全表等值断言为二元组）、`test_patterns_table_is_gone_classification_lives_in_l0`（PATTERNS 双侧不存在＋TEXT_RULES 类目序）。`ErrorsOutletTests` 6 条覆盖角标计数／清零摘除／一次性警告／同文去重／Agent.errors 同扫／缺状态栏降级／pump 驱动。

## 测试契约变更（AGENTS §2.4 如实记录）

- `test_pet_agent.py`：`test_only_three_categories_may_retry` 改从 `error_codes.TEXT_RULES` 码表派生可重试集合（断言 `{E-NET-RATE-LIMIT, E-NET-SERVER, E-NET-TIMEOUT}`），params/content 断言翻 False；`test_params_error_retries_at_once_with_fixed_params` → `test_params_error_no_longer_retries_automatically`（断言 allow=False、action 仍 `fix_params`）。
- `test_pet_retry_anim_edges.py`：两条 params 用例改断言不重试（`next_attempt` 不前进、无 `params` 键）。
- `test_state_transition_tables.py`：`PROBES` 改从 `error_codes.TEXT_RULES` 派生，`VERDICTS` 解包改二元组，`retry` 期望值改查 `error_codes.classify(probe).retryable`——判定表与转移表仍逐行一致，终态断言覆盖 params 新增终态。
- `test_error_codes.py`：`test_text_rules_mirror_patterns_order_categories_and_marks` 改为 `test_text_rules_categories_have_verdicts_and_registered_codes`（PATTERNS 已删，保真断言改验「每类目有 VERDICTS 兜底＋每码在 CODES 登记＋类目顺序不变」）。

## 测试证据

- **先红**：`tests/test_pet_agent_error_wiring.py` 首跑 10 条全红（缺 `sync_errors`／旧 VERDICTS 形状）；既有测试在实现前亦因三元组解包红。
- 命令与结果：
  - `run_selftests.py -k error_codes pet_agent` → **107 条全绿**（任务书定向口径）。
  - `run_selftests.py -k pet_agent_error_wiring error_codes pet_agent state_transition` → **119 条全绿**。
  - `run_selftests.py -k pet_retry_anim_edges pet_ui …` → **637 条全绿**（pet_ui 600+ 含真 Tk 隐藏桌面；`invalid command name …run` 为 Tk after 脚本收尾噪音，非用例红）。
  - `smoke_test.py --affected pet_agent pet_agent_rules` → **10/10 绿**（门禁段 16 个定向模块 152 秒全过）。
  - `smoke_test.py` → **9/9 绿**。
  - `smoke_test.py --architecture` → **502 条，failures=1**（见下节）。
  - 复跑 `run_selftests.py -k pet_ui`（角标缓存收尾后终态复核）：**612 条全绿**（隐藏桌面日志 `logs/hidden_selftest.log` 末行 `ALL TESTS PASSED`；外层 `run_selftests` 回显日志时 GBK 控制台遇 `\ufffd` 报 `UnicodeEncodeError` 退出码 1，属回显伪影，测试本体全过）。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（R3300 基线，本工作树未含本轮 diff） | 502 条，failures=1：`test_round_number_continuous`（`project_status.md` 停在 3234，状态页仅 master 可提交，工作树固有欠账） |
| 改后 | 502 条，failures=1：同一用例 `test_round_number_continuous`（`3234 != 3301`，因最新结果文件为 R3300；本文件落盘后预期变 `!= 3305`）——**失败集合不变，零新增红** |

过程插曲（如实记录）：首次 `--architecture` 误加 `-X utf8` 启动，父进程按 UTF-8 解码而覆盖率工具子进程（无 `-X utf8`）末行中文按 GBK 输出，reader 线程 `UnicodeDecodeError` → `test_branch_coverage_floor`／`test_coverage_baseline` 两条 ERROR；用任务书原命令 `python -B`（不加 `-X utf8`）复跑即全绿，确认为调用方式伪影而非代码问题；同轮新暴露的 `test_no_new_silent_exception_handlers` 红（新增 `except: pass`×2）已改 `app_logging.swallowed()` 修复并复验。

## 欠账与处置

1. **`test_round_number_continuous` 红**：`project_status.md` 停在 3234，工作树分支无法提交状态页——沿用 R3267/R3280/R3286/R3298/R3300 同口径既有欠账，合入轮由 master 侧同步解决。
2. **params 的 VERDICTS 提示文案**：`「…再立即重试一次」`按 D6-e 逐字保留；自动重试已关，该句现读作给用户的手动建议（先归一再用「重试失败项」）。若要改文案属用户可见复制变更，留待后续文案轮，不在本轮擅改。
3. **全量绿凭据**：`auto_full_safe.py --status` 显示欠账 False、无后台在跑；common-dir `full-safe-receipts.json` 无本树绿凭据（工作树净树＋状态页滞后使 `--all --safe` 绿凭据结构性不可得，同 R3300 `[NO_RECEIPT]` 口径）；上次后台全量（master HEAD `00e3938`，2026-11-18 03:47）红在 18 个无关模块，与本 diff 零交集，如实记录不冒充。
4. **D6-c 死码 12 个**：仍全部保留，删除待用户确认（R3300 欠账延续）。
5. **`self.errors` 出口范围**：本轮只接宠物与父 Agent 两份 ErrorLog；`orchestrator/skill_orchestrator.py` 的 `self.errors` 按任务书「不扩大编排器错误绑定范围」未动，若日后要把编排器错误也上屏需另行授权。

## 提交

- 提交信息：`R3304: …`（见 git log）；暂存范围仅 `程序/` 下本轮 8 个文件（5 改 3 测试含 1 新），`project_status.md` 未动。
