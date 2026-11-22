# R4000 结果：专题六（模型调用与费用）盘点 — DOC-T6A
<!-- round-evidence: {"commit_base": "ad3dcf70", "credential_hits": 0, "evidence_sha256": "a4ff7c8b1b9df20e", "exit": 0, "failed": 0, "passed": 0, "round": 4000, "tests": "docs-only"} -->

## 三问

- **本轮属于哪种类型**：§3.5 只读诊断轮（任务书 §4.10 盘点卡模板，DOC-T6A）。未改任何 `.py`／`.pyw`，未改已有文档；只新增报告与结果文件。
- **测试跑了吗、三个基线各是什么结果**：
  - 默认冒烟基线：未运行（只读诊断轮默认不跑测试；本卡验收命令未要求）。
  - 架构门禁：已运行。`PY -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`（本卡验收命令）全过；另按任务书 §4.0 第 10 条同批跑了 `test_requirement_traceability`、`test_design_coverage`、`test_doc_registry_migration`、`test_agent_doc_budget`，合计 85 项全部 OK，干净复跑退出码 0；分层增量 JSON `{"ok": true, "added": [], "removed": []}`。
  - 全量基线：未运行（本轮不跑 `smoke_test.py --all` 与 `--safe`，按执行者指令）。
- **欠账少了吗**：本轮不产生功能欠账；盘点中确认的文档缺口（「推荐模型线路」卡片无界面消费者、「两本账」口径不全）已记入报告差异清单 D6-01／D6-02，交主控裁决，不属本轮关闭范围。

## 改了哪些文件

- 新增 `tasks_round/专题六模型调用与费用盘点报告.md`（本卡交付物；按 §4.10 报告结构六块：范围、事实表 F6-01…F6-38、现有文档写到哪了、差异清单 D6-01…D6-02、给主控的问题建议 Q6-1…Q6-5、读过的文件清单）
- 新增 `tasks_round/tasks_round_4000_result.md`（本文件）

## 每条验收命令的结果

| 命令 | 结果 |
|---|---|
| `PY -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`（本卡验收命令） | 通过（与 §4.0 四个文档门禁合跑共 85 项全 OK，退出码 0） |
| `git diff --stat 相对分叉点` | 本车道相对 `master` 分叉点（8ca777e9）的差异为：R3993 已提交的专题五报告＋结果＋证据（上一轮，非本轮），本轮新增 `tasks_round/专题六模型调用与费用盘点报告.md` 与本结果文件；本轮改动范围内只有报告和结果文件 |

## 查不到的事项（未核实）

- 服务端 `provider_preset` 表与 `https://<服务器>:8433` 管理后台的真实实现与部署状态：文档 §7.9.7.1 自述「本轮未核对后台代码与部署」，本仓也没有服务端代码，标未核实。
- 供应商真实计价、缓存计费档位、账单自动对账：代码只按冻结费率估算并保留人工核对，真实账单须用户核对；`docs/process/每分钟成本核算.md` 末段「尚需实际验收」所列项（本地 GPU 采集、自定义云节点、共享资产分摊、自动对账、跨币种换算）均未实现，标未核实。
- `docs/specs/02_接口与详细设计.md`、`docs/specs/05_UIUX与交互规范.md` 是否另有费用／用量相关章节：本次未逐节核对，报告第 3 节已注明。
- 「推荐模型线路」卡片是被移除还是从未接线：差异 D6-01 只确认当前无界面消费者，历史去向未核实。

## 备注

- 结果文件按 §4.0 第 5 条只写相对 `程序/` 的路径；不写用户原话、账号、本机用户目录。
- 本轮未提交 `project_status.md`（仅 master 可提交，§2.6）。
