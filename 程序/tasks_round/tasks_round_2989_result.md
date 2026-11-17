# tasks_round_2989_result
<!-- round-evidence: {"commit_base": "9116672c", "credential_hits": 0, "evidence_sha256": "4debb0913b0f4f91", "exit": 0, "failed": 0, "passed": 404, "round": 2989, "tests": "run_selftests.py -k ui_status writing_status test_idea_chat test_timers test_skills test_ui_edges_controls test_ui_edges_pages ui_widgets"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（P1）：统一状态栏接入主壳——剧本准备页页内状态行并入统一底栏左区（用量摘要段）、会话说明按用户裁定删除、`NotificationDispatcher` 走四级消息总线（error/warning 常驻、info/success 自动消失）、旧 StringVar 与总线双向桥接、旧状态条暂隐藏。任务书原计划的 P1 轮次号 R2986 因并行车道占用，实际认领 **R2989**。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；定向批次一（ui_status/writing_status/ui_widgets/desktop_writing/desktop_idea_chat/ui_batch3/ui_style_engine）**75/75**；修复复验批（test_timers/test_skills/test_idea_chat/ui_status/writing_status/ui_edges_controls/ui_edges_pages/architecture.test_tooltip_boundary）**387 条 1 红→修复后 test_idea_chat 全绿**（其余文件同批已绿）；分层+静态名门禁 **14/14**。`smoke --affected`（135 模块串行 773 秒）首跑 20 文件红，根因全部定位并闭环：① 工作树缺 4 个 gitlink 外部技能包（`reference/HoLLMwood`、`skills/00全流程SKILL/AIGC创作全流程`、`01 剧本准备SKILL/剧本锻造`、`编剧技能集`）已从主工作区补齐，`skill_package_pins --check` 0 问题、技能计数 71→73；② 通知→状态栏镜像异步化破坏「同帧可读」契约，改为 publish 后同步 pump；③ 常驻心跳 after 使 test_timers 空集断言失效，契约同步（扣减状态栏心跳）；④ 历史面板改用 BaseDialog，过 tooltip 边界门禁。未重跑整轮 `--affected`（修复项均已逐项定向复绿）。
3. **project_status.md 的欠账少了吗？** 未改（仅 master 可提交）；无欠账变化。

## 本轮内容

- `ui/ui_status_bar.py`：after 全托管（`_after`+`_pending_afters`）、`<Destroy>` 取消全部回调防 invalid-command 泄漏、历史面板改 `BaseDialog`（业务模块不建 Toplevel）。
- `ui_widgets.py`：`NotificationDispatcher(bus=…)` 注入总线时走 `Message.make` 四级消息并同步 `pump()`（旧 StringVar 同帧镜像）；无总线宿主沿用原路径。
- `desktop.py`：创建 `StatusBus`/`StatusBar`（钉窗口最底）、旧 `status_label` 隐藏、`BusyState` 转圈宿主改挂新底栏、`_bus_to_status`/`_status_to_bus` 桥接与 `set_status_segment`。
- `desktop_writing_page.py`：删除页内状态行；`desktop_idea_chat.py`：收尾回调改 `set_status_segment('usage', 摘要, tooltip=全文)`，会话说明更新删除；`desktop_page_nav.py`：换页清空 usage 段。
- `ui_components.md`：通知节补充总线注入语义。
- 测试同步：`test_writing_status_line`（页内行删除→底栏段断言+桥接测试）、`test_idea_chat`（usage 段断言、会话说明删除断言）、`test_timers`（心跳 after 契约）、`test_ui_status_bar`（BaseDialog 历史面板）。

## 后续

R2xxx P2 标题行删除+Token 迁移+页头等价迁移；P3 路径收敛+文案规范；收尾全量。
