# R3245 结果：L1 基础设施层优化任务书 轮 0——基线与盘点（状态接续轮）
<!-- round-evidence: {"commit_base": "47c3a0b6", "credential_hits": 0, "evidence_sha256": "ce8a20e5a4693d6b", "exit": 0, "failed": 0, "passed": 0, "round": 3245, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型**：状态接续轮（L1 任务书轮 0；不改 `.py`，不跑 smoke／selftest）。
2. **测试跑了吗、三个基线过了吗**：按任务书轮 0 口径未跑测试（纯文档与盘点轮）；本轮无代码改动，三个基线不适用，下轮修复轮起恢复。
3. **欠账少了吗**：中性——本轮是摸底，不产生也不消化欠账；产出是后续轮 1–6 的实测输入。

## 交付

- **R0-a**：主工作区合并已结束（master `47c3a0b6` R3243）；新建工作树 `.agents/worktrees/devin-l1-infra`，分支 `codex/wip-R3245`，`round_claim.py next` 领得 **R3245**。
  - 过程损耗：首次在主工作区误领 **R3244**（归属记录挂到 master，已作废不用）；随后在功能工作树重领 R3245 并 `record` 补登正确归属。R3244 号段空缺属正常跳号。
- **R0-b 行号重测**：任务书 §2/§3 共 **79 处 `文件:行号` 引用全部可解析**（0 缺失、0 越界）；抽查 P0/P1 锚点内容逐条一致（`api_endpoints.py:92/101/137/161`、`model_metering.py:20-27/77`、`pet_llm.py:395`、`request_ledger.py:49/295/302/315/330`、`file_cache.py:21-24`、`usage_snapshot.py:26`、`project_settings.py:38`、`account_store.py:38`、`model_pool.py:748`、`model_diagnostics.py:71-76`、`model_router.py:59`、`broadcaster.py:31-33`）。唯一计数更新已就地写回任务书：`infra/` **51 个 `.py`**（含 `__init__.py`；v1 计 47、v2 计 50，master 在 v2 后又并入新模块）、生产运行时模块 **654**／覆盖率基线 **653**（差额仍为 `agent/__init__.py`）。
- **R0-c rpm 盘点**：`infra/model_pool.py` 出厂 `BUILTIN` 模型记录**均不含 `rpm` 字段**（0 命中）——rpm 是纯用户可选项（`FIELDS` 第 13 位、`pet_models_ui.py:560`「每分钟请求上限（可选）」），缺省＝不限制。仓库内无 rpm<20 的出厂默认值；用户自配分布属用户数据不在仓库，无法盘点。**结论：轮 1 无需上调出厂值；rpm<20 风险仅存在于用户自定义记录，L-N5 的「明显偏低的随轮 1 上调」本轮无对象。**
- **R0-d 幂等键核对**：生产代码 `Idempotency-Key` 零命中（仅 `tests/test_pet_agent.py` 幂等语义用例）。供应商文档核对结果：**OpenAI** 的 `Idempotency-Key` 仅存在于 Agentic Commerce API，Chat Completions／Responses／Batch 均无；**Anthropic** Messages/Batches 无发布幂等键；**DeepSeek** 官方文档无批处理与幂等键记载；Qwen 批接口未见幂等键说明。**结论：全部主流供应商「不发」**——轮 4 默认不携带该头，仅当用户指定某供应商书面确认支持时才启用。
- **R0-e 清扫阈值依据**：实测付费链路超时上限 `timeout=60`（pet_llm/model_router 方向）；单次 `metered()` 最坏链路 ≈ 传输层重放 3 × 60s ＋开销 ＜ 5 分钟。**L-N4 清扫阈值维持初值 30 分钟**（约 6 倍余量），轮 1 落地时可再校。
- **R0-f whitelist-framework 状态**：`git branch --merged master` 无 `codex/whitelist-framework`——**未合入 master**（R3215 合入的是依赖白名单政策与门禁，非该分支的 `RequestsJsonOpener` 实现）。「每次新建 Session 改懒建单例」属对方分支范围，本车道不代改，记入跨车道待办：待 whitelist-framework 合入或其 owner 确认后，轮 5 换 `requests` 时按 L0 Q9 口径实施。

## 变更文件

- `程序/tasks_round/L1基础设施层优化任务书.md`（新增入库；原主工作区未跟踪副本已移出，合入后以本文件为准）——头部补 R3245 重测注记、§2.1 两处计数、§2.2 infra 计数。
- `程序/tasks_round/tasks_round_3245_result.md`（本文件）。

## 验证

- 行号引用解析脚本：79/79 可解析（命令与输出见会话记录）。
- rpm／幂等键／超时／whitelist 状态均为 grep＋git 实测，非推测。
- 未跑 smoke／selftest／架构门禁：任务书轮 0 明确「不改 `.py`，不跑 smoke／selftest」。

## 后续

- 轮 1（P0 修复轮）前置已全部满足：行号有效、rpm 无需上调、幂等键口径确定、不依赖 L0 代码。
- 轮 5 前置：等 `codex/whitelist-framework` 合入 master。
- 轮 6 前置：等 L0 轮 3A、4A、5A 合入 master。
