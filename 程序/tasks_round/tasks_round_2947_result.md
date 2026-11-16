# R2947 结果：语音离线化·轮3——听写组件跨页复用＋挂到共享输入框（覆盖 13 页）
<!-- round-evidence: {"commit_base": "54fb2fdd", "credential_hits": 0, "evidence_sha256": "3a894dc3922fd17b", "exit": 0, "failed": 0, "passed": 326, "round": 2947, "tests": "run_selftests.py -k shared_input script_composer idea_chat ui_edges"} -->

## 三问

1. **轮次类型**：功能轮（任务书《语音输入离线化与VocoType集成》轮 3：UI 接线轮，不改识别后端）。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `tests/test_shared_input_voice.py` 5 条；`test_script_composer` 7/7、`test_shared_input_*` 35/35 绿；契约变更同步的 `test_idea_chat`/`test_ui_edges_pages` 失败点逐条改写后复测全绿；默认冒烟 8/8；架构分层/事件总线/无环/静带/导入边界/覆盖率基线定向复测全绿（覆盖率基线重测 **510 模块／70 覆盖**）。`-k script_composer shared_input idea_chat ui_edges` 全量回归见「验证记录」。
3. **欠账少了吗**：是。麦克风入口从「仅剧本准备页一颗页内按钮」变成「共享底部输入框唯一入口、13 页同一听写实例」；离线/云端两种后端在共享输入框上均可用（`create_session` 路由，轮 2 已落地）；01 页 composer 与共享栏的工具行重复（麦克风/附件/发送两套）按任务书点名收敛。

## 本轮交付（任务书轮 3 验收对照）

| 验收项 | 落地 |
|---|---|
| `VoiceInput` 提炼为可复用组件 | 新 `desktop_voice_input.py`（L4）：录音/会话/partial·final 浅色渲染/静音提示/`BackgroundTaskLifecycle` 代次逻辑原样迁出；解耦 `page`——`status` 接 StringVar 或可调用、`listening_style`/`idle_style` 由宿主按按钮样式给听写高亮；`desktop_writing_page` 改为 `from desktop_voice_input import VoiceInput`（旧路径兼容）。 |
| `SharedStageInput` 加麦克风 | 左簇 `[技能][附件][麦克风]`（`os.name=='nt'` 才建，非 Windows 无按钮）；`voice_input` 在 `_build` 末尾绑定 `self.input`（共享 Text 同一实例）；按钮命令 `_toggle_voice` 直接调 `voice.toggle()`（不走 `desktop.safe` 的 worker 拦截——听写与页面任务正交，行为差异如实记录）。 |
| 13 页同一实例、切页不重建 | `Desktop.shared_input` 本就是唯一实例，`_sync_shared_input` 只 `set_stage`/`pack_forget`；`voice_input` 挂在实例上随实例存活，录音会话与引擎子进程不受切页影响（`test_set_stage_keeps_voice_session_alive` 锚定）。 |
| 销毁即停、迟到结果丢弃 | `VoiceInput.__init__` 对绑定 Text 挂 `<Destroy>`→`stop()`（停录＋`session.cancel()`＋代次作废）；共享 Text 与窗口同生命周期，13 页共用一份绑定，不重复叠加。 |
| composer 重复入口收敛 | 共享模式（`input_box is shared_input.input`）下 `_composer_input_tail` 不再建页内麦克风/发送键，`_build_composer` 不再建「+」附件钮；`page.idea_voice_button/idea_voice_input/idea_attachment_button/idea_submit` 四个页级属性改为指向共享栏控件（`mic_button/voice_input/attachment_button/send_button`），下游引用（`update_script_interrupt_button`、附件卡片、测试）不断链。无共享实例的旧页面保留页内三键（`_composer_shared_mode` 区分）。 |
| 发送/终止合一键迁移 | `update_script_interrupt_button` 作用对象改为 `shared_input.send_button`：运行中→`ICON_STOP`＋`interrupt_script_agent`；空闲→恢复 `text='发送'`、`command=shared.send`（`/skill` 等命令解析不被页级改写绕过）、禁用态跟随 `idea_send` 必填门禁；`SharedStageInput.set_stage` 每次切页 `_reset_send_button` 复位，`PageNavMixin._sync_shared_input` 切回 script 页时补调一次重挂；方法加 `page_index==script` 守卫，别的阶段页不受剧本任务态影响。 |
| 附件卡片行 | `idea_uploaded_panel` 仍在 composer 卡片内（共享栏上方）；共享模式下卡片是卡片唯一内容，`refresh_uploaded_idea_attachments` 在无附件时把 `idea_composer_frame` 一并 `pack_forget`（不留空条），有附件时恢复 `pack(fill='x')`。 |

