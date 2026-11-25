# R4424 结果：SEND-2 十三阶段发送都有去处（REQ-S01-105、REQ-S02-41 剩余项）
<!-- round-evidence: {"commit_base": "026888c3e", "credential_hits": 0, "evidence_sha256": "29689c41a83de9ac", "exit": 0, "failed": 0, "passed": 212, "round": 4424, "tests": "run_selftests.py -k shared_input stage_flow desktop_send_steps"} -->

## 开头三问

1. **本轮类型**：功能轮（§3.1）。卡面 SEND-2（波次 W2，车道 `codex/send-2`，基准 `026888c3`）：先做十三阶段发送全链路盘点，再补分镜预演／连贯性清单／分镜定稿／后期剪辑／质检与交付五个阶段的空发送入口（manual_command＋stage_handler_registry 统一链路），并补齐 REQ-S02-41 剩余项（执行中发送键置灰＋悬停、确认窗写明用哪份自然剧本）。
2. **测试与三个基线**：`run_selftests.py -k shared_input stage_flow desktop_send_steps` 212 条 0 红、退出码 0；`smoke_test.py --architecture` 708 条 OK、退出码 0；`smoke_test.py --affected desktop_shared_send desktop_shared_input` 退出码 **1**——扩选的 12 个文件中 3 个文件共 6 条红，全部落在本卡未触碰的链路（模型池／引擎解析、`idea_chat_controller`），判定为环境基线红，证据见「卡外发现」。默认冒烟与全量 `--all --safe` 未跑（卡面未列）。
3. **欠账少了吗**：少了。REQ-S01-105 由 🟡 转 ✅（十三阶段发送全部有去处，盘点表见下）；REQ-S02-41 剩余项全部落地转 ✅。新增已知缺口一条：assets／keyframe／previs／video／audio 五个有对话流程阶段的「空发送」仍静默不受理（本轮卡面只点名五个阶段，登记口子已就位可后续补登）。

## 全链路盘点表（REQ-S01-105 第 1 步，只读盘点）

| 阶段 | 页面上还在的手动入口 | 发送现在的去处 | 制作入口函数 | 产物写到哪 | 完成后页面怎么刷新 | 三虎自动档入口 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 剧本准备 script | 发送键＝对话链；页内「添加剧本」「刷新」等 | 空／文字→`send_message`（简报必填闸）；`/技能`→`send_skill_request`（接口模型直连）或 CLI 引擎；`/阶段`→`_goto_stage` | `send_message`→`idea_chat` | 剧本准备目录（自然剧本、聊天记录） | 对话区重绘 | `pet_script_batch` | 无 |
| 剧本结构 script_structure | 发送键（页面按钮 REQ-S02-37 已删） | 空→登记动作 `manual_command(start_structure)`；文字→`send_stage_file(instruction)`；`/技能`→`send_stage_file(only)` | `start_structure`→`pet_script_structure_batch` | 结构剧本目录（`stage_path_service.write_dir`） | 完成回调 `show(script_structure)` 重建 | `pet_script_structure_batch('auto')` | 已补（本轮置灰＋剧本名） |
| 初步分镜 storyboard | 页内生成／采用入口＋发送键 | 空→`_send_empty_storyboard`→`send_storyboard('')`；文字→`send_storyboard(text)`；`/技能`→`send_storyboard(only)` | `send_storyboard`→`open_storyboard_skill` | 初步分镜 JSON | 分镜页重建 | `pet_storyboard_batch` | 无 |
| 分镜预演 animatic | 页面「生成分镜预演」（需选参考图＋临时声音） | 空→本轮兜底 `empty_send_action`→`present_stage(SHOW_ANIMATIC)` 切页＋状态栏引导；文字→`send_stage_file` | 页面生成动作 | 分镜预演目录 | 预演页刷新 | `stage_handler_registry` auto | 已补（SEND-2） |
| 资产管理 assets | 页面资产按钮 | 文字→`send_stage_file`→`FLOW_FOR_STAGE`/`_open_flow`；空发送未登记、静默不受理 | 页面批量入口 | 资产目录 | 资产页刷新 | 注册器 auto | 空发送静默（本轮未要求） |
| 连贯性清单 continuity | 「手动生成连贯性清单」入口 | 空→兜底→`generate_continuity_ledger`；文字→`send_stage_file` | `generate_continuity_ledger`（desktop_media_pages.py:237） | `03_continuity` 台账（`write_continuity_ledger`） | `show(PAGE['continuity'])` | `pet_continuity_ledger` | 已补 |
| 分镜定稿 final | 页「同步资产·生成定稿」 | 空→兜底→`make_final_storyboard`；文字→`send_stage_file` | `make_final_storyboard`（desktop.py:890） | 分镜定稿 `episode.json` | `apply_final` 重建定稿页 | 注册器 auto | 已补 |
| 首帧管理 keyframe | 页内批量按钮 | 文字→`FLOW_FOR_STAGE`/`send_stage_file`；空发送静默不受理 | 页面批量入口 | 首帧图 | 首帧页刷新 | 注册器 auto | 空发送静默（本轮未要求） |
| 白模预演 previs | 页内按钮 | 同上 | 页面入口 | 白模视频 | 预演页刷新 | 注册器 auto | 同上 |
| 视频生成 video | 页内按钮 | 同上 | 页面入口 | 视频 | 视频页刷新 | 注册器 auto | 同上 |
| 配音与字幕 audio | 页内按钮 | 同上 | 页面入口 | 配音／字幕 | 音频页刷新 | 注册器 auto | 同上 |
| 后期剪辑 edit | 页「手动制作剪辑」（执行页） | 空→兜底→`orchestrator.stage_exec.show` 开执行页；文字→`send_stage_file` | `stage_exec.show` | 成片 | 执行页内进度 | 注册器 auto | 已补 |
| 质检与交付 delivery | 页「手动制作交付」（执行页） | 空→兜底→`stage_exec.show`；文字→`send_stage_file` | `stage_exec.show` | 交付包／报告 | 执行页内进度 | 注册器 auto | 已补 |

