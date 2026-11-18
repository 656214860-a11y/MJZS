# R3343 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 7A（D9 静默放行——契约轮）
<!-- round-evidence: {"commit_base": "a25edab1", "credential_hits": 0, "evidence_sha256": "593174911f2cab60", "exit": 0, "failed": 0, "passed": 73, "round": 3343, "tests": "run_selftests.py -k asset_contract assets_scope confirm_gates"} -->

## 三问

1. **本轮类型**：§3.4 契约轮——L0 契约层防崩溃与协议补齐任务书「轮 7A：静默放行」。只动 `contract/asset_contract.py`（＋ `tests/test_asset_contract.py` 新用例），符合契约轮边界（只动五个契约模块之一、不动 L1 以上）。
2. **测试跑了吗、三个基线过了吗**：跑了。先红后绿：新用例改动前 `AssertionError: 0 != 1`（认不出类别返回空列表），改动后 27 条全绿；定向 `run_selftests.py -k asset_contract assets_scope confirm_gates asset_detail` 121 条 0 红；默认冒烟 9/9；`smoke_test.py --architecture` 532 条、唯一红 `test_round_number_continuous`（3234 != 3339，状态页滞后既有欠账，改前改后同一失败集合）；契约轮全量 `run_selftests.py --all --safe --allow-dirty-diagnostic` 实跑 8845 条／838.6 秒，10 个文件有红、逐条归因均与本改动无关（详见 §验证证据），`[NO_RECEIPT]` 仅诊断不记账（脏树口径同前轮）。
3. **欠账少了吗**：少了——R3230 §2.4「校验函数会静默放行」中 `asset_contract.validate` 认不出类别即放行一项已闭环：编号拼错、类别字段缺失现在各返回一条问题，不再以空列表冒充通过。新增欠账：无（边界观察见 §备注）。

## 任务与决策来源

