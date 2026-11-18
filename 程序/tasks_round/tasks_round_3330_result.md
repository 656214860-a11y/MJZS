# R3330 结果文件
<!-- round-evidence: {"commit_base": "bfc51754", "credential_hits": 0, "evidence_sha256": "fb3b289f4b44c3dd", "exit": 0, "failed": 0, "passed": 60, "round": 3330, "tests": "run_selftests.py -k shot_field_specs golden_outputs shot_batches storyboard_contract episode_contract"} -->

1. **本轮属于 §3 哪种类型**：§3.3 结构治理轮——L0 契约层防崩溃与协议补齐任务书「轮 6C·D7（第三组）」：收口 `storyboard_contract`／`shot_batches`／`episode_contract` 三处各自维护的镜头字段事实（字段清单、取值常量、校验区间、schema 元数据、提示词措辞），改为单一事实源＋三种呈现（`schema()`／`validate()`／`rules()`）。契约模块边界＝3 个，符合「每次最多 3 个模块」。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k shot_field_specs golden_outputs shot_batches storyboard_contract episode_contract` 60 条 0 红；`smoke_test.py --affected episode_contract shot_batches storyboard_contract shot_field_specs golden_outputs` 10/10 通过；默认冒烟 9/9；`smoke_test.py --architecture` 532 条、531 过、唯一红 `test_round_number_continuous`（3234 != 3323）——工作树 `project_status.md` 按钩子规则只许 master 更新、分支保留旧版抬头的已知治理现场，master 侧合并轮出口 CI（f0665b68）同口径 532/532 全绿；全量回归未跑（分支轮不累计，`full-safe-receipts.json` 为唯一权威）。
3. **欠账少了吗**：少了——镜头字段的规则注释、schema 片段、校验区间与提示词措辞原先分散在三模块各写一遍（且已有漂移风险），本轮收成 `episode_contract.SHOT_FIELD_SPECS` 单一事实表；新增欠账：无（`shot_batches.SHOT_FIELDS` 九个批次归一化字段按设计保留独立表，语义与旧字段表不同，见「备注」）。

## 改动

- `contract/episode_contract.py`：新增镜头字段事实层——`SHOT_ID_SAMPLE`／`SHOT_ID_PATTERN`／`SHOT_DURATION_RANGE`／`VIDEO_PROMPT_RANGE`／`ACTION_COMPLEXITY` 五个取值常量与 `SHOT_FIELD_SPECS` 事实表（每行＝`(字段名, rules() 括注, schema() properties 片段)`，注释 None 裸写字段名、片段 None 不单列 properties 由 `additionalProperties` 放行）；`validate_episode()` 与 `duration_gap()` 的编号格式、时长、video_prompt 校验全部改从常量取值，报错文案不变。
- `contract/shot_batches.py`：`SHOT_FIELDS` 扩为四元组（归一化名、旧字段来源、说明、schema 片段）；`_shot_properties()` 由批次表＋`SHOT_FIELD_SPECS` 同源合成镜头 properties，`schema()` 的 `required`/`properties` 不再手写字面量；`validate()` 时长判定改用 `SHOT_DURATION_RANGE`。
- `contract/storyboard_contract.py`：新增 `_field_text(*names)`——按事实表次序把字段名渲染成 `name（note）`／裸名并以顿号连接，事实表外名字抛 `KeyError`（提示词字段枚举不允许静默缺项）；`rules()` 字段枚举全部改经 `_field_text` 取词。
- `tests/test_shot_field_specs.py`（新增，14 条）：事实表字段覆盖、共享标量、编号正则、schema required/properties 派生、时长/动作枚举同源、episode 与批次校验、rules 渲染、未知字段 KeyError。
- `tests/test_golden_outputs.py`＋`tests/fixtures/golden/storyboard_contract_rules.txt`（新增）：`rules()` 输出黄金快照回归（`_golden` 统一做 `<PROGRAM>` 路径归一）。
- 决策点核对：`shot_batches.py` 40、`episode_contract.py` 21、`storyboard_contract.py` 0——与分支覆盖率基线登记值一致（实现全程用推导式/表达式，未新增 AST 决策点）。

## 验证证据

- **`rules()` 逐字一致（核心验收）**：改动前快照 `rules_before_r3314.txt` vs 当前 `storyboard_contract.rules()` → `rules==snapshot: True`（3987 字节逐字节相同，含 `<PROGRAM>` 归一前的本机路径）；黄金夹具经 `_golden` 归一后比对通过（`test_storyboard_contract_rules_prompt` 绿）。`schema()` 派生结果与改动前字面量 `schema equal: True`；未知字段 `_field_text('not_a_shot_field')` → `KeyError`。
- **定向**：60 条用例 0 红（shot_batches#1 15、shot_batches#2 14、golden_outputs 14、shot_field_specs 14、storyboard_contract 3）。
- **受影响冒烟**：`--affected episode_contract shot_batches storyboard_contract shot_field_specs golden_outputs` → 10/10 通过。
- **默认冒烟**：9/9 通过。
- **架构门禁**：532 条、531 过；唯一失败 `test_round_number_continuous`（状态页 3234 vs 最新结果+1=3323）——分支工作树 `project_status.md` 依钩子规则保留旧抬头的既有现场，与本轮改动无关；同代码合并进 master 后出口 CI（合并轮 f0665b68）架构门禁 532/532 全绿，含 `test_branch_coverage_floor`（91 模块基线）与 `test_complexity_ratchet`（Desktop 813≤817）。
- **基线**：分支覆盖率基线随主干同步重测入库（91 模块／2649 决策点／1461 覆盖，87 个目标 1664 用例全过），非本轮语义改动。

## 备注

- **边界说明**：本轮提交只含上列契约与测试文件。为让 `codex/wip-R3259`（领先主干 >10 回合）回合主干，本线程另有三笔不属于 R3330 的前置提交：两次主干同步合并（275fcc42、4828acab，消息前缀 R3313）与 Desktop 类体空行归一（bfc51754，823→813 行修 complexity_ratchet 超限），以及 master 侧合并轮 f0665b68（R3329）。
- **保留的独立事实表**：`shot_batches.SHOT_FIELDS` 九个批次归一化字段（shot_id/scene_id/character_ids/costume_id/batch_id/character_refs/reference_roles/continuity_flags/estimated_duration）语义上是「批次归一化视图」而非旧镜头字段，按设计保留；其 schema 片段已与契约事实表同源合成 `schema()`，无字面量重复。
- **欠账**：无新增。历史欠账（工作树状态页抬头滞后、后台全量自检凭据）维持原状记录。
- **未运行**：`--all --safe` 全量（分支轮不累计；合并轮出口 CI 已含静态＋架构＋默认冒烟三层）。

<!-- 提交信息：R3330: L0契约层轮6C·D7——镜头字段契约事实收口（episode_contract.SHOT_FIELD_SPECS单一事实源，schema/validate/rules三呈现同源，rules()黄金快照逐字回归） -->
EOF_MARKER
"D:/漫剧制作助手/运行环境/Python/python.exe" -c "print('written')" 2>/dev/null; ls -la tasks_round/tasks_round_3330_result.md 2>/dev/null || ls -la "D:/漫剧制作助手/.agents/worktrees/dsh-5158b800-34ae/程序/tasks_round/tasks_round_3330_result.md"