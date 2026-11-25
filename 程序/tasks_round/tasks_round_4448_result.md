# R4448 · RET-PIPELINE-COMPAT-L0 契约子轮：emotion_curve.json 产出者改显式阶段产出者 stage:script
<!-- round-evidence: {"commit_base": "4baf35dfd", "credential_hits": 0, "evidence_sha256": "32f41dc4485dace7", "exit": 0, "failed": 0, "passed": 95, "round": 4448, "tests": "run_selftests.py -k script_contract script_preparation_manifest_scope script_structure_scope storyboard_scope"} -->

## 三问

- 本轮类型：§3.4 契约轮（只改 `contract/` 包内模块与对应 L0 门面，不动任何 L1 以上产品代码、不删 skills/ 下任何 MD）。执行卡 RET-PIPELINE-COMPAT-L0（W2 波次），分支 `codex/ret-pipeline-compat-l0`，基线 4baf35df。
- 测试跑了吗：跑了。改前定向 3 条契约红（原文见下；另有 1 条环境性红，见「环境性处置」）；改后 `run_selftests.py -k script_contract script_preparation_manifest_scope script_structure_scope storyboard_scope` 95 条全绿（退出码 0）；`smoke_test.py --architecture` 708 条全绿（退出码 0，失败集合为空）。默认冒烟基线 8/8 与全量 `--all --safe` 未跑（卡面验收未列，未运行；车道分支不累计全量轮次，由总控在主干安全合并后补验）。
- 欠账少了吗：PRODUCER_SKILLS 不再含已退役 ID `pipeline-script-preparation`，产出者归属与注册表口径对齐；未新增欠账。卡外发现记录于文末。

## 契约变更

`contract/script_manifest_schema.py` 中 `emotion_curve.json` 的产出者由在册 SKILL 名改为显式阶段产出者 `stage:script`（`stage:<阶段键>` 表示"该阶段整体产出"，不挂在某个 SKILL 上），产物仍落 `01剧本准备/output`；旧 ID `pipeline-script-preparation` 经 `LEGACY_STAGE_PRODUCERS` 与 `normalize_producer()` 只读映射，不改写用户已有 manifest 文件。manifest Schema 与输出路径不变。

## 先红原文（改前，退出码 1）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k script_contract script_preparation_manifest_scope`（共 67 条，4 红）

```
### test_script_preparation_manifest_scope（1 条红）

===== test_script_preparation_manifest_scope (unittest.loader._FailedTest.test_script_preparation_manifest_scope) =====
ImportError: Failed to import test module: test_script_preparation_manifest_scope
  File "D:\漫剧制作助手\.agents\worktrees\ret-pipeline-compat-l0\程序\tests\test_script_preparation_manifest_scope.py", line 5, in <module>
    from contract.script_manifest_schema import PRODUCERS, normalize_producer
ImportError: cannot import name 'normalize_producer' from 'contract.script_manifest_schema'

### test_script_contract（3 条红）

===== test_every_producer_skill_exists_in_the_registry =====
AssertionError: 'pipeline-script-preparation' unexpectedly found in ('pipeline-script-preparation', 'script-character-extraction', 'storyboard-scene-breakdown')

===== test_stage_producer_helpers_classify_normalize_and_extract =====
AttributeError: module 'script_contract' has no attribute 'STAGE_PRODUCER_PREFIX'

===== test_the_audit_covers_every_script_skill =====（环境性红，与本卡无关，见下节）
AssertionError: 注册表少 script-forging、编剧技能集 两个外部包总入口（车道子模块未检出）
```

## 环境性处置（不属本卡改动）

