# R4176 结果：阶段配置保存保留失效 SKILL 引用（FIX-AUD-SKILL-STAGECFG）
<!-- round-evidence: {"commit_base": "12ce348b", "credential_hits": 0, "evidence_sha256": "ded740ec66e104fd", "exit": 0, "failed": 0, "passed": 23, "round": 4176, "tests": "run_selftests.py -k stage_config stage_gate_modes"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 FIX-AUD-SKILL-STAGECFG（波次 W2）；缺陷 AUD-SKILL D7——`stage_config.put` 在任何保存时经 `clean_skills` 静默丢弃失效或已禁用的 SKILL 引用，发送门禁 `validate_selected_skills` 靠 `skill_config.json` 原始 `skills` 列表报「未加载／已禁用」，保存时抹掉等于绕过门禁。车道 `codex/fix-aud-skill-stagecfg`，基准 `12ce348b`。

（二）测试与三个基线：`run_selftests.py -k stage_config stage_gate_modes` 改前（只加测试未改产品）23 条里 3 条红（均为本卡新增用例），改后 23 条全过，退出码 0。`smoke_test.py --architecture` 700 条全过，退出码 0。默认冒烟与全量未跑。

（三）欠账：无新增。读视图 `get()`/`load()` 仍走 `clean_skills` 清洗（面板口径不变）；`synchronize()` 原本就保留失效项，本轮未动。

## 缺陷复现

改前 `orchestrator/stage_config.py`：`put()`（原 341-358 行）先 `data = load(project, reg)`——`load()` 对每个阶段的 `skills` 过 `clean_skills`（原 114-125 行，只留注册表在册项），再 `save_all()` 原样落盘。结果是**任何一次 `put`（只改模型、只改推理等级、只改别的阶段）都会把全部 13 个阶段里失效／已禁用引用从磁盘上抹掉**，`validate_selected_skills`（`orchestrator/workflow_settings.py:615-634`）读到的已是干净列表，「已禁用／未加载」分支永远走不到。

新增 `StageConfigSkillPreservationTests`（`tests/test_stage_config_empty_project_cache.py:60-121`）3 条用例在未改产品时跑出 3 红，红因即缺陷本身：

- `test_save_without_skill_changes_keeps_stale_references_on_disk`：`AssertionError: Lists differ: ['script-skill'] != ['script-skill', 'disabled-skill', 'ghost-skill']`——只改 `model` 的保存把 script 阶段的失效与已禁用引用清掉；video 阶段 `['ghost-video-skill']` 同样被清成 `[]`。
- `test_explicit_skill_selection_remains_the_way_to_clear_stale_references`：`AssertionError: Lists differ: [] != ['ghost-video-skill']`——显式重存 script 勾选时，**没被碰的 video 阶段**失效引用也被连带抹掉。
- `test_send_gate_still_reports_the_preserved_references`：`AssertionError: ValueError not raised`——无关阶段保存之后门禁不再报错，缺陷端到端坐实。

现状判定：该清洗**不是有意设计**。`synchronize()`（`stage_config.py:153-212`，原有代码）明确注释「保留失效选择作为发送门禁依据；用户确认取消后才可移除」，说明保留失效引用供门禁报错是既定契约；`put` 里的 `clean_skills` 只是读取视图的复用，落盘副作用属缺陷。

## 改了哪些文件

- `orchestrator/stage_config.py`：
  - :128-150 新增 `_clean_skills_for_save()`：落盘归一——有效项照旧去重并归一别名（含 deprecated→replacedBy 迁移、错阶段项剔除，口径与 `clean_skills` 一致）；`reg.getById(name) is None` 的项（失效或已禁用）原样保留、不去重丢弃。
  - :372-380 `put()`：`load()` 之后读一次落盘原文 `_workflow_data(project)`，把**本次未显式改写**的各阶段 `skills` 用 `_clean_skills_for_save` 按原样归一回 `data`——失效／已禁用引用留在落盘配置里。
  - :385 `put()`：显式 `skills` 参数同样走 `_clean_skills_for_save`——用户重存勾选列表仍是移除失效项的确认入口（不在新列表里的失效项消失；显式写入的失效名也保留给门禁报错，不再被静默吃掉）。
- `tests/test_stage_config_empty_project_cache.py`：新增 `json`/`mock`/`skill_registry`/`workflow_settings` 导入（:3,7,9-11）、`_FakeSkill`/`_FakeRegistry`（:28-57）、`StageConfigSkillPreservationTests`（:60-121，3 条用例）。全部临时目录，不建 Desktop/Tk。
- 本结果文件。

行为边界：公开函数签名未动；`get()`/`load()`/`synchronize()`/`save_all()` 未动；只有 `put` 的落盘口径变化。未改 `workflow_settings.py`、`skill_registry.py` 及任何门禁逻辑。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 开工三查 | `status --porcelain` 无输出；`git log -1` = `12ce348b`；分支 `codex/fix-aud-skill-stagecfg` |
| 定向（改前，只加测试） | 退出码 1；23 条，3 红（均为本卡新增用例，红因见上） |
| 定向（改后） | 退出码 0；23 条全绿；尾部原文：`共 23 条用例，2.0 秒；0 个文件有红` … `ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；尾部原文：`Ran 700 tests in 283.512s` / `OK` / `✅ 架构治理测试：tests/architecture` |
| `scripts\dev.py claim` | 领到 4176 |

改前定向输出尾部原文（3 条红）：

```
===== test_explicit_skill_selection_remains_the_way_to_clear_stale_references ... =====
AssertionError: Lists differ: [] != ['ghost-video-skill']

===== test_save_without_skill_changes_keeps_stale_references_on_disk ... =====
AssertionError: Lists differ: ['script-skill'] != ['script-skill', 'disabled-skill', 'ghost-skill']

===== test_send_gate_still_reports_the_preserved_references ... =====
AssertionError: ValueError not raised

共 23 条用例，1.9 秒；1 个文件有红
```

改后定向输出尾部原文：

```
  test_stage_gate_modes         14 条     0.1 秒

共 23 条用例，2.0 秒；0 个文件有红
最慢 3 路工作单元：
  test_stage_config_empty_project_cache    0.2 秒 / 5 条
  test_stage_gate_modes         0.1 秒 / 14 条
  architecture.test_writing_api_stage_config_boundary    0.0 秒 / 4 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：…\selftest-incremental.json
最近 5 轮自检中位基线：2.0 秒

ALL TESTS PASSED
```

## 没有验证的地方

- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面只要求定向＋架构门禁）。
- `put(skills=[...])` 显式列表里夹带失效名时现在也会保留（供门禁报错），卡面允许文件内未见断言该场景被丢弃的既有用例；定向与架构门禁全绿，未跑全量确认其余消费者。
- 真实桌面 SKILL 面板端到端未验（用例均为临时目录＋假注册表，未建 Desktop/Tk）。

## 卡外发现（只记录，未动）

- `put()` 现在每次保存多读一次 `skill_config.json`（`_workflow_data`），相对 `load()` 的一次读取；量级可忽略，未做合并读取优化（超出最小改动）。
