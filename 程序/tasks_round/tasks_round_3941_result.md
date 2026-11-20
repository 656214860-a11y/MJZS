# R3941 结果：历史残留盘点任务书
<!-- round-evidence: {"commit_base": "fbcde1c4", "credential_hits": 0, "evidence_sha256": "586ceb241f585e1d", "exit": 0, "failed": 0, "passed": 0, "round": 3941, "tests": "docs-only"} -->

## 1. 三问

- 轮次类型：文档轮（只读盘点，新增一本文档任务书；未改源码、测试与门禁）。对应 `分层收口与并行冲刺任务书.md` §8 W1。
- 测试跑了吗、三个基线过了吗：未跑冒烟、架构门禁与全量（文档轮默认不跑）。在本车道跑了文档适用检查：`tests.architecture.test_taskbook_closure` 8/8、`tests.test_static_names` 8/8、`tests.architecture.test_agent_doc_budget` 11/11、`维护记录/基准脚本/doc_registry.py --check` 通过（87 份文档）。最新绿全量仍以 `full-safe-receipts.json` 为准，本轮未产生新凭据。
- 欠账少了吗：没有减少。本轮把历史欠账核实成了可执行清单，并新发现两条此前未记录的残留（见 §3）。

## 2. 产出

| 文件 | 内容 |
|---|---|
| `tasks_round/历史残留清理任务书.md` | 前半：A–J 类盘点清单，每条附可复核命令与 master `fbcde1c4` 实测结果；后半：清理轮 A–E 分轮计划与验收勾选，状态「待执行」 |
| `tasks_round/tasks_round_3941_result.md` | 本文件 |

## 3. 盘点结论摘要

- **实锤残留**：仓库根 `.agents/` 被 git 跟踪 78 个会话工件（39 `.out`、22 个 `c8-*.py` 探针、6 `.patch`、3 `.diff`、3 `.whl`、`.agents/tmp-pip-probe/`）；hooks 公共目录残留 `pre-commit.bak_20261004_0433`；`tasks_round/` 根目录散落十余件已收尾轮次的一次性证据（目录共 1038 项，`任务完成/` 20 件为活跃凭据不动）。
- **零引用模块分三类**：路径启动型 6 个判定保留（`optimizer_mcp_bridge`、`voice_mcp_server`、`voice_engine/bootstrap`、`offline_asr_server`、`blender_previs_template`、`app_shortcut` 待裁定）；已建待接线型 12 个（`ui/ui_*.py` ×11 出自文件卡片与HITL R3123–R3138＋`domain/checkpoint_tree.py`，组件与测试全绿但未接页面，需用户裁定接线或回收）；疑似死代码 4 个（`ui/edit_habits_dialog.py`、`ui/project_settings_dialog.py`、`orchestrator/codex_skill_sync.py`、`app_shortcut.py`）。
- **门面**：全树 225 个纯转发门面中 49 个全仓零引用，退役沿用 `deadcode_20261116/retire_facades.py` 路线分批执行。
- **延期项核对**：CRT-026/027/028 三个死符号 grep 0 命中，可核销；`legacy_compat` 仍有 5 个生产调用方（退役日 2027-03-31 未到）；L2 三项（`recoverable` 字段 0 读取、`is_failure()` 0 调用、三个 `schema()` 0 消费者）仍开放；`engine_probe` 已在 `infra/`。
- **核实非残留**：`skills/` 全部有主（13 阶段包＋`templates/` 14 yaml 被 `skill_templates.py` 等消费＋4 个外部分发技能包被 `workflow_settings.SKILL_PRESETS`/`agent_skill_sync` 引用）；`维护记录/任务队列.json` 不存在；3 个 `.gitmodules` 子模块本 worktree 未初始化，主工作区状态留清理轮 D3 核实。

## 4. 本轮新记下、尚未处理的两条

1. `orchestrator/codex_skill_sync.py` 与在用的 `orchestrator/agent_skill_sync.py` 并存，前者仅测试引用、docstring 自称保留旧签名——疑似兼容壳，已列入清理轮 B1 复核，不在本轮处置。
2. `.agents/` 跟踪残留与仓库根 `reorganize_install.py` 孤儿脚本均需用户过目后才动（清理轮 A1/D2），本轮未做任何删除。

## 5. 下一步

按 `历史残留清理任务书.md` 第二部分排车道：清理轮 A（`.agents/` 取消跟踪＋gitignore、hooks `.bak`、tasks_round 旧证据归档）为机械安全项可先行；清理轮 D 的组件接线/回收裁定需用户拍板后才可动工。

## 6. 提交与车道说明

- 提交：`codex/residue-inventory` 车道，`dev.py commit`，仅含本文档两件，未改 `.py`。
- 按冲刺任务书通用规则登记合并队列交接，不自行合并 master。
- 已知车道注意：`test_round_number_continuous` 在本车道可能因状态页抬头仍是主干轮次而失败，属既有口径（R3932 §3.2 同案），待主干结果轮次超过 3941 后变基消化。
- 状态页 `project_status.md` 按规则仅 master 可提交，本车道不动；合并轮落地主干时同步抬头为 3942。

（commit hash 由提交后回填：______）

## 完成记录

- R3941（本轮）：盘点完成，任务书入库，状态「待执行」。证据：本文档两文件；文档检查四项全过（见 §1）。
- 任务书收尾：待清理轮 A–E 全部执行并输出 `tasks_round/任务完成/历史残留清理·任务完成.md` 后勾销。

## 验收自答（W1 验收项）

- 每条记录都有可复核命令和结果：是，任务书第一部分每条目附命令与实测输出。
- 没有改动任何源码或测试：是，本轮仅新增 `tasks_round/历史残留清理任务书.md` 与本结果文件。
- 注册走合并队列，不自己合并：是，见 §6。
