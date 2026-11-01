# R1719：契约轮（流程文档）——AGENTS.md 规则重写：开工阅读分级、角色分工、写测试／跑测试／审查／提交时机、REQ 编号链与 --find

- 执行者：Codex
- 轮次类型：契约轮（流程文档）
- 日期：2026-10-19
- 状态：允许文件已改完；架构门禁未达 0 红，两条红均与本次文件无关，见“需裁决事项”。

## 三个问题

1. 本轮属于 §3 哪种类型？契约轮（只改流程文档与需求索引入口）。
2. 测试跑了吗、三个基线过了吗？定向 19 项通过；架构门禁 368 项中 366 通过、2 失败；默认冒烟与完整安全全量未运行。
3. `project_status.md` 的欠账少了吗？未改状态页，不适用。

## A–H 落点

| 条 | 落在哪一节 | 原文删了什么 | 搬到哪里／引用位置 |
| --- | --- | --- | --- |
| A | §0 | 删掉“所有任务都须读完 AGENTS／architecture／PROJECT_MAP／project_status”的统一顺序 | 原位重写：任务书派发只读本文件、任务书、点名文件；自主会话保留完整读取。无外移 |
| B | §4.1／§4.2、§2.5 规则 27、§2.6 开头、§7 第 1／4 条 | 删除旧“双角色／Executor 自审”结构；轮次与提交条款改为提交方执行 | §4 原位；`CLAUDE.md`“开发流程约定”同步角色分工 |
| C | §5“写测试” | 合并原分散测试条款 | §5 原位；新增先红后绿、行为断言、真 Tk 几何、skip 常量与台账、REQ 锚点、禁止弱化断言（引 §2.4） |
| D | §5“跑测试”表与列表 | 原测试触发表与全量段落压缩 | §5 原位；新增 `-k`、`--affected` 覆盖全部消费者、`--architecture`、GUI 锁等待；全量细则引 `runbook.md` §4 |
| E | §4.1 | 删除旧自审职责表述 | 原位写明每次执行方交付后、提交前，在隔离验证工作树复跑并核对范围 |
| F | §2.6 开头、§7 第 1／4 条 | 领号／提交不再写成执行方义务 | 原位明确由提交方执行；新增独立复核全绿、一批一轮、只暂存本批、REQ／DES 编号 |
| G | §2.7 第 4／7 条、`tests/architecture/test_requirement_traceability.py` | 原第 4 条只写锚点门禁，无查询入口 | 原位补 `--find` 命令与编号链；脚本新增 `--find`，复用 `DOC_ANCHOR`／`NAME_ANCHOR` 扫描 |
| H | §3.6–3.11、§5 | 六节模板化“适用／边界／验收”改为一张表；§5 全量、后台补跑、凭据段压缩 | 原位压缩，无规则外移；全量细节引 `runbook.md` §4，门禁清单引 `architecture.md` |

## 命令与计数

| 命令 | 实际输出 |
| --- | --- |
| `len(open('程序/AGENTS.md').read())` | 15609 → 15018（≤ 15600） |
| `python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_agents_md` | Ran 19 tests，OK |
| `python -B tests/architecture/test_requirement_traceability.py --find REQ-S01-51` | 11 行，exit 0；首行为 `tests/test_idea_download_import.py: BodyNamedDownloadImportTests.test_req_s01_51_body_project_mismatch_or_missing_is_ignored` |
| `python -B smoke_test.py --architecture` | Ran 368 tests，258.793s，2 failures，exit 1 |

**先红后绿证据**：新增 `--find` 前，直接运行该脚本报 `ModuleNotFoundError: No module named 'tests'`，exit 1；加导入引导与入口后同一命令 exit 0，列出 `BodyNamedDownloadImportTests` 下 11 个锚定 `REQ-S01-51` 的测试方法。

## 两条架构红灯（与本次文件无关）

1. `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`：断言 `R1715 欠一次完整安全全量`。HEAD 为 `790315f6 R1715`，属提交方／后台补跑范畴。
2. `test_todo_comment_snapshot.test_keyword_comments_match_the_reviewed_snapshot`：`desktop.py` 注释快照行号期望 1019、实际 1087；工作树中 `desktop.py` 有他人未提交改动（101 增／33 删），本次未触碰。

## 范围与未运行

- 改动：`程序/AGENTS.md`、`CLAUDE.md`、`程序/tests/architecture/test_requirement_traceability.py`；新增本结果文件。
- 未改：`docs/`、`runbook.md`、`project_status.md`、生产代码、`desktop.py`。
- 未运行：默认冒烟、完整安全全量、任何 git 写命令（提交、领号、暂存、分支）。

## 需裁决事项

1. 验收第 2 条要求架构门禁 0 红，但当前树受 `R1715` 全量欠账与他人 `desktop.py` 未提交改动影响；需提交方清理／补跑后复验，或确认接受 366/368 且两条红与本批无关。
2. 本任务未改 `runbook.md`：§3.6–3.11 与 §5 的细节是原位压缩并引用现有 runbook 段落，没有需要承接的新细节。

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 字数（Python len）：15018 ≤ 15600。
- `test_requirement_traceability.py --find REQ-S01-51`：列出 test_idea_download_import 的锚点。
- `smoke_test.py --architecture`：368/368 OK。执行方报告的 2 红（全量欠账、desktop.py 注释行号）来自主树他人未提交改动，隔离树不复现。
- 规则正文由 Claude 逐条审阅，A–H 均落地。