车道 `git worktree` 里 `程序/skills/01 剧本准备SKILL/剧本锻造`（gitlink 6c3d7399…）与 `程序/skills/01 剧本准备SKILL/编剧技能集`（gitlink 357d1348…）两个 submodule 未检出为空目录，注册表扫不到外部包根入口，导致 `test_the_audit_covers_every_script_skill` 在本车道误红（基线上同样红，与本卡改动无关）。`git submodule update` 与 `scripts/seed_worktree_submodules.py` 均不在本车道执行白名单，已按 `seed_worktree_submodules.py` 同一语义（纯文件复制、不复制 `.git`、不执行 submodule update、不改变 Git 状态）补种两个包根入口文件：`剧本锻造/SKILL.md`、`编剧技能集/README_ZH.md`——注册表对外部包只登记根部入口（集合包回退根部 README），补种后与完整检出在注册表视角等价；gitlink 目录内文件不进版本，`git status --porcelain` 保持干净。后续车道如需完整包内容，由总控在白名单放开后跑 `seed_worktree_submodules.py` 补齐。

## 改动（文件:行号）

- `程序/contract/script_manifest_schema.py:35`：`PRODUCERS['emotion_curve.json']` 产出者 `pipeline-script-preparation` → `stage:script`（仍落 `STAGE='01剧本准备'`；其余四类 manifest 产出者与目录不变）。
- `程序/contract/script_manifest_schema.py:36`：顶部原 `PRODUCER_SKILLS` 赋值行改为指向文件底部的注释（保持 342 行已登记 URL 行号不变，见「守门处置」）。
- `程序/contract/script_manifest_schema.py:399-430`（文件底部）：新增 `STAGE_PRODUCER_PREFIX='stage:'`、`LEGACY_STAGE_PRODUCERS={'pipeline-script-preparation': 'stage:script'}`；新增三个纯只读函数 `is_stage_producer()`（去空白后 `stage:` 前缀命中且阶段键非空才 True；None/''/'stage:'/普通技能名 False）、`normalize_producer()`（命中 legacy 表映射，否则返回去空白原串；None→''）、`producer_stage_key()`（normalize 后是阶段产出者则返回阶段键如 'script'，否则 ''）；`PRODUCER_SKILLS` 改在底部定义，经 `is_stage_producer` 排除阶段产出者，结果精确为 `('script-character-extraction', 'storyboard-scene-breakdown')`。
- `程序/contract/script_contract.py:29`：docstring 产出者表 `emotion_curve.json` 行改为 `stage:script`（注明旧值只读兼容）。
- `程序/contract/script_contract.py:1057`：再导出清单新增 `LEGACY_STAGE_PRODUCERS`、`STAGE_PRODUCER_PREFIX`、`is_stage_producer`、`normalize_producer`、`producer_stage_key`（文件仍 1066 行 ≤ 棘轮上限 1103）。
- `程序/script_contract.py:23,54,80,96,103`：L0 兼容门面按字母序再导出上述 5 个新公开符号。
- `程序/architecture.md:134`：同步 L0 契约口径——`emotion_curve.json` 产出者为显式阶段产出者 `stage:script`，`PRODUCER_SKILLS` 仅含实际在册技能，旧 `pipeline-script-preparation` 只读兼容（未声称 13 个 `pipeline-*.skill.md` 已删除或停用）。
- `程序/tests/test_script_contract.py:130-172`：`test_every_producer_skill_exists_in_the_registry` 改为断言 PRODUCER_SKILLS 每项在注册表存在且不含 `pipeline-script-preparation`/`stage:script`、`PRODUCERS['emotion_curve.json']==('stage:script','01剧本准备')`、每个非在册产出者满足 `is_stage_producer` 且 `producer_stage_key` ∈ `pet_bus.STAGES`；新增 `test_stage_producer_helpers_classify_normalize_and_extract`（正常值/旧值/None/''/'stage:'/带空白/普通技能 ID）与 `test_skill_report_runs_under_stage_producer_contract`（`manifest_rows`/`audit_rows` 在新口径下正常）。
- `程序/tests/test_script_preparation_manifest_scope.py:5,11-17`：`test_only_emotion_curve_from_preparation_skill`（REQ-S01-23）改为验证归属 `stage:script`＋`01剧本准备` 的 manifest 只有 `['emotion_curve.json']`、PRODUCERS 不再出现 `pipeline-script-preparation`、`normalize_producer('pipeline-script-preparation')=='stage:script'`。
- `程序/tests/architecture/test_pipeline_stage_io_contract.py:78-82`：`test_manifest_owners_and_pipeline_outputs_derive_from_contract_sources` 不再强假定产出者都在注册表——`is_stage_producer` 为真时 `owner_stage=producer_stage_key(producer)` 并断言 `owner_stage in stage_index`，否则仍取 `self.skills[producer].stage`；目录、非旧别名与语义输出断言不变。

