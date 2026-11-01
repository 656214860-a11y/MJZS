# R2283 结果：剧本准备聊天页气泡改版、rewind 与逐行流式回复（功能轮）

## 三问
- 轮次类型：功能轮（§3）。用户在 01 剧本准备聊天页提出 6 点改动。
- 测试：`run_selftests.py -k idea_chat ui_edges writing_api desktop_writing bubble`（经 gui_hidden）全过；`smoke_test.py --architecture` 仅剩 2 条本工作树环境问题（缺 `维护记录\基准历史.json`；状态页轮次连续性，由合并轮同步）。未跑全量、未手动在真实界面验证。
- `project_status.md` 欠账：未增减。

## 改动
1. 气泡最大宽度 `BUBBLE_MAX_RATIO=0.84`。
2. skill 摘要与时间合并为一行页脚，位于每条消息正文之后、操作图标之前。
3. 删除消息编辑功能（聊天区仍只读，`guard_bubble_key` 拦输入）。
4. 悬停图标修复：后加的 `tag_bind('<Enter>')` 未带 `add='+'`，覆盖了显示操作图标的绑定；去掉这些绑定。（对“悬停时图标不显示”的理解，用户未确认。）
5. rewind：用户消息新增 rewind 图标，原文回填输入框，不改聊天记录。
6. 逐行流式回复：新增 L2 `writing_stream.py`（`stream_to` 订阅、`chat_streaming` 在 chat 协议下走 `adapter.stream`，没出字就失败退回普通请求）；桌面层经缓冲每 80 ms 在“思考中”行下追加文字，回复落地或清除时撤掉。仅 chat 协议 API 模型生效；messages 协议（Claude 带工具）与命令行/桌面代理路径仍一次性回复。

## 门禁登记
- `writing_stream` 登记为 L2（`tests/architecture/_layers.py`）、`架构统一基数.json` 第一项 `scope_audit_pending`、`覆盖率基线.json`（0 覆盖，336→337）、`runbook.md` 口径文字。
- 拆出新模块的原因：`writing_api.py` 加流式后超过行数上限 1373。
- 测试：删除原编辑相关用例并改为新用例（页脚/rewind、流式显示与清除、`StreamingChatTests` 4 条）。断言未弱化。
