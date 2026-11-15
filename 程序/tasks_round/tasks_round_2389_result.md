# R2389 结构治理轮·执行（README 逐期界面日志原文归档）

- **本轮类型**：结构治理轮·执行（§3.3）。来源 `维护记录/项目整理诊断_20261113.md` 第 3 批「README 瘦身」，按其 J/K 方案执行，未扩大范围。
- **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 通过；定向 21 项通过（`tests.test_line_endings`、`tests.test_app_metadata`）；架构门禁 416 项中 2 失败 1 错误，三项均为本轮之前已存在的登记红项／环境缺件（逐条见「验证」），本轮改动未新增红项。未跑全量安全回归：本轮未改任何 `.py`，按 §5 不触发。
- **`project_status.md` 的欠账少了吗**：没少，也没有新增。`project_status.md` 只由 master 更新，本分支按 §2.6 只写 `tasks_round/tasks_round_2389_result.md`。

## 一、本轮改动

| 文件 | 改动 |
|---|---|
| `程序/README.md` | 2169 行 → 347 行。原「六、第 45 期」至「三十三、第 71 期」（332~2169 行，约 85%）原文迁出；补「当前状态摘要」；修正两处过时数字；末尾保留归档指针 |
| `程序/tasks_round/归档/2026-11_历史文档/README_界面变更日志.md` | 新增，1842 行，即迁出的逐期记录原文 |

1. **原文归档，不改写历史**：迁出的 1842 行逐字保留（含小节编号「六、第 45 期」…「三十三、第 71 期」），只换存放位置；README 留一句指针指向归档文件与 git，查历史细节走那两条路。
2. **补「当前状态摘要」**：13 个制作阶段顺序（01 剧本准备 → … → 13 质检与交付），并写明顺序唯一权威是 `pet_bus.STAGES`／`STAGE_NAMES`、目录名见 `stage_layout.STAGES`；同时给文档索引（`docs/stages/`、`architecture.md`、`distribution_manifest.md`、`runbook.md`）、运行期零第三方依赖、含 Tk 测试走 `工作流任务/gui_hidden.py` 隐藏桌面、账号／订阅与云端为显式推迟项。
3. **更正过时数字**：`skill_panel.py`（10 个制作阶段共用一块面板）→ 13 个；阶段配置按钮位置「（01～10 页）」→「（01～13 页）」。这两处是本轮唯一的内容更正，均以 `pet_bus.STAGES` 的 13 阶段为依据。
4. **行尾**：`程序/README.md` 在 `.gitattributes` 里固定 CRLF，改写后仍为 CRLF；归档文件为新增 `.md`，按 `*.md text eol=lf` 落 LF。

## 二、验证

命令均用 §1 指定的随附解释器 `D:\漫剧制作助手\运行环境\Python\python.exe`。

- 行尾与元数据：`python -B -m unittest tests.test_line_endings tests.test_app_metadata` → 21 项全通过；`line_endings` 对 `README.md` 与归档文件均无 `problems`。
- 默认冒烟：`python -B smoke_test.py` → 8/8 通过。
- 结构治理门禁：`python -B smoke_test.py --architecture` → 416 项，2 失败 1 错误，逐条原因：
  1. `test_agents_md.py::…::test_performance_history_is_declared_as_historical_only`（error，`FileNotFoundError`）—— 缺 `程序/维护记录/基准历史.json`。该文件被 gitignore，只在主检出存在；R2244 结果里已登记为红项。
  2. `test_round_baselines.py::test_round_number_continuous` —— `project_status.md` 轮次头 2366 与分支最新结果轮次不符。状态页只在 master 提交时更新，本分支按 §2.6 不写状态页；本轮新增 2389 后该断言的期望值随之变化，仍是同一登记红项。
  3. `test_skill_reference_injection`（failure）—— `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md` 只以未跟踪内容存在于主检出，worktree 内没有。
- 未运行：`run_selftests.py --all --safe`。理由：本轮只改 `.md`，不触发 §5 的全量条件；全量真实绿凭据以 common-dir `full-safe-receipts.json` 为准（最近一次 `last_full_safe_all_round` 为 2353）。2026-11-02 的后台全量在 `test_distribution_selfcheck` 红，原因是未跟踪的 `漫剧制作助手_图标_54664761.ico` 未在清单声明——与本轮改动无关，该测试在本轮架构门禁中是通过的。

## 三、没做／留给后续

- 诊断报告第 4、5 批（`使用说明.md` 的 12→13 阶段与分镜预演行、`配置说明.md`／`批量资产说明.md` 是否合并、`默认创意示例.md` 保留、文档终稿化）未在本轮做，按一轮一件事留给后续轮次。
- 诊断报告 §八 的 skills 断链（`workflow_settings.SKILL_ALIASES` 仍指已删目录）未修，属代码改动，须单独一轮先红后绿，不与本轮 `.md` 混提。
- 本分支（`codex/wip-R2388`）合入 master 需等主检出那 6 个他人未提交文件收口；本轮不合并、不改主检出。