- 任务书轮 7A（`L0契约层防崩溃与协议补齐任务书.md:681-690`）：D9-a `asset_contract.py` 认不出类别时返回一条问题、不再返回空列表（R3230 §2.4），先查全部调用方对「空列表＝通过」的依赖；D9-b 先红后绿：类别字段缺失、编号拼错各一条。验收：跑全量。
- 诊断出处：`tasks_round_3230_result.md` §2.4（`:114`）——`asset_contract.py` `if not kind: return problems`，`problems` 为空列表即视为通过，编号拼错、类别字段缺失都算合规。
- 领号：`round_claim.py next` → **R3343**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`）。

## 「空列表＝通过」调用方核查（D9-a 前置）

`asset_contract.validate(asset, aid)` 全仓调用面（生产＋测试，grep `asset_contract`／`validate` 双向核对）：

| 调用方 | 位置 | 对「空列表＝通过」的依赖 |
| --- | --- | --- |
| `domain/confirm_gates._validate_asset` | `domain/confirm_gates.py:200-202`，被 `check_fields`（G-01 字段完整性，客观门禁）逐条调用，问题串拼进 `run('G-01')['problems']`，`passed = not problems` | **唯一生产消费链**。G-01 是登记在 `GATES` 表的客观门禁，但当前生产代码只对主观门禁 G-05/G-06/G-08 调 `run()`（`stage_execution_service.run_stage_confirmation_gate` 的调用点：`ui/desktop_automation_tick.py:268`、`ui/desktop_media_pages.py:283`；`ui/asset_detail.py:262` 只跑 G-05/G-06）——**G-01 在生产路径上暂无自动调用点**，`summary()`/`passed()`/`run('G-01')` 目前只有测试在用 |
| 测试 | `tests/test_asset_contract.py`（ValidateTests）、`tests/test_assets_scope.py:48-57` | 全部传合法编号（CHAR_/LOC_/PROP_），不断言「认不出类别返回空」 |
| SKILL `asset.validate` 工具 | `ui/skill_tools.py:672` | 只是 `PAGES` 页跳登记（`ToolNeedsPage`），不调契约函数 |
| 其余 `asset_contract` 消费方 | `prompt_templates`（锚点/职责）、`script_manifest_contract`（KINDS）、`script_manifest_schema`（HINTS/字段化）、`continuity_ledger`（merged_anchor）、`asset_plan`（normalize/state_variants）、`asset_detail*`（cells/card_lines 等）、`resolve_aspect_ratio` 各调用点 | 均不调 `validate` |

**结论**：依赖「空列表＝通过」的只有 G-01 `check_fields` 一条链，且 G-01 当前无生产自动调用点；测试侧无任何用例依赖「认不出类别放行」。改动爆炸半径＝G-01 显式运行时多报一条问题＋直接调 `validate` 的调用方。

## 级别自决（D9-a 授权内）

任务书授权：旧项目里确有无类别资产属合法旧数据 → 定 warn/diagnostic；会误伤合法数据 → 保留放行并记录。查证结论：**无类别资产不是合法旧数据，定为问题级（进 problems 列表）**，理由：

1. **契约本就要求资产条目以 `(CHAR|LOC|PROP)_\d{3,}` 编号为键**：`domain/asset_plan._sync_plan` 对清单 `assets.json` 顶层键逐条 `re.fullmatch` 校验、不合规直接 `ValueError`（`asset_plan.py:92-94`）；`missing_ids`（G-04）同样只认该模式（`asset_contract.py:415`）；`import_asset_image` 强制 fullmatch（`asset_batch_service.py`）；`schema()` 的 `patternProperties` 也只覆盖三类编号。演示数据、全部测试、`docs/stages/S05_资产管理.md` REQ-S05-14 均按此口径。
2. **类别判定有两级来源**：`kind_of(aid)`（编号前缀 CHAR_/LOC_/PROP_）或资产自带 `character_id`/`scene_id`/`prop_id` 字段。两级都指不出 ⇒ 该条目违反资产清单契约本身，正是 R3230 §2.4 点名的「编号拼错、类别字段缺失」缺陷数据，不是历史合法形态。
3. **不会误伤合法数据**：合法资产必然命中两级来源之一；`kind_of` 前缀口径（`CHAR_` 即认，不要求数字位）未动，`CHAR_x` 这类「前缀像编号」的条目仍按 character 校验、行为不变。L0 契约层不能反向 import `infra.diagnostic_capture`（分层硬约束 11），`validate` 也没有 warn 通道——返回问题串是该函数唯一表达「不合规」的方式；G-01 的拒收动作本来就是「打回上一阶段补齐」，与畸形数据匹配。
4. **真实路径几乎触达不到**：喂给门禁的 `assets` 来自 `asset_requirements()`→`sync_asset_plan`（键已被 `_sync_plan` 强校验）或旧编号目录 `04资产管理` 的直读同一格式文件；畸形键在同步期就会让整个清单读不出来（返回 `{}`），轮不到 `validate` 逐条判。

## 实现（`contract/asset_contract.py`，唯一改动）

- `validate()`：`kind` 为空时由 `return problems`（恒为空列表＝静默放行）改为返回一条问题：
  `'认不出资产类别：<aid>（编号要 CHAR_/LOC_/PROP_ 开头，或资产里带 character_id／scene_id／prop_id）'`；`aid` 为空白时显示 `（空编号）`。
- docstring 补记该规则与 R3230 §2.4 出处。未动 `kind_of`／`normalize`／`missing_ids`／`schema` 及任何其他函数；`normalize` 的类别识别口径（aid 前缀＋`state_variants` 兜底）与 `validate` 的（aid 前缀＋`*_id` 字段）本就不同，本轮不对齐（见 §备注边界观察）。

## 先红后绿证据（D9-b）

新用例 `test_an_unrecognized_category_is_a_problem_not_a_silent_pass`（`tests/test_asset_contract.py` ValidateTests）：

- **类别字段缺失**：`ac.validate({"name": "无类别"}, "")` → 须恰好 1 条问题；
- **编号拼错**：`"CHRA_001"`／`"CHAR-001"`／`"SH001"` 三种拼错各恰好 1 条且含「类别」；
- ***_id 兜底**：`{"character_id": "CHAR_009", "locked": True}` 配杂项键 → 走角色规则（报 character_anchor／canonical_board），不报「类别」；
- **合法类别不变**：`PROP_001` 合法资产仍返回 `[]`。

改动前（红）实测输出：

```
FAIL: test_an_unrecognized_category_is_a_problem_not_a_silent_pass
AssertionError: 0 != 1        # ac.validate({"name": "无类别"}, "") 返回 []（静默放行）
Ran 27 tests in 0.008s — FAILED (failures=1)
```

改动后（绿）：`Ran 27 tests — OK`。

## 验证证据

- **定向**：`run_selftests.py -k asset_contract assets_scope confirm_gates asset_detail` → 8 个测试文件／13 路工作单元，**121 条用例 0 红**（test_asset_contract×2、test_assets_scope、test_confirm_gates×3、test_confirm_gates_cache、test_asset_detail×3、test_asset_detail_service、两个 architecture 边界用例；Tk 段经隐藏桌面，跨树 GUI 令牌排队约 10 分钟后跑完，699.1 秒）。
- **默认冒烟**：`smoke_test.py` → **9/9 通过**。
- **架构门禁**：`smoke_test.py --architecture` → **532 条，failures=1**：`test_round_number_continuous`（`3234 != 3339`——`project_status.md` 停在 3234、仅 master 可提交的既有治理欠账；本结果文件落盘后期望值顺延为 3344，失败集合不变）。分支覆盖率棘轮：`asset_contract.py` AST 决策点实测 **66，与基线一致**（新分支为 `or` 表达式与既有 `if` 换体，AST 口径不增点）；覆盖率下限 83.0% 不受影响（新分支有用例覆盖）。复杂度/模块规模棘轮：validate 约 64 行、模块约 483 行，远低于上限。
- **契约轮全量**：`run_selftests.py --all --safe --allow-dirty-diagnostic` → **共 8845 条用例，838.6 秒，10 个文件有红**，`[NO_RECEIPT]` 仅诊断不写绿凭据（工作树含未提交改动，脏树口径同 R3300 等前轮；`full-safe-receipts.json` 最近绿凭据停在 2026-10-03/R3293，净树绿凭据结构性不可得，如实记录不冒充）。实际跳过 5 条用例（登记位不等于已跳过）。
  - 排队经过：首次提交被「后台自动全量正在运行」闸拒——主仓 CI 工作树（`.wt/ci`，HEAD `9e3d1924b0`）`auto_full_safe.py` 13:00:33 起持锁跑完全量（18.5 分钟后退出码 1，该树自身红项与本改动无关）；其后跨树 `full-safe-selftest.lock` 又被另一树 R3327 的全量（PID 50988，13:19–13:36）持有，等锁释放后本树 13:36 起跑、13:51 结束。
  - **红项归因（10 个文件逐条核对，零条触及 asset_contract）**：
    | 红文件 | 红数 | 归因 |
    | --- | --- | --- |
    | `architecture.test_round_baselines` | 1 | `test_round_number_continuous` 状态页滞后既有欠账（同 --architecture 单跑） |
    | `test_line_endings` | 1 | `desktop.py` 换行符：HEAD 提交态即纯 LF（0 CRLF／970 LF，工作区与 HEAD 一致），测试登记表期望 CRLF——分支既有现场，与本改动文件无关 |
    | `test_api_cache_usage` | 1 | 与 CI 树并发全量同红数（1）——共享环境/基线因 |
    | `test_model_gateway_robustness` | 2 | 同上（2），报 `URLError: network suppressed` 网络抑制环境 |
    | `test_secret_status_diagnostics` | 1 | 同上（1） |
    | `test_model_pool_redirects` | 34 | 同上（34）；R3309 已记「轮 5 传输收敛的测试接缝不兼容（model_pool_redirects 等）」为已知欠账 |
    | `test_shared_adapter_infrastructure` | 1 | 同上（1） |
    | `test_core#7` | 1 | `Desktop object has no attribute 'win'` Tk 生命周期环境问题（同上 1）；该文件的 `validate` 是 `writing.validate_episode`，与 asset_contract 无关 |
    | `test_latent_defects_r2175` | 8 | 同上（8），mock urlopen 未触发类环境红 |
    | `test_ui_motion_perf#1` | 1 | `test_motion_is_monotonic_ease_out_and_ends_idle` 帧数计时 flaky（全量负载下恰好 2 帧）；**单独复跑 `-k ui_motion_perf` 27/27 全绿** |
  - **非因性证据**：上述 7 个文件（除 line_endings/ui_motion_perf/round_baselines 外）在不含本改动的 CI 工作树并发全量中红数逐一相同（1/2/1/34/1/1/8）；本改动只加一条「认不出类别」问题串，唯一生产消费链 G-01 由定向 121 条全绿覆盖。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（本工作树 HEAD `a25edab1`，未含本轮 diff；上轮 R3338 同机实测口径） | 532 条，failures=1：`test_round_number_continuous` |