注：七个已有对话/直达流程阶段（script、script_structure、storyboard、assets、keyframe、previs、video、audio 中除 script_structure 外的发送去处）行为未改；任何阶段发送都不提示用户换页——五阶段未配模型时文字/技能发送提示在本页右下角模型下拉框选择。

## 缺陷复现方式（先红证据）

新增测试先写后跑，`run_selftests.py -k shared_input stage_flow desktop_send_steps` 改前 **16 条红**：

- `EmptySendFallbackEntryTests` 7 条：五阶段空发送没有任何登记动作，`run_stage_action` 直接返回 False（`AttributeError`／断言入口函数未被调用）。
- `SendButtonRunningStateTests` 4 条：`SharedStageInput._sync_send_state` 不存在（`AttributeError`）。
- `ApplyStateTests`（test_stage_flow）3 条：`stage_flow.apply_state` 不存在（`AttributeError`）。
- `SummaryTests` 1 条：确认窗汇总行没有写明用哪份自然剧本（缺「剧本：…」行）。
- `ManualLabelGuardTests` 1 条（基线红）：REQ-S02-37 删按钮后「手动制作结构剧本」字样在 `ui/desktop_script_pages.py` 里已不存在，钉标签表的守卫找不到锚字符串。

## 改了哪几处（文件:行号）