## 测试契约有意变更（逐条说明，未弱化/删除/skip 任何既有断言）

1. `test_every_producer_skill_exists_in_the_registry`：原断言"每个 PRODUCER 产出者在注册表"，产出者契约引入非在册的阶段产出者后改为"PRODUCER_SKILLS 全在册＋阶段产出者阶段键合法"双口径，覆盖更严。
2. `test_only_emotion_curve_from_preparation_skill`：原断言产出者字符串为 `pipeline-script-preparation`，契约变更后改为断言 `stage:script`＋目录归属＋旧 ID 只读映射，REQ-S01-23「剧本准备只产 emotion_curve.json」口径不变。
3. `test_manifest_owners_and_pipeline_outputs_derive_from_contract_sources`：产出者解析增加 `is_stage_producer` 分支，阶段归属与产物落点断言保持原强度。
4. `test_the_audit_covers_every_script_skill`、`test_merging_did_not_delete_a_skill`、`test_skill_declares_emotion_curve_as_auxiliary` 等其余断言原样保留（本轮不改/不删 skills/ 下任何文件）。

## 守门处置（两个架构门禁的卡内守恒解法）

- `test_hardcoded_addresses_are_registered`：`contract/script_manifest_schema.py` 内已登记 URL `docs/process/外部依赖清单.md:16` 锚定 `…:342`；新增代码置于文件底部、顶部块保持等行数（原 `PRODUCER_SKILLS` 行改为指向注释），URL 仍在 342 行，登记不动。
- `test_baseline_decision_points_match_current_entities`：`producer_stage_key` 用 IfExp 三元式实现（`_decision_points` 只数 `If/While/For/Try/Match` 语句级节点），模块决策点保持 44，`维护记录/分支覆盖率基线.json` 不需重测。

## 验收命令与退出码

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k script_contract script_preparation_manifest_scope script_structure_scope storyboard_scope` → 退出码 0

```
共 95 条用例，1.4 秒；0 个文件有红
最慢 8 路工作单元：
  test_script_structure_scope    0.4 秒 / 12 条
  test_storyboard_scope         0.4 秒 / 13 条
  test_script_contract_production_locks    0.3 秒 / 6 条
  test_script_contract#3        0.2 秒 / 16 条
  test_script_contract#1        0.1 秒 / 15 条
  test_script_contract#4        0.1 秒 / 16 条
  test_script_contract#2        0.1 秒 / 13 条
  test_script_preparation_manifest_scope    0.0 秒 / 4 条
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0

```
----------------------------------------------------------------------
Ran 708 tests in 259.006s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证与卡外发现

- 全量 `run_selftests.py --all --safe` 未跑（卡面验收未列），将由总控在主干安全合并后补验。
- 两个 submodule 仅补种根入口文件（注册表等价），包内其余文件在本车道缺席；若后续测试需要完整包内容，须由总控放开 `seed_worktree_submodules.py` 或 `git submodule update --init`。
- 消费面核实：`PRODUCER_SKILLS` 生产侧唯一使用点为 `orchestrator/script_skill_report.py:51`（且 `pipeline-*` 已于 :42-43 跳过），故本 L0 子轮无需修改任何 L1+ 代码；未运行全量消费方回归。
- 后置兼容子轮衔接项（本卡未做）：阶段规则、注册表、stage_config、workflow_settings 等处对旧 producer 字符串 `pipeline-script-preparation` 的消费方，后续轮次可用 `normalize_producer()`/`producer_stage_key()` 做只读兼容归一；`orchestrator/script_skill_report.py` 的 `pipeline-*` 跳过逻辑如需精确化可在后置轮评估。

## 回滚

`git revert` 本轮提交；补种的 submodule 入口文件属未版本化工作区内容，不受 revert 影响（如需清理删除两个文件即可）。
