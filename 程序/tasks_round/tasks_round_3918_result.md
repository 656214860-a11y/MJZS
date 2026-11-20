# R3918 结果：状态接续轮——项目交接文件同步

## 1. 三问

- 轮次类型：状态接续轮（`runbook.md` §15 的 3.11）。只按仓库事实、已有凭据和已有报告改状态页，不改生产代码，不把推测写成完成。
- 测试跑了吗、三个基线过了吗：未跑。2026-11-20 17:54 起，`codex/l2-edit-source-publication` 工作树持有共享的 `full-safe-runner.lock` 与 `gui-selftest.lock`（PID 7796，命令 `run_selftests.py --all --safe --force --gui-wait 1800`）。本轮再开含 Tk 的冒烟会抢这把隐藏桌面锁。默认冒烟、架构门禁、安全全量都未重跑。
- 欠账少了吗：没有。`scripts/auto_full_safe.py --status` 仍是自 R3849 至 R3915 的 1 个源码轮，门禁线 8。本轮不改 `.py`，不改变这个计数。

## 2. 改动

- `程序/project_status.md`：轮次头 3916→3919。当前能力改为 13 阶段、白名单依赖（`requirements.txt` 生产锁）、剧本读写目录 `01剧本准备/`（旧 `writing/` 只读兼容）。验证基线补上 R3849 绿凭据口径。已知阻塞补上 2026-11-20 的分支尖端。已核对存在的结果文件与评估清单链接改到归档路径。
- 本结果文件。

依据：`contract/pet_bus.py` 的 `STAGES` 为 13 项；`requirements.txt` 生产锁 8 个包；`domain/writing_tools.py` 写明只可写 `01剧本准备/`，旧 `writing/` 只读回退；`tests/test_stage_templates.py` 把 12 份 `*_process_template.yaml` 加上 `animatic.yaml` 断言为 `len(STAGES)`。

## 3. 凭据（提交前再次读取）

- 最新绿凭据：R3849，树 `36ab86d05cdf8f660e1cd48edd8f84c05408ce73`，1025.121 秒，`2026-11-19T22:30:50`。`git rev-parse 98dafefa:程序` 与该树一致。
- 历史末行：同一提交 `98dafefa`，外层 1037 秒，成功，无失败文件。
- R3849 结果文件正文是「未跑全量」（写于全量结束前）。总条数没有任何留存，不追认。明细见 R3854。
- `last_full_safe_all_at` 仍是 `2026-10-03`，与凭据条目时间不一致，状态页已写明不能当作 R3849 的日期。

## 4. 临时脚本

主树未跟踪的 `.agents/tmp-pip-probe/` 四个脚本是 `foundation-integration-final` 在 R3909 前后的一次性探针，仓库内无引用。按 `runbook.md` §12 脏树协议①，复制到 `.git/rescue/foundation-integration-final/tmp-pip-probe/`，SHA256 一致后删除工作树副本。未入提交。

| 文件 | SHA256 |
| --- | --- |
| `audit_probe.py` | `23A7ADC1921219D019D7E1A47477EC78335A4CCB689A092169F93AD9473B729F` |
| `audit_probe2.py` | `9734E436FAA9BF05531F3E66373F132CA130B0D461D36615A5574ED3507401E5` |
| `prep_commit_3909.py` | `23EBEF5F22B36BAA473E9ABBF12488DBAE405EE32C93771A776C892A975FCF1D` |
| `run_branch_cov.py` | `0B40F38A206B96B7AF8373AB474C74C5876EBD7F41A154D672A1EF0A961AD6E7` |

`codex/foundation-integration-final` 工作树里未提交的覆盖率基线未动。

## 5. 开放任务书（master 工作树，按文件名对照）

`程序/tasks_round/*任务书*.md` 29 份。`任务完成/` 里除 `README.md` 外 19 份能对上任务书，下列 10 份没有完成文件：

- `L0契约宪法化演进级任务书.md`
- `L1基础设施层企业级任务书.md`
- `L3编排调度可靠性与容量验收任务书.md`
- `R3060_桌面界面打磨任务书.md`
- `全量锁卡死治理任务书.md`
- `六层架构收口与企业级演进任务书.md`
- `共享输入框下拉修复任务书.md`
- `共享输入框与skill体系重构任务书.md`
- `架构地基加固任务书.md`
- `目录治理与结构门禁任务书_R3812.md`

`地基门禁疏通任务书.md` 与 R3916 结果只在 `codex/gate-unblock`（`2e3399af`），不在 master。该结果写明：六支历史快照已改名；`codex/foundation-ffmpeg-runtime` 为 `0f359379`；定向测试、合入、U3、U4 都还没做。

## 6. 本轮未改的文档

- 根 `CLAUDE.md`：已写白名单依赖和 13 阶段，本轮不改。
- `程序/PROJECT_MAP.md`：抽查到的阶段数是 13。第 27 行离线语音一行仍写「主程序零第三方依赖」，指的是主程序与独立 ASR 子进程的边界，本轮不改这句。
- `程序/AGENTS.md`：接近 16000 字节预算，本轮不动。
- `程序/architecture.md`、`程序/维护记录/优化待办队列.md`：master 上非合并提交的 pre-commit 只放行状态页、`tasks_round_*_result.md` 和 `维护记录/任务队列.json`。下列过时点本轮读到原文，留到后续 `codex/` 分支：
  - `architecture.md` 第 34 行仍列 `skills/cinematic-director/`，该目录不存在。
  - 第 57 行仍写 `skills/01`—`12`。
  - 第 76 行模板清单没有 `animatic`。
  - 第 125 行写 `domain/message_parts` 暂未进 `_layers.py`，但 `tests/architecture/_layers.py` 第 56 行已经 `_register(2, "message_parts")`。
- 优化待办队列里指向 `tasks_round/归档/2026-10/` 的旧链接、U14、A7，本轮没有逐条重开，不写成已复核。

## 7. 提交

不走 `scripts/dev.py commit`。该入口会把 `tasks_round/evidence/R3918.json` 放进暂存区，master 非合并提交的 pre-commit（规则 34a）会拒绝这个文件。R3912（`c4dedb53`）是直接提交状态页和结果文件的先例。`runbook.md` §13 第 35 条的收尾动作也是 `git add` 加 `git commit`。不推送。

## 8. 来源

2026-11-20 14:50 的交接要求更新项目状态与工程文档。当时启动的后台代理 `9a8138c7` 没有改到文件。本轮收口其中可以在 master 上提交的状态页部分。
