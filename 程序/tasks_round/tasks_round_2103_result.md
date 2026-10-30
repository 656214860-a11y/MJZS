# R2103 桌面模型续发二选一（续用上次对话只发增量／新对话完整发送）（功能轮）

轮次类型：功能轮（§3.1）。日期：2026-10-30。分支 `codex/wip-R2085`，基于 master `389007ed`（R2086）。

- 轮次号：开工时领的是 R2085。提交时钩子报中央已领到 R2100（`d1d804e1`，已提交），重新领到 R2101，提交时 R2102 又被另一会话领走，等它提交（`56921394`）后再领到 R2103，改号提交；R2085、R2101 成为空号。分支名仍按派单保留为 `codex/wip-R2085`：`claim` 自动切出的 `codex/wip-R<号>` 已切回原分支，空分支已删除。
- 基线偏差：派单时写的基线是 `33b684b8`（R2080），开工时 master 已前进到 `389007ed`。新的提交里有 R2081 和 R2086 的隔离修复，所以直接从最新 HEAD 拉分支。
- 文档先行（§2.7）：先写 REQ-S01-62 和 DES-S01-62，再写红测，最后写实现。

## 三问

- 本轮类型：功能轮。原来桌面模型（`desktop-app`，如 Gemini；`claude-desktop-app`）每次续发都把 SKILL、规则和全部上下文完整粘贴一遍。现在：
  - 可以只发增量；
  - 用户手改过的大纲等文件会内联进去；
  - SKILL 或规则变了时强制完整发送。
- 测试与基线：
  - 新增 `tests/test_desktop_send_ledger.py`，10 条全过。
  - 定向 selftest、`--affected`、默认冒烟、架构门禁的结果见下方“验证”。
  - 没有跑 `--all --safe`。
- `project_status.md` 欠账：不增不减。本分支不改 `project_status.md`，合入时由 master 同步。

## 需求与设计

- 需求是 `docs/stages/S01_剧本准备.md` 的 **REQ-S01-62**，设计是同文件的 **DES-S01-62**，锚点行指向 `test_desktop_send_ledger`。
- 适用范围：剧本准备阶段（`writing`），排除简报提取（`intake_only`），引擎为 `desktop-app` 和 `claude-desktop-app`。CLI 和 API 路径不变。
- 发送规则：
  1. 没有记录、记录读不出，或固定部分指纹变了：直接完整发送，不弹窗。固定部分指SKILL、交付契约、文风、修改习惯、用户指令和语言，用 `prompt_with_settings('', config, stage)` 的 sha256 表示。
  2. 有记录且固定部分没变：弹出「选择发送方式」对话框。
     - 「续用上次对话（约 N 字）」是主按钮，只发本次指令和自上次以来改动过的材料正文。
     - 「新对话完整发送（约 M 字）」重发 SKILL 和全部现有材料。
     - 「取消」、关窗和 Esc 都不复制、不粘贴，回执记为 `failed`。
  3. 三虎全自动（`gate_level()=='auto'`）不弹窗，直接完整发送，并在状态栏说明。
  4. 内容复制进剪贴板后立即更新台账，不等自动粘贴的结果。

## 改动

- 新增 `desktop_send_ledger.py`（L3）：续发台账与计划。
  - 台账放在 `程序/private/桌面续发/<项目路径哈希>.json`，与 `edit_habits` 的修改记录同理，交付或分享项目时不会带出去。
  - 项目的「工作流任务」目录没有路径权威，而且受 `test_workflow_dir_ratchet` 约束，所以台账不放那里。
  - 台账键是 `stage|engine|display_model`。换了引擎或模型就找不到记录，按完整发送处理。
  - 材料清单只经既有路径函数取得：
    - `brief_complete_path` 给出已确认简报；
    - `delivery_document_path` 给出项目设定、项目大纲、角色卡、自然剧本；
    - `script_baseline_path` 给出当前采用的自然剧本，只在它不是 RAW 时才取。
  - 每份材料的指纹是文件字节的 sha256。
  - 读写分别走 `file_cache.read_json` 和 `agent.core.save` + `artifact_schema.stamp`。
- 新增 `desktop_send_choice.py`（L4）：续发编排与界面。
  - `prepare_native()` 在后台线程运行，接管原 `prepare()` 里桌面分支的交付方式、任务文件和下载收件箱登记。只有计划为 `choice` 时，才另写一份增量任务文件。
  - `choose()` 在 Tk 线程运行，负责弹窗或直接发送，然后交回 `done()`，再记台账。
  - `SendChoiceDialog` 基于 `ui_widgets.BaseDialog` 和 `DescriptionBlock`。
- `desktop_idea_chat.py`：
  - `prepare()` 桌面分支改为调用 `prepare_native`；
  - `done()` 遇到 `send_plan` 时先交给 `choose`。
  - 文件净减 11 行，从 1148 行降到 1137 行，没有超过模块体积棘轮。
