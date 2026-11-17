# R3006 结果：SKILL 生命周期 T1——体检上屏＋发送前预览＋用户层根目录迁移对称
<!-- round-evidence: {"commit_base": "6ecbfd5f", "credential_hits": 0, "evidence_sha256": "290bd160ffa4991d", "exit": 0, "failed": 0, "passed": 58, "round": 3006, "tests": "run_selftests.py -k skill_health"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T1）。
**测试**：跑了——先红后绿（迁移/体检用例先失败后转绿）；定向 `run_selftests -k pet_ui skill_health` 666 条全绿（含新文件 5 分片）；`smoke_test.py --affected` 冒烟 8/8、门禁 1870 条中仅 test_pet_ui 2 条 GUI 时序用例在高负载下抖动（隔离复跑及整文件复跑均绿，与本轮模块无关）；`smoke_test.py --architecture` 470 条全绿。
**基线**：冒烟 8/8；架构门禁 470/470；全量回归未跑（分支不累计欠账，合入 master 前按风险触发判定）。
**欠账**：无新增；任务书 T2–T10 为后续独立轮次。

## 本轮做了什么

1. **SKILL 体检服务（L3，不发不写）**：`workflow_settings.skill_health_report()`——`registry.scan(force=True)` 后把 `Registry.problems()/warnings()` 按 SKILL 名归位（归不了位的进全局清单），并对每个 SKILL 做发送前干跑：与 `freeze_skills` 同口径的 `strict＋depth=-1` 内联预演，产出每行的字段问题、软警告、引用闭包（复用 `reference_row` 五字段）、预计内联字符数与上限、错误与状态（ok/warning/problem/error）。`stage` 参数支持阶段 id 或中文名过滤。
2. **阻断异常携带闭包**：`_skill_blocks`/`_inline_skill_report` 的引用越界、缺失、超上限三类 `ValueError` 改经 `_closure_blocked()` 附带 `skill_closure`（走到那一步的部分闭包），体检据此展示「断在哪、之前加载了什么」；发送路径行为不变，仍是同一批异常同一批文案。
3. **体检上屏（L4）**：阶段 SKILL 面板管理下拉新增「体检」项（`MANAGE_HEALTH`），`show_skill_health()` 弹 `BaseDialog`：全局问题/警告区＋逐 SKILL 状态行（Treeview），点选查看详情文本（问题、警告、干跑错误、引用闭包表、内联字符预估）。只读，不发送、不落盘。
4. **用户层根目录迁移对称**：`Registry._migrate_root_manifests()` 由只扫内置层根目录改为遍历 `_layers()` 两层。用户层根目录 `*.skill.md`：stage 可识别且用户层同名阶段目录存在→移入；目录不存在→按内置目录名补建后移入（与「新增 SKILL」写入目录同口径）；stage 缺失/非法、目标已存在、读写失败→保留原文件并记入 problems，不静默丢失。此前用户层根目录文件静默不可见。
5. **权威文档同步**：`AGENTS.md` 权威源表与 `architecture.md` 相应小节补记体检入口与用户层根目录迁移语义（层语义有变，同轮更新）。

## 先红后绿证据

新增 `tests/test_skill_health_service.py`（9 条：报告归位/闭包/过滤/全局归集 3 条、用户层迁移 4 条、面板体检入口 2 条）。实现前迁移与体检用例失败（用户层根目录 SKILL `getById` 返回 None、`skill_health_report` 不存在）；实现后 `run_selftests -k pet_ui skill_health` 666 条全绿，其中本文件 5 分片 58 条全过。

## 验证记录

- `smoke_test.py --affected skill_registry skill_panel workflow_settings`：冒烟 8/8；门禁 1870 条，唯一红为 `test_pet_ui` 2 条（`PanelQuietTests`/`PanelTextTests` 的气泡可见性与文案时序断言），当时机器 28+ python 进程、GUI 令牌排队第 4 位的高负载环境；两条用例单独复跑绿，`test_pet_ui` 整文件 49 分片复跑绿，与本轮改动模块（skill_registry/skill_panel/workflow_settings）无 import 关系。
- `smoke_test.py --architecture`：470 条全绿（含 AGENTS.md/architecture.md 一致性门禁）。
- `run_selftests.py --serial -k pet_ui skill_health`：666 条 ALL TESTS PASSED。
- 外部 gitlink 包（HoLLMwood、AIGC创作全流程、剧本锻造、编剧技能集）已在工作树物化，`scripts/skill_package_pins.py --check` 3 包 0 问题；物化仅补齐工作树缺失内容，不入提交。

## 改动文件

`workflow_settings.py`（体检服务＋闭包异常）、`skill_registry.py`（双层根目录迁移）、`skill_panel.py`（体检入口与详情弹窗）、`tests/test_skill_health_service.py`（新增）、`AGENTS.md`、`architecture.md`。

## 未做/移交

- 发送前预览目前以「体检干跑」形态呈现（闭包＋字符预估＋阻断原因）；T7 统一管理页落地时再决定是否把勾选级「发送前预览」并入管理页。
- T2 文件夹直选/ZIP 导入、T3 台账远程字段、T4 台账消费为后续独立轮次。
