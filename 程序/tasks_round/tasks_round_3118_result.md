# R3118 功能轮结果：文件卡片与 HITL·轮 3/8——part 分派渲染器 + 思考卡 + 产物/工具行 + 消息工具栏
<!-- round-evidence: {"commit_base": "bebd897a", "credential_hits": 0, "evidence_sha256": "e291ae3323a8561d", "exit": 0, "failed": 0, "passed": 180, "round": 3118, "tests": "run_selftests.py -k part_renderers message_toolbar idea_chat"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 3/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`tests/test_part_renderers.py`（6/6）、`tests/test_message_toolbar.py`（4/4）、`-k idea_chat part_renderers message_toolbar chat_status` 全绿（ALL TESTS PASSED）；默认冒烟与架构门禁见下。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；把「kind→渲染器」注册表、折叠思考卡、产物/工具行、单条消息工具栏（复制/删除/编辑重发/引用/重新生成）落地。

## 改动

- 新增 `ui/ui_part_renderers.py`（L4，唯一分派入口）：
  - `PART_RENDERERS`：`text/reasoning/tool_call/tool_result/source/file/artifact/data` → 渲染函数，借鉴 Open WebUI `ContentRenderer` / AI Elements `Message.Part`；
  - `render_reasoning` + `toggle_reasoning`：折叠「思考过程」标题，正文按需插入/删除；
  - `render_artifact`：产物行「标题 · kind」，点行回调 `host.open_artifact`；
  - `render_tool_call` / `render_tool_result`：工具名 · 状态 · 耗时；
  - `render_parts(..., skip_text=True)`：气泡正文之后只追加非 TEXT part（正常文本行不受影响）；
  - 只消费 `ui_tokens` 颜色/间距，动作经 `host` 回调注入（不 import Desktop）。
- `desktop_idea_bubbles.py`：
  - `add_bubble` 末尾接 `render_parts(skip_text=True)`（旧文本行只有 TEXT，排版不变）；
  - 新增 `quote_bubble_message`（`> 引用` 前缀带入输入框）与 `regenerate_bubble_message`（回填并重发）。
- `desktop_idea_menus.py`：单条消息右键菜单新增「复制这条／删除这条／编辑并重发／引用到输入框／重新生成」（删除走既有 `safe` + 回收语义）。
- 新增测试 `tests/test_part_renderers.py`（6 条）、`tests/test_message_toolbar.py`（4 条）。

## 测试证据

- `python -B tests/test_part_renderers.py` → `Ran 6 tests ... OK`（真 Tk Text：注册表覆盖、折叠/展开、产物行、工具行、skip_text、未知类型跳过）。
- `python -B tests/test_message_toolbar.py` → `Ran 4 tests ... OK`（真 Desktop：菜单五项、引用前缀、重新生成重发、编辑回填）。
- `python -B run_selftests.py -k idea_chat part_renderers message_toolbar chat_status` → `ALL TESTS PASSED`。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；含 `skip台账` 与覆盖率基线 535 口径同步）。

## 契约变更（§2.4）

- 新增 L4 `ui/ui_part_renderers.py` 与两个气泡方法；单条消息菜单新增 5 项（`assertIn` 断言，不影响既有用例）。
- `add_bubble` 仅对「含非 TEXT part」的行追加渲染；现有文本行行为不变。
- 零第三方依赖不变。

## 范围外 / 已知缺口

- 02–13 页的产物卡片（文件卡片流）与「采纳/重新生成/收藏」动作留给轮 4/5 接线（本轮的产物行已具备回调位）。
- 富媒体（图片 Lightbox/多候选/代码高亮/红绿 Diff）在轮 5；分支树在轮 6。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3118`（R3101/R3102/R3114/R3118 同链）；commit hash 见回填。