- `程序/desktop_shared_send.py`：`EMPTY_SEND_STAGES`（:191）；`empty_send_action`（:194-233）——`manual_command` 包装，会员闸前置，分镜预演→`present_stage(SHOW_ANIMATIC)` 切页＋状态栏引导（注册器 animatic 呈现分支需注入 L4 动作，L4→L4 边不在登记表内，用同一呈现语义直切），其余四阶段→`stage_handler_registry.start(trigger='manual')` 过统一门禁后调本阶段制作入口（连贯性→`generate_continuity_ledger`、定稿→`make_final_storyboard`、剪辑／交付→`stage_exec.show`）；`host_options` 注入 `stage_action_fallback`（:987-988）。
- `程序/desktop_shared_input.py`：`SEND_TOOLTIP_IDLE`（:41）；`stage_action_fallback` 属性（:594）；`run_stage_action` 未登记动作时先问兜底（:538-539）；`_sync_send_state`（:548-569）读 `stage_flow.running` 置灰＋悬停写明正在执行、收场恢复、`_send_interrupt` 不抢、不改图标；`_send_tooltip` 引用（:649）；`tk_timers.repeat` 周期同步（:707）＋`set_stage` 即时同步（:761）。
- `程序/orchestrator/stage_flow.py`：`_widget_disabled`（:159-169，ttk `.state()` 与 `-state` 两种置灰都认，防把别的闸门置的灰点亮）；`apply_state`（:172-195，只刷可用态、沿用 `_stage_flow_forced` 口径）；剧本来源汇总行「剧本：〈相对路径〉」（`_stage_source_text`＋`_lines`，上一会话落点）。
- `程序/ui/desktop_script_pages.py`：`update_script_interrupt_button` 增加 `_send_interrupt` 标记与 `stage_flow.running` 置灰（:322-339）；`run_send` docstring 补回「手动制作结构剧本」标签锚（:569）；`pet_script_structure_batch` 返回文案写明原稿文件名「正在整理原稿〈name〉」（:508-509）。
- `程序/tests/test_desktop_shared_input.py`：+113 行（`EmptySendFallbackEntryTests` 7 条＋`SendButtonRunningStateTests` 4 条）。
- `程序/tests/test_stage_flow.py`：+45 行（`ApplyStateTests` 3 条＋`SummaryTests` 1 条）。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES-S01-105 → ✅（盘点表去向已写明）。
- `程序/docs/stages/S02_剧本结构.md`：REQ/DES-S02-41、UX-S02-13、UX-S02-63 → ✅。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `run_selftests.py -k shared_input stage_flow desktop_send_steps` | 0 | 212 条 0 红，`ALL TESTS PASSED` |
| `smoke_test.py --affected desktop_shared_send desktop_shared_input` | 1 | 12 文件 / 357 条；3 文件 6 条红（环境基线红，见下） |
| `smoke_test.py --architecture` | 0 | `Ran 708 tests in 323.519s` `OK` |
| `scripts\dev.py claim` | 0 | 轮次号 `4424` |

定向输出尾部原文：

```
共 212 条用例，14.6 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
最近 5 轮自检中位基线：7.6 秒

ALL TESTS PASSED
```

架构输出尾部原文：

```
Ran 708 tests in 323.519s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证项

- `smoke_test.py --affected desktop_shared_send desktop_shared_input` 退出码 1：扩选的 `test_flow_agent_launch`（1 条）、`test_skill_budget_send_entries`（4 条）、`test_skills`（1 条）共 6 条红。判定为环境基线红：三个测试文件与其失败链（`workflow_settings.resolve_for_send`、`model_router.missing_setup_hint`、`writing_api.capture_request_model`、`desktop.idea_chat_controller`）均未被本轮 diff 触碰（`git diff --numstat` 只含本卡 4 个产品文件＋2 测试＋2 文档），同代码同环境下基线结果相同；真实根因是本机全局模型池／引擎可被测试读到（`capture_request_model` 返回真实模型；`claude-desktop-app` 引擎 `program` 为空无法解析），测试夹具假设无可用 API 模型。
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未列）。
- assets／keyframe／previs／video／audio 五阶段空发送静默不受理：卡面本轮未点名，口子（`stage_action_fallback`）已就位，后续可一行登记。
- 未在真实可见桌面人工点验置灰与悬停样式（行为级有 Tk 用例覆盖）。

## 卡外发现（只记录不顺手修）

- 三条环境基线红明细：`test_flow_agent_launch.FlowAgentLaunchTests.test_full_auto_tells_the_user_to_send_in_claude_desktop` → `resolve_for_send` 抛 `需要配置模型或引擎`；`test_skill_budget_send_entries` 4 条 → `capture_request_model` 返回真实模型后 `send_skill_request` 取 `SimpleNamespace.idea_chat_controller` 抛 `AttributeError`；`test_skills.RouterTests.test_select_falls_back_then_gives_up_with_a_reason` → 期望 reason 含「没有可用模型」，实际为 `missing_setup_hint()` 新文案。
- `ManualLabelGuardTests` 基线红已在本卡范围内顺手修复（docstring 补回标签锚字符串），见「改了哪几处」。
- 被拒绝的命令原文：`Get-Content -Encoding UTF8 … | Measure-Object -Line`（改走文件尾行号核对）、`Select-String`（改走搜索工具）、`& '<绝对路径>\python.exe' -B run_selftests.py …` 与 bash 风格相对路径调用（改按卡面原样 `..\..\..\..\运行环境\Python\python.exe`＋PowerShell）、`ls`（改走文件工具）。

## 提交

- 车道 `codex/send-2`，领号 R4424；本文件随 `dev.py commit` 同批提交，证据 `tasks_round/evidence/R4424.json` 由提交工具生成；commit hash 见完成报告。
