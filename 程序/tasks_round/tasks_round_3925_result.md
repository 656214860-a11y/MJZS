# R3925 结果：对齐架构扫描范围，避免车道合并冲突

## 1. 三问

- 轮次类型：文档校正。只改 `architecture.md`。
- 测试跑了吗、三个基线过了吗：未跑冒烟、架构门禁和全量。句子取自已在 `codex/governance-land` 提交的原文，不改生产代码。
- 欠账少了吗：没有。最新绿凭据仍是 R3849。

## 2. 改动

`skill_registry` 的两处扫描范围从 `skills/01`—`12` 改为 `01`—`13`，措辞改为「只扫描」。注册规则不再把已退役的 `00全流程SKILL` 写成特例，改为层间路径回退、不包含总控包特例。`Registry.files()` 一段与 `codex/governance-land` 对齐：R3820 删除内建总控资源与五个专用工具，保留通用 `skill_orchestrator`、注册器与 `production_locks`。主干上没有 `skills/THIRD_PARTY_NOTICES.md`，这句话不写进去。

`domain/message_parts` 的括注仍是「暂未进 `_layers.py` 登记」。这一整行若改成「已登记」，会给 `codex/foundation-c8-updater` 和 `codex/foundation-integration-final` 新增冲突，本轮不动。

## 3. 车道对齐

合入本句之前，先在下面三条干净车道上提交了同一处对齐。提交说明是 `WIP:`，没有领取轮次号：

- `codex/account-design-consolidation` `d5eb1e62`
- `codex/retire-builtin-prerequisite` `95588a60`
- `codex/wip-r3764` `89a1c057`

`codex/directory-governance-execution` 正在合并 `99554eb1`，冲突已经解完、尚未提交。没有改它的 `architecture.md`，也没有替它完成合并。

`git merge-file`（基线是 merge-base，主干侧是本轮句子）结果：

- `account-design-consolidation`、`retire-builtin-prerequisite`、`governance-land`、`wip-r3764`、`foundation-c8-updater`、`foundation-integration-final`：0 处冲突。
- `directory-governance-execution`：仍是 1 处，与改之前相同，没有加重。

## 4. 提交

在 `codex/architecture-doc-facts` 提交后快进 master。不绕过钩子，不推送。
