# R1752：文档轮——退役 .agent-handoff 接力协议并对齐 程序/AGENTS.md（ALIGN）

- 轮次类型：文档轮（纯文字改动，仅 `程序/AGENTS.md`，未领号，由调度方归档与提交）。
- 背景核对：根目录 `AGENTS.md` 现文为“`.agent-handoff/` 自 2026-10-19 起停更，只作历史证据，不必读、不要写。当前状态以 `程序/project_status.md` 为准，本轮任务以任务书为准。”（`type` 在 Git Bash 下不可用，改用读取文件核对）。
- 测试：`run_selftests.py -k root_layout app_metadata` 通过，2 个测试文件 / 6 条用例 / 0 红；断言未动（本轮未改任何测试）。

## 两处改动（前 → 后）

### 1. §2.6 第 41 条下缩进段落（原第 130 行）

改前：

>     非 master 分支／worktree 也不得写 `.agent-handoff/backlog.md` 与 `.agent-handoff/snapshot.md`；分支记录只写 `程序/tasks_round/tasks_round_<n>_result.md`，合入 master 后单独提交一次补进 `project_status.md`（提交信息 `R<n>: 补记分支 <分支名> 的轮次记录`）。

改后：

>     分支记录只写 `程序/tasks_round/tasks_round_<n>_result.md`，合入 master 后单独提交一次补进 `project_status.md`（提交信息 `R<n>: 补记分支 <分支名> 的轮次记录`）。

保留内容：分支记录位置、合入 master 后补记 `project_status.md`、括号内提交信息格式原样。

### 2. §9「上下文与接力」正文（原第 290 行）

改前：

> 上下文不足或执行被中断时，记录目标、已改文件、实际验证、阻塞和下一条安全操作，遵循根目录接力协议；压缩上下文不代表任务完成。新会话只按 §0 恢复，不重复另设阅读顺序。

改后：

> 上下文不足或执行被中断时，记录目标、已改文件、实际验证、阻塞和下一条安全操作，把这些写入本轮结果文件（`tasks_round_<n>_result.md` 或 pending 结果文件），不再写 `.agent-handoff/`；压缩上下文不代表任务完成。新会话只按 §0 恢复，不重复另设阅读顺序。

保留内容：章节标题 `## 9. 上下文与接力` 未改；后两句原样保留。

## grep 剩余命中及保留理由

命令：`grep -n "agent-handoff\|接力" AGENTS.md`

- 第 288 行 `## 9. 上下文与接力`：章节标题，任务书要求不改，避免锚点失效。
- 第 290 行 `…不再写 `.agent-handoff/`；…`：本轮新写的说明句，明确该目录停更后不再写入，符合根目录新说法。

除上述两处外无其他命中。

## 实际命令与结果

- `run_selftests.py -k root_layout app_metadata`（解释器 `D:\漫剧制作助手\运行环境\Python\python.exe -B`）：
  - `test_root_layout` 1 条 0.1 秒；`test_app_metadata` 5 条 0.5 秒。
  - 共 6 条用例，2.7 秒；0 个文件有红；`ALL TESTS PASSED`。
- 未运行：`--affected`、架构门禁、全量（任务书明确要求由调度方验收时执行）。
- 未执行任何 git 写命令；未改 `project_status.md`、测试、代码、根目录 `AGENTS.md` 或 `.agent-handoff/`；未新增 `.bak_*`。

## 需裁决事项

无。

## 独立验收（Claude）

- 范围：根目录 `AGENTS.md` 是用户本人已改好的未提交修改（2 增 5 删，把接力协议段落改为"`.agent-handoff/` 自 2026-10-19 起停更，只作历史证据"），本轮原样提交，调度方未改一字；`程序/AGENTS.md` 的两处对齐由执行方（Qoder DeepSeek-Flash，约 40 秒）完成，调度方核对 diff：只改 §2.6 第 41 条下缩进段落（去掉对 `.agent-handoff/backlog.md`／`snapshot.md` 禁写的表述，其余原样）与 §9 正文（改为写入本轮结果文件、不再写 `.agent-handoff/`，标题与后两句不动），无越界。
- 执行方：`run_selftests -k root_layout app_metadata` 6 条 0 红。调度方在主树：见下方命令计数。
- `.agent-handoff/` 目录本身保留作历史证据，未删除；`test_root_layout` 仍登记该目录为"代理接力记录"，未改。
- 断言未动；未改任何测试与代码。
- 调度方命令计数（主树，已应用补丁）：`smoke_test.py --architecture` 375 条仅 1 条红，即已知不阻断的「欠一次完整安全全量」（后台补跑项）；`run_selftests -k root_layout app_metadata test_agents_md` 21 条 0 红（4.7 秒）。
