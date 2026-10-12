# R1339：O15 请求冻结与「已加载」清单核对各生成入口

类型：功能轮（§3.1；本项为「建议/验证」，交付为入口核对与测试）。承接 R1267 清单 O15（O01—O14 已完成）。中央轮次 1339。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k request_freeze_entries` 3/3、关联 `-k workflow_settings request_freeze_entries writing` 全绿、默认冒烟 8/8，0 红。
- 欠账：O15 关闭，清单剩 O16—O48；本轮号 1339 − 上次绿全量 1336 = 3 < 5，且未改生产行为（只加测试），不跑全量。

## 核对结论（各入口是否消费同一请求快照）
- 直连 API（剧本页发送）：`writing_api.capture_request` 在发送边界解析一次模型/调用方式/技能内容；`freeze_skills` 落 `frozen_skill_prompt` 与 `skill_injection`（`selected` 路径 ＋ `loaded` 的 name/chars/sha256，不含密钥）。✅
- 桌面 Agent 投递：桌面所有阶段派发只经 `desktop.open_flow_agent` 一条入口（`launch_interactive` 在 desktop 内仅此一处调用），`config` 在 `build()` 之前捕获一次；writing 分支额外 `validate_selected_skills`＋`freeze_skills`，并把 `skill_injection` 写进回执。三虎/自动链复用同一入口。✅
- 手动剧本任务书：`writing.prepare` 只发布任务书与随包 SKILL 路径，不发起模型请求，因此不需要冻结技能正文。✅（不适用）
- 媒体生成：TTS 的批次配置冻结与缓存身份已由 O12 关闭（`tts_api.freeze_settings`）。✅（O12）
- 每条任务的「已勾选／本次实际加载」：`idea_chat.skill_injection_summary` 已按 `skill_injection` 显示，并挂在对话气泡的元信息行上。

## 实现
- 未改生产逻辑（验证项）。新增 `tests/test_request_freeze_entries.py` 三条入口差异测试：
  - `capture_request` 冻结后，改技能文件与阶段配置只影响新任务；同一次捕获的 `frozen_skill_prompt` 与摘要不变，新任务摘要变化。
  - 直连 API 与桌面 Agent 两种入口对同一份技能得到的 `selected`／`loaded.sha256` 一致。
  - 静态核对：`desktop` 的直连发送走 `capture_request`、writing 投递走 `validate_selected_skills`＋`freeze_skills`，`open_flow_agent` 的配置快照先于工作线程内的提示词构建；`writing_api` 在发送边界 `freeze_skills`；桌面只经一条 Agent 投递入口。
- 不新增第二套配置解析器：测试只消费 `workflow_settings` 既有解析结果。

## 验证
- `-k request_freeze_entries` 3/3、0 红；`-k workflow_settings request_freeze_entries writing` 全绿；默认冒烟 8/8。
- 台账无变化：未改 `writing_api.py`／`desktop.py` 生产代码，`json.loads` 台账不变；未新增架构测试文件（架构数不变）。

## 风险与边界
- 非 writing 阶段的桌面 Agent 投递捕获了 `config` 快照但**不内联技能正文**（CLI 自行按路径读取），因此其回执暂不记 `skill_injection` 摘要；这是既有设计（CLI 读文件），本项只做核对，未强行内联以免改变 CLI 行为与提示词体积。
- 静态核对断言的是「入口与捕获顺序」，不是真实点击界面；未重启应用、未真实投递。

[TASK_COMPLETE] 各生成入口核对完成：直连 API 与桌面 Agent 投递都从发送边界一次捕获的请求快照取模型/调用方式/技能内容（含 sha256 版本摘要，不含密钥），改配置只影响新任务、切调用方式不回读新配置；手动任务书不发起模型请求，媒体生成的批次冻结已由 O12 关闭；补 3 条入口差异测试（含静态入口核对），未复制第二套配置解析器；定向 3/3、关联全绿、默认冒烟 8/8，0 红。