| 改后 | 532 条，failures=1：同一用例（期望值随最新结果文件递增）——**失败集合不变，零新增红** |

## 备注

- **范围**：本轮提交只含 `contract/asset_contract.py`＋`tests/test_asset_contract.py`＋本结果文件（证据 JSON 由提交门禁生成）。`project_status.md` 未动（仅 master 可提交）；未跟踪的 `tasks_round/地基加固_跨车道交接单档.md` 未 add。
- **边界观察（记录不改，超出本轮范围）**：① `validate` 的类别识别用 `*_id` 字段兜底，`normalize` 用 `state_variants` 键兜底——两口径本就不同；aid 无法识别但 `*_id` 能识别时，`normalize` 不补默认值，`validate` 会按原始字段判（可能多报字段问题）。真实清单键必为合法编号，触发面仅限畸形键＋`*_id` 兜底的边角，未对齐。② `kind_of` 只认 `CHAR_/LOC_/PROP_` 前缀不要求数字位（`CHAR_01`、`CHAR_x` 仍按 character 校验）；编号全形态 `\d{3,}` 由 `_sync_plan`/`missing_ids`/`import_asset_image` 把关，`validate` 本身不查编号形态——「编号拼错」的验收按「类别认不出」口径覆盖（CHRA_/CHAR-/SH001 等），前缀像编号的畸形编号仍归对应类别校验，未扩 scope。③ `docs/stages/S05_资产管理.md` REQ-S05-14 校验规则清单未写「认不出类别」一条，属阶段文档口径，任务书本轮边界只许动 `contract/asset_contract.py`，记录待后续文档轮同步。
- **凭据状态**：工作树含未提交改动，全量以 `--allow-dirty-diagnostic` 运行＝真实执行但不记账（`[NO_RECEIPT]`），与 R3300 等前轮同口径；净树绿凭据结构性不可得（状态页滞后＋脏树），如实记录不冒充。
- **任务书验收对照**：D9-a ✅ 认不出类别返回一条问题（调用方核查＋级别自决如上）；D9-b ✅ 先红后绿两条用例；跑全量 ✅（结果见上节，红项全部归因非本改动）。

## 遗留欠账

- 无新增。本任务书 §9「明确不做」各项（recoverable 消费、schema() 生成器、queue.put 锁外、前缀校验路径、重试次数、except:pass 治理、errors 无界、自动采用启动闸测试、write_dir 项目根校验、配置版本迁移、requests Session 策略）均未触碰，状态同任务书登记。
- 任务书整体收尾（全部轮次完成后的《任务完成文件》）不属于本轮，待 7B 及后续轮次结束时统一输出。

## 提交

- 以 `dev.py commit -m "R3343: …" --tests asset_contract assets_scope confirm_gates` 提交本结果文件所列三处改动；证据 JSON `tasks_round/evidence/R3343.json` 由提交门禁生成并盖章（commit_base 为提交前 HEAD，commit hash 见 `git log`）。
</content>
</invoke>
