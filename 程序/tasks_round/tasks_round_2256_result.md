# R2256 合并轮结果

- 轮次类型：合并轮。
- 合入：`codex/wip-R2253`（a3d50d25，R2253：视频提示词渲染选 API 模型时直连，不经 Qwen；入口键 final→video_prompt）到 master（564e2e29 之上）。
- 冲突：无，自动合并。
- 断言未动。
- 验证：合并后在主检出经 `gui_hidden.py` 跑 `smoke_test.py --architecture`（见下方结果）；未跑全量。
