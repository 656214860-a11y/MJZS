# R4287 结果：UX-S03-SEND 初步分镜发送入口（删除手动制作按钮，共享输入框发送走批量准备链）
<!-- round-evidence: {"commit_base": "729f8800", "credential_hits": 0, "evidence_sha256": "cb5a7cce39905a3f", "exit": 0, "failed": 0, "passed": 269, "round": 4287, "tests": "run_selftests.py -k desktop_shared_input shared_input_stages shared_input_ui storyboard_page_controller storyboard_page_loading manual_gate stage_flow stage_command_contract storyboard_direct_api ui_edges_pages complexity_ratchet"} -->

> 由合入接管会话代提交，原执行者中断。原执行者已在工作区完成全部产品、测试与文档改动，未领号、未写结果文件、未提交。接管会话没有改产品与测试代码，只做了三件事：存救援补丁、按卡面验收命令重跑定向测试、领号并写本文件后提交合入。本文件里的测试数字是接管会话在车道基准 `729f8800`（未变基）上亲眼跑出的；变基后的结果见提交后的合入轮出口 CI。

## 开头三问

1. **本轮类型**：功能轮（任务卡 UX-S03-SEND，波次 W2，车道 `codex/ux-s03-send`，车道基准 `729f8800`／R4228）。
2. **测试和三个基线数**：卡面第一条验收命令（十个关键词）共 265 条用例、0 个文件有红、退出码 0。三个基线数（全量、分支覆盖、启动）本轮未测：按卡面「不跑全量自测和默认冒烟」，全量与默认冒烟未运行；`smoke_test.py --affected` 与 `smoke_test.py --architecture` 接管会话也未重跑，由合入时的出口 CI 覆盖架构门禁与默认冒烟。
3. **欠账**：`tests/architecture/test_complexity_ratchet.py` 不在卡面允许文件里，但旧按钮实现删除后 `Desktop` 类实测行数下降，原执行者把上限从 817 下调到 813（只收紧、不放宽），随本批提交。

## 改了哪些文件

- `desktop_shared_send.py`：新增窄入口 `send_storyboard(desktop, text='', *, only=None) -> bool`；S03 的空发送、自由文本、`/技能`、`/子引擎` 都走它，不再直接 `_open_flow`。
- `desktop_shared_input.py`：`SharedStageInput.send()` 对 S03 空发送先过 `upstream_send_error`、捕获模型快照并标记在途，受理才清稿；`run_stage_action` 传播回调 False。
- `desktop.py`：`present_stage` 仅在 `OPEN_STORYBOARD` 且有本次发送上下文时调 `open_storyboard_skill(None, request_text=..., only=..., model_snapshot=...)`，其余委托既有 `stage_run_action`；删除「手动制作分镜」按钮及空容器。
- `ui/desktop_pet_bridge.py`：新增 `start_storyboard_send`，复用 `pet_storyboard_batch(trigger='manual')`。
- `ui/storyboard_files.py`：`open_storyboard_skill` 新增仅关键字参数 `request_text`／`only`／`model_snapshot`，异步准备前冻结项目、所选文件、补充文本与模型快照，token 隔离迟到回调。
- 文档：`docs/stages/S03_初步分镜.md`（REQ-S03-54、DES-S03-54 由 ⬜ 改 ✅，接口与交互两节标题改为已实现，测试锚定表登记）、`docs/specs/08_对话式交互与输出排版.md`（§8 第 03 行、§11、§13 发送与恢复／防重与草稿两行）。
- 测试：`test_shared_input_stages.py`（`StoryboardSendChainTests` 等）、`test_desktop_shared_input.py`（`StoryboardEmptySendTests`）、`test_stage_command_contract.py`（`StoryboardSendRegistryContractTests`）、`test_shared_input_ui.py`、`test_manual_gate.py`、`test_stage_flow.py`、`test_ui_edges_pages.py`、`tests/architecture/test_complexity_ratchet.py`。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `run_selftests.py -k desktop_shared_input shared_input_stages shared_input_ui storyboard_page_controller storyboard_page_loading manual_gate stage_flow stage_command_contract storyboard_direct_api ui_edges_pages`（卡面第一条验收，接管会话在车道基准上重跑） | 0 | 共 265 条用例，76.5 秒；0 个文件有红；实际跳过 0 条；ALL TESTS PASSED |
| `smoke_test.py --affected desktop_shared_send desktop_shared_input storyboard_files desktop_pet_bridge` | — | 接管会话未重跑 |
| `smoke_test.py --architecture` | — | 接管会话未单独重跑；合入时出口 CI 的架构门禁覆盖 |
| `scripts\dev.py claim` | 0 | 轮次 4287 |

先红后绿：原执行者中断前没有留下先红输出的原文，接管会话没有回退产品代码去重放先红，这一项如实记为未见。

## 有意修改的旧 UI 预期（卡面要求逐项注明）

- `test_manual_gate.py`：`test_the_storyboard_button_does_not_start_the_agent_when_stopped`（旧按钮被闸拦下）改为两条：`test_the_storyboard_page_has_no_legacy_manual_button`（页面不再有「手动制作分镜」）与 `test_storyboard_send_does_not_start_the_agent_when_gated`（发送入口同样过 `before_manual`）。
- `test_stage_flow.py`：`ManualLabelGuardTests` 的 PAGES 去掉 storyboard 的「手动制作分镜」，EXEMPTIONS 登记「REQ-S03-54：初步分镜制作入口改为共享输入框发送，按钮已删除」。
- `test_ui_edges_pages.py`：`test_step2_rows_hug_their_content_boxes` 去掉「手动制作分镜」到内容框的距离断言，改为断言按钮不存在且 `shared_input.stage_action("storyboard")` 已登记；主动作按钮表里 storyboard 由「手动制作分镜」改为「手动采用分镜」。

## 卡面「补充」四条测试的落点

① 勾选 [A, B] 发送 `/C` 只启动 C 一次：`test_storyboard_named_skill_ignores_checked_list`、`test_named_unchecked_skill_runs_only_it_without_rewriting_config`；② 勾选 [A] 发送 `/A` 只启动 A 一次：`test_storyboard_named_same_as_checked_still_only_once`、`test_named_checked_skill_runs_once_without_rewriting_config`；③ 空发送按勾选顺序启动 A：`test_storyboard_empty_send_uses_checked_not_named`、`test_empty_send_preserves_checked_order_and_config`；④ 三种情况都不改写 `stage_config`：同上各条的 `without_rewriting_config`／`preserves_..._config` 断言。

## 卡外发现（只记录不顺手改）

- `ui/pet_ui_stages.py` 的 `run_skill` 把点名名单和勾选名单取交集，点名的技能没勾选会被拒；它属于三虎聊天那条路，由需求设计另定。本卡未改。

## 如实说明

- 车道基准是 `729f8800`，卡面写的基准 `6e687b94` 不是开工时的 HEAD；原执行者没有留下开工核验记录。
- 接管会话无法确认原 Cursor 会话的进程工作目录，只核对了命令行：合入接管时没有命令行指向本车道目录的 python、node、cursor、codex、devin 进程，车道文件最后写入时间是接管前三个半小时以上。

## 未覆盖项

- 真实桌面界面上逐按钮点验、真实模型调用与产出：未做，本卡禁止真实付费调用。
- Windows 拼音、矮窗口等通用输入框生命周期：属 REQ-S01-107，不在本卡。
- 三虎自动链的回归只有既有测试覆盖，没有单独跑三虎专项。
