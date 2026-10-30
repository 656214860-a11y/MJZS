# R2138 结果：合入 codex/wip-R2136（R2136：剧本准备页语音输入改为录音＋云端识别 qwen3-asr-flash）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。
- 测试和三个基线：本轮在主检出合并后运行，均通过。
  - 定向自检全过。
  - 默认冒烟 8/8。
  - 架构门禁 410 项 OK。
  - 全量未运行。
- project_status.md 欠账：没有增减，只同步了当前轮次。

## 为什么合并
- 用户反馈「识别准确率很差，第二次点击后提示语音输入已结束，无法输入」。
- 「语音输入已结束。」只出现在 R2112 的 SAPI 听写旧代码里。R2136 的新实现当时只在 `codex/wip-R2136` 分支上，master 还没有，所以用户运行的仍是旧版本。合入后重启应用才会用上新实现。

## 合并
- 来源：`codex/wip-R2136` 的 R2136（8a64d8ad）。合并前 master 为 1c5a1d1e（R2137）。
- 冲突：只有 `docs/stages/S01_剧本准备.md` 追溯表一处。处理方式是保留 master 新增的 REQ-S01-72～75 行，并在 REQ-S01-71 行补上 `test_speech_api`。
- 断言未动。

## 验证（本轮运行，主检出合并后）
- `run_selftests -k test_script_composer test_platform_tools test_speech_api test_idea_chat test_desktop_automation_service req_s01_anchors requirement_traceability`（经 gui_hidden）：ALL TESTS PASSED。
- `smoke_test.py`：8/8。
- `smoke_test.py --architecture`：410 项 OK。

## 未验证
- 未跑全量。
- 合并后用户还没有重启应用，用真人说话实测。
