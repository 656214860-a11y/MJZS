# R1452 契约轮：文档收口

1. **本轮类型？** 契约轮。仅同步现行文档和轮次证据；不改源码、测试、基线配置或门禁语义。按任务书指定的 R1452 执行；共享领号已至 R1453，不另领号或回写计数器。
2. **测试与基线？** 文档定向 19/19 通过；唯一一次 `smoke_test.py --architecture` 运行 340 项，4 项失败，未重跑。任务书限定不跑全量。R1442 历史全量内容树已核对；5054 例来自任务书，不冒充本轮复测。
3. **是否欠账？** 本轮无源码全量新增欠账；架构有 4 项失败，涉及缺失 SKILL 文件、skip 台账、TODO 快照、裸 JSON 读取棘轮，超出本轮三份现行文档的修改范围，未改代码／测试／台账消除失败；独立报告缺口及全量边界见下文。Git 暂存被沙箱权限阻止，按用户指令停在已改好、未暂存、未提交状态。

## 范围与交付

- 工作分支 `codex/wip-R1452`，起始 HEAD `df549c4`；按 §0 完成启动必读及接力入口、snapshot、risks、backlog 阅读后编辑。
- `AGENTS.md`：422 → 328 行；删除重复解释及过期历史计数，合并硬折行；保留硬约束、轮次协议、权威源表、测试规则和授权来源。删除前检查 `test_agents_md.py` 全文及测试中的相关字符串，压缩后另做语义审阅。
- `project_status.md`：当前轮次改为 1453；加入 R1441–R1451 的提交／报告核对表；说明历史全量及共享后续凭据；更新已移除框架对应的现行能力和暂缓方案，历史条目保留轮次及结果，旧模块名改为退役职责描述。
- `architecture.md`：删除已退役角色模块、配置键和异常类型的现行引用，改为剧本 SKILL 角色审核与编剧风格；保留 R1441／R1442 移除证据链接。`PROJECT_MAP.md` 无这些已删除模块引用，无需修改。
- `TASK_R1452.md` 是用户任务书，不纳入暂存或提交。本轮报告同时作为文档任务接力记录，不改共享接力文件。

## 轮次和验证证据

- R1444（`4671210`）无独立报告，后以 `f63684c` 合入 R1447；R1445 车道以 `07d265a` 归 R1447；R1448 车道以 `df549c4` 归 R1451。各车道不补造独立测试结论。
- R1449 无独立报告；`git log --all` 中 `b873155` 归 R1453，尚未进入本工作树初始 HEAD 的祖先链。其余轮次均链接已有结果报告；R1447／R1451 的早期失败或阻塞与后续验收分阶段记载。
- 任务书原文：**最近一次全量绿：HEAD 797e31e，5054 例，0 红**。这是 R1442 历史时点；`git rev-parse 797e31e:程序` 为 `2c9128f7b12cde064dc64ef31f56408dcf165519`，与共享 `full-safe-receipts.json` 的 R1442 成功凭据一致（`2026-10-15T05:16:01`，524.971 秒）。5054 为任务书给定数量，未发现原始计数日志。
- 共享凭据另有 R1447（`2026-10-15T14:17:50`，522.153 秒）及 R1453（`2026-10-15T16:42:37`，419.548 秒）；最新后台结果 HEAD `37d421e1f59123815a8941a6f0a23d7220b0ed7d`、退出 0、无红项。这些属于其他检出的后续成功，不能替代本分支验证。
- 全文残留核对排除 `维护记录`、`tasks_round` 的历史证据；根目录 `crud_audit_20260926.md` 也是 2026-09-26 的历史维护审计，旧框架记载属于当时事实，保留原件。任务书只授权三个现行文档及本轮报告，未改该历史审计。

## 本轮验证

- 文档相关：`python -B -m unittest architecture.test_agents_md architecture.test_round_baselines`（目录 `程序/tests`，`PYTHONPATH=..`）：19 项，2.673 秒，全部通过。
- 架构：`python -B smoke_test.py --architecture`：340 项，131.197 秒，4 项失败，退出 1；仅此一次，未重跑。
  - `test_skill_reference_injection.py:19`：缺 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md`。
  - `test_skip_hygiene.py:114`：台账 223 条，源码 226 条。
  - `test_todo_comment_snapshot.py:52`：`desktop.py` 中 `_tick_async_result` 的快照行号 2824 与实际 2843 不符。
  - `test_unification_ratchet.py`：`script_workspace_service.py:259` 的裸 JSON 读取触发棘轮；`架构统一基数.json` 已登记该文件旧行 246，属于位置漂移。
- 既存状态核验：上述测试目录、`desktop.py`、`script_workspace_service.py`、skip 台账、TODO 快照与架构统一基数相对 HEAD 均无差异；缺失的 SKILL 引用在 HEAD 中同样不存在。历史全量凭据不能覆盖本次失败。
- 失败修复次数为 0：四项涉及的技能文件、源码与 JSON 台账不在用户授权的文档范围内；保留失败证据，不扩展修改。
- `git diff --check` 通过；受任务约束的现行文档与 PROJECT_MAP 未发现已删除模块名残留。
- 使用随附解释器 `运行环境/Python/python.exe`；不运行默认冒烟或全量，不操作 GUI、业务数据或外部服务。

## 提交与接力

- 已设置 `CODEX_STAGE_ALLOWLIST=程序/AGENTS.md;程序/project_status.md;程序/architecture.md;程序/tasks_round/tasks_round_1452_result.md`，仅对这四个路径执行 `git add --`。
- `git add` 退出 128：`Unable to create D:/漫剧制作助手/.git/worktrees/R1452/index.lock: Permission denied`。索引位于沙箱可写根之外，无法暂存，因此未继续 `git commit`；未请求提权或绕过限制。
- **commit hash：无；交付状态：已改好、未暂存、未提交。** `TASK_R1452.md` 未暂存；无 push、无 master 合并。预定提交标题为 `R1452: 收口轮次文档并精简协作规则`。
- 接力：在具有正常 Git 写权限的环境按本报告白名单提交；4 项既存架构失败应另行授权处理，不扩展本轮文档范围。现有 pre-commit 另有限制：工作分支不可提交 `project_status.md`；本轮因更早的索引权限错误尚未执行到钩子，后续提交须正视任务书与该限制的冲突，不能假定提交一定成功。
