# R2612 结果：删除「只收自然语言剧本」内容闸门，结构化正文可保存／列出／采用
<!-- round-evidence: {"commit_base": "01c38e1b", "credential_hits": 0, "evidence_sha256": "da942a2e9e4fc70c", "exit": 0, "failed": 0, "passed": 331, "round": 2612, "tests": "run_selftests.py -k script_contract script_workspace_service writing_api stage_execution_service idea_chat"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）中的用户指定契约调整。R2599 修复同一症状（Gemini Desktop 落盘
   `\r\r\n` 双重回车被「字段表格」闸门误杀）的后续：用户明确要求删除整个
   「只收自然语言剧本」规则——结构化特征正文不再被程序拒绝，可保存、进入
   可采用清单并被采用；空正文仍拒绝，采用仍须用户显式选择（REQ-S01-21），
   阶段④产出契约不变（REQ-S01-16/17，模型侧 SKILL 要求不变）。
   轮次号说明：本轮工作在更早会话以 R2604 领号、未及提交会话即中断；
   本会话续作时先领 R2607，提交被 commit-msg 钩子拦下（中央计数器已被
   其他车道推进到 R2611），重新领取 **R2612**。R2604、R2607 均成空号
   （无提交、无结果文件）；R2607 的定向证据 331 条全绿已随拒绝提交移除，
   本轮证据以 R2612.json 为准。分支 `codex/wip-R2612`（由脏树
   `codex/wip-R2599` 经 `park_dirty_checkout` 两次带出，含 R2599 提交
   01c38e1b）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - `smoke_test.py --affected script_contract idea_chat script_workspace_service stage_execution_service writing_api`：
     163 个测试文件 **2869 条用例，0 个文件有红**，488.9 秒；
     实际跳过 1 条既有登记位（`test_stage_profile_wrong_preset_rejected`）。
     R2599 记录的 `test_ui_edges` 创意回显环境性红本轮未复现，全绿。
   - `smoke_test.py --architecture`：466 条，**1 红**
     `test_round_number_continuous`（2595 != 2600）——`project_status.md`
     轮次头仅 master 可提交，本分支携带 R2599 结果文件而状态页未同步，
     属分支固有口径、非本轮改动引入，合入轮同步状态页后转绿。
   - 定向证据：`dev.py commit --tests`（五模块关键词）生成
     `tasks_round/evidence/R2612.json`，见提交信息与证据文件。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账；合入 master 前
     按 §5 触发条件另计）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；净删除一个 L0 模块（`script_natural_gate.py`，58 行）与
   `script_contract` 内 56 行闸门代码。覆盖率基线 368→367、runbook §11
   数字、architecture.md L0 名单与 `save_natural_script` 描述、
   `tests/architecture/_layers.py` 登记、S01 阶段文档
   （REQ-S01-83／DES-S01-83／锚点行）已同步。

## 契约变化（§2.4／§2.7）

- 删除 `script_contract.natural_script_violations`／`require_natural_script`／
  `is_natural_script` 与整个 L0 模块 `script_natural_gate`
  （`has_foreign_field_table` 及节拍表豁免逻辑）。
- `save_natural_script`：只保留 `.md` 后缀与非空校验，仍经
  `agent.core.save_text` 原子落盘。
- `natural_script_paths`：只按「非空 `.md`」收录，不再查内容形态。
- `resolve_script_source`：采用记录仍按「相对路径＋SHA256」核验，
  不再查内容形态；旧项目里哈希过期的采用记录仍需用户重新采用一次
  （既有显式选择机制，不属本轮改动）。
- 调用点同步去闸门：`idea_chat`（`save_reply`／`save_manual_creative`／
  `auto_save_reply`／`import_local_document`／`_script_reply`）、
  `writing_api`（`_write_script_raw`／`_auto_save_script_raw`／
  `_save_formal_script`）、`script_workspace_service`
  （`_find_draft`／`adopt_natural_script`）、
  `stage_execution_service.collect_writing_quality`；空正文仍各自拦截。
- 测试契约同步（断言按新契约重写，未弱化）：结构化特征正文断言「照常
  落盘／照常进可采用清单／照常自动存档」，空正文仍断言拒绝。

## 改动清单

- `程序/script_contract.py`：删闸门函数与 `_NATURAL_SCRIPT_FORBIDDEN`、
  `script_natural_gate` import；`save_natural_script`／`natural_script_paths`／
  `resolve_script_source` 去内容检查（1209→1169 行）。
- `程序/script_natural_gate.py`：删除（L0 模块整体移除）。
- `程序/idea_chat.py`、`程序/writing_api.py`、
  `程序/script_workspace_service.py`、`程序/stage_execution_service.py`：
  去闸门调用，保留空内容等基础校验。
- `程序/tests/architecture/_layers.py`：L0 登记移除 `script_natural_gate`。
- `程序/tests/test_script_contract.py`、`test_script_workspace_service.py`、
  `test_writing_api.py`：契约断言同步（REQ-S01-83 锚点）。
- `程序/docs/stages/S01_剧本准备.md`：新增 REQ-S01-83、DES-S01-83、锚点行。
- `程序/architecture.md`：L0 名单移除 `script_natural_gate`，
  `save_natural_script` 描述改为「原子发布口径（R2612 起不做内容闸门）」。
- `程序/维护记录/覆盖率基线.json`：删 `script_natural_gate.py` 条目，
  `modules_total` 368→367（`modules_covered` 59 不变）。
- `程序/runbook.md` §11：基线数字 368/309→367/308。

## 验证

- 改动前红证据：沿用 R2599/R2497 记录——带节拍表的 `\r\r\n` 文件曾被判
  `('字段表格',)`；闸门删除后该路径整体不存在。
- 改动后绿：`--affected` 2869 条 0 红；`--architecture` 466 条 1 红
  （分支固有轮次号口径，见上）；默认冒烟 8/8。
- 真实项目影响：用户项目 `natural_script_selection.json` 指向的旧文件
  哈希与当前内容不符，`resolve_script_source` 仍返回 `None`——这是显式
  采用记录的既有行为，删除闸门后用户在剧本准备页重新「采用此剧本」
  即可刷新选用记录。

## 未运行项与说明

- 全量 `--all --safe` 未跑：功能分支不累计欠账，合入 master 前按 §5
  触发条件执行；`test_round_number_continuous` 红为分支状态页滞后，
  合入轮更新 `project_status.md` 后转绿。
- R2604／R2607 空号：领号后未提交（会话中断／中央计数器被推进），
  无代码、无结果文件可回滚；本轮全部改动以 R2612 为准。
- 队列：`round_claim.py show` 无 pending/claimed 项，本轮无对应队列 ID。