## 测试与契约变更（如实，§2.4）

- 新增 `tests/test_shared_input_voice.py` 5 条：按钮与会话绑定共享 Text、左簇 pack 顺序、`set_stage` 不重建会话不打断录音、dictation 写入共享输入框与关麦定稿、输入框销毁停录＋取消、非 Windows 无麦克风按钮。
- `test_script_composer.py`：麦克风两条用例的断言同步——按钮/会话断言改指 `shared_input.mic_button/voice_input`，听写中样式 `Tokens.Primary.TButton`、空闲 `Tokens.Secondary.TButton`（共享 SecondaryButton 的高亮口径）；`test_submit_switches_between_send_and_stop` 空闲态文字 `ICON_SEND`→`'发送'` 并先向共享输入框写入文本（共享 `send()` 空文本拒收，契约使然）。
- `test_idea_chat.py`：两处 `ICON_SEND`→`'发送'`；`ICON_ADD`→`'附件'`（共享文字键）；附件卡片横向断言由「麦克风右侧/发送左侧」改为「composer 卡片内不出界」（麦克风与卡片已不同行）。
- `test_ui_edges_pages.py`：提示文案断言同步（`附件点「附件」`）；composer 卡片断言改为「无附件时卡片整体收起＋附件/发送键在共享输入条内＋底栏发送在共享条上方」。
- 顺带修复存量小缺陷：`_WritingPage.stop_input_hint` 补 `event=None` 形参——`_composer_dispatch` 按名转派时统一传 event，原签名在共享 Text 销毁回调里抛 TypeError（stderr 噪音，非本轮引入）。
- **并行回归暴露的既有时序 flake（如实记录）**：`test_microphone_dictates_live_into_input` 在 8 路并行下红过一次——最后一次听写插入触发的 `<<Modified>>`→`refresh_idea_send_state` 250ms 防抖恰好在 `voice.poll()` 写入「密钥无效」之后的 `win.update()` 里到期，`_apply_idea_send_state` 把状态覆盖成「还缺必填：…」（R2663 既有机制，与本轮改动无关：同一共享 Text、同一门禁）。修法是测试侧确定性处理：报错段前 `after_cancel` 掉 pending 的门禁刷新，不改任何断言；`test_script_composer` 单跑复测 7/7 绿。

## 架构门禁适配（如实）

- `tests/architecture/_layers.py`：`desktop_voice_input` 登记 L4。
- `PROJECT_MAP.md`「离线语音识别」行补组件与收敛说明；`desktop_shared_input.py` 模块 docstring 布局行同步 `[skill][附件][麦克风]`。
- `维护记录/覆盖率基线.json` 重测刷新（510 模块／70 覆盖）；`runbook.md` §11 数字同步（510/70/440）。
- `architecture.md` L4 表不逐模块枚举（`desktop_writing_page`/`desktop_shared_input` 本就不在列），无需改；权威表同步归轮 5。

## 验证记录

- `python -B smoke_test.py`：8/8 绿。
- `python -B smoke_test.py --affected desktop_shared_input desktop_voice_input desktop_script_pages desktop_idea_attachments`：9/9 绿，定向 7 个测试文件 62 条用例 0 红。
- `run_selftests.py -k script_composer shared_input idea_chat ui_edges`：**326 条用例 0 红**（首轮 8 红全部为 §2.4 契约断言，改写后复跑；其中 `test_microphone_dictates_live_into_input` 另有一次并行时序 flake，根因与修法见上节，修后复跑全绿）。
- 架构定向复测：`test_coverage_baseline`/`test_layers`/`test_event_bus_boundary`/`test_no_circular_import`/`test_static_hygiene`/`test_import_error_boundaries` 24 条全绿。
- 覆盖率基线重测：`scripts/coverage_report.py`（既有 9 组定向用例）97 条 OK，`modules_total` 509→**510**、`modules_covered` 70；`维护记录/覆盖率基线.json` 与 `runbook.md` §11 数字同步。
- 未实测：真实麦克风＋真实 FunASR 引擎的端到端听写（需模型与音频硬件，属轮 5 整机验收；协议/会话/渲染路径已由 fake 全覆盖）。

## 下一步（轮 4）

自定义词典/热词（`data/语音识别.json` `hotword` 节＋`speech_settings_ui` 词典编辑）、AI 文本优化、MCP 语音转文字（`optimizer_mcp_bridge` 模式）。
