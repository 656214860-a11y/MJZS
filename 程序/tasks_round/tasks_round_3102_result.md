# R3102 功能轮结果：文件卡片与 HITL·轮 1/8——消息 parts 数据模型 + schema 版本化 + 对话.json 迁移
<!-- round-evidence: {"commit_base": "75096bd6", "credential_hits": 0, "evidence_sha256": "61ddbecfb45b39c0", "exit": 0, "failed": 0, "passed": 178, "round": 3102, "tests": "run_selftests.py -k message_parts idea_chat idea_transcript domain/message_parts.py domain/idea_transcript.py tests/test_message_parts.py PROJECT_MAP.md architecture.md runbook.md 维护记录/覆盖率基线.json tasks_round/tasks_round_3102_result.md"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 1/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`tests/test_message_parts.py`（8/8）、默认冒烟（9/9）、架构门禁（483/483）、定向 `-k idea_chat message_parts idea_transcript`（178 条 0 红，ALL TESTS PASSED）。未跑全量 `--all --safe`：本轮不在 master 提交点（§5 触发条件未到）。
3. **欠账少了吗？** 无新增欠账；本轮把「消息 = 有序 typed parts」的数据契约与旧 `对话.json` 迁移落地，为轮 2–8（状态机/渲染器/HITL/分支/富媒体）提供地基。

## 改动

- 新增 `domain/message_parts.py`（L2 纯数据契约；不 import Tk、不发网络、不读写盘）：
  - `PartType`（text/reasoning/tool_call/tool_result/source/file/artifact/data）、`PartState`、`ArtifactKind`；
  - `Artifact`／`Document`／`Part`／`Message` dataclass；
  - `part`／`text_part`／`reasoning_part`、`derive_parts`／`ensure_parts`／`set_text`／`parts_of`／`text_of`／`reasoning_of`／`has_content`／`message_from_row`／`row_from_message`／`artifact_from_part`；
  - `SCHEMA_VERSION=2`、`VERSION_KEY='schema_version'`。
- `domain/idea_transcript.py`：
  - `_read_rows` 读取时补 `parts`（旧扁平 `text` → TEXT，旧 `thinking`／`reasoning` → REASONING），按 `has_content` 保留「只有思考」的行；
  - `save_rows` 写入带 `schema_version=2` 与每行 `parts`；
  - `replace`／`repair_internal_replies` 改用 `set_text` 同步 TEXT part；
  - `_same_message` 改为 `_message_key`：跨副本去重忽略派生 `parts` 与补写 `model_id`（修复旧版残留「同一条消息被数两遍/删不掉」）。
- `tests/test_message_parts.py`：新增 8 条用例（parts 形状、schema 版本、REASONING 保留、`set_text`、`has_content`、消息往返、旧对话迁移、写入带版本与 parts）。
- `PROJECT_MAP.md`／`architecture.md`／`runbook.md`：补 `domain/message_parts` 说明、覆盖率基线口径 534/71、L2 注记。
- `维护记录/覆盖率基线.json`：新增生产模块 `domain/message_parts.py`（0/141），总数 533→534、覆盖 71 不变。
- `维护记录/架构统一基数.json`：无净改动（曾试登 L2 后回退）。

## 测试证据

- `python -B tests/test_message_parts.py` → `Ran 8 tests ... OK`。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`）。
- `python -B run_selftests.py -k idea_chat message_parts idea_transcript` → `共 178 条用例 ... 0 个文件有红`、`ALL TESTS PASSED`。

## 契约变更（§2.4）

- `对话.json`／`已删除消息.json` 的新写入带 `schema_version=2` 与每行 `parts`；读取侧容忍缺 `parts`（旧文件读取时派生）。
- `_same_message` 判据扩展为忽略派生 `parts` 与补写 `model_id`；受影响断言未改动，新增用例覆盖。
- 未弱化/删除/跳过任何既有测试。

## 环境说明（不进入本轮提交）

本工作树缺 4 个 gitlink 子模块内容（`AIGC创作全流程`、`剧本锻造`、`编剧技能集`、`HoLLMwood`）与 gitignored 的 `维护记录/基准历史.json`；已从主工作区复制到工作树供测试。这些路径不是源码交付，不进入提交。

## 范围外 / 已知缺口

- `domain/message_parts` 暂未进 `_layers.py` L0/L1 登记：作为纯数据契约，登记会触发 L0/L1 分支覆盖率基线重测与 `test_service_return_contract` 的范围记录；本轮按「包实体无顶层门面」暂缓，已在 `architecture.md` L2 行注记，留待门面轮统一登记。
- 「回复时把 thinking 实际写进 REASONING part」的接线未做（数据模型已支持；回复解析在轮 2 状态机一并接）。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3102`；commit hash 见文末回填。