- `artifact_schema.py`：注册 `desktop_send_ledger` v1。
- `tests/architecture/_layers.py`：登记 `desktop_send_ledger` 为 L3、`desktop_send_choice` 为 L4。
- `runbook.md` §11：覆盖率口径数字从 326／276 改为 328／278。
- `维护记录/覆盖率基线.json`：用 `scripts/coverage_report.py` 按原 8 个目标重跑，模块数从 326 变为 328。其余模块的行数变化是前几轮的累积漂移，由工具刷新。

## 设计取舍

- 完整发送也会内联全部现有材料的正文，这是有意扩展。否则新对话拿不到用户手改过的大纲，只能看到路径。
- 增量里的「本次指令」用 `followup`，也就是 `script_followup` 的输出：不带 SKILL，但带交付契约和用户输入。不用 `continuation_instruction`，因为它只给路径。
- 内联的材料正文追加在请求预算预检之后，不再重新计入预算。材料很大时，预算报告会偏小。
- 台账在复制后同步写入。自动粘贴失败时，内容其实已在剪贴板里，用户会手动粘贴，所以仍然算作已发出。

## 测试

- `tests/test_desktop_send_ledger.py`：
  - `DesktopResendTests` 8 条，经真实的 `Desktop.open_flow_agent` 发送，外部入口全部打桩：
    - 首发完整发送，不弹窗，并记台账；
    - 只改大纲时弹窗，增量比完整稿短，并且内联新大纲；
    - 未改动的材料不内联；
    - 选择新对话时复制完整稿；
    - SKILL 变化时强制完整发送；
    - 坏台账按没有记录处理，并重建台账；
    - 全自动不弹窗；
    - 取消时什么都不发。
  - `SendChoiceDialogTests` 2 条，用真 Tk 窗口：
    - 三个按钮的文字和估算字数正确，点击后返回对应选择；
    - 关窗等同取消。
- 红测输出（实现前）：
  ```
  ModuleNotFoundError: No module named 'desktop_send_ledger'
  Ran 1 test ... FAILED (errors=1)
  ```
- 本轮自己写的夹具改过一处：`SKILL` 从 21 字补到符合真实体量（约 3600 字）。原来 SKILL 比增量说明还短，「增量比完整稿短」的断言无法成立。断言未动。
- 既有测试一条断言都没改。`test_workflow::test_native_claude_writing_pastes_contract_and_frozen_skill_body` 曾因首发也写了增量任务文件而变红（任务文件数 2 != 1）。修法是改实现：只在 `choice` 模式下写增量文件。

## 验证

均经 `工作流任务/gui_hidden.py` 在隐藏桌面运行。

- `python -B -m unittest tests.test_desktop_send_ledger`：10/10 通过。
- `run_selftests.py -k desktop_send_ledger desktop_idea_chat idea_chat writing workflow client_profiles flow_agent`：共 476 条，0 个文件有红（537.1 秒，机器上同时有其他会话在跑测试）。第一次运行时 `test_workflow` 有 1 条红，修复见“测试”一节。
- `smoke_test.py --affected desktop_idea_chat desktop_send_ledger desktop_send_choice artifact_schema`：9/9 通过。
- `smoke_test.py --architecture`：共 410 条。第一次运行的红项：
  - `record` 有 8 个参数，超过上限 7。已收拢为 `sent` 参数对象。
  - 覆盖率基线缺 2 个新模块。已刷新，`runbook.md` §11 的口径数字同步改为 328／278。之后单独复跑 `tests.architecture.test_coverage_baseline`，5/5 通过。
  - 剩下两条是环境和流程红，不是本轮引入：
    - `test_agents_md::test_performance_history_is_declared_as_historical_only`：本 worktree 缺 `维护记录/基准历史.json`。
    - `test_round_baselines::test_round_number_continuous`：2086 != 2087，因为状态页轮次号与最新结果报告不连续，起因是 R2086 先于本轮合入。
- 默认 `smoke_test.py`：8/8 通过。这次运行早于 `record` 参数收拢；收拢之后跑过上面的定向 selftest 和 `--affected`。

## 没有做的

- 没有真实粘贴进 Gemini 或 Claude Desktop 窗口，也没有确认对话里确实能续上上一轮。
- 没有目视检查弹窗的真实效果（中文字号、按钮宽度）。
- 没有跑 `--all --safe` 全量，需要合入后由后台补跑。
- 跟进项：`test_workflow` 里的桌面用例不打桩 `desktop_send_ledger.PROGRAM`，所以会在本机 `程序/private/桌面续发/` 留下以临时项目路径为键的台账。这些文件已被 gitignore，键每次都不同，不影响结果；`edit_habits` 也是同样做法。如果要彻底隔离，可以在 selftest 夹具里统一重定向 `PROGRAM`。

## 提交与回滚

- 只提交到 `codex/wip-R2085`（提交信息用 R2103），没有推送。
- 回滚方法：`git revert <本轮提交>`。台账文件在 `private/` 下，删除不影响功能，只会让下一次按完整发送处理。
