# R2092 结果：剧本准备页对话去底色、悬停图标、清屏压缩、麦克风语音输入（功能轮）

## 需求
- REQ-S01-65：消息不铺底色；模型消息靠左铺开，用户消息靠右按字宽收紧（仿 Claude Code 桌面版）。
- REQ-S01-66：鼠标悬停消息时左下角显出「复制」「删除」图标，点击转调整条复制／删除；隐藏时只换前景色、不改行高。右键菜单移除「复制整条信息」「删除整条信息」；「清屏」改名「清屏压缩」。
- REQ-S01-67：输入框「+」右侧新增麦克风按钮：先聚焦输入框，再模拟 Win+H 调起 Windows 语音输入；调起失败只在状态栏提示；非 Windows 不显示按钮。
- DES-S01-65／DES-S01-67 已写入 `docs/stages/S01_剧本准备.md`，锚定表改为 REQ-S01-62~67 → `test_script_composer`。

## 改动文件
- `desktop_idea_bubbles.py`：底色去除、模型边距、`add_bubble_actions`／`show_bubble_actions`，复制选区时滤掉图标字符。
- `desktop_idea_menus.py`：右键菜单去两项，「清屏压缩」。
- `desktop_writing_page.py`：麦克风按钮与 `start_voice_input`。
- `platform_tools.py`：`start_voice_typing()`（ctypes `keybd_event` 发 Win+H）。
- `ui_tokens.py`：`ICON_COPY`、`ICON_MICROPHONE`。
- `writing_api.py`：「清屏压缩」文案。
- `runbook.md` §11：模块数同步覆盖率基线（R2082 新增 `ui_composer_style`）为 327／277。

## 测试
- 新增：`test_script_composer` 两条（悬停图标显隐与点击转调；麦克风聚焦并调起、失败提示）。
- 契约有意变更、同步断言（断言未弱化）：
  - `test_idea_chat`：消息 background 由浅绿改为 ''；右键菜单断言改为不含两项、首项「删除全部信息」；「清屏」→「清屏压缩」；`test_user_bubbles_are_right_and_model_bubbles_are_left` 的「模型右边距更大」改为「模型消息比用户消息更宽」（模型现铺满可用宽度）。
  - `test_req_s01_anchors`：底色断言改为两者都无底色，并以用户 lmargin1 大于模型来区分左右。

## 验证（本轮运行）
- `run_selftests -k script_composer req_s01_anchors`：全通过。
- `run_selftests -k idea_chat script_composer req_s01_anchors`：2 红，均为 `BubbleLayoutTests` 中聊天记录异步加载未完成（日志仍是「正在读取聊天记录…」）；同组用例在上一次运行中通过，HEAD 基线该测试类亦有红项，属既有时序不稳，非本轮引入。
- 更早一次 `-k idea_chat ui_edges … platform_tools idea_bubble`：`test_unattended_pipeline_runs_end_to_end_without_clicks` 在并发负载下 185 ticks 超 60；单独重跑 OK。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：剩 2 项既有红：`test_performance_history_is_declared_as_historical_only`（基准历史.json 未入库）、`test_round_number_continuous`（2076 != 2083）。

## 未验证
- Win+H 能否把听写文字写进 Tk Text 控件未在真机验证，需用户实机试用。
