# R1840 结果：desktop_idea_chat.open_flow_agent 改写成类（整理轮）

- 改动：`IdeaChatMixin.open_flow_agent` 用 c2c 改写成 `_FlowAgentLaunch`，原方法变成薄壳，keyword-only 参数按关键字转交。函数从 252 行降下来，最长的方法 `launch_cli` 为 94 行；`OVERSIZE_CAPS` 删除该条。c2c 的产物有两处手工修正：
  - 内层闭包 `build` 和类的入口 `build` 重名，后一个会覆盖前一个，已把工作线程那一步改名为 `prepare`；
  - 宿主字段改名为 `host`，薄壳不再把 keyword-only 参数按位置传。
- 差分测试先行：`tests/test_open_flow_agent_equivalence.py`，旧实现取 HEAD 原文内嵌。宿主替身同步执行 `async_`、截留 `win.after` 定时器，派发台账、引擎、上下文、粘贴、剪贴板等外部入口全部只记账。新旧实现跑同一组 16 个场景：GPT 桌面、仅提取、CLI 首启／续发／新会话重启／千问续发、排队后获槽／被拒／超时、重复任务（复用／重试／不去重）、Claude Desktop、桌面模型、技能同步失败，对照完整调用记录。旧实现自比为绿。
- 按名字找代码的测试同步（断言含义不变）：
  - `tests/test_request_freeze_entries.py`：源码片段改为新写法，定位从 `def open_flow_agent` 改为 `class _FlowAgentLaunch`，`def build():` 改为 `def prepare(self):`；
  - `tests/test_codex_skill_sync.py`：定位改为类里的 `prepare`，并一并收集 `self.xxx(...)` 这类属性调用，另加一条“确实找到了 prompt_with_settings”的断言，防止空过。
- 变异检验：启动成功的提示“已自动提交”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：
  - 通过：差分测试；test_claude_writing_session、test_codex_skill_sync、test_desktop_idea_chat_desktop_paste、test_idea_inline_brief、test_idea_semantic_brief、test_request_freeze_entries、test_req_s09_anchors、test_workflow；`run_selftests.py --architecture`。
  - test_idea_chat、test_keyframe_comfy 只有 1 项红（`test_initial_brief_discovery_failure_is_visible_without_blocking_input`），在 HEAD 上同样红，R1831 已记录。
- 断言未动（原有断言一条未删、未放宽；只同步了定位方式和源码片段）。
