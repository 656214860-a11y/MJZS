# R2267 合并轮结果

- 轮次类型：合并轮。
- 合入：`codex/wip-R2265`（R2265：白模预演选 API 模型时拒绝并提示需本地 Agent，不启动 Qwen）到 master。
- 冲突：无，自动合并。断言未动。未跑全量。
- 合并时 `tests/test_storyboard_direct_api.py` 把“其他阶段不进直连”的示例阶段从 previs 换成 video_prompt（白模预演选 qwen 现在被有意拒绝，R2265）；断言未动。
