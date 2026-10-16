# R1625 文档三件：数据模型字段字典、任务状态与尝试链、部署运维手册（Q11）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q11）。
- 三基线：默认冒烟 **8/8**；架构门禁 **356 项**（本轮不改代码、按 §5 去重未重复单跑，定性由 post-commit 全量覆盖）；全量凭据见「欠账」。
- **全量凭据已落地**：R1624（HEAD `13dea0a`）的后台安全全量于 02:01:23 **绿灯结束**（502 秒、`red: []`、凭据 tree `bde64b00`、round 1624）。R1620–R1623 欠下的那次完整安全全量到此清账；`test_round_baselines`（含欠账账簿项）21 项 OK。
- 欠账：本轮只增删 `程序/*.md`（`data_model.md`、`task_states.md`、`runbook.md`、`PROJECT_MAP.md`）与轮次文档。
  按 `run_selftests.is_source_change` 的口径（程序目录内非 `skills/` 的 `.md` 不算源码）**不是源码轮**，欠账计数不变。

## 为什么要写，而不是把 R1610 的话抄一遍

R1610 只说「缺数据模型字段字典、任务状态说明、部署 runbook」。真写的时候发现三处**必须核原始证据**的地方，
照抄清单会把错的东西写进文档：

1. **金额口径**：R1610 只提「计费要有不变量」。核 `tasks_round_1615_result.md` 后，真实缺陷是
   `price()` 对分项各自四舍五入后又对总和对角四舍五入（差 1e-4），而「缺价返回 `None`、绝不补零」是
   `_model_price()` 的另一条不变量。文档按实际写两条，不写「缺价按 0 记」这种不存在的缺陷。
2. **解释器缺模块**：本会话里 `import trace`／`import symtable` 失败，看着像 alpha 构建不全。核
   `tests/test_stdlib_closure.py` 才知道这是**有意裁剪**的 58 个标准库模块（第 34 期第 11 条），
   并有静态闸禁止它们回来。这一条留给 Q12 的解释器策略，本轮不写进 runbook 的环境表。
3. **备份目录**：`升级备份/` 在仓库根、当前为空。AGENTS §2.6 写明它是历史证据、**今后不再新增**，
   回滚由 Git 承担。所以 runbook 不写「回滚＝覆盖备份目录」。

## 三份文档

| 文件 | 内容 | 权威源（文档只是投影） |
| --- | --- | --- |
| `data_model.md` | 版本化产物清单、队列台账行字段、任务历史、任务中心投影字段、费用与 Token、通知与事件 | `artifact_schema.REGISTRY`、`desktop_automation_service`、`task_center_service`、`pet_llm`、`pet_agent` |
| `task_states.md` | 三层状态边界、后台队列状态机（含禁止转移）、镜头／资产生命周期词表、尝试链键位、原因码与重试判定、改词表检查单 | `desktop_automation_service`、`video_lifecycle_service`、`pet_agent`、`pet_llm`、`tests/test_state_transition_tables.py` |
| `runbook.md` | 运行环境、启动入口、自检命令与代价、全量欠账与凭据、升级回滚、常见故障、清理 | `AGENTS.md`、`smoke_test.py`、`run_selftests.py`、`scripts/`、`environment_check.py` |

三份都在开头写明「本文件是投影、不一致以代码为准」，`PROJECT_MAP.md` 的阅读入口补了一行索引指向它们。

## 为什么没有顺手加门禁

这三份文档的权威源**分散在多个模块**（队列、投影、重试、schema 各一处）。要写「文档与代码一致」的断言，
就得在测试里再抄一份字段表——那是把文档变成第二份实现，比它现在会过期更糟。做法是：
①文档只写「键名 → 含义 → 缺失时怎么办」，不写算法细节；②每节点名权威源模块；③`task_states.md` 给出
改词表的检查单（改常量 → 同冻结副本 → 跑哪两个门禁）。已有的词表冻结副本门禁保持原样，未动。

## 验证

| 项 | 结果 |
| --- | --- |
| `tests.architecture.test_round_baselines` | 见下（连续性靠它） |
| `tests.test_line_endings` | 新增 `.md` 必须 LF（`*.md text eol=lf`） |
| `python smoke_test.py` | 默认冒烟 8/8 |

## 诚实边界

- 文档是投影，会随代码漂移；本轮不引入「文档一致性」自动门禁，理由见上（避免第二份实现）。
- 字段字典只覆盖**有跨模块读者**的格式：资产批量记录、视频镜头台账的字段以各自写入方为准；
  私有格式（连接收据、缩略图索引等）刻意不登记，避免先于代码过期。
- `task_states.md` 里的状态图是按代码里真实的 `_finish`／`_expire`／`cancel` 行为画的，未做运行时追踪；
  R1617 的全转移表仍是状态空间的权威证据。
- 未实机演练 runbook 的启动路径与故障处置（本环境 GUI 会话不稳定），命令与路径均逐条核对了盘上是否存在。
